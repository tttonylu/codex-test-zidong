"""Minimal in-memory registry service for the NAS control plane."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from nas_control_plane.models import InstanceRecord, TerminalRecord
from nas_control_plane.services.repositories import TerminalStateRepository
from shared.protocol import HeartbeatPayload, InstanceSnapshotPayload, TerminalRegistrationPayload


class TerminalRegistryService:
    """Stores the latest terminal and instance state snapshots in memory."""

    def __init__(self, repository: TerminalStateRepository | None = None) -> None:
        self._repository = repository
        self._terminals: dict[str, TerminalRecord] = {}
        self._instances: dict[str, InstanceRecord] = {}
        self._load_state()

    def register_terminal(self, payload: TerminalRegistrationPayload) -> TerminalRecord:
        """Create or refresh a terminal registration entry."""

        record = self._terminals.get(payload.terminal_id)
        if record is None:
            record = TerminalRecord(
                terminal_id=payload.terminal_id,
                hostname=payload.hostname,
                operator_name=payload.operator_name,
                status="registered",
                agent_version=payload.agent_version,
                capabilities=list(payload.capabilities),
                metadata=dict(payload.metadata),
            )
        else:
            record = replace(
                record,
                hostname=payload.hostname,
                operator_name=payload.operator_name,
                agent_version=payload.agent_version,
                capabilities=list(payload.capabilities),
                metadata=dict(payload.metadata),
            )

        self._terminals[payload.terminal_id] = record
        self._persist_terminal(record)
        return record

    def record_heartbeat(self, payload: HeartbeatPayload) -> TerminalRecord:
        """Update last-seen and capacity values from a heartbeat payload."""

        record = self._require_terminal(payload.terminal_id)
        record = replace(
            record,
            status=payload.status,
            last_seen_at=payload.reported_at,
            metadata={
                **record.metadata,
                **payload.metadata,
                "active_instance_count": payload.active_instance_count,
                "queued_task_count": payload.queued_task_count,
            },
        )
        self._terminals[payload.terminal_id] = record
        self._persist_terminal(record)
        return record

    def sync_instances(
        self,
        terminal_id: str,
        snapshots: Iterable[InstanceSnapshotPayload],
    ) -> list[InstanceRecord]:
        """Replace the known instance set for one terminal with fresh snapshots."""

        self._require_terminal(terminal_id)

        synced: list[InstanceRecord] = []
        terminal_instance_ids: set[str] = set()

        for snapshot in snapshots:
            if snapshot.terminal_id != terminal_id:
                raise ValueError("snapshot terminal_id does not match sync target")

            terminal_instance_ids.add(snapshot.instance_id)
            record = InstanceRecord(
                instance_id=snapshot.instance_id,
                terminal_id=snapshot.terminal_id,
                profile_id=snapshot.profile_id,
                handle=snapshot.handle,
                runtime_status=snapshot.runtime_status,
                window_id=snapshot.window_id,
                remark=snapshot.remark,
                metadata=dict(snapshot.metadata),
            )
            self._instances[snapshot.instance_id] = record
            synced.append(record)

        stale_ids = [
            instance_id
            for instance_id, record in self._instances.items()
            if record.terminal_id == terminal_id and instance_id not in terminal_instance_ids
        ]
        for instance_id in stale_ids:
            del self._instances[instance_id]

        self._persist_terminal(self._terminals[terminal_id])
        self._persist_instances_for_terminal(terminal_id, synced, terminal_instance_ids)
        return synced

    def get_terminal(self, terminal_id: str) -> TerminalRecord | None:
        """Return one terminal by id if it exists."""

        return self._terminals.get(terminal_id)

    def get_instance(self, instance_id: str) -> InstanceRecord | None:
        """Return one instance by id if it exists."""

        return self._instances.get(instance_id)

    def list_terminals(self, status: str | None = None) -> list[TerminalRecord]:
        """Return known terminals, optionally filtered by status."""

        records = list(self._terminals.values())
        if status is None:
            return records
        return [record for record in records if record.status == status]

    def list_instances(
        self,
        terminal_id: str | None = None,
        runtime_status: str | None = None,
    ) -> list[InstanceRecord]:
        """Return known instances, optionally filtered by terminal and runtime status."""

        records = list(self._instances.values())
        if terminal_id is not None:
            records = [record for record in records if record.terminal_id == terminal_id]
        if runtime_status is not None:
            records = [record for record in records if record.runtime_status == runtime_status]
        return records

    def summary(self) -> dict[str, object]:
        """Return a small aggregate view for management queries."""

        terminal_status_counts: dict[str, int] = {}
        for record in self._terminals.values():
            terminal_status_counts[record.status] = terminal_status_counts.get(record.status, 0) + 1

        instance_status_counts: dict[str, int] = {}
        for record in self._instances.values():
            instance_status_counts[record.runtime_status] = instance_status_counts.get(record.runtime_status, 0) + 1

        return {
            "terminal_count": len(self._terminals),
            "instance_count": len(self._instances),
            "terminal_status_counts": terminal_status_counts,
            "instance_status_counts": instance_status_counts,
        }

    def _require_terminal(self, terminal_id: str) -> TerminalRecord:
        try:
            return self._terminals[terminal_id]
        except KeyError as exc:
            raise KeyError(f"terminal not registered: {terminal_id}") from exc

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._terminals, self._instances = self._repository.load_state()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_state(self._terminals, self._instances)

    def _persist_terminal(self, record: TerminalRecord) -> None:
        if self._repository is None:
            return
        if hasattr(self._repository, "upsert_terminal"):
            self._repository.upsert_terminal(record)
            return
        self._save_state()

    def _persist_instances_for_terminal(
        self,
        terminal_id: str,
        records: list[InstanceRecord],
        keep_instance_ids: set[str],
    ) -> None:
        if self._repository is None:
            return
        if hasattr(self._repository, "upsert_instance") and hasattr(
            self._repository,
            "delete_instances_for_terminal_except",
        ):
            for record in records:
                self._repository.upsert_instance(record)
            self._repository.delete_instances_for_terminal_except(terminal_id, keep_instance_ids)
            return
        self._save_state()
