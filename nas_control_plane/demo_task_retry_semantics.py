"""Verification script for explicit task retry and final-state semantics."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload, TaskControlPayload
from terminal_agent.adapters import NasControlPlaneClient


def main() -> None:
    state_path = Path("nas_control_plane/state.task-retry-semantics.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8778, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8778")

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-retryable",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="chat",
                parameters={"target_handle": "retryable", "retry_limit": 2},
                priority=2,
            )
        )
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-retryable-1",
                task_id="task-retryable",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="chat",
                status="running",
                started_at=datetime(2026, 5, 16, 15, 59, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-retryable-1",
                task_id="task-retryable",
                terminal_id="terminal-a",
                status="failed",
                summary="chat failed",
                error_code="bitbrowser.request_failed",
                error_message="proxy timeout",
                retryable=True,
                final=False,
                details={"phase": "open"},
                emitted_at=datetime(2026, 5, 16, 16, 0, 0),
            )
        )
        client.control_task(
            TaskControlPayload(
                task_id="task-retryable",
                action="retry",
                reason="network recovered",
                requested_by="ops",
            )
        )

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-final-failed",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="follow",
                parameters={"target_handle": "final-one", "retry_limit": 0},
                priority=1,
            )
        )
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-final-failed-1",
                task_id="task-final-failed",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="follow",
                status="running",
                started_at=datetime(2026, 5, 16, 16, 0, 30),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-final-failed-1",
                task_id="task-final-failed",
                terminal_id="terminal-a",
                status="failed",
                summary="follow failed",
                error_code="worker.missing_instance_id",
                error_message="instance missing",
                retryable=False,
                final=True,
                details={"phase": "validate"},
                emitted_at=datetime(2026, 5, 16, 16, 1, 0),
            )
        )

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-cancelled",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="probe",
                parameters={"target_url": "https://x.com/home"},
                priority=1,
            )
        )
        client.control_task(
            TaskControlPayload(
                task_id="task-cancelled",
                action="cancel",
                reason="manual stop",
                requested_by="ops",
            )
        )

        retryable = client.get_task("task-retryable")
        final_failed = client.get_task("task-final-failed")
        cancelled = client.get_task("task-cancelled")

        retry_error = None
        try:
            client.control_task(
                TaskControlPayload(
                    task_id="task-final-failed",
                    action="retry",
                    reason="should fail",
                    requested_by="ops",
                )
            )
        except RuntimeError as exc:
            retry_error = str(exc)

        print(
            json.dumps(
                {
                    "retryable_status": retryable["status"],
                    "retryable_attempt_count": retryable["attempt_count"],
                    "retryable_max_attempts": retryable["max_attempts"],
                    "retryable_final": retryable["final"],
                    "retryable_last_error_code": retryable["last_error_code"],
                    "final_failed_status": final_failed["status"],
                    "final_failed_retryable": final_failed["retryable"],
                    "final_failed_final": final_failed["final"],
                    "final_failed_last_error_code": final_failed["last_error_code"],
                    "cancelled_status": cancelled["status"],
                    "cancelled_final": cancelled["final"],
                    "cancelled_reason": cancelled["cancel_reason"],
                    "retry_error_contains": "not retryable" in retry_error if retry_error else False,
                },
                separators=(",", ":"),
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)
        time.sleep(0.2)
        if state_path.exists():
            try:
                state_path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
