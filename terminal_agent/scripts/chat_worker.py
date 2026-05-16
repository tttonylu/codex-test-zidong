"""Chat worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import execute_browser_open_action
from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a chat task using a structured browser-open action."""

    target = str(context.task.parameters.get("target_handle", "unknown"))
    target_url = f"https://x.com/messages/compose?recipient_id={target}"
    return execute_browser_open_action(
        context,
        action="chat",
        summary="chat executed",
        target_url=target_url,
        target_details={"target_handle": target},
    )
