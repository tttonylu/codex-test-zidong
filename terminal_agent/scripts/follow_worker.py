"""Follow worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import execute_browser_open_action
from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a follow task using a structured browser-open action."""

    target = str(context.task.parameters.get("target_handle", "unknown"))
    target_url = f"https://x.com/{target}"
    return execute_browser_open_action(
        context,
        action="follow",
        summary="follow executed",
        target_url=target_url,
        target_details={"target_handle": target},
    )
