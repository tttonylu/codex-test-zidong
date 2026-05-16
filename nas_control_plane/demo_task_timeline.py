"""Verification script for task timeline persistence and query APIs."""

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
    state_path = Path("nas_control_plane/state.task-timeline.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8777, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8777")

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-timeline-1",
                terminal_id="terminal-timeline",
                instance_id="instance-timeline",
                script_name="follow",
                parameters={"target_handle": "timeline_target", "retry_limit": 1},
                priority=1,
            )
        )
        client.claim_tasks("terminal-timeline")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-timeline-1",
                task_id="task-timeline-1",
                terminal_id="terminal-timeline",
                instance_id="instance-timeline",
                script_name="follow",
                status="running",
                started_at=datetime(2026, 5, 16, 16, 0, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-timeline-1",
                task_id="task-timeline-1",
                terminal_id="terminal-timeline",
                status="failed",
                summary="follow failed",
                error_code="bitbrowser.request_failed",
                error_message="timeout",
                retryable=True,
                final=False,
                details={"error": "timeout"},
                emitted_at=datetime(2026, 5, 16, 16, 1, 0),
            )
        )
        client.control_task(
            TaskControlPayload(
                task_id="task-timeline-1",
                action="retry",
                reason="retry after timeout",
                requested_by="ops-user",
            )
        )

        events = client.list_task_events("task-timeline-1")
        print(
            json.dumps(
                {
                    "event_types": [item["event_type"] for item in events["items"]],
                    "statuses": [item["status"] for item in events["items"]],
                    "messages": [item["message"] for item in events["items"]],
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
