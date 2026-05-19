"""Text views for NAS management queries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from nas_control_plane.models import (
    AccountInventoryRecord,
    ActionLogRecord,
    CreatorInboxRecord,
    DailyActionStatRecord,
    InstanceRecord,
    PluginCampaignRecord,
    TaskRecord,
    TerminalRecord,
)


def render_terminal_summary(record: TerminalRecord) -> str:
    """Render one terminal record as a compact text block."""

    metadata = record.metadata or {}
    blocked_instance_ids = metadata.get("blocked_instance_ids", [])
    slots = metadata.get("slots", [])
    return "\n".join(
        [
            f"terminal: {record.terminal_id}",
            f"host: {record.hostname}",
            f"operator: {record.operator_name}",
            f"status: {record.status}",
            f"agent: {record.agent_version}",
            f"last_seen: {_format_value(record.last_seen_at)}",
            f"capabilities: {', '.join(record.capabilities) if record.capabilities else '-'}",
            f"max_parallel_tasks: {_format_value(metadata.get('max_parallel_tasks'))}",
            f"task_source_mode: {_format_value(metadata.get('task_source_mode'))}",
            f"task_source_status: {_format_value(metadata.get('task_source_status'))}",
            f"task_source_queue_topic: {_format_value(metadata.get('task_source_queue_topic'))}",
            f"slot_count: {_format_value(metadata.get('slot_count'))}",
            f"result_outbox_count: {_format_value(metadata.get('result_outbox_count'))}",
            f"active_task_count: {_format_value(metadata.get('active_task_count'))}",
            f"queued_task_count: {_format_value(metadata.get('queued_task_count'))}",
            f"blocked_instance_ids: {', '.join(blocked_instance_ids) if blocked_instance_ids else '-'}",
            f"slots: {_format_slots(slots)}",
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

    parameters = record.parameters or {}
    return "\n".join(
        [
            f"task: {record.task_id}",
            f"terminal: {record.terminal_id}",
            f"preferred_terminal: {record.preferred_terminal_id}",
            f"script: {record.script_name}",
            f"status: {record.status}",
            f"pending_family: {_task_pending_family(record.status)}",
            f"terminal_affinity: {record.terminal_affinity}",
            f"recovery_target_terminal_id: {record.recovery_target_terminal_id or '-'}",
            f"attempts: {record.attempt_count}/{record.retry_limit + 1}",
            f"retryable: {record.retryable}",
            f"final: {record.final}",
            f"error: {record.last_error_code or '-'}",
            f"wait_reason: {parameters.get('wait_reason') or '-'}",
            f"retry_kind: {record.retry_kind or '-'}",
            f"dispatch_mode: {parameters.get('dispatch_mode') or '-'}",
            f"dispatch_path: {_task_dispatch_path(record)}",
            f"queue_dispatch_status: {parameters.get('queue_dispatch_status') or '-'}",
            f"queue_dispatch_accepted: {_format_value(parameters.get('queue_dispatch_accepted'))}",
            f"queue_topic: {parameters.get('queue_topic') or '-'}",
            f"delivery_id: {parameters.get('delivery_id') or '-'}",
            f"claim_lease_id: {parameters.get('claim_lease_id') or '-'}",
            f"plugin_name: {parameters.get('plugin_name') or '-'}",
            f"account_id: {parameters.get('account_id') or '-'}",
            f"account_handle: {parameters.get('account_handle') or '-'}",
            f"ammo_target_id: {parameters.get('ammo_target_id') or '-'}",
            f"ammo_target_value: {parameters.get('ammo_target_value') or '-'}",
            f"creator_id: {parameters.get('creator_id') or '-'}",
            f"campaign_id: {parameters.get('campaign_id') or '-'}",
            f"blocked_by_instance_id: {parameters.get('blocked_by_instance_id') or '-'}",
            f"recovered_from_terminal_id: {parameters.get('recovered_from_terminal_id') or '-'}",
            f"recovery_claim_terminal_id: {parameters.get('recovery_claim_terminal_id') or '-'}",
            f"retry_available_at: {parameters.get('retry_available_at') or '-'}",
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


def render_creator_summary(record: CreatorInboxRecord) -> str:
    """Render one creator inbox row as a compact text block."""

    return "\n".join(
        [
            f"creator_inbox: {record.inbox_id}",
            f"creator_id: {record.creator_id}",
            f"handle: {record.handle or '-'}",
            f"source: {record.source}",
            f"plugin_name: {record.plugin_name or '-'}",
            f"terminal_id: {record.terminal_id or '-'}",
            f"profile_id: {record.profile_id or '-'}",
            f"status: {record.status}",
            f"received_at: {_format_value(record.received_at)}",
        ]
    )


def render_account_summary(record: AccountInventoryRecord) -> str:
    """Render one plugin account row as a compact text block."""

    return "\n".join(
        [
            f"account: {record.account_id}",
            f"profile_id: {record.profile_id}",
            f"handle: {record.handle or '-'}",
            f"terminal_id: {record.terminal_id or '-'}",
            f"plugin_name: {record.plugin_name or '-'}",
            f"status: {record.status}",
            f"capability_tags: {', '.join(record.capability_tags) if record.capability_tags else '-'}",
            f"last_used_at: {_format_value(record.last_used_at)}",
        ]
    )


def render_daily_stat_summary(record: DailyActionStatRecord) -> str:
    """Render one daily aggregate stat row as a compact text block."""

    return "\n".join(
        [
            f"stat: {record.stat_id}",
            f"date: {record.stat_date}",
            f"plugin_name: {record.plugin_name or '-'}",
            f"script_name: {record.script_name}",
            f"action_type: {record.action_type}",
            f"account_id: {record.account_id or '-'}",
            f"terminal_id: {record.terminal_id or '-'}",
            f"success_count: {record.success_count}",
            f"failure_count: {record.failure_count}",
            f"total_count: {record.total_count}",
            f"updated_at: {_format_value(record.updated_at)}",
        ]
    )


def render_campaign_summary(record: PluginCampaignRecord) -> str:
    """Render one plugin campaign row as a compact text block."""

    return "\n".join(
        [
            f"campaign: {record.campaign_id}",
            f"plugin_name: {record.plugin_name}",
            f"script_name: {record.script_name}",
            f"action_type: {record.action_type}",
            f"status: {record.status}",
            f"copy_items: {len(record.copy_items)}",
            f"updated_at: {_format_value(record.updated_at)}",
        ]
    )


def _format_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _format_slots(slots: object) -> str:
    if not isinstance(slots, list) or not slots:
        return "-"
    parts: list[str] = []
    for item in slots:
        if not isinstance(item, dict):
            continue
        slot_id = item.get("slot_id") or "slot"
        status = item.get("status") or "-"
        script_name = item.get("script_name") or "-"
        task_id = item.get("task_id") or "-"
        bound_instance_id = item.get("bound_instance_id") or "-"
        selection_reason = item.get("selection_reason") or "-"
        parts.append(
            f"{slot_id}:{status}:{script_name}:task={task_id}:instance={bound_instance_id}:reason={selection_reason}"
        )
    return " | ".join(parts) if parts else "-"


def _task_pending_family(status: str) -> str:
    if status in {"retry_pending", "manual_retry_pending", "terminal_recovery_pending"}:
        return status
    return "-"


def _task_dispatch_path(record: TaskRecord) -> str:
    parameters = record.parameters or {}
    dispatch_mode = str(parameters.get("dispatch_mode") or "claim_http")
    if dispatch_mode == "queue_pull":
        topic = parameters.get("queue_topic") or "-"
        return f"queue_pull:{topic}"
    return "claim_http:/tasks/claim"
