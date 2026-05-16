"""Helpers for structured worker execution steps."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from terminal_agent.scripts.types import WorkerContext, WorkerExecutionError, WorkerOutcome, WorkerStepResult


def execute_browser_open_action(
    context: WorkerContext,
    *,
    action: str,
    summary: str,
    target_url: str,
    target_details: dict[str, Any] | None = None,
) -> WorkerOutcome:
    """Execute a browser-open based action with structured step tracking."""

    steps: list[WorkerStepResult] = []
    browser_id = _require_instance_id(context=context, action=action, steps=steps)
    client = _require_bitbrowser_client(context=context, action=action, steps=steps)

    steps.append(
        _completed_step(
            "prepare_target",
            {
                "action": action,
                "browser_id": browser_id,
                "target_url": target_url,
                **dict(target_details or {}),
            },
        )
    )

    try:
        response = client.open_browser_for_url(
            browser_id=browser_id,
            target_url=target_url,
            queue=True,
        )
    except RuntimeError as exc:
        steps.append(
            _failed_step(
                "open_browser",
                {
                    "action": action,
                    "browser_id": browser_id,
                    "target_url": target_url,
                    "error": str(exc),
                },
            )
        )
        raise WorkerExecutionError(
            f"{action} browser open failed",
            error_code=_classify_bitbrowser_error(exc),
            retryable=True,
            details={
                "action": action,
                "browser_id": browser_id,
                "target_url": target_url,
                **dict(target_details or {}),
            },
            steps=steps,
        ) from exc

    response_data = response.get("data", {})
    steps.append(
        _completed_step(
            "open_browser",
            {
                "action": action,
                "browser_id": browser_id,
                "target_url": target_url,
                "browser_open_result": response_data,
            },
        )
    )

    return WorkerOutcome(
        summary=summary,
        details={
            "action": action,
            "instance_id": browser_id,
            "terminal_id": context.terminal_id,
            "target_url": target_url,
            **dict(target_details or {}),
            "browser_open_result": response_data,
        },
        steps=steps,
    )


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
    if "open failed" in message:
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
