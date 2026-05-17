"""Verification script for NAS recovery policy mapping."""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload
from terminal_agent.adapters import NasControlPlaneClient
from terminal_agent.runtime import TerminalRuntime


def main() -> None:
    state_path = Path("nas_control_plane/state.recovery-policy.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8780, state_path=state_path)
    try:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)

        client = NasControlPlaneClient("http://127.0.0.1:8780")
        runtime = TerminalRuntime(
            terminal_id="terminal-policy-01",
            hostname="workstation-policy",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["task.execute"],
        )
        client.register_terminal(runtime.registration_payload())

        cases = [
            ("task-policy-open", "bitbrowser.open_failed"),
            ("task-policy-close", "bitbrowser.close_failed"),
            ("task-policy-script", "worker.unsupported_script"),
        ]
        outputs: list[dict[str, object]] = []

        for task_id, error_code in cases:
            client.create_task(
                TaskAssignmentPayload(
                    task_id=task_id,
                    terminal_id="terminal-policy-01",
                    instance_id="bb-policy-1",
                    script_name="follow",
                    parameters={"target_handle": "policy_user"},
                    priority=5,
                    retry_limit=1,
                    close_after_actions=True,
                    requested_by="demo",
                )
            )
            client.mark_task_running(
                ScriptRunPayload(
                    run_id=f"run-{task_id}",
                    task_id=task_id,
                    terminal_id="terminal-policy-01",
                    instance_id="bb-policy-1",
                    script_name="follow",
                    status="running",
                    started_at=datetime.now(UTC),
                )
            )
            client.submit_task_result(
                ActionResultPayload(
                    run_id=f"run-{task_id}",
                    task_id=task_id,
                    terminal_id="terminal-policy-01",
                    status="failed",
                    summary=f"{error_code} failed",
                    error_code=error_code,
                    error_message=error_code,
                    retryable=None,
                    final=None,
                    details={},
                )
            )
            task = client.get_task(task_id)
            outputs.append(
                {
                    "task_id": task_id,
                    "status": task["status"],
                    "retryable": task["retryable"],
                    "final": task["final"],
                    "recommended_action": task["parameters"].get("recommended_action"),
                    "failure_category": task["parameters"].get("failure_category"),
                    "retry_delay_seconds": task["parameters"].get("retry_delay_seconds"),
                }
            )

        print(json.dumps(outputs, separators=(",", ":")))
    finally:
        server.shutdown()
        server.server_close()
        if state_path.exists():
            state_path.unlink()


if __name__ == "__main__":
    main()
