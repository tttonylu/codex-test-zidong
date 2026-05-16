"""Verification script for the human-readable CLI task-report output."""

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


def main() -> None:
    state_path = Path("nas_control_plane/state.cli-task-report-text.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8782, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8782")
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-cli-report-1",
                terminal_id="terminal-cli",
                instance_id="instance-cli",
                script_name="chat",
                parameters={"target_handle": "cli_user", "retry_limit": 1},
                priority=1,
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-task-cli-report-1",
                task_id="task-cli-report-1",
                terminal_id="terminal-cli",
                status="failed",
                summary="chat failed",
                error_code="bitbrowser.request_failed",
                error_message="rate limited",
                retryable=True,
                final=False,
                details={"error": "rate limited"},
                emitted_at=datetime(2026, 5, 17, 12, 0, 0),
            )
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "nas_control_plane.cli",
                "--base-url",
                "http://127.0.0.1:8782",
                "task-report",
                "--task-id",
                "task-cli-report-1",
            ],
            cwd=Path.cwd(),
            check=True,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        print(output.strip())
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
