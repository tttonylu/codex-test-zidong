"""Minimal in-memory task dispatch service."""

from __future__ import annotations

from datetime import datetime
from dataclasses import replace

from nas_control_plane.models import TaskRecord
from nas_control_plane.services.repositories import TaskRepository
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload


class TaskDispatchService:
    """Stores and serves simple terminal-bound task assignments."""

    def __init__(self, repository: TaskRepository | None = None) -> None:
        self._repository = repository
        self._tasks: dict[str, TaskRecord] = {}
        self._load_state()

    def create_task(self, payload: TaskAssignmentPayload) -> TaskRecord:
        """Create a new queued task."""

        record = TaskRecord(
            task_id=payload.task_id,
            terminal_id=payload.terminal_id,
            script_name=payload.script_name,
            status="queued",
            instance_id=payload.instance_id,
            priority=payload.priority,
            retry_limit=payload.retry_limit,
            close_after_actions=payload.close_after_actions,
            requested_by=payload.requested_by,
            parameters=dict(payload.parameters),
        )
        self._tasks[record.task_id] = record
        self._save_state()
        return record

    def list_tasks(self, terminal_id: str | None = None) -> list[TaskRecord]:
        """Return all tasks, optionally filtered by terminal."""

        records = list(self._tasks.values())
        if terminal_id is None:
            return records
        return [record for record in records if record.terminal_id == terminal_id]

    def claim_tasks(self, terminal_id: str) -> list[TaskRecord]:
        """Return queued tasks for one terminal and mark them as dispatched."""

        claimed: list[TaskRecord] = []
        for task_id, record in list(self._tasks.items()):
            if record.terminal_id != terminal_id or record.status != "queued":
                continue
            updated = replace(record, status="dispatched")
            self._tasks[task_id] = updated
            claimed.append(updated)
        claimed.sort(key=lambda item: (-item.priority, item.created_at))
        self._save_state()
        return claimed

    def record_result(self, payload: ActionResultPayload) -> TaskRecord:
        """Update one task from a terminal execution result."""

        try:
            record = self._tasks[payload.task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {payload.task_id}") from exc

        updated = replace(
            record,
            status=payload.status,
            retryable=bool(payload.retryable),
            final=bool(payload.final),
            last_error_code=payload.error_code,
            last_error_message=payload.error_message or None,
            parameters={
                **record.parameters,
                "result_summary": payload.summary,
                "result_details": dict(payload.details),
                "result_emitted_at": payload.emitted_at.isoformat(),
                "result_run_id": payload.run_id,
                "updated_at": datetime.utcnow().isoformat(),
                "last_error_code": payload.error_code,
                "last_error_message": payload.error_message,
                "retryable": payload.retryable,
                "final": payload.final,
            },
        )
        if updated.attempt_count > updated.retry_limit + 1:
            updated = replace(updated, final=True, retryable=False)
        self._tasks[payload.task_id] = updated
        self._save_state()
        return updated

    def mark_running(self, payload: ScriptRunPayload) -> TaskRecord:
        """Mark one claimed task as running."""

        try:
            record = self._tasks[payload.task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {payload.task_id}") from exc

        updated = replace(
            record,
            status=payload.status,
            attempt_count=record.attempt_count + 1,
            parameters={
                **record.parameters,
                "run_id": payload.run_id,
                "run_script_name": payload.script_name,
                "run_started_at": payload.started_at.isoformat() if payload.started_at else None,
                "run_step_count": payload.step_count,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        self._tasks[payload.task_id] = updated
        self._save_state()
        return updated

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._tasks = self._repository.load_tasks()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_tasks(self._tasks)
