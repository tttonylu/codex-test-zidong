"""Minimal task dispatch service with explicit retry semantics."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from nas_control_plane.models import TaskAttemptRecord, TaskEventRecord, TaskRecord
from nas_control_plane.services.repositories import TaskRepository
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload, TaskControlPayload


class TaskDispatchService:
    """Stores and serves terminal-bound task assignments."""

    TERMINAL_STATUSES = {"completed", "cancelled"}

    def __init__(self, repository: TaskRepository | None = None) -> None:
        self._repository = repository
        self._tasks: dict[str, TaskRecord] = {}
        self._event_repository = None
        self._load_state()
        if repository is not None and hasattr(repository, "_store"):
            from nas_control_plane.services.sqlite_repositories import SqliteTaskEventRepository

            self._event_repository = SqliteTaskEventRepository(repository._store)

    def create_task(self, payload: TaskAssignmentPayload) -> TaskRecord:
        """Create a new queued task."""

        parameters = dict(payload.parameters)
        max_attempts = _resolve_max_attempts(parameters)
        record = TaskRecord(
            task_id=payload.task_id,
            terminal_id=payload.terminal_id,
            script_name=payload.script_name,
            status="queued",
            instance_id=payload.instance_id,
            priority=payload.priority,
            attempt_count=0,
            max_attempts=max_attempts,
            retryable=False,
            final=False,
            last_error_code=None,
            last_error_message=None,
            cancel_reason=None,
            parameters=_normalize_parameters(parameters, max_attempts=max_attempts),
        )
        self._tasks[record.task_id] = record
        self._persist_task(record)
        self._append_event(
            task_id=record.task_id,
            terminal_id=record.terminal_id,
            event_type="created",
            status=record.status,
            message=f"task {record.task_id} created",
            details={"script_name": record.script_name, "priority": record.priority},
        )
        return record

    def list_tasks(self, terminal_id: str | None = None) -> list[TaskRecord]:
        """Return all tasks, optionally filtered by terminal."""

        records = list(self._tasks.values())
        if terminal_id is None:
            return records
        return [record for record in records if record.terminal_id == terminal_id]

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Return one task by id if it exists."""

        return self._tasks.get(task_id)

    def list_task_events(self, task_id: str | None = None) -> list[TaskEventRecord]:
        """Return task timeline events, optionally filtered by task id."""

        if self._event_repository is None:
            return []
        records = self._event_repository.load_events()
        if task_id is None:
            return records
        return [record for record in records if record.task_id == task_id]

    def list_task_attempts(self, task_id: str) -> list[TaskAttemptRecord]:
        """Return aggregated execution attempts for one task."""

        events = self.list_task_events(task_id=task_id)
        attempts: list[TaskAttemptRecord] = []
        attempt_by_run_id: dict[str, TaskAttemptRecord] = {}

        for event in events:
            if event.event_type == "running":
                attempt = TaskAttemptRecord(
                    task_id=event.task_id,
                    attempt_number=len(attempts) + 1,
                    terminal_id=event.terminal_id,
                    status=event.status,
                    run_id=event.run_id,
                    script_name=_string_detail(event.details, "script_name"),
                    started_at=_datetime_detail(event.details, "started_at") or event.emitted_at,
                    details=dict(event.details),
                )
                attempts.append(attempt)
                if event.run_id is not None:
                    attempt_by_run_id[event.run_id] = attempt
                continue

            if event.event_type != "result":
                continue

            attempt = attempt_by_run_id.get(event.run_id) if event.run_id is not None else None
            if attempt is None:
                attempt = TaskAttemptRecord(
                    task_id=event.task_id,
                    attempt_number=len(attempts) + 1,
                    terminal_id=event.terminal_id,
                    status=event.status,
                    run_id=event.run_id,
                    finished_at=event.emitted_at,
                    details={},
                )
                attempts.append(attempt)
                if event.run_id is not None:
                    attempt_by_run_id[event.run_id] = attempt

            attempt.status = event.status
            attempt.finished_at = event.emitted_at
            attempt.summary = event.message
            attempt.error_code = _string_detail(event.details, "error_code")
            attempt.error_message = _string_detail(event.details, "error") or event.message if event.status != "completed" else None
            attempt.retryable = _bool_detail(event.details, "retryable")
            attempt.final = _bool_detail(event.details, "final")
            attempt.step_count = _int_detail(event.details, "step_count") or 0
            failed_step = _last_failed_step(event.details)
            if failed_step is not None:
                attempt.failed_step_name = _string_detail(failed_step, "name")
                attempt.failed_step_status = _string_detail(failed_step, "status")
            (
                attempt.failure_category,
                attempt.recommended_action,
            ) = _classify_attempt_failure(
                error_code=attempt.error_code,
                error_message=attempt.error_message,
                failed_step_name=attempt.failed_step_name,
                retryable=attempt.retryable,
            )
            attempt.details = dict(event.details)

        return attempts

    def list_tasks_filtered(
        self,
        terminal_id: str | None = None,
        status: str | None = None,
        script_name: str | None = None,
    ) -> list[TaskRecord]:
        """Return tasks using optional management filters."""

        records = list(self._tasks.values())
        if terminal_id is not None:
            records = [record for record in records if record.terminal_id == terminal_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        if script_name is not None:
            records = [record for record in records if record.script_name == script_name]
        records.sort(key=lambda item: (-item.priority, item.created_at))
        return records

    def summary(self) -> dict[str, object]:
        """Return a compact aggregate view over task state."""

        status_counts: dict[str, int] = {}
        script_counts: dict[str, int] = {}
        for record in self._tasks.values():
            status_counts[record.status] = status_counts.get(record.status, 0) + 1
            script_counts[record.script_name] = script_counts.get(record.script_name, 0) + 1

        return {
            "task_count": len(self._tasks),
            "status_counts": status_counts,
            "script_counts": script_counts,
        }

    def claim_tasks(self, terminal_id: str) -> list[TaskRecord]:
        """Return queued tasks for one terminal and mark them as dispatched."""

        claimed: list[TaskRecord] = []
        for task_id, record in list(self._tasks.items()):
            if record.terminal_id != terminal_id or record.status != "queued":
                continue
            updated = replace(record, status="dispatched", final=False)
            self._tasks[task_id] = updated
            claimed.append(updated)
        claimed.sort(key=lambda item: (-item.priority, item.created_at))
        self._persist_tasks(claimed)
        for record in claimed:
            self._append_event(
                task_id=record.task_id,
                terminal_id=record.terminal_id,
                event_type="claimed",
                status=record.status,
                message=f"task {record.task_id} claimed by terminal",
                details={"priority": record.priority},
            )
        return claimed

    def control_task(self, payload: TaskControlPayload) -> TaskRecord:
        """Apply a control-plane action such as cancel or retry."""

        record = self._require_task(payload.task_id)
        now = datetime.utcnow().isoformat()

        if payload.action == "cancel":
            if record.status in self.TERMINAL_STATUSES or record.status == "failed":
                raise ValueError(f"task cannot be cancelled from status: {record.status}")
            updated = replace(
                record,
                status="cancelled",
                retryable=False,
                final=True,
                cancel_reason=payload.reason,
                parameters=_with_task_metadata(
                    record,
                    cancel_reason=payload.reason,
                    cancelled_by=payload.requested_by,
                    cancelled_at=now,
                    updated_at=now,
                ),
            )
        elif payload.action == "retry":
            if record.status != "failed":
                raise ValueError(f"task can only be retried from failed status, got: {record.status}")
            if not record.retryable:
                raise ValueError("task is not retryable")
            if record.final:
                raise ValueError("task is already final")
            if record.attempt_count >= record.max_attempts:
                raise ValueError(
                    f"task retry limit reached: {record.attempt_count}/{record.max_attempts}"
                )
            updated = replace(
                record,
                status="queued",
                retryable=False,
                final=False,
                last_error_code=None,
                last_error_message=None,
                parameters=_with_task_metadata(
                    record,
                    retry_count=record.attempt_count,
                    retry_requested_by=payload.requested_by,
                    retry_requested_at=now,
                    updated_at=now,
                    last_error=None,
                ),
            )
        else:
            raise ValueError(f"unsupported task action: {payload.action}")

        self._tasks[payload.task_id] = updated
        self._persist_task(updated)
        self._append_event(
            task_id=updated.task_id,
            terminal_id=updated.terminal_id,
            event_type=payload.action,
            status=updated.status,
            message=f"task {updated.task_id} cancelled" if payload.action == "cancel" else f"task {updated.task_id} retried",
            details={
                "reason": payload.reason,
                "requested_by": payload.requested_by,
                "attempt_count": updated.attempt_count,
            },
        )
        return updated

    def record_result(self, payload: ActionResultPayload) -> TaskRecord:
        """Update one task from a terminal execution result."""

        record = self._require_task(payload.task_id)
        next_attempt = record.attempt_count
        if record.status in {"queued", "dispatched"}:
            next_attempt = min(record.max_attempts, record.attempt_count + 1)
        last_error_message = None
        if payload.status != "completed":
            last_error_message = payload.error_message or str(payload.details.get("error") or payload.summary)

        retryable = False
        final = payload.status in self.TERMINAL_STATUSES
        if payload.status == "failed":
            if payload.retryable is None:
                retryable = record.attempt_count < record.max_attempts
            else:
                retryable = bool(payload.retryable)
            if record.attempt_count >= record.max_attempts:
                retryable = False
            final = bool(payload.final) if payload.final is not None else not retryable
        elif payload.final is not None:
            final = bool(payload.final)

        updated = replace(
            record,
            status=payload.status,
            attempt_count=next_attempt,
            retryable=retryable,
            final=final,
            last_error_code=payload.error_code if payload.status != "completed" else None,
            last_error_message=last_error_message,
            parameters=_with_task_metadata(
                replace(record, attempt_count=next_attempt, last_error_message=last_error_message),
                result_summary=payload.summary,
                result_details=dict(payload.details),
                result_emitted_at=payload.emitted_at.isoformat(),
                result_run_id=payload.run_id,
                last_error=last_error_message,
                updated_at=datetime.utcnow().isoformat(),
            ),
        )
        self._tasks[payload.task_id] = updated
        self._persist_task(updated)
        self._append_event(
            task_id=updated.task_id,
            terminal_id=updated.terminal_id,
            event_type="result",
            status=updated.status,
            run_id=payload.run_id,
            message=payload.summary,
            details={
                **dict(payload.details),
                "error_code": updated.last_error_code,
                "error_message": updated.last_error_message,
                "retryable": updated.retryable,
                "final": updated.final,
            },
        )
        return updated

    def mark_running(self, payload: ScriptRunPayload) -> TaskRecord:
        """Mark one claimed task as running."""

        record = self._require_task(payload.task_id)
        next_attempt = record.attempt_count
        if record.status in {"queued", "dispatched"}:
            next_attempt = min(record.max_attempts, record.attempt_count + 1)

        updated = replace(
            record,
            status=payload.status,
            attempt_count=next_attempt,
            retryable=False,
            final=False,
            last_error_code=None,
            last_error_message=None,
            parameters=_with_task_metadata(
                record,
                run_id=payload.run_id,
                run_script_name=payload.script_name,
                run_started_at=payload.started_at.isoformat() if payload.started_at else None,
                last_error=None,
                retry_count=max(0, next_attempt - 1),
                updated_at=datetime.utcnow().isoformat(),
            ),
        )
        self._tasks[payload.task_id] = updated
        self._persist_task(updated)
        self._append_event(
            task_id=updated.task_id,
            terminal_id=updated.terminal_id,
            event_type="running",
            status=updated.status,
            run_id=payload.run_id,
            message=f"task {updated.task_id} running",
            details={
                "script_name": payload.script_name,
                "started_at": payload.started_at.isoformat() if payload.started_at else None,
            },
        )
        return updated

    def _load_state(self) -> None:
        if self._repository is None:
            return
        self._tasks = self._repository.load_tasks()

    def _save_state(self) -> None:
        if self._repository is None:
            return
        self._repository.save_tasks(self._tasks)

    def _persist_task(self, record: TaskRecord) -> None:
        if self._repository is None:
            return
        if hasattr(self._repository, "upsert_task"):
            self._repository.upsert_task(record)
            return
        self._save_state()

    def _persist_tasks(self, records: list[TaskRecord]) -> None:
        if self._repository is None:
            return
        if hasattr(self._repository, "upsert_task"):
            for record in records:
                self._repository.upsert_task(record)
            return
        self._save_state()

    def _append_event(
        self,
        *,
        task_id: str,
        terminal_id: str,
        event_type: str,
        status: str,
        message: str | None,
        details: dict[str, object],
        run_id: str | None = None,
    ) -> None:
        if self._event_repository is None:
            return
        now = datetime.utcnow()
        event = TaskEventRecord(
            event_id=f"{task_id}:{event_type}:{now.isoformat()}",
            task_id=task_id,
            terminal_id=terminal_id,
            event_type=event_type,
            status=status,
            emitted_at=now,
            run_id=run_id,
            message=message,
            details=details,
        )
        self._event_repository.append_event(event)

    def _require_task(self, task_id: str) -> TaskRecord:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc


def _resolve_max_attempts(parameters: dict[str, object]) -> int:
    if parameters.get("max_attempts") is not None:
        return max(1, int(parameters["max_attempts"]))
    if parameters.get("retry_limit") is not None:
        return max(1, int(parameters["retry_limit"]) + 1)
    return 1


def _normalize_parameters(parameters: dict[str, object], *, max_attempts: int) -> dict[str, object]:
    normalized = dict(parameters)
    normalized["retry_limit"] = max(0, max_attempts - 1)
    normalized["retry_count"] = max(0, int(normalized.get("retry_count", 0)))
    normalized["max_attempts"] = max_attempts
    normalized.setdefault("last_error", None)
    normalized.setdefault("cancel_reason", None)
    return normalized


def _with_task_metadata(record: TaskRecord, **updates: object) -> dict[str, object]:
    parameters = dict(record.parameters)
    parameters["retry_limit"] = max(0, record.max_attempts - 1)
    parameters["retry_count"] = max(0, record.attempt_count - 1)
    parameters["max_attempts"] = record.max_attempts
    parameters["cancel_reason"] = record.cancel_reason
    parameters["last_error"] = record.last_error_message
    parameters.update(updates)
    return parameters


def _string_detail(details: dict[str, object], key: str) -> str | None:
    value = details.get(key)
    if value is None:
        return None
    return str(value)


def _bool_detail(details: dict[str, object], key: str) -> bool | None:
    value = details.get(key)
    if value is None:
        return None
    return bool(value)


def _datetime_detail(details: dict[str, object], key: str) -> datetime | None:
    value = details.get(key)
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _int_detail(details: dict[str, object], key: str) -> int | None:
    value = details.get(key)
    if value is None:
        return None
    return int(value)


def _last_failed_step(details: dict[str, object]) -> dict[str, object] | None:
    raw_steps = details.get("steps")
    if not isinstance(raw_steps, list):
        return None
    failed_steps = [step for step in raw_steps if isinstance(step, dict) and step.get("status") == "failed"]
    if not failed_steps:
        return None
    return failed_steps[-1]


def _classify_attempt_failure(
    *,
    error_code: str | None,
    error_message: str | None,
    failed_step_name: str | None,
    retryable: bool | None,
) -> tuple[str | None, str | None]:
    if error_code is None and error_message is None and failed_step_name is None:
        return None, None

    code = (error_code or "").lower()
    message = (error_message or "").lower()
    failed_step = (failed_step_name or "").lower()

    if code.startswith("bitbrowser.") or failed_step == "open_browser":
        return "bitbrowser", "Check BitBrowser availability, then retry the task."
    if code.startswith("worker.missing_") or "requires instance_id" in message or "requires bitbrowser_client" in message:
        return "input", "Fix task inputs or runtime dependencies before retrying."
    if code == "worker.unsupported_script":
        return "unsupported", "Use a supported script name or implement the missing worker."
    if "timeout" in message or "rate limited" in message or "429" in message:
        if retryable:
            return "network", "Wait for recovery or cooldown, then retry the task."
        return "network", "Investigate connectivity or platform throttling before retrying."
    if code.endswith(".execution_failed") or code.startswith("worker."):
        return "worker", "Inspect worker execution details and failed steps before retrying."
    if retryable:
        return "transient", "Review the latest error and retry when the dependency is healthy."
    return "unknown", "Inspect the task report details and audit log before taking action."
