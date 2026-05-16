"""Probe worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import action_plan_from_parameters, execute_browser_action_plan
from terminal_agent.scripts.types import BrowserAction, WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a probe task using a structured browser action plan."""

    target_url = str(context.task.parameters.get("target_url", "https://x.com/home"))
    plan = action_plan_from_parameters(context.task.parameters)
    if plan is None:
        plan = [
            BrowserAction(
                name="navigate_probe_target",
                kind="navigate",
                params={"target_url": target_url, "queue": True},
            )
        ]
        if bool(context.task.parameters.get("annotate_remark", False)):
            plan.append(
                BrowserAction(
                    name="annotate_probe_target",
                    kind="annotate",
                    params={"remark": f"probe:{target_url}"},
                )
            )
    return execute_browser_action_plan(
        context,
        action="probe",
        summary="probe executed",
        plan=plan,
        target_details={"target_url": target_url},
    )
