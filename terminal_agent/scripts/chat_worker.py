"""Chat worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a chat task using the BitBrowser open API when available."""

    browser_id = context.task.instance_id
    if not browser_id:
        raise ValueError("chat task requires instance_id")

    if context.bitbrowser_client is None:
        raise ValueError("chat worker requires bitbrowser_client")

    target = str(context.task.parameters.get("target_handle", "unknown"))
    action_name = str(context.metadata.get("action_name") or "chat")
    if action_name == "icebreaker":
        target_url = f"https://x.com/messages/compose?recipient_id={target}&mode=icebreaker"
    elif action_name == "ad":
        target_url = f"https://x.com/messages/compose?recipient_id={target}&mode=ad"
    else:
        target_url = f"https://x.com/messages/compose?recipient_id={target}"
    response = context.bitbrowser_client.open_browser(
        browser_id=browser_id,
        args=[target_url],
        queue=True,
    )
    response_data = response.get("data", {})

    return WorkerOutcome(
        summary="chat executed",
        details={
            "action": action_name,
            "target_handle": target,
            "target_url": target_url,
            "instance_id": browser_id,
            "terminal_id": context.terminal_id,
            "browser_open_result": response_data,
        },
        step_count=1,
        steps=[
            {
                "name": "open_browser",
                "status": "completed",
                "action": action_name,
                "target_url": target_url,
            }
        ],
    )
