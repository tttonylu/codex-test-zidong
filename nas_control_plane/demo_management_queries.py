"""Verification script for NAS management query endpoints."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)
from terminal_agent.adapters import NasControlPlaneClient


def main() -> None:
    state_path = Path("nas_control_plane/state.management.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8774, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8774")

        client.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-a",
                hostname="host-a",
                operator_name="alice",
                agent_version="0.1.0",
                capabilities=["scan", "execute"],
                metadata={"zone": "a"},
            )
        )
        client.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-b",
                hostname="host-b",
                operator_name="bob",
                agent_version="0.1.0",
                capabilities=["scan"],
                metadata={"zone": "b"},
            )
        )
        client.send_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-a",
                reported_at=datetime(2026, 5, 16, 13, 0, 0),
                status="online",
                active_instance_count=1,
                queued_task_count=1,
                metadata={"cpu": "normal"},
            )
        )
        client.send_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-b",
                reported_at=datetime(2026, 5, 16, 13, 1, 0),
                status="idle",
                active_instance_count=0,
                queued_task_count=0,
                metadata={"cpu": "low"},
            )
        )
        client.sync_instances(
            "terminal-a",
            [
                InstanceSnapshotPayload(
                    terminal_id="terminal-a",
                    instance_id="instance-a1",
                    profile_id="profile-a1",
                    handle="user_a1",
                    runtime_status="running",
                    window_id="win-a1",
                    remark="runner",
                    metadata={"seq": 1},
                )
            ],
        )
        client.sync_instances(
            "terminal-b",
            [
                InstanceSnapshotPayload(
                    terminal_id="terminal-b",
                    instance_id="instance-b1",
                    profile_id="profile-b1",
                    handle="user_b1",
                    runtime_status="idle",
                    window_id="win-b1",
                    remark="standby",
                    metadata={"seq": 2},
                )
            ],
        )

        client.create_task(
            TaskAssignmentPayload(
                task_id="task-follow-a",
                terminal_id="terminal-a",
                instance_id="instance-a1",
                script_name="follow",
                parameters={"target_handle": "target_a"},
                priority=2,
            )
        )
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-chat-b",
                terminal_id="terminal-b",
                instance_id="instance-b1",
                script_name="chat",
                parameters={"target_handle": "target_b"},
                priority=1,
            )
        )
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-follow-a",
                task_id="task-follow-a",
                terminal_id="terminal-a",
                instance_id="instance-a1",
                script_name="follow",
                status="running",
                started_at=datetime(2026, 5, 16, 13, 2, 0),
                metadata={"phase": "open"},
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-follow-a",
                task_id="task-follow-a",
                terminal_id="terminal-a",
                status="completed",
                summary="follow finished",
                details={"duration_ms": 1234},
                emitted_at=datetime(2026, 5, 16, 13, 3, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-chat-b",
                task_id="task-chat-b",
                terminal_id="terminal-b",
                status="failed",
                summary="chat failed",
                error_code="bitbrowser.request_failed",
                error_message="network",
                retryable=True,
                final=False,
                details={"reason": "network"},
                emitted_at=datetime(2026, 5, 16, 13, 4, 0),
            )
        )

        online_terminals = client.list_terminals(status="online")
        idle_instances = client.list_instances(runtime_status="idle")
        failed_logs = client.list_logs_filtered(level="error")
        completed_tasks = client.list_tasks_filtered(status="completed")
        terminal_a = client.get_terminal("terminal-a")
        task_follow_a = client.get_task("task-follow-a")
        log_error = client.get_log("log-2")
        summary = client.get_summary()

        print(
            json.dumps(
                {
                    "online_terminal_ids": [item["terminal_id"] for item in online_terminals["items"]],
                    "idle_instance_ids": [item["instance_id"] for item in idle_instances["items"]],
                    "completed_task_ids": [item["task_id"] for item in completed_tasks["items"]],
                    "error_log_ids": [item["log_id"] for item in failed_logs["items"]],
                    "terminal_a_status": terminal_a["status"],
                    "task_follow_a_status": task_follow_a["status"],
                    "log_error_level": log_error["level"],
                    "summary_task_statuses": summary["tasks"]["status_counts"],
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
