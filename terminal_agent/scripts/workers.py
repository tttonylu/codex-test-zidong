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

    def execute(
        self,
        task: TaskAssignmentPayload,
        *,
        terminal_hostname: str = "unknown",
        bitbrowser_client: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerExecution:
        """Execute one task and build the corresponding lifecycle payloads."""

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

        try:
            outcome = self._dispatch(context)
            result = ActionResultPayload(
                run_id=run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="completed",
                summary=outcome.summary,
                details=outcome.details,
                emitted_at=datetime.utcnow(),
            )
        except Exception as exc:
            result = ActionResultPayload(
                run_id=run.run_id,
                task_id=task.task_id,
                terminal_id=task.terminal_id,
                status="failed",
                summary=f"{task.script_name} failed",
                details={
                    "error": str(exc),
                    "instance_id": task.instance_id,
                    "parameters": dict(task.parameters),
                },
                emitted_at=datetime.utcnow(),
            )

        return WorkerExecution(run=run, result=result)

    def _dispatch(self, context: WorkerContext) -> WorkerOutcome:
        try:
            worker = self._workers[context.task.script_name]
        except KeyError as exc:
            raise ValueError(f"unsupported script: {context.task.script_name}") from exc
        return worker(context)
