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
        self._save_state()
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
                "active_task_count": payload.metadata.get("active_task_count", 0),
                "blocked_instance_ids": list(payload.metadata.get("blocked_instance_ids", [])),
                "queued_task_count": payload.queued_task_count,
            },
        )
        self._terminals[payload.terminal_id] = record
        self._save_state()
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

        self._save_state()
        return synced

    def list_terminals(
        self,
        *,
        status: str | None = None,
        operator_name: str | None = None,
        min_active_task_count: int | None = None,
        max_parallel_tasks: int | None = None,
        blocked_instance_id: str | None = None,
    ) -> list[TerminalRecord]:
        """Return known terminals, optionally filtered."""

        return [
            record
            for record in self._terminals.values()
            if _matches_terminal(
                record,
                status=status,
                operator_name=operator_name,
                min_active_task_count=min_active_task_count,
                max_parallel_tasks=max_parallel_tasks,
                blocked_instance_id=blocked_instance_id,
            )
        ]

    def get_terminal(self, terminal_id: str) -> TerminalRecord:
        """Return one terminal by identifier."""

        try:
            return self._terminals[terminal_id]
        except KeyError as exc:
            raise KeyError(f"terminal not found: {terminal_id}") from exc

    def list_instances(
        self,
        *,
        terminal_id: str | None = None,
        runtime_status: str | None = None,
    ) -> list[InstanceRecord]:
        """Return known instances, optionally filtered."""

        records = list(self._instances.values())
        if terminal_id is not None:
            records = [record for record in records if record.terminal_id == terminal_id]
        if runtime_status is not None:
            records = [record for record in records if record.runtime_status == runtime_status]
        return records

    def get_instance(self, instance_id: str) -> InstanceRecord:
        """Return one instance by identifier."""

        try:
            return self._instances[instance_id]
        except KeyError as exc:
            raise KeyError(f"instance not found: {instance_id}") from exc

    def _require_terminal(self, terminal_id: str) -> TerminalRecord:
        try:
            return self._terminals[terminal_id]
        except KeyError as exc:
            raise KeyError(f"terminal not registered: {terminal_id}") from exc

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._terminals = self._repository.load_terminals()
        self._instances = self._repository.load_instances()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_terminals(self._terminals)
        self._repository.save_instances(self._instances)


def _matches_terminal(
    record: TerminalRecord,
    *,
    status: str | None,
    operator_name: str | None,
    min_active_task_count: int | None,
    max_parallel_tasks: int | None,
    blocked_instance_id: str | None,
) -> bool:
    if status is not None and record.status != status:
        return False
    if operator_name is not None and record.operator_name != operator_name:
        return False
    metadata = record.metadata or {}
    if min_active_task_count is not None and int(metadata.get("active_task_count", 0)) < min_active_task_count:
        return False
    if max_parallel_tasks is not None and int(metadata.get("max_parallel_tasks", -1)) != max_parallel_tasks:
        return False
    if blocked_instance_id is not None:
        blocked = {str(item) for item in metadata.get("blocked_instance_ids", [])}
        if blocked_instance_id not in blocked:
            return False
    return True
