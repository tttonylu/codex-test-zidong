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
class TaskRecord:
    """Represents a task dispatched by the NAS."""

    task_id: str
    terminal_id: str
    script_name: str
    status: str
    instance_id: str | None = None
    priority: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


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
