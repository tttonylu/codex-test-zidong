"""Follow worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import action_plan_from_parameters, execute_browser_action_plan
from terminal_agent.scripts.types import BrowserAction, WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a follow task using a structured browser action plan."""

    target = str(context.task.parameters.get("target_handle", "unknown"))
    target_url = f"https://x.com/{target}"
    plan = action_plan_from_parameters(context.task.parameters)
    if plan is None:
        plan = [
            BrowserAction(
                name="navigate_profile",
                kind="navigate",
                params={"target_url": target_url, "queue": True},
            )
        ]
        if bool(context.task.parameters.get("annotate_remark", False)):
            plan.append(
                BrowserAction(
                    name="annotate_follow_target",
                    kind="annotate",
                    params={"remark": f"follow:{target}"},
                )
            )
    return execute_browser_action_plan(
        context,
        action="follow",
        summary="follow executed",
        plan=plan,
        target_details={"target_handle": target, "target_url": target_url},
    )
