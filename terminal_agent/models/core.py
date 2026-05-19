"""Runtime-facing models for the terminal agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.protocol import ScriptRunPayload, TaskAssignmentPayload


@dataclass(slots=True)
class TerminalState:
    """Represents the local terminal runtime state."""

    terminal_id: str
    hostname: str
    status: str
    agent_version: str
    active_instance_count: int = 0
    active_task_count: int = 0
    queued_task_count: int = 0
    last_heartbeat_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InstanceState:
    """Represents one local BitBrowser-backed instance."""

    instance_id: str
    profile_id: str
    runtime_status: str
    health_status: str = "unknown"
    handle: str | None = None
    window_id: str | None = None
    remark: str | None = None
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LocalTask:
    """Represents a task accepted by the terminal agent."""

    task_id: str
    script_name: str
    status: str
    instance_id: str | None = None
    priority: int = 0
    retry_limit: int = 0
    close_after_actions: bool = False
    requested_by: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ScriptSlot:
    """Represents one executable worker slot on the terminal."""

    slot_id: str
    status: str
    script_name: str | None = None
    bound_instance_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    assignment: TaskAssignmentPayload | None = None
    run: ScriptRunPayload | None = None
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
