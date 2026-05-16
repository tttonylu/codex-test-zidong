"""Verification script for the aggregated task report view."""

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
    state_path = Path("nas_control_plane/state.task-report.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8779, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8779")

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-report-1",
                terminal_id="terminal-report",
                instance_id="instance-report",
                script_name="chat",
                parameters={"target_handle": "report_user", "retry_limit": 1},
                priority=2,
            )
        )
        client.claim_tasks("terminal-report")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-task-report-1-a1",
                task_id="task-report-1",
                terminal_id="terminal-report",
                instance_id="instance-report",
                script_name="chat",
                status="running",
                started_at=datetime(2026, 5, 17, 11, 0, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-report-1-a1",
                task_id="task-report-1",
                terminal_id="terminal-report",
                status="failed",
                summary="chat failed",
                error_code="chat.rate_limited",
                error_message="platform rate limited",
                retryable=True,
                final=False,
                details={
                    "error": "platform rate limited",
                    "http_status": 429,
                    "step_count": 4,
                    "steps": [
                        {
                            "name": "validate_instance_id",
                            "status": "completed",
                            "started_at": "2026-05-17T11:00:00",
                            "finished_at": "2026-05-17T11:00:00",
                            "details": {"action": "chat", "browser_id": "instance-report"},
                        },
                        {
                            "name": "validate_bitbrowser_client",
                            "status": "completed",
                            "started_at": "2026-05-17T11:00:00",
                            "finished_at": "2026-05-17T11:00:00",
                            "details": {"action": "chat"},
                        },
                        {
                            "name": "prepare_target",
                            "status": "completed",
                            "started_at": "2026-05-17T11:00:00",
                            "finished_at": "2026-05-17T11:00:00",
                            "details": {"action": "chat", "target_handle": "report_user"},
                        },
                        {
                            "name": "open_browser",
                            "status": "failed",
                            "started_at": "2026-05-17T11:00:01",
                            "finished_at": "2026-05-17T11:00:01",
                            "details": {"action": "chat", "error": "platform rate limited"},
                        },
                    ],
                },
                emitted_at=datetime(2026, 5, 17, 11, 1, 0),
            )
        )
        client.control_task(
            TaskControlPayload(
                task_id="task-report-1",
                action="retry",
                reason="retry after cooldown",
                requested_by="ops-user",
            )
        )

        report = client.get_task_report("task-report-1")
        print(
            json.dumps(
                {
                    "task_status": report["task"]["status"],
                    "attempt_count": len(report["attempts"]),
                    "event_count": len(report["events"]),
                    "latest_log_level": report["latest_log"]["level"] if report["latest_log"] else None,
                    "latest_log_error_code": report["latest_log"]["details"].get("error_code") if report["latest_log"] else None,
                    "attempt_statuses": [item["status"] for item in report["attempts"]],
                    "attempt_step_counts": [item["step_count"] for item in report["attempts"]],
                    "action_summary_count": report["action_summary"]["action_count"],
                    "failed_step_names": [item["failed_step_name"] for item in report["attempts"]],
                    "failure_categories": [item["failure_category"] for item in report["attempts"]],
                    "recommended_action": report["action_summary"]["recommended_action"],
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
