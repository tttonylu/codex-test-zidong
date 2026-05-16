"""Minimal script worker registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload
from terminal_agent.scripts import chat_worker, extract_worker, follow_worker, probe_worker
from terminal_agent.scripts.types import WorkerContext, WorkerExecutionError, WorkerOutcome, WorkerStepResult


@dataclass(slots=True)
class WorkerExecution:
    """Represents one worker execution with start and finish payloads."""

    run: ScriptRunPayload
    result: ActionResultPayload


class ScriptWorkerRegistry:
    """Dispatches tasks to simple in-process workers by script name."""

    def __init__(self) -> None:
        self._workers: dict[str, Callable[[WorkerContext], WorkerOutcome]] = {
            "follow": follow_worker.execute,
            "chat": chat_worker.execute,
            "probe": probe_worker.execute,
            "extract": extract_worker.execute,
        }

    def build_run(
        self,
        task: TaskAssignmentPayload,
        *,
        terminal_hostname: str = "unknown",
    ) -> ScriptRunPayload:
        """Build the lifecycle run payload before worker execution starts."""

        return ScriptRunPayload(
            run_id=f"run-{task.task_id}",
            task_id=task.task_id,
            terminal_id=task.terminal_id,
            instance_id=task.instance_id,
            script_name=task.script_name,
            status="running",
            started_at=datetime.utcnow(),
            metadata={"worker": task.script_name, "terminal_hostname": terminal_hostname},
        )

    def execute_run(
        self,
        task: TaskAssignmentPayload,
        *,
        run: ScriptRunPayload,
        terminal_hostname: str = "unknown",
        bitbrowser_client: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> ActionResultPayload:
        """Execute one task for an already-created lifecycle run."""

        context = WorkerContext(
            task=task,
            terminal_id=task.terminal_id,
            hostname=terminal_hostname,
            bitbrowser_client=bitbrowser_client,
            metadata=dict(metadata or {}),
        )

        try:
            outcome = self._dispatch(context)
            return ActionResultPayload(
                run_id=run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="completed",
                summary=outcome.summary,
                retryable=False,
                final=True,
                details=_build_result_details(outcome),
                emitted_at=datetime.utcnow(),
            )
        except WorkerExecutionError as exc:
            return ActionResultPayload(
                run_id=run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="failed",
                summary=f"{task.script_name} failed",
                error_code=exc.error_code,
                error_message=str(exc),
                retryable=exc.retryable,
                final=not exc.retryable,
                details={
                    **exc.details,
                    "error": str(exc),
                    "instance_id": task.instance_id,
                    "parameters": dict(task.parameters),
                    "steps": _serialize_steps(exc.steps),
                    "step_count": len(exc.steps),
                },
                emitted_at=datetime.utcnow(),
            )
        except Exception as exc:
            error_code, retryable = _classify_worker_failure(task.script_name, exc)
            return ActionResultPayload(
                run_id=run.run_id,
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
                    "steps": [],
                    "step_count": 0,
                },
                emitted_at=datetime.utcnow(),
            )

    def execute(
        self,
        task: TaskAssignmentPayload,
        *,
        terminal_hostname: str = "unknown",
        bitbrowser_client: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerExecution:
        """Execute one task and build the corresponding lifecycle payloads."""

        run = self.build_run(task, terminal_hostname=terminal_hostname)
        result = self.execute_run(
            task,
            run=run,
            terminal_hostname=terminal_hostname,
            bitbrowser_client=bitbrowser_client,
            metadata=metadata,
        )
        return WorkerExecution(run=run, result=result)

    def _dispatch(self, context: WorkerContext) -> WorkerOutcome:
        try:
            worker = self._workers[context.task.script_name]
        except KeyError as exc:
            raise ValueError(f"unsupported script: {context.task.script_name}") from exc
        return worker(context)


def _classify_worker_failure(script_name: str, exc: Exception) -> tuple[str, bool]:
    message = str(exc).lower()
    if "requires instance_id" in message:
        return "worker.missing_instance_id", False
    if "requires bitbrowser_client" in message:
        return "worker.missing_bitbrowser_client", False
    if "unsupported script" in message:
        return "worker.unsupported_script", False
    if "bitbrowser open failed" in message:
        return "bitbrowser.open_failed", True
    if "bitbrowser request failed" in message:
        return "bitbrowser.request_failed", True
    return f"{script_name}.execution_failed", True


def _build_result_details(outcome: WorkerOutcome) -> dict[str, Any]:
    return {
        **outcome.details,
        "steps": _serialize_steps(outcome.steps),
        "step_count": len(outcome.steps),
    }


def _serialize_steps(steps: list[WorkerStepResult]) -> list[dict[str, Any]]:
    return [
        {
            "name": step.name,
            "status": step.status,
            "started_at": step.started_at.isoformat(),
            "finished_at": step.finished_at.isoformat(),
            "details": dict(step.details),
        }
        for step in steps
    ]
