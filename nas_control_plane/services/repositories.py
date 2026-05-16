"""Repository layer for NAS state sections."""

from __future__ import annotations

from datetime import datetime

from nas_control_plane.models import ActionLogRecord, InstanceRecord, TaskRecord, TerminalRecord
from nas_control_plane.services.store import JsonStateStore


class TerminalStateRepository:
    """Reads and writes terminal and instance state sections."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_terminals(self) -> dict[str, TerminalRecord]:
        return {
            terminal_id: _terminal_from_dict(item)
            for terminal_id, item in self._store.read_section("terminals").items()
        }

    def save_terminals(self, records: dict[str, TerminalRecord]) -> None:
        self._store.write_section(
            "terminals",
            {terminal_id: _terminal_to_dict(item) for terminal_id, item in records.items()},
        )

    def load_instances(self) -> dict[str, InstanceRecord]:
        return {
            instance_id: _instance_from_dict(item)
            for instance_id, item in self._store.read_section("instances").items()
        }

    def save_instances(self, records: dict[str, InstanceRecord]) -> None:
        self._store.write_section(
            "instances",
            {instance_id: _instance_to_dict(item) for instance_id, item in records.items()},
        )


class TaskRepository:
    """Reads and writes task state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_tasks(self) -> dict[str, TaskRecord]:
        return {
            task_id: _task_from_dict(item)
            for task_id, item in self._store.read_section("tasks").items()
        }

    def save_tasks(self, records: dict[str, TaskRecord]) -> None:
        self._store.write_section(
            "tasks",
            {task_id: _task_to_dict(item) for task_id, item in records.items()},
        )


class AuditLogRepository:
    """Reads and writes audit log state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_logs(self) -> list[ActionLogRecord]:
        return [_log_from_dict(item) for item in self._store.read_section("logs")]

    def save_logs(self, records: list[ActionLogRecord]) -> None:
        self._store.write_section("logs", [_log_to_dict(item) for item in records])


def _terminal_to_dict(record: TerminalRecord) -> dict[str, object]:
    return {
        "terminal_id": record.terminal_id,
        "hostname": record.hostname,
        "operator_name": record.operator_name,
        "status": record.status,
        "agent_version": record.agent_version,
        "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
        "capabilities": list(record.capabilities),
        "metadata": dict(record.metadata),
    }


def _terminal_from_dict(payload: dict[str, object]) -> TerminalRecord:
    last_seen_at = payload.get("last_seen_at")
    return TerminalRecord(
        terminal_id=str(payload["terminal_id"]),
        hostname=str(payload["hostname"]),
        operator_name=str(payload["operator_name"]),
        status=str(payload["status"]),
        agent_version=str(payload["agent_version"]),
        last_seen_at=datetime.fromisoformat(str(last_seen_at)) if last_seen_at else None,
        capabilities=list(payload.get("capabilities", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def _instance_to_dict(record: InstanceRecord) -> dict[str, object]:
    return {
        "instance_id": record.instance_id,
        "terminal_id": record.terminal_id,
        "profile_id": record.profile_id,
        "handle": record.handle,
        "runtime_status": record.runtime_status,
        "window_id": record.window_id,
        "remark": record.remark,
        "metadata": dict(record.metadata),
    }


def _instance_from_dict(payload: dict[str, object]) -> InstanceRecord:
    return InstanceRecord(
        instance_id=str(payload["instance_id"]),
        terminal_id=str(payload["terminal_id"]),
        profile_id=str(payload["profile_id"]),
        handle=str(payload["handle"]) if payload.get("handle") is not None else None,
        runtime_status=str(payload["runtime_status"]),
        window_id=str(payload["window_id"]) if payload.get("window_id") is not None else None,
        remark=str(payload["remark"]) if payload.get("remark") is not None else None,
        metadata=dict(payload.get("metadata", {})),
    )


def _task_to_dict(record: TaskRecord) -> dict[str, object]:
    return {
        "task_id": record.task_id,
        "terminal_id": record.terminal_id,
        "script_name": record.script_name,
        "status": record.status,
        "instance_id": record.instance_id,
        "priority": record.priority,
        "attempt_count": record.attempt_count,
        "max_attempts": record.max_attempts,
        "retryable": record.retryable,
        "final": record.final,
        "last_error_code": record.last_error_code,
        "last_error_message": record.last_error_message,
        "cancel_reason": record.cancel_reason,
        "parameters": dict(record.parameters),
        "created_at": record.created_at.isoformat(),
    }


def _task_from_dict(payload: dict[str, object]) -> TaskRecord:
    parameters = dict(payload.get("parameters", {}))
    status = str(payload["status"])
    max_attempts = _resolve_task_max_attempts(payload, parameters)
    attempt_count = _resolve_task_attempt_count(payload, parameters, status)
    retryable = bool(payload.get("retryable", False))
    final = bool(payload.get("final", False))
    if "retryable" not in payload and status == "failed" and attempt_count < max_attempts:
        retryable = True
    if "final" not in payload:
        final = status in {"completed", "cancelled"} or (status == "failed" and not retryable)

    return TaskRecord(
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        script_name=str(payload["script_name"]),
        status=status,
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        priority=int(payload.get("priority", 0)),
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        retryable=retryable,
        final=final,
        last_error_code=str(payload["last_error_code"]) if payload.get("last_error_code") is not None else None,
        last_error_message=(
            str(payload["last_error_message"])
            if payload.get("last_error_message") is not None
            else str(parameters["last_error"])
            if parameters.get("last_error") is not None
            else None
        ),
        cancel_reason=(
            str(payload["cancel_reason"])
            if payload.get("cancel_reason") is not None
            else str(parameters["cancel_reason"])
            if parameters.get("cancel_reason") is not None
            else None
        ),
        parameters=parameters,
        created_at=datetime.fromisoformat(str(payload["created_at"])),
    )


def _resolve_task_max_attempts(payload: dict[str, object], parameters: dict[str, object]) -> int:
    if payload.get("max_attempts") is not None:
        return max(1, int(payload["max_attempts"]))
    if parameters.get("max_attempts") is not None:
        return max(1, int(parameters["max_attempts"]))
    if parameters.get("retry_limit") is not None:
        return max(1, int(parameters["retry_limit"]) + 1)
    return 1


def _resolve_task_attempt_count(
    payload: dict[str, object],
    parameters: dict[str, object],
    status: str,
) -> int:
    if payload.get("attempt_count") is not None:
        return max(0, int(payload["attempt_count"]))

    retry_count = max(0, int(parameters.get("retry_count", 0)))
    if status in {"running", "completed", "failed", "cancelled", "dispatched"}:
        return retry_count + 1
    return retry_count


def _log_to_dict(record: ActionLogRecord) -> dict[str, object]:
    return {
        "log_id": record.log_id,
        "terminal_id": record.terminal_id,
        "level": record.level,
        "message": record.message,
        "emitted_at": record.emitted_at.isoformat(),
        "task_id": record.task_id,
        "run_id": record.run_id,
        "details": dict(record.details),
    }


def _log_from_dict(payload: dict[str, object]) -> ActionLogRecord:
    return ActionLogRecord(
        log_id=str(payload["log_id"]),
        terminal_id=str(payload["terminal_id"]),
        level=str(payload["level"]),
        message=str(payload["message"]),
        emitted_at=datetime.fromisoformat(str(payload["emitted_at"])),
        task_id=str(payload["task_id"]) if payload.get("task_id") is not None else None,
        run_id=str(payload["run_id"]) if payload.get("run_id") is not None else None,
        details=dict(payload.get("details", {})),
    )
