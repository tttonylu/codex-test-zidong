"""Follow worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a follow task using the BitBrowser open API when available."""

    browser_id = context.task.instance_id
    if not browser_id:
        raise ValueError("follow task requires instance_id")

    if context.bitbrowser_client is None:
        raise ValueError("follow worker requires bitbrowser_client")

    target = str(context.task.parameters.get("target_handle", "unknown"))
    target_url = f"https://x.com/{target}"
    response = context.bitbrowser_client.open_browser(
        browser_id=browser_id,
        args=[target_url],
        queue=True,
    )
    response_data = response.get("data", {})

    return WorkerOutcome(
        summary="follow executed",
        details={
            "action": "follow",
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
                "action": "follow",
                "target_url": target_url,
            }
        ],
    )
