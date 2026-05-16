"""Verification script for the NAS management CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    TerminalRegistrationPayload,
)
from terminal_agent.adapters import NasControlPlaneClient


def _run_cli(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "nas_control_plane.cli", "--base-url", "http://127.0.0.1:8776", *args],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    state_path = Path("nas_control_plane/state.cli.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8776, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8776")

        client.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-cli",
                hostname="cli-host",
                operator_name="ops",
                agent_version="0.1.0",
                capabilities=["scan", "execute"],
                metadata={"zone": "cli"},
            )
        )
        client.send_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-cli",
                reported_at=datetime(2026, 5, 16, 15, 0, 0),
                status="online",
                active_instance_count=0,
                queued_task_count=1,
                metadata={"load": "low"},
            )
        )
        created_follow = _run_cli(
            "create-follow-task",
            "--task-id",
            "task-cli-1",
            "--terminal-id",
            "terminal-cli",
            "--instance-id",
            "instance-cli-1",
            "--target-handle",
            "cli_target",
            "--priority",
            "1",
            "--retry-limit",
            "1",
            "--annotate-remark",
        )
        created_chat = _run_cli(
            "create-chat-task",
            "--task-id",
            "task-cli-2",
            "--terminal-id",
            "terminal-cli",
            "--instance-id",
            "instance-cli-2",
            "--target-handle",
            "cli_fail",
            "--priority",
            "2",
            "--retry-limit",
            "2",
            "--annotate-remark",
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-cli-2",
                task_id="task-cli-2",
                terminal_id="terminal-cli",
                status="failed",
                summary="chat failed",
                error_code="bitbrowser.request_failed",
                error_message="rate limited",
                retryable=True,
                final=False,
                details={"error": "rate limited"},
                emitted_at=datetime(2026, 5, 16, 15, 1, 0),
            )
        )

        summary = _run_cli("summary")
        terminal = _run_cli("terminals", "--terminal-id", "terminal-cli")
        failed_tasks = _run_cli("tasks", "--status", "failed")
        cancelled = _run_cli(
            "cancel-task",
            "--task-id",
            "task-cli-1",
            "--reason",
            "manual stop",
            "--requested-by",
            "cli-user",
        )
        retried = _run_cli(
            "retry-task",
            "--task-id",
            "task-cli-2",
            "--reason",
            "retry after wait",
            "--requested-by",
            "cli-user",
        )
        task_events = _run_cli("task-events", "--task-id", "task-cli-2")
        task_attempts = _run_cli("task-attempts", "--task-id", "task-cli-2")
        task_report = _run_cli("task-report", "--task-id", "task-cli-2", "--raw")

        print(
            json.dumps(
                {
                    "summary_task_count": summary["tasks"]["task_count"],
                    "terminal_status": terminal["status"],
                    "follow_action_names": [item["name"] for item in created_follow["parameters"]["action_plan"]],
                    "chat_action_names": [item["name"] for item in created_chat["parameters"]["action_plan"]],
                    "failed_task_ids": [item["task_id"] for item in failed_tasks["items"]],
                    "cancelled_status": cancelled["status"],
                    "retried_status": retried["status"],
                    "retried_attempt_count": retried["attempt_count"],
                    "task_event_types": [item["event_type"] for item in task_events["items"]],
                    "task_attempt_statuses": [item["status"] for item in task_attempts["items"]],
                    "task_report_latest_log_level": task_report["latest_log"]["level"] if task_report["latest_log"] else None,
                    "task_report_action_summary_count": task_report["action_summary"]["action_count"],
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
