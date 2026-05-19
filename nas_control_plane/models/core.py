"""Minimal persistence-facing models for the NAS control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TerminalRecord:
    """Represents one registered terminal machine."""

    terminal_id: str
    hostname: str
    operator_name: str
    status: str
    agent_version: str
    last_seen_at: datetime | None = None
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InstanceRecord:
    """Represents one managed instance known by the NAS."""

    instance_id: str
    terminal_id: str
    profile_id: str
    handle: str | None
    runtime_status: str
    window_id: str | None = None
    remark: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginAutoDispatchRecord:
    """Represents one active auto-dispatch rule for plugin runtime pull."""

    rule_id: str
    account_id: str
    plugin_name: str
    script_name: str
    action_plan: list[dict[str, Any]] = field(default_factory=list)
    campaign_id: str | None = None
    terminal_id: str | None = None
    instance_id: str | None = None
    target_type: str = "handle"
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class TaskRecord:
    """Represents a task dispatched by the NAS."""

    task_id: str
    terminal_id: str
    preferred_terminal_id: str
    script_name: str
    status: str
    instance_id: str | None = None
    terminal_affinity: str = "required"
    recovery_target_terminal_id: str | None = None
    priority: int = 0
    retry_limit: int = 0
    close_after_actions: bool = False
    requested_by: str | None = None
    retry_kind: str | None = None
    attempt_count: int = 0
    retryable: bool = False
    final: bool = False
    last_error_code: str | None = None
    last_error_message: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class QueueDeliveryRecord:
    """Represents one persisted queue-backed delivery tracked by the NAS."""

    delivery_id: str
    task_id: str
    terminal_id: str
    queue_topic: str | None
    status: str
    claim_lease_id: str | None = None
    claimed_by_terminal_id: str | None = None
    available_at: datetime | None = None
    claim_expires_at: datetime | None = None
    attempt_count: int = 0
    last_error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class CreatorInboxRecord:
    """Represents one creator/blogger identifier reported by plugin scripts."""

    inbox_id: str
    creator_id: str
    handle: str | None
    source: str
    terminal_id: str | None = None
    profile_id: str | None = None
    plugin_name: str | None = None
    dedupe_key: str | None = None
    status: str = "received"
    raw_payload: dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class AmmoTargetRecord:
    """Represents one distributable target item for follow/chat style plugin work."""

    target_id: str
    target_value: str
    target_type: str
    source: str
    status: str = "available"
    creator_id: str | None = None
    assigned_account_id: str | None = None
    assigned_terminal_id: str | None = None
    assigned_task_id: str | None = None
    consumed_at: datetime | None = None
    assigned_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class AccountInventoryRecord:
    """Represents one account available to plugin scripts for work assignment."""

    account_id: str
    profile_id: str
    handle: str | None
    terminal_id: str | None
    plugin_name: str | None
    status: str = "available"
    capability_tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class DailyActionStatRecord:
    """Represents one daily aggregated plugin action metric row."""

    stat_id: str
    stat_date: str
    account_id: str | None
    terminal_id: str | None
    plugin_name: str | None
    script_name: str
    action_type: str
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class PluginCampaignRecord:
    """Represents one plugin-facing campaign/copy bundle."""

    campaign_id: str
    plugin_name: str
    script_name: str
    action_type: str
    status: str = "active"
    copy_items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ScriptRunRecord:
    """Represents one execution attempt for a dispatched task."""

    run_id: str
    task_id: str
    terminal_id: str
    script_name: str
    status: str
    instance_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionLogRecord:
    """Represents an audit log entry stored on the NAS side."""

    log_id: str
    terminal_id: str
    level: str
    message: str
    emitted_at: datetime = field(default_factory=datetime.utcnow)
    task_id: str | None = None
    run_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BlacklistRecord:
    """Represents one blocked target that all accounts should skip."""

    target_id: str
    target_value: str
    target_type: str = "handle"
    reason: str | None = None
    source: str = "manual"
    created_at: datetime = field(default_factory=datetime.utcnow)
