"""Shared worker execution types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
class WorkerStepResult:
    """Represents one structured step inside a worker execution."""

    name: str
    status: str
    started_at: datetime
    finished_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrowserAction:
    """Represents one high-level browser action in a worker plan."""

    name: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)


class WorkerExecutionError(RuntimeError):
    """Structured worker failure with partial execution context."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        retryable: bool,
        details: dict[str, Any] | None = None,
        steps: list[WorkerStepResult] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.details = dict(details or {})
        self.steps = list(steps or [])


@dataclass(slots=True)
class WorkerOutcome:
    """Normalized worker execution result."""

    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    steps: list[WorkerStepResult] = field(default_factory=list)
