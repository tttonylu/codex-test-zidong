"""Verification script for task cancel and retry controls."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import ActionResultPayload, TaskAssignmentPayload, TaskControlPayload
from terminal_agent.adapters import NasControlPlaneClient


def main() -> None:
    state_path = Path("nas_control_plane/state.task-controls.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8775, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8775")

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-cancel-1",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="follow",
                parameters={"target_handle": "cancel_me"},
                priority=1,
            )
        )
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-retry-1",
                terminal_id="terminal-a",
                instance_id="instance-a",
                script_name="chat",
                parameters={"target_handle": "retry_me", "retry_limit": 2},
                priority=2,
            )
        )

        client.control_task(
            TaskControlPayload(
                task_id="task-cancel-1",
                action="cancel",
                reason="operator stopped this task",
                requested_by="ops-user",
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-retry-1-attempt-1",
                task_id="task-retry-1",
                terminal_id="terminal-a",
                status="failed",
                summary="chat failed",
                error_code="chat.execution_failed",
                error_message="proxy timeout",
                retryable=True,
                final=False,
                details={"error": "proxy timeout"},
                emitted_at=datetime(2026, 5, 16, 14, 0, 0),
            )
        )
        retry_record = client.control_task(
            TaskControlPayload(
                task_id="task-retry-1",
                action="retry",
                reason="retry after proxy recovery",
                requested_by="ops-user",
            )
        )

        cancelled = client.get_task("task-cancel-1")
        retried = client.get_task("task-retry-1")
        error_logs = client.list_logs_filtered(level="error")

        print(
            json.dumps(
                {
                    "cancelled_status": cancelled["status"],
                    "cancel_reason": cancelled.get("cancel_reason"),
                    "retried_status": retried["status"],
                    "attempt_count": retried["attempt_count"],
                    "last_error_code": retried.get("last_error_code"),
                    "last_error_message": retried.get("last_error_message"),
                    "retry_requested_status": retry_record["status"],
                    "retryable": retried["retryable"],
                    "final": retried["final"],
                    "error_log_failure_reason": error_logs["items"][0]["details"].get("failure_reason"),
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
