"""Shared worker execution types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters.bitbrowser import BitBrowserClient


@dataclass(slots=True)
class WorkerContext:
    """Execution context passed into a worker."""

    task: TaskAssignmentPayload
    terminal_id: str
    hostname: str
    bitbrowser_client: BitBrowserClient | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkerOutcome:
    """Normalized worker execution result."""

    summary: str
    details: dict[str, Any] = field(default_factory=dict)
