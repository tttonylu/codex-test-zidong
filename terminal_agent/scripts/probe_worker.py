"""Probe worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import execute_browser_open_action
from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a probe task using a structured browser-open action."""

    target_url = str(context.task.parameters.get("target_url", "https://x.com/home"))
    return execute_browser_open_action(
        context,
        action="probe",
        summary="probe executed",
        target_url=target_url,
    )
