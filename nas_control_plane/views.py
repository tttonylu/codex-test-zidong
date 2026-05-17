"""Text views for NAS management queries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from nas_control_plane.models import ActionLogRecord, InstanceRecord, TaskRecord, TerminalRecord


def render_terminal_summary(record: TerminalRecord) -> str:
    """Render one terminal record as a compact text block."""

    return "\n".join(
        [
            f"terminal: {record.terminal_id}",
            f"host: {record.hostname}",
            f"operator: {record.operator_name}",
            f"status: {record.status}",
            f"agent: {record.agent_version}",
            f"last_seen: {_format_value(record.last_seen_at)}",
            f"capabilities: {', '.join(record.capabilities) if record.capabilities else '-'}",
        ]
    )


def render_instance_summary(record: InstanceRecord) -> str:
    """Render one instance record as a compact text block."""

    return "\n".join(
        [
            f"instance: {record.instance_id}",
            f"terminal: {record.terminal_id}",
            f"profile: {record.profile_id}",
            f"handle: {record.handle or '-'}",
            f"runtime_status: {record.runtime_status}",
            f"window_id: {record.window_id or '-'}",
            f"remark: {record.remark or '-'}",
        ]
    )


def render_task_summary(record: TaskRecord) -> str:
    """Render one task record as a compact text block."""

    return "\n".join(
        [
            f"task: {record.task_id}",
            f"terminal: {record.terminal_id}",
            f"script: {record.script_name}",
            f"status: {record.status}",
            f"attempts: {record.attempt_count}/{record.retry_limit + 1}",
            f"retryable: {record.retryable}",
            f"final: {record.final}",
            f"error: {record.last_error_code or '-'}",
        ]
    )


def render_log_summary(record: ActionLogRecord) -> str:
    """Render one log record as a compact text block."""

    return "\n".join(
        [
            f"log: {record.log_id}",
            f"terminal: {record.terminal_id}",
            f"level: {record.level}",
            f"task: {record.task_id or '-'}",
            f"run: {record.run_id or '-'}",
            f"message: {record.message}",
        ]
    )


def render_collection(title: str, items: Iterable[str]) -> str:
    """Render a titled list of text blocks."""

    blocks = [f"## {title}"]
    blocks.extend(items)
    return "\n\n".join(blocks)


def _format_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
