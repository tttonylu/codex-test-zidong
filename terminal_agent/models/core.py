"""Minimal runtime-facing models for the terminal agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TerminalState:
    """Represents the local terminal runtime state."""

    terminal_id: str
    hostname: str
    status: str
    agent_version: str
    active_instance_count: int = 0
    queued_task_count: int = 0
    last_heartbeat_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InstanceState:
    """Represents one local BitBrowser-backed instance."""

    instance_id: str
    profile_id: str
    runtime_status: str
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
    parameters: dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ScriptSlot:
    """Represents one executable slot or worker assignment on the terminal."""

    slot_id: str
    script_name: str
    status: str
    bound_instance_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
