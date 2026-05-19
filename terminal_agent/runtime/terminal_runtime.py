"""Terminal runtime for registration, heartbeat, sync, and slot state."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)
from terminal_agent.models import InstanceState, LocalTask, ScriptSlot, TerminalState
from terminal_agent.runtime.health_monitor import HealthAction, HealthMonitor
from terminal_agent.runtime.instance_manager import InstanceManager
from terminal_agent.runtime.repositories import TerminalRuntimeRepository
from terminal_agent.runtime.store import JsonStateStore


class TerminalRuntime:
    """Produces terminal-side payloads from local runtime and slot state."""

    def __init__(
        self,
        terminal_id: str,
        hostname: str,
        operator_name: str,
        agent_version: str,
        capabilities: list[str] | None = None,
        max_parallel_tasks: int | None = None,
        state_path: str | Path | None = None,
        health_monitor: HealthMonitor | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self._operator_name = operator_name
        self._capabilities = list(capabilities or [])
        self._max_parallel_tasks = max_parallel_tasks
        self._instance_manager = InstanceManager()
        self._tasks: dict[str, LocalTask] = {}
        self._slots: dict[str, ScriptSlot] = {}
        self._runtime_state: dict[str, object] = {"recovered_task_ids_pending": []}
        self._health_monitor = health_monitor
        self._restart_requests: list[tuple[str, str]] = []
        self._result_outbox: list[ActionResultPayload] = []
        self._memory = memory_service
        self._repository = (
            TerminalRuntimeRepository(JsonStateStore(state_path))
            if state_path is not None
            else None
        )
        self._state = TerminalState(
            terminal_id=terminal_id,
            hostname=hostname,
            status="booting",
            agent_version=agent_version,
        )
        self._load_state()
        self._ensure_slot_pool()
        self._recover_unfinished_slots()
        self._save_state()

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
                "blocked_instance_ids": self.blocked_instance_ids(),
                "slot_count": len(self._slots),
                "slots": self.slot_snapshot(),
                "recovered_task_ids": list(self._runtime_state.get("recovered_task_ids_pending", [])),
                "task_source_mode": self._runtime_state.get("task_source_mode"),
                "task_source_status": self._runtime_state.get("task_source_status"),
                "task_source_queue_topic": self._runtime_state.get("task_source_queue_topic"),
                "result_outbox_count": len(self._result_outbox),
            },
        )

    def runtime_metadata(self) -> dict[str, object]:
        """Return a mutable copy of terminal-local runtime metadata."""

        return dict(self._runtime_state)

    def set_runtime_metadata(self, values: dict[str, object]) -> None:
        """Replace terminal-local runtime metadata and persist it."""

        recovered_task_ids_pending = list(self._runtime_state.get("recovered_task_ids_pending", []))
        self._runtime_state = {
            **dict(values),
            "recovered_task_ids_pending": recovered_task_ids_pending,
        }
        self._save_state()

    def merge_runtime_metadata(self, values: dict[str, object]) -> None:
        """Merge terminal-local runtime metadata and persist it."""

        self.set_runtime_metadata(
            {
                **self._runtime_state,
                **dict(values),
            }
        )

    def clear_runtime_metadata_keys(self, keys: list[str]) -> None:
        """Remove selected terminal-local runtime metadata keys and persist it."""

        updated = dict(self._runtime_state)
        for key in keys:
            updated.pop(key, None)
        self.set_runtime_metadata(updated)

    def set_recovered_task_ids_pending(self, task_ids: list[str]) -> None:
        """Replace the locally pending recovered task identifiers and persist them."""

        self._runtime_state["recovered_task_ids_pending"] = list(task_ids)
        self._save_state()

    def enqueue_result_outbox(self, payload: ActionResultPayload) -> None:
        """Persist one completed result for later replay."""

        self._result_outbox.append(payload)
        self._save_state()

    def result_outbox_items(self) -> list[ActionResultPayload]:
        """Return the current persisted result outbox items."""

        return list(self._result_outbox)

    def ack_result_outbox_item(self, run_id: str) -> None:
        """Remove one replayed result from the local outbox."""

        self._result_outbox = [item for item in self._result_outbox if item.run_id != run_id]
        self._save_state()

    def accept_tasks(self, tasks: Iterable[LocalTask]) -> list[LocalTask]:
        """Merge a fresh assignment batch into the known local task set."""

        accepted = list(tasks)
        for task in accepted:
            self._tasks[task.task_id] = task
        self._refresh_task_counts()
        self._save_state()
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

    def update_instance_identity(
        self,
        *,
        instance_id: str,
        handle: str | None,
        remark: str | None,
        profile_id: str | None = None,
        runtime_status: str | None = None,
    ) -> InstanceState:
        """Update one local instance after a confirmed browser identity change."""

        updated = self._instance_manager.update_instance_identity(
            instance_id=instance_id,
            handle=handle,
            remark=remark,
            profile_id=profile_id,
            runtime_status=runtime_status,
        )
        self._state.active_instance_count = len(self._instance_manager.list_instances())
        self._save_state()
        return updated

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
                "blocked_instance_ids": self.blocked_instance_ids(),
                "slot_count": len(self._slots),
                "slots": self.slot_snapshot(),
                "recovered_task_ids": list(self._runtime_state.get("recovered_task_ids_pending", [])),
                "task_source_mode": self._runtime_state.get("task_source_mode"),
                "task_source_status": self._runtime_state.get("task_source_status"),
                "task_source_queue_topic": self._runtime_state.get("task_source_queue_topic"),
                "result_outbox_count": len(self._result_outbox),
            },
        )

    def claim_capacity(self) -> int | None:
        """Return how many tasks this terminal should claim in one cycle."""

        if self._max_parallel_tasks is None:
            return None
        return min(len(self.available_slots()), max(0, self._max_parallel_tasks - self._state.active_task_count))

    def blocked_instance_ids(self) -> list[str]:
        """Return instance identifiers that are currently occupying execution slots."""

        return [
            slot.bound_instance_id
            for slot in self._slots.values()
            if slot.status in {"assigned", "running"} and slot.bound_instance_id is not None
        ]

    def available_slots(self) -> list[ScriptSlot]:
        """Return slots that may accept new assignments."""

        return [slot for slot in self._slots.values() if slot.status == "idle"]

    def select_slot_for_assignment(self, assignment: TaskAssignmentPayload) -> ScriptSlot:
        """Choose the best slot for one assignment using affinity and recent usage."""

        idle_slots = self.available_slots()
        if not idle_slots:
            raise RuntimeError("no slot available for assignment")

        preferred_instance_id = assignment.instance_id
        preferred_script_name = assignment.script_name

        def score(slot: ScriptSlot) -> tuple[int, int, str]:
            affinity = 0
            if preferred_instance_id is not None and slot.metadata.get("last_instance_id") == preferred_instance_id:
                affinity += 100
            if preferred_script_name is not None and slot.metadata.get("last_script_name") == preferred_script_name:
                affinity += 20
            if slot.metadata.get("last_task_id") is None:
                affinity += 5
            recent_use = int(slot.metadata.get("usage_count", 0))
            return (-affinity, recent_use, slot.slot_id)

        return sorted(idle_slots, key=score)[0]

    def slot_snapshot(self) -> list[dict[str, object]]:
        """Return a compact external view of the current slot occupancy."""

        snapshot: list[dict[str, object]] = []
        for slot in sorted(self._slots.values(), key=lambda item: item.slot_id):
            snapshot.append(
                {
                    "slot_id": slot.slot_id,
                    "status": slot.status,
                    "task_id": slot.task_id,
                    "script_name": slot.script_name,
                    "bound_instance_id": slot.bound_instance_id,
                    "run_id": slot.run_id,
                    "usage_count": slot.metadata.get("usage_count", 0),
                    "last_instance_id": slot.metadata.get("last_instance_id"),
                    "selection_reason": slot.metadata.get("selection_reason"),
                }
            )
        return snapshot

    def assignment_for_slot(self, slot_id: str) -> TaskAssignmentPayload | None:
        """Return the current assignment bound to one slot, if any."""

        return self._slots[slot_id].assignment

    def assign_task_to_slot(self, assignment: TaskAssignmentPayload) -> ScriptSlot:
        """Bind one claimed task to the next available slot."""

        slot = self.select_slot_for_assignment(assignment)

        task = LocalTask(
            task_id=assignment.task_id,
            script_name=assignment.script_name,
            status="queued",
            instance_id=assignment.instance_id,
            priority=assignment.priority,
            retry_limit=assignment.retry_limit,
            close_after_actions=assignment.close_after_actions,
            requested_by=assignment.requested_by,
            parameters=dict(assignment.parameters),
        )
        self._tasks[task.task_id] = task
        now = datetime.utcnow()
        slot.status = "assigned"
        slot.script_name = assignment.script_name
        slot.bound_instance_id = assignment.instance_id
        slot.run_id = None
        slot.task_id = assignment.task_id
        slot.assignment = assignment
        slot.run = None
        slot.assigned_at = now
        slot.started_at = None
        slot.finished_at = None
        slot.metadata = {
            **slot.metadata,
            "assignment_count": int(slot.metadata.get("assignment_count", 0)) + 1,
            "last_task_id": assignment.task_id,
            "last_instance_id": assignment.instance_id,
            "last_script_name": assignment.script_name,
            "selection_reason": self._selection_reason(slot, assignment),
        }
        self._refresh_task_counts()
        self._save_state()
        return slot

    def mark_slot_started(self, slot_id: str, run_id: str) -> None:
        """Mark one assigned slot as actively running."""

        slot = self._slots[slot_id]
        task_id = slot.task_id
        if task_id is None:
            raise RuntimeError(f"slot has no task assignment: {slot_id}")
        task = self._tasks[task_id]
        task.status = "running"
        slot.status = "running"
        slot.run_id = run_id
        slot.started_at = datetime.utcnow()
        self._refresh_task_counts()
        self._save_state()

    def release_slot(self, slot_id: str, task_status: str = "completed") -> None:
        """Release one slot after execution finishes."""

        slot = self._slots[slot_id]
        if slot.task_id is not None and slot.task_id in self._tasks:
            self._tasks[slot.task_id].status = task_status
        slot.status = "idle"
        slot.script_name = None
        slot.bound_instance_id = None
        slot.run_id = None
        slot.task_id = None
        slot.assignment = None
        slot.run = None
        slot.assigned_at = None
        slot.started_at = None
        slot.finished_at = datetime.utcnow()
        slot.metadata = {
            **slot.metadata,
            "last_finished_at": slot.finished_at.isoformat(),
            "last_task_status": task_status,
            "usage_count": int(slot.metadata.get("usage_count", 0)) + 1,
        }
        self._refresh_task_counts()
        self._save_state()

    # ── optional mem0 integration ────────────────────────────

    @property
    def memory_service(self) -> Any | None:
        """Optional WorkspaceMemoryService for cross-session memory."""
        return self._memory

    def remember(
        self,
        fact: str,
        *,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a fact in optional workspace memory (no-op if memory not configured)."""
        if self._memory is None:
            return
        merged_meta = dict(metadata or {})
        merged_meta.setdefault("terminal_id", self._state.terminal_id)
        self._memory.remember_fact(
            fact,
            agent_id=f"terminal:{self._state.terminal_id}",
            tags=tags,
        )

    def clear_nonpersistent_slots(self) -> int:
        """Clear local in-memory slot occupancy that has no durable recovery backing."""

        cleared = 0
        for slot in self._slots.values():
            if slot.status == "idle":
                continue
            self.release_slot(slot.slot_id, task_status="failed")
            cleared += 1
        return cleared

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

        self._ensure_slot_pool()
        target = max(0, count)
        placeholders = [
            slot for slot in self._slots.values() if slot.status == "running" and slot.task_id is None
        ]
        if len(placeholders) < target:
            for slot in self.available_slots()[: target - len(placeholders)]:
                slot.status = "running"
                slot.script_name = "manual-occupancy"
                slot.metadata = {"manual": True}
        elif len(placeholders) > target:
            for slot in placeholders[target:]:
                slot.status = "idle"
                slot.script_name = None
                slot.metadata = {}
        self._refresh_task_counts()
        self._save_state()

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

    # -- health monitor integration ----------------------------------------

    @property
    def health_monitor(self) -> HealthMonitor | None:
        """Return the optional health monitor instance."""
        return self._health_monitor

    def running_slots(self) -> list[ScriptSlot]:
        """Return all slots that are currently assigned or running."""
        return [
            slot for slot in self._slots.values()
            if slot.status in {"assigned", "running"}
        ]

    def register_health_action(self, action: HealthAction) -> None:
        """Record a health action and update instance metadata.

        For ``restart`` actions, the instance is flagged so that
        ``agent_loop`` can pick it up and execute ``close→open``.
        """
        instance = self._instance_manager.get_instance(action.instance_id)
        if instance is not None:
            instance.metadata["instance_health_status"] = action.action
            instance.metadata["health_reason"] = action.reason
            if action.action == "restart":
                instance.metadata["restart_requested"] = True
                instance.metadata["restart_reason"] = action.reason
                instance.health_status = "restarting"
                # Deduplicate restart requests
                if not any(iid == action.instance_id for iid, _ in self._restart_requests):
                    self._restart_requests.append((action.instance_id, action.reason))

    def restart_requested_instances(self) -> list[tuple[str, str]]:
        """Return ``(instance_id, reason)`` for instances pending restart."""
        return list(self._restart_requests)

    def ack_restart_executed(self, instance_id: str) -> None:
        """Remove one instance from the restart queue after restart is done."""
        self._restart_requests = [
            (iid, reason) for iid, reason in self._restart_requests
            if iid != instance_id
        ]

    def _ensure_slot_pool(self) -> None:
        slot_count = self._max_parallel_tasks if self._max_parallel_tasks is not None else 1
        slot_count = max(1, slot_count)
        for index in range(1, slot_count + 1):
            slot_id = f"slot-{index:02d}"
            self._slots.setdefault(slot_id, ScriptSlot(slot_id=slot_id, status="idle"))

    def _refresh_task_counts(self) -> None:
        self._state.active_task_count = sum(1 for slot in self._slots.values() if slot.status == "running")
        self._state.queued_task_count = sum(1 for slot in self._slots.values() if slot.status == "assigned")

    def _load_state(self) -> None:
        if self._repository is None:
            return
        self._slots = self._repository.load_slots()
        self._tasks = self._repository.load_tasks()
        self._runtime_state = self._repository.load_runtime() or {"recovered_task_ids_pending": []}
        self._result_outbox = self._repository.load_result_outbox()

    def _save_state(self) -> None:
        if self._repository is None:
            return
        self._repository.save_slots(self._slots)
        self._repository.save_tasks(self._tasks)
        self._repository.save_runtime(self._runtime_state)
        self._repository.save_result_outbox(self._result_outbox)

    def _recover_unfinished_slots(self) -> None:
        recovered_any = False
        for slot in self._slots.values():
            if slot.status not in {"assigned", "running"}:
                continue
            recovered_any = True
            if slot.task_id is not None and slot.task_id in self._tasks:
                task = self._tasks[slot.task_id]
                task.status = "abandoned"
                task.parameters = {
                    **task.parameters,
                    "recovered_from_slot_id": slot.slot_id,
                    "recovered_run_id": slot.run_id,
                    "recovered_at": datetime.utcnow().isoformat(),
                }
                pending = list(self._runtime_state.get("recovered_task_ids_pending", []))
                pending.append(task.task_id)
                self._runtime_state["recovered_task_ids_pending"] = pending
            slot.metadata = {
                **slot.metadata,
                "recovered": True,
                "recovered_at": datetime.utcnow().isoformat(),
                "previous_status": slot.status,
            }
            slot.status = "idle"
            slot.script_name = None
            slot.run_id = None
            slot.task_id = None
            slot.assignment = None
            slot.run = None
            slot.assigned_at = None
            slot.started_at = None
            slot.bound_instance_id = None
        if recovered_any:
            self._refresh_task_counts()
            self._save_state()

    def _selection_reason(self, slot: ScriptSlot, assignment: TaskAssignmentPayload) -> str:
        instance_id = assignment.instance_id
        if instance_id is not None and slot.metadata.get("last_instance_id") == instance_id:
            return "instance_affinity"
        if slot.metadata.get("last_script_name") == assignment.script_name:
            return "script_affinity"
        return "least_used"

    def ack_recovered_task_ids(self, recovered_task_ids: list[str]) -> None:
        """Acknowledge recovered tasks after NAS accepts the heartbeat."""

        pending = list(self._runtime_state.get("recovered_task_ids_pending", []))
        remaining = [task_id for task_id in pending if task_id not in set(recovered_task_ids)]
        self._runtime_state["recovered_task_ids_pending"] = remaining
        self._save_state()
