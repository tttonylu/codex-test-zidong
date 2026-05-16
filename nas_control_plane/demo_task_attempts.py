"""Verification script for aggregated task attempt views."""

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
    state_path = Path("nas_control_plane/state.task-attempts.demo.sqlite3")
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
                task_id="task-attempts-1",
                terminal_id="terminal-attempts",
                instance_id="instance-attempts",
                script_name="follow",
                parameters={"target_handle": "attempt_user", "retry_limit": 1},
                priority=1,
            )
        )
        client.claim_tasks("terminal-attempts")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-attempts-1-a1",
                task_id="task-attempts-1",
                terminal_id="terminal-attempts",
                instance_id="instance-attempts",
                script_name="follow",
                status="running",
                started_at=datetime(2026, 5, 17, 10, 0, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-attempts-1-a1",
                task_id="task-attempts-1",
                terminal_id="terminal-attempts",
                status="failed",
                summary="follow failed",
                error_code="TIMEOUT",
                error_message="network timeout",
                retryable=True,
                final=False,
                details={
                    "error": "network timeout",
                    "step_count": 3,
                    "steps": [
                        {
                            "name": "validate_instance_id",
                            "status": "completed",
                            "started_at": "2026-05-17T10:00:00",
                            "finished_at": "2026-05-17T10:00:00",
                            "details": {"action": "follow", "browser_id": "instance-attempts"},
                        },
                        {
                            "name": "prepare_target",
                            "status": "completed",
                            "started_at": "2026-05-17T10:00:00",
                            "finished_at": "2026-05-17T10:00:00",
                            "details": {"action": "follow", "target_handle": "attempt_user"},
                        },
                        {
                            "name": "open_browser",
                            "status": "failed",
                            "started_at": "2026-05-17T10:00:01",
                            "finished_at": "2026-05-17T10:00:01",
                            "details": {"action": "follow", "error": "network timeout"},
                        },
                    ],
                },
                emitted_at=datetime(2026, 5, 17, 10, 1, 0),
            )
        )
        client.control_task(
            TaskControlPayload(
                task_id="task-attempts-1",
                action="retry",
                reason="retry after timeout",
                requested_by="ops-user",
            )
        )
        client.claim_tasks("terminal-attempts")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-attempts-1-a2",
                task_id="task-attempts-1",
                terminal_id="terminal-attempts",
                instance_id="instance-attempts",
                script_name="follow",
                status="running",
                started_at=datetime(2026, 5, 17, 10, 2, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-attempts-1-a2",
                task_id="task-attempts-1",
                terminal_id="terminal-attempts",
                status="completed",
                summary="follow completed",
                final=True,
                details={"result": "ok"},
                emitted_at=datetime(2026, 5, 17, 10, 3, 0),
            )
        )

        attempts = client.list_task_attempts("task-attempts-1")
        print(
            json.dumps(
                {
                    "attempt_numbers": [item["attempt_number"] for item in attempts["items"]],
                    "statuses": [item["status"] for item in attempts["items"]],
                    "run_ids": [item["run_id"] for item in attempts["items"]],
                    "error_codes": [item["error_code"] for item in attempts["items"]],
                    "summaries": [item["summary"] for item in attempts["items"]],
                    "step_counts": [item["step_count"] for item in attempts["items"]],
                    "failed_step_names": [item["failed_step_name"] for item in attempts["items"]],
                    "failure_categories": [item["failure_category"] for item in attempts["items"]],
                    "recommended_actions": [item["recommended_action"] for item in attempts["items"]],
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
