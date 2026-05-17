"""Minimal terminal runtime for registration, heartbeat, and snapshot sync."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from shared.protocol import HeartbeatPayload, InstanceSnapshotPayload, TaskAssignmentPayload, TerminalRegistrationPayload
from terminal_agent.models import InstanceState, LocalTask, TerminalState
from terminal_agent.runtime.instance_manager import InstanceManager


class TerminalRuntime:
    """Produces terminal-side payloads from local runtime state."""

    def __init__(
        self,
        terminal_id: str,
        hostname: str,
        operator_name: str,
        agent_version: str,
        capabilities: list[str] | None = None,
        max_parallel_tasks: int | None = None,
    ) -> None:
        self._operator_name = operator_name
        self._capabilities = list(capabilities or [])
        self._max_parallel_tasks = max_parallel_tasks
        self._instance_manager = InstanceManager()
        self._tasks: dict[str, LocalTask] = {}
        self._state = TerminalState(
            terminal_id=terminal_id,
            hostname=hostname,
            status="booting",
            agent_version=agent_version,
        )

    @property
    def instance_manager(self) -> InstanceManager:
        """Expose the instance manager so scans can populate local state."""

        return self._instance_manager

    def registration_payload(self) -> TerminalRegistrationPayload:
        """Build a registration payload for the NAS control plane."""

        return TerminalRegistrationPayload(
            terminal_id=self._state.terminal_id,
            hostname=self._state.hostname,
            operator_name=self._operator_name,
            agent_version=self._state.agent_version,
            capabilities=list(self._capabilities),
            metadata={
                **self._state.metadata,
                "max_parallel_tasks": self._max_parallel_tasks,
            },
        )

    def accept_tasks(self, tasks: Iterable[LocalTask]) -> list[LocalTask]:
        """Replace the known local task set with a fresh assignment batch."""

        accepted = list(tasks)
        self._tasks = {task.task_id: task for task in accepted}
        self._state.queued_task_count = len(accepted)
        return accepted

    def accept_task_assignments(self, assignments: Iterable[TaskAssignmentPayload]) -> list[LocalTask]:
        """Convert remote task assignments into local task state."""

        tasks = [
            LocalTask(
                task_id=item.task_id,
                script_name=item.script_name,
                status="queued",
                instance_id=item.instance_id,
                priority=item.priority,
                retry_limit=item.retry_limit,
                close_after_actions=item.close_after_actions,
                requested_by=item.requested_by,
                parameters=dict(item.parameters),
            )
            for item in assignments
        ]
        return self.accept_tasks(tasks)

    def refresh_instances(self, states: Iterable[InstanceState]) -> list[InstanceState]:
        """Replace local instances with the latest scan results."""

        snapshot = self._instance_manager.load_snapshot(states)
        self._state.active_instance_count = len(snapshot)
        return snapshot

    def refresh_instances_from_scan(self, states: Iterable[InstanceState]) -> list[InstanceState]:
        """Alias for scan-driven refresh to keep caller intent explicit."""

        return self.refresh_instances(states)

    def heartbeat_payload(self, reported_at: datetime | None = None) -> HeartbeatPayload:
        """Build a heartbeat payload using the current local state."""

        stamp = reported_at or datetime.utcnow()
        self._state.last_heartbeat_at = stamp
        if self._state.status == "booting":
            self._state.status = "online"

        return HeartbeatPayload(
            terminal_id=self._state.terminal_id,
            reported_at=stamp,
            status=self._state.status,
            active_instance_count=self._state.active_instance_count,
            queued_task_count=self._state.queued_task_count,
            metadata={
                **self._state.metadata,
                "max_parallel_tasks": self._max_parallel_tasks,
                "active_task_count": self._state.active_task_count,
            },
        )

    def claim_capacity(self) -> int | None:
        """Return how many tasks this terminal should claim in one cycle."""

        if self._max_parallel_tasks is None:
            return None
        return max(0, self._max_parallel_tasks - self._state.active_task_count)

    def mark_task_started(self, task_id: str) -> None:
        """Mark one local task as actively executing."""

        task = self._tasks.get(task_id)
        if task is None:
            return
        if task.status == "running":
            return
        task.status = "running"
        self._state.active_task_count += 1
        self._state.queued_task_count = max(0, self._state.queued_task_count - 1)

    def mark_task_finished(self, task_id: str) -> None:
        """Mark one local task as no longer occupying an execution slot."""

        task = self._tasks.get(task_id)
        if task is None:
            return
        if task.status != "running":
            return
        task.status = "completed"
        self._state.active_task_count = max(0, self._state.active_task_count - 1)

    def set_active_task_count(self, count: int) -> None:
        """Force the current active task count for verification or recovery."""

        self._state.active_task_count = max(0, count)

    def instance_snapshot_payloads(self) -> list[InstanceSnapshotPayload]:
        """Build sync payloads for all known local instances."""

        return [
            InstanceSnapshotPayload(
                terminal_id=self._state.terminal_id,
                instance_id=state.instance_id,
                profile_id=state.profile_id,
                handle=state.handle,
                runtime_status=state.runtime_status,
                window_id=state.window_id,
                remark=state.remark,
                metadata=dict(state.metadata),
            )
            for state in self._instance_manager.list_instances()
        ]

    def mark_instances_synced(self, synced_at: datetime | None = None) -> None:
        """Stamp local instances after a successful remote sync."""

        self._instance_manager.mark_synced(synced_at)
