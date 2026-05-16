"""Helpers for structured worker execution steps."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from terminal_agent.scripts.types import BrowserAction, WorkerContext, WorkerExecutionError, WorkerOutcome, WorkerStepResult


def execute_browser_action_plan(
    context: WorkerContext,
    *,
    action: str,
    summary: str,
    plan: list[BrowserAction],
    target_details: dict[str, Any] | None = None,
) -> WorkerOutcome:
    """Execute a high-level browser action plan with structured step tracking."""

    steps: list[WorkerStepResult] = []
    browser_id = _require_instance_id(context=context, action=action, steps=steps)
    client = _require_bitbrowser_client(context=context, action=action, steps=steps)

    steps.append(
        _completed_step(
            "prepare_target",
            {
                "action": action,
                "browser_id": browser_id,
                "plan": [item.name for item in plan],
                **dict(target_details or {}),
            },
        )
    )

    action_results: list[dict[str, Any]] = []
    for item in plan:
        try:
            response = client.execute_action(browser_id=browser_id, action=item.kind, **item.params)
        except RuntimeError as exc:
            steps.append(
                _failed_step(
                    item.name,
                    {
                        "action": action,
                        "browser_id": browser_id,
                        "browser_action": item.kind,
                        **dict(item.params),
                        "error": str(exc),
                    },
                )
            )
            raise WorkerExecutionError(
                f"{action} action failed at step: {item.name}",
                error_code=_classify_bitbrowser_error(exc),
                retryable=True,
                details={
                    "action": action,
                    "browser_id": browser_id,
                    "failed_step": item.name,
                    "failed_action": item.kind,
                    **dict(target_details or {}),
                },
                steps=steps,
            ) from exc
        except ValueError as exc:
            steps.append(
                _failed_step(
                    item.name,
                    {
                        "action": action,
                        "browser_id": browser_id,
                        "browser_action": item.kind,
                        **dict(item.params),
                        "error": str(exc),
                    },
                )
            )
            raise WorkerExecutionError(
                f"{action} action plan invalid at step: {item.name}",
                error_code="worker.invalid_browser_action",
                retryable=False,
                details={
                    "action": action,
                    "browser_id": browser_id,
                    "failed_step": item.name,
                    "failed_action": item.kind,
                    **dict(target_details or {}),
                },
                steps=steps,
            ) from exc

        response_data = response.get("data", {})
        action_results.append(
            {
                "name": item.name,
                "kind": item.kind,
                "params": dict(item.params),
                "result": response_data,
            }
        )
        steps.append(
            _completed_step(
                item.name,
                {
                    "action": action,
                    "browser_id": browser_id,
                    "browser_action": item.kind,
                    **dict(item.params),
                    "result": response_data,
                },
            )
        )

    return WorkerOutcome(
        summary=summary,
        details={
            "action": action,
            "instance_id": browser_id,
            "terminal_id": context.terminal_id,
            **dict(target_details or {}),
            "browser_action_results": action_results,
        },
        steps=steps,
    )


def execute_browser_open_action(
    context: WorkerContext,
    *,
    action: str,
    summary: str,
    target_url: str,
    target_details: dict[str, Any] | None = None,
) -> WorkerOutcome:
    """Execute a single-step browser navigation action."""

    return execute_browser_action_plan(
        context,
        action=action,
        summary=summary,
        plan=[
            BrowserAction(
                name="open_browser",
                kind="navigate",
                params={"target_url": target_url, "queue": True},
            )
        ],
        target_details={
            "target_url": target_url,
            **dict(target_details or {}),
        },
    )


def action_plan_from_parameters(parameters: dict[str, Any]) -> list[BrowserAction] | None:
    """Parse an explicit browser action plan from task parameters."""

    raw_plan = parameters.get("action_plan")
    if raw_plan is None:
        return None
    if not isinstance(raw_plan, list):
        raise WorkerExecutionError(
            "action_plan must be a list",
            error_code="worker.invalid_action_plan",
            retryable=False,
            details={"action_plan_type": type(raw_plan).__name__},
            steps=[],
        )

    plan: list[BrowserAction] = []
    for index, item in enumerate(raw_plan, start=1):
        if not isinstance(item, dict):
            raise WorkerExecutionError(
                "action_plan items must be objects",
                error_code="worker.invalid_action_plan",
                retryable=False,
                details={"item_index": index, "item_type": type(item).__name__},
                steps=[],
            )
        kind = item.get("kind")
        if not isinstance(kind, str) or not kind:
            raise WorkerExecutionError(
                "action_plan item missing kind",
                error_code="worker.invalid_action_plan",
                retryable=False,
                details={"item_index": index},
                steps=[],
            )
        name = item.get("name")
        if not isinstance(name, str) or not name:
            name = f"{kind}_{index}"
        params = item.get("params", {})
        if not isinstance(params, dict):
            raise WorkerExecutionError(
                "action_plan item params must be an object",
                error_code="worker.invalid_action_plan",
                retryable=False,
                details={"item_index": index, "params_type": type(params).__name__},
                steps=[],
            )
        plan.append(BrowserAction(name=name, kind=kind, params=dict(params)))
    return plan


def build_local_outcome(
    *,
    action: str,
    summary: str,
    terminal_id: str,
    instance_id: str | None,
    details: dict[str, Any] | None = None,
    step_name: str = "complete_local_action",
) -> WorkerOutcome:
    """Build a structured non-browser worker outcome."""

    step_details = {
        "action": action,
        "terminal_id": terminal_id,
        "instance_id": instance_id,
        **dict(details or {}),
    }
    return WorkerOutcome(
        summary=summary,
        details=step_details,
        steps=[_completed_step(step_name, step_details)],
    )


def _require_instance_id(
    *,
    context: WorkerContext,
    action: str,
    steps: list[WorkerStepResult],
) -> str:
    browser_id = context.task.instance_id
    if browser_id:
        steps.append(_completed_step("validate_instance_id", {"action": action, "browser_id": browser_id}))
        return browser_id

    steps.append(_failed_step("validate_instance_id", {"action": action}))
    raise WorkerExecutionError(
        f"{action} task requires instance_id",
        error_code="worker.missing_instance_id",
        retryable=False,
        details={"action": action},
        steps=steps,
    )


def _require_bitbrowser_client(
    *,
    context: WorkerContext,
    action: str,
    steps: list[WorkerStepResult],
):
    client = context.bitbrowser_client
    if client is not None:
        steps.append(_completed_step("validate_bitbrowser_client", {"action": action}))
        return client

    steps.append(_failed_step("validate_bitbrowser_client", {"action": action}))
    raise WorkerExecutionError(
        f"{action} worker requires bitbrowser_client",
        error_code="worker.missing_bitbrowser_client",
        retryable=False,
        details={"action": action},
        steps=steps,
    )


def _classify_bitbrowser_error(exc: RuntimeError) -> str:
    message = str(exc).lower()
    if "open failed" in message or "remark update failed" in message or "close failed" in message:
        return "bitbrowser.open_failed"
    return "bitbrowser.request_failed"


def _completed_step(name: str, details: dict[str, Any]) -> WorkerStepResult:
    now = datetime.utcnow()
    return WorkerStepResult(
        name=name,
        status="completed",
        started_at=now,
        finished_at=now,
        details=dict(details),
    )


def _failed_step(name: str, details: dict[str, Any]) -> WorkerStepResult:
    now = datetime.utcnow()
    return WorkerStepResult(
        name=name,
        status="failed",
        started_at=now,
        finished_at=now,
        details=dict(details),
    )
