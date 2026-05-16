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

    def list_logs(self) -> list[ActionLogRecord]:
        """Return all audit log records."""

        return list(self._logs)

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._logs = self._repository.load_logs()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_logs(self._logs)
