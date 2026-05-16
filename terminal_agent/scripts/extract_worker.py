"""Extract worker entrypoint."""

from __future__ import annotations

from terminal_agent.scripts.helpers import build_local_outcome
from terminal_agent.scripts.types import WorkerContext, WorkerOutcome


def execute(context: WorkerContext) -> WorkerOutcome:
    """Execute a minimal extract task."""

    source = context.task.parameters.get("source", "unknown")
    return build_local_outcome(
        action="extract",
        summary="extract executed",
        terminal_id=context.terminal_id,
        instance_id=context.task.instance_id,
        details={"source": source},
        step_name="collect_extract_source",
    )
