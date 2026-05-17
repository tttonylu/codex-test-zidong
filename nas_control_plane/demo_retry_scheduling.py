"""Verification script for delayed retry scheduling semantics."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from nas_control_plane.models import TaskRecord
from nas_control_plane.services.tasks import TaskDispatchService
from shared.protocol import ActionResultPayload


def main() -> None:
    current = datetime(2026, 5, 17, 12, 0, 0)

    def now_fn() -> datetime:
        return current

    service = TaskDispatchService(now_fn=now_fn)
    service._tasks["task-delay-01"] = TaskRecord(  # noqa: SLF001
        task_id="task-delay-01",
        terminal_id="terminal-delay-01",
        script_name="follow",
        status="running",
        instance_id="bb-delay-1",
        priority=9,
        retry_limit=1,
        attempt_count=1,
        parameters={},
    )

    failed = service.record_result(
        ActionResultPayload(
            run_id="run-delay-01",
            task_id="task-delay-01",
            terminal_id="terminal-delay-01",
            status="failed",
            summary="open failed",
            error_code="bitbrowser.open_failed",
            error_message="open failed",
        )
    )
    retried = service.retry_task("task-delay-01", requested_by="demo")
    immediate_claim = service.claim_tasks("terminal-delay-01")

    current = current + timedelta(seconds=14)
    early_claim = service.claim_tasks("terminal-delay-01")

    current = current + timedelta(seconds=1)
    ready_claim = service.claim_tasks("terminal-delay-01")

    print(
        json.dumps(
            {
                "after_failure_status": failed.status,
                "after_failure_retryable": failed.retryable,
                "retry_delay_seconds": failed.parameters.get("retry_delay_seconds"),
                "retry_available_at": retried.parameters.get("retry_available_at"),
                "immediate_claim_count": len(immediate_claim),
                "early_claim_count": len(early_claim),
                "ready_claim_count": len(ready_claim),
                "ready_claim_status": ready_claim[0].status if ready_claim else None,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
