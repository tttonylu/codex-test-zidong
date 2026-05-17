"""Minimal in-memory task dispatch service."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from nas_control_plane.models import TaskRecord
from nas_control_plane.services.recovery import resolve_recovery_policy
from nas_control_plane.services.repositories import TaskRepository
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload


class TaskDispatchService:
    """Stores and serves simple terminal-bound task assignments."""

    def __init__(
        self,
        repository: TaskRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._now_fn = now_fn or datetime.utcnow
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

    def get_task(self, task_id: str) -> TaskRecord:
        """Return one task by identifier."""

        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

    def query_tasks(
        self,
        *,
        terminal_id: str | None = None,
        status: str | None = None,
        script_name: str | None = None,
        retryable: bool | None = None,
        final: bool | None = None,
    ) -> list[TaskRecord]:
        """Return tasks matching the requested filters."""

        records = self.list_tasks(terminal_id=terminal_id)
        return [
            record
            for record in records
            if _matches_task_filter(
                record,
                status=status,
                script_name=script_name,
                retryable=retryable,
                final=final,
            )
        ]

    def claim_tasks(self, terminal_id: str) -> list[TaskRecord]:
        """Return queued tasks for one terminal and mark them as dispatched."""

        claimed: list[TaskRecord] = []
        now = self._now_fn()
        for task_id, record in list(self._tasks.items()):
            if record.terminal_id != terminal_id:
                continue
            if record.status == "queued":
                pass
            elif record.status == "retry_pending":
                if not retry_task_ready(record, now):
                    continue
            else:
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

        policy = resolve_recovery_policy(payload.error_code)
        exhausted = updated_retry_limit_exhausted(record)
        retryable_requested = payload.retryable if payload.retryable is not None else policy.retryable
        final = bool(payload.final) or (payload.status != "completed" and (exhausted or not retryable_requested))
        retryable = retryable_requested and not final
        status = payload.status
        if payload.status != "completed":
            status = "retryable_failure" if retryable else "terminal_failure"

        updated = replace(
            record,
            status=status,
            retryable=retryable,
            final=final,
            last_error_code=payload.error_code,
            last_error_message=payload.error_message or None,
            parameters={
                **record.parameters,
                "result_summary": payload.summary,
                "result_details": dict(payload.details),
                "result_emitted_at": payload.emitted_at.isoformat(),
                "result_run_id": payload.run_id,
                "updated_at": self._now_fn().isoformat(),
                "last_error_code": payload.error_code,
                "last_error_message": payload.error_message,
                "failure_category": policy.category,
                "recommended_action": policy.recommended_action,
                "retry_delay_seconds": policy.retry_delay_seconds,
                "retry_available_at": None,
                "retryable": retryable,
                "final": final,
            },
        )
        self._tasks[payload.task_id] = updated
        self._save_state()
        return updated

    def retry_task(self, task_id: str, requested_by: str | None = None) -> TaskRecord:
        """Ask NAS to queue another attempt for a previously failed task."""

        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        exhausted = updated_retry_limit_exhausted(record)
        accepted = record.status in {"failed", "terminal_failure", "retryable_failure", "retry_pending"} and not exhausted
        retry_delay_seconds = _coerce_retry_delay_seconds(record.parameters.get("retry_delay_seconds"))
        now = self._now_fn()
        parameters = {
            **record.parameters,
            "retry_requested_at": now.isoformat(),
            "retry_requested_by": requested_by,
            "updated_at": now.isoformat(),
        }
        if accepted:
            parameters["retry_request_accepted"] = True
            parameters["retry_available_at"] = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
            updated = replace(
                record,
                status="retry_pending",
                retryable=False,
                final=False,
                parameters=parameters,
            )
        else:
            parameters["retry_request_accepted"] = False
            parameters["retry_blocked_reason"] = "retry_limit_exceeded" if exhausted else "task_not_retryable"
            updated = replace(
                record,
                status="terminal_failure" if record.status != "completed" else record.status,
                retryable=False,
                final=True if record.status != "completed" else record.final,
                parameters=parameters,
            )

        self._tasks[task_id] = updated
        self._save_state()
        return updated

    def cancel_task(self, task_id: str, requested_by: str | None = None) -> TaskRecord:
        """Cancel one task when it has not reached a final completed state."""

        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        cancellable = record.status in {"queued", "dispatched", "running", "retry_pending"}
        parameters = {
            **record.parameters,
            "cancel_requested_at": self._now_fn().isoformat(),
            "cancel_requested_by": requested_by,
            "updated_at": self._now_fn().isoformat(),
        }
        if cancellable:
            parameters["cancel_request_accepted"] = True
            updated = replace(
                record,
                status="cancelled",
                retryable=False,
                final=True,
                parameters=parameters,
            )
        else:
            parameters["cancel_request_accepted"] = False
            parameters["cancel_blocked_reason"] = "task_already_final"
            updated = replace(
                record,
                parameters=parameters,
            )

        self._tasks[task_id] = updated
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
                "updated_at": self._now_fn().isoformat(),
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


def updated_retry_limit_exhausted(record: TaskRecord) -> bool:
    """Return whether one more retry would exceed the configured limit."""

    return record.attempt_count >= record.retry_limit + 1


def retry_task_ready(record: TaskRecord, now: datetime) -> bool:
    """Return whether one retry-pending task may be claimed now."""

    if record.status != "retry_pending":
        return True

    raw = record.parameters.get("retry_available_at")
    if not raw:
        return True

    try:
        available_at = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    return available_at <= now


def _matches_task_filter(
    record: TaskRecord,
    *,
    status: str | None,
    script_name: str | None,
    retryable: bool | None,
    final: bool | None,
) -> bool:
    if status is not None and record.status != status:
        return False
    if script_name is not None and record.script_name != script_name:
        return False
    if retryable is not None and record.retryable is not retryable:
        return False
    if final is not None and record.final is not final:
        return False
    return True


def _coerce_retry_delay_seconds(raw: object) -> int:
    try:
        return max(0, int(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0
