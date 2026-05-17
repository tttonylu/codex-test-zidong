"""Verification script for task cancel semantics."""

from __future__ import annotations

from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import NasControlPlaneClient
from terminal_agent.runtime import TerminalRuntime


def main() -> None:
    state_path = Path("nas_control_plane/state.task-cancel.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8774, state_path=state_path)
    try:
        import threading
        import time

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)

        client = NasControlPlaneClient("http://127.0.0.1:8774")
        client.register_terminal(
            TerminalRuntime(
                terminal_id="terminal-cancel-01",
                hostname="workstation-cancel",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["task.execute"],
            ).registration_payload()
        )
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-cancel-01",
                terminal_id="terminal-cancel-01",
                instance_id="bb-cancel-1",
                script_name="follow",
                parameters={"target_handle": "cancel_user"},
                priority=5,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        cancelled = client.cancel_task("task-cancel-01", requested_by="demo")
        task = client.get_task("task-cancel-01")
        print(
            {
                "cancelled_status": cancelled["status"],
                "final": cancelled["final"],
                "retryable": cancelled["retryable"],
                "cancel_request_accepted": task["parameters"].get("cancel_request_accepted"),
            }
        )
    finally:
        server.shutdown()
        server.server_close()
        if state_path.exists():
            state_path.unlink()


if __name__ == "__main__":
    main()
