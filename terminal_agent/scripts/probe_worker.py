"""Probe worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a probe task using the BitBrowser open API when available."""

    browser_id = context.task.instance_id
    if not browser_id:
        raise ValueError("probe task requires instance_id")

    if context.bitbrowser_client is None:
        raise ValueError("probe worker requires bitbrowser_client")

    target_url = str(context.task.parameters.get("target_url", "https://x.com/home"))
    response = context.bitbrowser_client.open_browser(
        browser_id=browser_id,
        args=[target_url],
        queue=True,
    )
    response_data = response.get("data", {})

    return WorkerOutcome(
        summary="probe executed",
        details={
            "action": "probe",
            "instance_id": browser_id,
            "target_url": target_url,
            "terminal_id": context.terminal_id,
            "browser_open_result": response_data,
        },
    )
