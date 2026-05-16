"""Verification script for human-readable CLI task list and attempt output."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import ActionResultPayload, TaskAssignmentPayload
from terminal_agent.adapters import NasControlPlaneClient


def _run_text(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "nas_control_plane.cli", "--base-url", "http://127.0.0.1:8783", *args],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    state_path = Path("nas_control_plane/state.cli-task-views-text.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8783, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8783")
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-cli-views-1",
                terminal_id="terminal-cli",
                instance_id="instance-cli",
                script_name="follow",
                parameters={"target_handle": "cli_user", "retry_limit": 1},
                priority=1,
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-cli-views-1",
                task_id="task-cli-views-1",
                terminal_id="terminal-cli",
                status="failed",
                summary="follow failed",
                error_code="bitbrowser.request_failed",
                error_message="rate limited",
                retryable=True,
                final=False,
                details={"error": "rate limited"},
                emitted_at=datetime(2026, 5, 17, 13, 0, 0),
            )
        )

        tasks_text = _run_text("tasks")
        attempts_text = _run_text("task-attempts", "--task-id", "task-cli-views-1")

        print(tasks_text)
        print("---")
        print(attempts_text)
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
