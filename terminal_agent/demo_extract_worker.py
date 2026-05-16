"""Quick verification script for the extract worker path."""

from __future__ import annotations

import json

from shared.protocol import TaskAssignmentPayload
from terminal_agent.scripts import ScriptWorkerRegistry


def main() -> None:
    registry = ScriptWorkerRegistry()
    execution = registry.execute(
        TaskAssignmentPayload(
            task_id="task-extract-01",
            terminal_id="terminal-extract-01",
            instance_id="instance-extract-01",
            script_name="extract",
            parameters={"source": "profile_page"},
            priority=1,
        )
    )
    print(
        json.dumps(
            {
                "run_status": execution.run.status,
                "result_status": execution.result.status,
                "summary": execution.result.summary,
                "details": execution.result.details,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
