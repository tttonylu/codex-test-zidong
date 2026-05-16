"""Audit logging service."""

from __future__ import annotations

from nas_control_plane.models import ActionLogRecord
from nas_control_plane.services.repositories import AuditLogRepository
from shared.protocol import ActionResultPayload


class AuditService:
    """Stores action result events as audit log records."""

    def __init__(self, repository: AuditLogRepository | None = None) -> None:
        self._repository = repository
        self._logs: list[ActionLogRecord] = []
        self._load_state()

    def record_action_result(self, payload: ActionResultPayload) -> ActionLogRecord:
        """Append an audit log entry for one terminal execution result."""

        level = "info" if payload.status == "completed" else "error"
        failure_reason = None
        if payload.status != "completed":
            failure_reason = payload.error_message or payload.details.get("error") or payload.summary
        record = ActionLogRecord(
            log_id=f"log-{len(self._logs) + 1}",
            terminal_id=payload.terminal_id,
            level=level,
            message=payload.summary,
            emitted_at=payload.emitted_at,
            task_id=payload.task_id,
            run_id=payload.run_id,
            details={
                **payload.details,
                "result_status": payload.status,
                "error_code": payload.error_code,
                "error_message": payload.error_message,
                "retryable": payload.retryable,
                "final": payload.final,
                "failure_reason": failure_reason,
            },
        )
        self._logs.append(record)
        self._persist_log(record)
        return record

    def list_logs(self) -> list[ActionLogRecord]:
        """Return all audit log records."""

        return list(self._logs)

    def get_log(self, log_id: str) -> ActionLogRecord | None:
        """Return one log by id if it exists."""

        for record in self._logs:
            if record.log_id == log_id:
                return record
        return None

    def list_logs_filtered(
        self,
        terminal_id: str | None = None,
        task_id: str | None = None,
        level: str | None = None,
    ) -> list[ActionLogRecord]:
        """Return logs using optional management filters."""

        records = list(self._logs)
        if terminal_id is not None:
            records = [record for record in records if record.terminal_id == terminal_id]
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        if level is not None:
            records = [record for record in records if record.level == level]
        return records

    def latest_log_for_task(self, task_id: str) -> ActionLogRecord | None:
        """Return the most recent audit log for one task."""

        records = [record for record in self._logs if record.task_id == task_id]
        if not records:
            return None
        return max(records, key=lambda item: item.emitted_at)

    def summary(self) -> dict[str, object]:
        """Return a compact aggregate view over audit logs."""

        level_counts: dict[str, int] = {}
        for record in self._logs:
            level_counts[record.level] = level_counts.get(record.level, 0) + 1

        return {
            "log_count": len(self._logs),
            "level_counts": level_counts,
        }

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._logs = self._repository.load_logs()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_logs(self._logs)

    def _persist_log(self, record: ActionLogRecord) -> None:
        if self._repository is None:
            return
        if hasattr(self._repository, "append_log"):
            self._repository.append_log(record)
            return
        self._save_state()
