"""Minimal shared payload contracts for the first implementation phase."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TerminalRegistrationPayload:
    """Describes a terminal announcing itself to the NAS control plane."""

    terminal_id: str
    hostname: str
    operator_name: str
    agent_version: str
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        return asdict(self)


@dataclass(slots=True)
class HeartbeatPayload:
    """Periodic health and capacity report emitted by a terminal agent."""

    terminal_id: str
    reported_at: datetime
    status: str
    active_instance_count: int
    queued_task_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        data = asdict(self)
        data["reported_at"] = self.reported_at.isoformat()
        return data


@dataclass(slots=True)
class InstanceSnapshotPayload:
    """Terminal-side view of a managed BitBrowser instance."""

    terminal_id: str
    instance_id: str
    profile_id: str
    handle: str | None
    runtime_status: str
    window_id: str | None = None
    remark: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        return asdict(self)


@dataclass(slots=True)
class TaskAssignmentPayload:
    """Task assignment sent from NAS to a terminal."""

    task_id: str
    terminal_id: str
    instance_id: str | None
    script_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        return asdict(self)


@dataclass(slots=True)
class ScriptRunPayload:
    """Lifecycle snapshot for one script execution."""

    run_id: str
    task_id: str
    terminal_id: str
    instance_id: str | None
    script_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        data = asdict(self)
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        return data


@dataclass(slots=True)
class ActionResultPayload:
    """Result reported after a task or action finishes."""

    run_id: str
    task_id: str
    terminal_id: str
    status: str
    summary: str
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    final: bool | None = None
    details: dict[str, Any] = field(default_factory=dict)
    emitted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        data = asdict(self)
        data["emitted_at"] = self.emitted_at.isoformat()
        return data


@dataclass(slots=True)
class TaskControlPayload:
    """Control action applied to a task from the NAS side."""

    task_id: str
    action: str
    reason: str | None = None
    requested_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the payload."""

        return asdict(self)
