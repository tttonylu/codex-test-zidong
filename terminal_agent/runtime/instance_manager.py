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
                handle=state.handle,
                window_id=state.window_id,
                remark=state.remark,
                last_synced_at=stamp,
                metadata=dict(state.metadata),
            )

    def list_instances(self) -> list[InstanceState]:
        """Return all current instance states."""

        return list(self._instances.values())
