"""Extract worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a minimal extract task."""

    source = context.task.parameters.get("source", "unknown")
    return WorkerOutcome(
        summary="extract executed",
        details={
            "action": "extract",
            "source": source,
            "instance_id": context.task.instance_id,
            "terminal_id": context.terminal_id,
        },
    )
