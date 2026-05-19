"""Repository layer for NAS state sections."""

from __future__ import annotations

from datetime import datetime

from nas_control_plane.models import (
    AccountInventoryRecord,
    ActionLogRecord,
    AmmoTargetRecord,
    BlacklistRecord,
    CreatorInboxRecord,
    DailyActionStatRecord,
    InstanceRecord,
    PluginAutoDispatchRecord,
    PluginCampaignRecord,
    QueueDeliveryRecord,
    TaskRecord,
    TerminalRecord,
)
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


class QueueDeliveryRepository:
    """Reads and writes queue delivery state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_deliveries(self) -> dict[str, QueueDeliveryRecord]:
        return {
            delivery_id: _queue_delivery_from_dict(item)
            for delivery_id, item in self._store.read_section("queue_deliveries").items()
        }

    def save_deliveries(self, records: dict[str, QueueDeliveryRecord]) -> None:
        self._store.write_section(
            "queue_deliveries",
            {delivery_id: _queue_delivery_to_dict(item) for delivery_id, item in records.items()},
        )


class CreatorInboxRepository:
    """Reads and writes creator inbox state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_items(self) -> dict[str, CreatorInboxRecord]:
        return {
            inbox_id: _creator_inbox_from_dict(item)
            for inbox_id, item in self._store.read_section("creator_inbox").items()
        }

    def save_items(self, records: dict[str, CreatorInboxRecord]) -> None:
        self._store.write_section(
            "creator_inbox",
            {inbox_id: _creator_inbox_to_dict(item) for inbox_id, item in records.items()},
        )


class AmmoTargetRepository:
    """Reads and writes ammo target state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_targets(self) -> dict[str, AmmoTargetRecord]:
        return {
            target_id: _ammo_target_from_dict(item)
            for target_id, item in self._store.read_section("ammo_targets").items()
        }

    def save_targets(self, records: dict[str, AmmoTargetRecord]) -> None:
        self._store.write_section(
            "ammo_targets",
            {target_id: _ammo_target_to_dict(item) for target_id, item in records.items()},
        )


class AccountInventoryRepository:
    """Reads and writes account inventory state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_accounts(self) -> dict[str, AccountInventoryRecord]:
        return {
            account_id: _account_inventory_from_dict(item)
            for account_id, item in self._store.read_section("account_inventory").items()
        }

    def save_accounts(self, records: dict[str, AccountInventoryRecord]) -> None:
        self._store.write_section(
            "account_inventory",
            {account_id: _account_inventory_to_dict(item) for account_id, item in records.items()},
        )


class DailyActionStatRepository:
    """Reads and writes daily aggregated action stats."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_stats(self) -> dict[str, DailyActionStatRecord]:
        return {
            stat_id: _daily_action_stat_from_dict(item)
            for stat_id, item in self._store.read_section("daily_action_stats").items()
        }

    def save_stats(self, records: dict[str, DailyActionStatRecord]) -> None:
        self._store.write_section(
            "daily_action_stats",
            {stat_id: _daily_action_stat_to_dict(item) for stat_id, item in records.items()},
        )


class PluginCampaignRepository:
    """Reads and writes plugin campaign/copy bundle state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_campaigns(self) -> dict[str, PluginCampaignRecord]:
        return {
            campaign_id: _plugin_campaign_from_dict(item)
            for campaign_id, item in self._store.read_section("plugin_campaigns").items()
        }

    def save_campaigns(self, records: dict[str, PluginCampaignRecord]) -> None:
        self._store.write_section(
            "plugin_campaigns",
            {campaign_id: _plugin_campaign_to_dict(item) for campaign_id, item in records.items()},
        )


class PluginAutoDispatchRepository:
    """Reads and writes plugin auto-dispatch rules."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_rules(self) -> dict[str, PluginAutoDispatchRecord]:
        return {
            rule_id: _plugin_auto_dispatch_from_dict(item)
            for rule_id, item in self._store.read_section("plugin_auto_dispatch_rules").items()
        }

    def save_rules(self, records: dict[str, PluginAutoDispatchRecord]) -> None:
        self._store.write_section(
            "plugin_auto_dispatch_rules",
            {rule_id: _plugin_auto_dispatch_to_dict(item) for rule_id, item in records.items()},
        )


class BlacklistRepository:
    """Reads and writes the global blacklist."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_all(self) -> dict[str, BlacklistRecord]:
        return {
            item_id: _blacklist_from_dict(item)
            for item_id, item in self._store.read_section("blacklist").items()
        }

    def save_all(self, records: dict[str, BlacklistRecord]) -> None:
        self._store.write_section(
            "blacklist",
            {item_id: _blacklist_to_dict(item) for item_id, item in records.items()},
        )

    def add(self, record: BlacklistRecord) -> BlacklistRecord:
        data = dict(self._store.read_section("blacklist"))
        data[record.target_id] = _blacklist_to_dict(record)
        self._store.write_section("blacklist", data)
        return record

    def remove(self, target_id: str) -> None:
        data = dict(self._store.read_section("blacklist"))
        data.pop(target_id, None)
        self._store.write_section("blacklist", data)

    def exists(self, target_value: str) -> bool:
        data = self._store.read_section("blacklist")
        return any(
            item.get("target_value") == target_value
            for item in data.values()
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
        "preferred_terminal_id": record.preferred_terminal_id,
        "script_name": record.script_name,
        "status": record.status,
        "instance_id": record.instance_id,
        "terminal_affinity": record.terminal_affinity,
        "recovery_target_terminal_id": record.recovery_target_terminal_id,
        "priority": record.priority,
        "retry_limit": record.retry_limit,
        "close_after_actions": record.close_after_actions,
        "requested_by": record.requested_by,
        "retry_kind": record.retry_kind,
        "attempt_count": record.attempt_count,
        "retryable": record.retryable,
        "final": record.final,
        "last_error_code": record.last_error_code,
        "last_error_message": record.last_error_message,
        "parameters": dict(record.parameters),
        "created_at": record.created_at.isoformat(),
    }


def _task_from_dict(payload: dict[str, object]) -> TaskRecord:
    parameters = dict(payload.get("parameters", {}))
    retry_kind = payload.get("retry_kind")
    if retry_kind is None:
        retry_kind = parameters.get("retry_kind")
    return TaskRecord(
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        preferred_terminal_id=str(payload.get("preferred_terminal_id") or payload["terminal_id"]),
        script_name=str(payload["script_name"]),
        status=str(payload["status"]),
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        terminal_affinity=str(payload.get("terminal_affinity", "required") or "required"),
        recovery_target_terminal_id=(
            str(payload["recovery_target_terminal_id"])
            if payload.get("recovery_target_terminal_id") is not None
            else None
        ),
        priority=int(payload.get("priority", 0)),
        retry_limit=int(payload.get("retry_limit", 0)),
        close_after_actions=bool(payload.get("close_after_actions", False)),
        requested_by=str(payload["requested_by"]) if payload.get("requested_by") is not None else None,
        retry_kind=str(retry_kind) if retry_kind is not None else None,
        attempt_count=int(payload.get("attempt_count", 0)),
        retryable=bool(payload.get("retryable", False)),
        final=bool(payload.get("final", False)),
        last_error_code=str(payload["last_error_code"]) if payload.get("last_error_code") is not None else None,
        last_error_message=str(payload["last_error_message"]) if payload.get("last_error_message") is not None else None,
        parameters=parameters,
        created_at=datetime.fromisoformat(str(payload["created_at"])),
    )


def _queue_delivery_to_dict(record: QueueDeliveryRecord) -> dict[str, object]:
    return {
        "delivery_id": record.delivery_id,
        "task_id": record.task_id,
        "terminal_id": record.terminal_id,
        "queue_topic": record.queue_topic,
        "status": record.status,
        "claim_lease_id": record.claim_lease_id,
        "claimed_by_terminal_id": record.claimed_by_terminal_id,
        "available_at": record.available_at.isoformat() if record.available_at else None,
        "claim_expires_at": record.claim_expires_at.isoformat() if record.claim_expires_at else None,
        "attempt_count": record.attempt_count,
        "last_error": record.last_error,
        "details": dict(record.details),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _queue_delivery_from_dict(payload: dict[str, object]) -> QueueDeliveryRecord:
    available_at = payload.get("available_at")
    claim_expires_at = payload.get("claim_expires_at")
    return QueueDeliveryRecord(
        delivery_id=str(payload["delivery_id"]),
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        queue_topic=str(payload["queue_topic"]) if payload.get("queue_topic") is not None else None,
        status=str(payload["status"]),
        claim_lease_id=str(payload["claim_lease_id"]) if payload.get("claim_lease_id") is not None else None,
        claimed_by_terminal_id=(
            str(payload["claimed_by_terminal_id"]) if payload.get("claimed_by_terminal_id") is not None else None
        ),
        available_at=datetime.fromisoformat(str(available_at)) if available_at else None,
        claim_expires_at=datetime.fromisoformat(str(claim_expires_at)) if claim_expires_at else None,
        attempt_count=int(payload.get("attempt_count", 0)),
        last_error=str(payload["last_error"]) if payload.get("last_error") is not None else None,
        details=dict(payload.get("details", {})),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _creator_inbox_to_dict(record: CreatorInboxRecord) -> dict[str, object]:
    return {
        "inbox_id": record.inbox_id,
        "creator_id": record.creator_id,
        "handle": record.handle,
        "source": record.source,
        "terminal_id": record.terminal_id,
        "profile_id": record.profile_id,
        "plugin_name": record.plugin_name,
        "dedupe_key": record.dedupe_key,
        "status": record.status,
        "raw_payload": dict(record.raw_payload),
        "received_at": record.received_at.isoformat(),
    }


def _creator_inbox_from_dict(payload: dict[str, object]) -> CreatorInboxRecord:
    return CreatorInboxRecord(
        inbox_id=str(payload["inbox_id"]),
        creator_id=str(payload["creator_id"]),
        handle=str(payload["handle"]) if payload.get("handle") is not None else None,
        source=str(payload["source"]),
        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
        profile_id=str(payload["profile_id"]) if payload.get("profile_id") is not None else None,
        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
        dedupe_key=str(payload["dedupe_key"]) if payload.get("dedupe_key") is not None else None,
        status=str(payload.get("status", "received")),
        raw_payload=dict(payload.get("raw_payload", {})),
        received_at=datetime.fromisoformat(str(payload["received_at"])),
    )


def _ammo_target_to_dict(record: AmmoTargetRecord) -> dict[str, object]:
    return {
        "target_id": record.target_id,
        "target_value": record.target_value,
        "target_type": record.target_type,
        "source": record.source,
        "status": record.status,
        "creator_id": record.creator_id,
        "assigned_account_id": record.assigned_account_id,
        "assigned_terminal_id": record.assigned_terminal_id,
        "assigned_task_id": record.assigned_task_id,
        "consumed_at": record.consumed_at.isoformat() if record.consumed_at else None,
        "assigned_at": record.assigned_at.isoformat() if record.assigned_at else None,
        "metadata": dict(record.metadata),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _ammo_target_from_dict(payload: dict[str, object]) -> AmmoTargetRecord:
    consumed_at = payload.get("consumed_at")
    assigned_at = payload.get("assigned_at")
    return AmmoTargetRecord(
        target_id=str(payload["target_id"]),
        target_value=str(payload["target_value"]),
        target_type=str(payload["target_type"]),
        source=str(payload["source"]),
        status=str(payload.get("status", "available")),
        creator_id=str(payload["creator_id"]) if payload.get("creator_id") is not None else None,
        assigned_account_id=(
            str(payload["assigned_account_id"]) if payload.get("assigned_account_id") is not None else None
        ),
        assigned_terminal_id=(
            str(payload["assigned_terminal_id"]) if payload.get("assigned_terminal_id") is not None else None
        ),
        assigned_task_id=str(payload["assigned_task_id"]) if payload.get("assigned_task_id") is not None else None,
        consumed_at=datetime.fromisoformat(str(consumed_at)) if consumed_at else None,
        assigned_at=datetime.fromisoformat(str(assigned_at)) if assigned_at else None,
        metadata=dict(payload.get("metadata", {})),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _account_inventory_to_dict(record: AccountInventoryRecord) -> dict[str, object]:
    return {
        "account_id": record.account_id,
        "profile_id": record.profile_id,
        "handle": record.handle,
        "terminal_id": record.terminal_id,
        "plugin_name": record.plugin_name,
        "status": record.status,
        "capability_tags": list(record.capability_tags),
        "metadata": dict(record.metadata),
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _account_inventory_from_dict(payload: dict[str, object]) -> AccountInventoryRecord:
    last_used_at = payload.get("last_used_at")
    return AccountInventoryRecord(
        account_id=str(payload["account_id"]),
        profile_id=str(payload["profile_id"]),
        handle=str(payload["handle"]) if payload.get("handle") is not None else None,
        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
        status=str(payload.get("status", "available")),
        capability_tags=list(payload.get("capability_tags", [])),
        metadata=dict(payload.get("metadata", {})),
        last_used_at=datetime.fromisoformat(str(last_used_at)) if last_used_at else None,
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _daily_action_stat_to_dict(record: DailyActionStatRecord) -> dict[str, object]:
    return {
        "stat_id": record.stat_id,
        "stat_date": record.stat_date,
        "account_id": record.account_id,
        "terminal_id": record.terminal_id,
        "plugin_name": record.plugin_name,
        "script_name": record.script_name,
        "action_type": record.action_type,
        "success_count": record.success_count,
        "failure_count": record.failure_count,
        "total_count": record.total_count,
        "metadata": dict(record.metadata),
        "updated_at": record.updated_at.isoformat(),
    }


def _daily_action_stat_from_dict(payload: dict[str, object]) -> DailyActionStatRecord:
    return DailyActionStatRecord(
        stat_id=str(payload["stat_id"]),
        stat_date=str(payload["stat_date"]),
        account_id=str(payload["account_id"]) if payload.get("account_id") is not None else None,
        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
        script_name=str(payload["script_name"]),
        action_type=str(payload["action_type"]),
        success_count=int(payload.get("success_count", 0)),
        failure_count=int(payload.get("failure_count", 0)),
        total_count=int(payload.get("total_count", 0)),
        metadata=dict(payload.get("metadata", {})),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _plugin_campaign_to_dict(record: PluginCampaignRecord) -> dict[str, object]:
    return {
        "campaign_id": record.campaign_id,
        "plugin_name": record.plugin_name,
        "script_name": record.script_name,
        "action_type": record.action_type,
        "status": record.status,
        "copy_items": list(record.copy_items),
        "metadata": dict(record.metadata),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _plugin_campaign_from_dict(payload: dict[str, object]) -> PluginCampaignRecord:
    return PluginCampaignRecord(
        campaign_id=str(payload["campaign_id"]),
        plugin_name=str(payload["plugin_name"]),
        script_name=str(payload["script_name"]),
        action_type=str(payload["action_type"]),
        status=str(payload.get("status", "active")),
        copy_items=list(payload.get("copy_items", [])),
        metadata=dict(payload.get("metadata", {})),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


def _plugin_auto_dispatch_to_dict(record: PluginAutoDispatchRecord) -> dict[str, object]:
    return {
        "rule_id": record.rule_id,
        "account_id": record.account_id,
        "plugin_name": record.plugin_name,
        "script_name": record.script_name,
        "action_plan": list(record.action_plan),
        "campaign_id": record.campaign_id,
        "terminal_id": record.terminal_id,
        "instance_id": record.instance_id,
        "target_type": record.target_type,
        "status": record.status,
        "metadata": dict(record.metadata),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _plugin_auto_dispatch_from_dict(payload: dict[str, object]) -> PluginAutoDispatchRecord:
    return PluginAutoDispatchRecord(
        rule_id=str(payload["rule_id"]),
        account_id=str(payload["account_id"]),
        plugin_name=str(payload["plugin_name"]),
        script_name=str(payload["script_name"]),
        action_plan=list(payload.get("action_plan", [])),
        campaign_id=str(payload["campaign_id"]) if payload.get("campaign_id") is not None else None,
        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        target_type=str(payload.get("target_type", "handle")),
        status=str(payload.get("status", "active")),
        metadata=dict(payload.get("metadata", {})),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )


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


def _blacklist_to_dict(record: BlacklistRecord) -> dict[str, object]:
    return {
        "target_id": record.target_id,
        "target_value": record.target_value,
        "target_type": record.target_type,
        "reason": record.reason,
        "source": record.source,
        "created_at": record.created_at.isoformat(),
    }


def _blacklist_from_dict(payload: dict[str, object]) -> BlacklistRecord:
    return BlacklistRecord(
        target_id=str(payload["target_id"]),
        target_value=str(payload["target_value"]),
        target_type=str(payload.get("target_type", "handle")),
        reason=str(payload["reason"]) if payload.get("reason") is not None else None,
        source=str(payload.get("source", "manual")),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
    )
