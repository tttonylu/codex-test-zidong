"""Minimal script worker registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload
from terminal_agent.scripts import chat_worker, extract_worker, follow_worker, probe_worker
from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


@dataclass(slots=True)
class WorkerExecution:
    """Represents one worker execution with start and finish payloads."""

    context: WorkerContext
    run: ScriptRunPayload
    result: ActionResultPayload | None = None


class ScriptWorkerRegistry:
    """Dispatches tasks to simple in-process workers by script name."""

    def __init__(self) -> None:
        self._workers: dict[str, Callable[[WorkerContext], WorkerOutcome]] = {
            "follow": follow_worker.execute,
            "chat": chat_worker.execute,
            "probe": probe_worker.execute,
            "extract": extract_worker.execute,
        }

    def prepare_execution(
        self,
        task: TaskAssignmentPayload,
        *,
        terminal_hostname: str = "unknown",
        bitbrowser_client: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerExecution:
        """Build the running payload and execution context before the worker runs."""

        started_at = datetime.utcnow()
        run = ScriptRunPayload(
            run_id=f"run-{task.task_id}",
            task_id=task.task_id,
            terminal_id=task.terminal_id,
            instance_id=task.instance_id,
            script_name=task.script_name,
            status="running",
            started_at=started_at,
            metadata={"worker": task.script_name},
        )
        context = WorkerContext(
            task=task,
            terminal_id=task.terminal_id,
            hostname=terminal_hostname,
            bitbrowser_client=bitbrowser_client,
            metadata=dict(metadata or {}),
        )
        return WorkerExecution(context=context, run=run)

    def finish_execution(self, execution: WorkerExecution) -> WorkerExecution:
        """Run the worker and attach the final result payload."""

        task = execution.context.task

        try:
            outcome = self._dispatch(execution.context)
            if (
                task.close_after_actions
                and task.instance_id
                and execution.context.bitbrowser_client is not None
            ):
                outcome = self._append_close_step(
                    outcome,
                    execution.context.bitbrowser_client.close_browser(task.instance_id),
                )
            result = ActionResultPayload(
                run_id=execution.run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="completed",
                summary=outcome.summary,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                retryable=outcome.retryable if outcome.retryable is not None else False,
                final=outcome.final if outcome.final is not None else True,
                details={
                    **outcome.details,
                    "step_count": outcome.step_count,
                    "steps": list(outcome.steps),
                },
                emitted_at=datetime.utcnow(),
            )
        except Exception as exc:
            error_code = _classify_worker_failure(task.script_name, exc)
            retryable = error_code in {"bitbrowser.request_failed", "bitbrowser.open_failed"}
            result = ActionResultPayload(
                run_id=execution.run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="failed",
                summary=f"{task.script_name} failed",
                error_code=error_code,
                error_message=str(exc),
                retryable=retryable,
                final=not retryable,
                details={
                    "error": str(exc),
                    "instance_id": task.instance_id,
                    "parameters": dict(task.parameters),
                    "step_count": 0,
                },
                emitted_at=datetime.utcnow(),
            )

        execution.result = result
        return execution

    def execute(
        self,
        task: TaskAssignmentPayload,
        *,
        terminal_hostname: str = "unknown",
        bitbrowser_client: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerExecution:
        """Execute one task and build the corresponding lifecycle payloads."""

        execution = self.prepare_execution(
            task,
            terminal_hostname=terminal_hostname,
            bitbrowser_client=bitbrowser_client,
            metadata=metadata,
        )
        return self.finish_execution(execution)

    def _dispatch(self, context: WorkerContext) -> WorkerOutcome:
        try:
            worker = self._workers[context.task.script_name]
        except KeyError as exc:
            raise ValueError(f"unsupported script: {context.task.script_name}") from exc
        return worker(context)

    def _append_close_step(self, outcome: WorkerOutcome, close_result: Any) -> WorkerOutcome:
        steps = list(outcome.steps)
        steps.append(
            {
                "name": "close_browser",
                "status": "completed",
                "action": "close",
                "result": close_result.get("data", {}),
            }
        )
        return WorkerOutcome(
            summary=outcome.summary,
            details={**outcome.details, "close_browser_result": close_result.get("data", {})},
            error_code=outcome.error_code,
            error_message=outcome.error_message,
            retryable=outcome.retryable,
            final=outcome.final,
            step_count=outcome.step_count + 1,
            steps=steps,
        )


def _classify_worker_failure(script_name: str, exc: Exception) -> str:
    message = str(exc).lower()
    if "requires instance_id" in message:
        return "worker.missing_instance_id"
    if "requires bitbrowser_client" in message:
        return "worker.missing_bitbrowser_client"
    if "unsupported script" in message:
        return "worker.unsupported_script"
    if "request failed" in message:
        return "bitbrowser.request_failed"
    if "open failed" in message:
        return "bitbrowser.open_failed"
    if "close failed" in message:
        return "bitbrowser.close_failed"
    if "remark update failed" in message:
        return "bitbrowser.remark_update_failed"
    return f"{script_name}.execution_failed"
