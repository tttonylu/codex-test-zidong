"""Audit logging service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
            },
        )
        self._logs.append(record)
        self._save_state()
        return record

    def record(
        self,
        *,
        terminal_id: str,
        level: str,
        message: str,
        task_id: str | None = None,
        run_id: str | None = None,
        details: dict[str, Any] | None = None,
        emitted_at: datetime | None = None,
    ) -> ActionLogRecord:
        """Append a generic audit log entry."""

        record = ActionLogRecord(
            log_id=f"log-{len(self._logs) + 1}",
            terminal_id=terminal_id,
            level=level,
            message=message,
            emitted_at=emitted_at or datetime.now(UTC),
            task_id=task_id,
            run_id=run_id,
            details=dict(details or {}),
        )
        self._logs.append(record)
        self._save_state()
        return record

    def list_logs(self) -> list[ActionLogRecord]:
        """Return all audit log records."""

        return list(self._logs)

    def query_logs(
        self,
        *,
        terminal_id: str | None = None,
        task_id: str | None = None,
        level: str | None = None,
    ) -> list[ActionLogRecord]:
        """Return logs matching the requested filters."""

        return [
            record
            for record in self._logs
            if _matches_log(record, terminal_id=terminal_id, task_id=task_id, level=level)
        ]

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._logs = self._repository.load_logs()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_logs(self._logs)


def _matches_log(
    record: ActionLogRecord,
    *,
    terminal_id: str | None,
    task_id: str | None,
    level: str | None,
) -> bool:
    if terminal_id is not None and record.terminal_id != terminal_id:
        return False
    if task_id is not None and record.task_id != task_id:
        return False
    if level is not None and record.level != level:
        return False
    return True
