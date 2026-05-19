"""Minimal local instance manager used by the terminal runtime."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from terminal_agent.models import InstanceState


class InstanceManager:
    """Maintains a local in-memory view of managed instances."""

    def __init__(self) -> None:
        self._instances: dict[str, InstanceState] = {}

    def upsert_instance(self, state: InstanceState) -> InstanceState:
        """Insert or replace one instance state."""

        self._instances[state.instance_id] = state
        return state

    def get_instance(self, instance_id: str) -> InstanceState | None:
        """Return one instance by identifier when present."""

        return self._instances.get(instance_id)

    def update_instance_identity(
        self,
        *,
        instance_id: str,
        handle: str | None,
        remark: str | None,
        profile_id: str | None = None,
        runtime_status: str | None = None,
    ) -> InstanceState:
        """Update one instance after a confirmed account/login identity change."""

        existing = self._instances.get(instance_id)
        if existing is None:
            updated = InstanceState(
                instance_id=instance_id,
                profile_id=profile_id or instance_id,
                runtime_status=runtime_status or "running",
                health_status="unknown",
                handle=handle,
                window_id=instance_id,
                remark=remark,
            )
        else:
            updated = InstanceState(
                instance_id=existing.instance_id,
                profile_id=profile_id or existing.profile_id,
                runtime_status=runtime_status or existing.runtime_status,
                health_status=existing.health_status,
                handle=handle,
                window_id=existing.window_id,
                remark=remark,
                last_synced_at=existing.last_synced_at,
                metadata=dict(existing.metadata),
            )
        self._instances[instance_id] = updated
        return updated

    def load_snapshot(self, states: Iterable[InstanceState]) -> list[InstanceState]:
        """Replace the full local instance set with a fresh scan result."""

        snapshot = list(states)
        self._instances = {state.instance_id: state for state in snapshot}
        return snapshot

    def mark_synced(self, synced_at: datetime | None = None) -> None:
        """Stamp all known instances with the latest sync time."""

        stamp = synced_at or datetime.utcnow()
        for instance_id, state in list(self._instances.items()):
            self._instances[instance_id] = InstanceState(
                instance_id=state.instance_id,
                profile_id=state.profile_id,
                runtime_status=state.runtime_status,
                health_status=state.health_status,
                handle=state.handle,
                window_id=state.window_id,
                remark=state.remark,
                last_synced_at=stamp,
                metadata=dict(state.metadata),
            )

    def list_instances(self) -> list[InstanceState]:
        """Return all current instance states."""

        return list(self._instances.values())
