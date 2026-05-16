"""Local verification script for task execution result reporting."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.runtime import TerminalAgentLoop, TerminalRuntime


class MockBitBrowserHandler(BaseHTTPRequestHandler):
    """Small local mock for BitBrowser scan endpoints."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8")) if raw else {}

        if self.path == "/health":
            body = {"success": True}
        elif self.path == "/browser/list":
            page = int(payload.get("page", 0))
            if page == 0:
                body = {
                    "success": True,
                    "data": {
                        "list": [
                            {
                                "id": "bb-exec-1",
                                "remark": "Exec_User",
                                "status": 1,
                                "name": "Exec Browser",
                                "seq": 31,
                                "groupId": "g-exec",
                            }
                        ]
                    },
                }
            else:
                body = {"success": True, "data": {"list": []}}
        elif self.path == "/browser/open":
            body = {
                "success": True,
                "data": {
                    "id": payload.get("id"),
                    "args": payload.get("args", []),
                    "queue": payload.get("queue", True),
                    "ws": "ws://127.0.0.1:53325/devtools/browser/mock-exec",
                    "http": "127.0.0.1:53325",
                },
            }
        else:
            self.send_response(404)
            self.end_headers()
            return

        out = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence local mock request logging."""


def main() -> None:
    state_path = Path("nas_control_plane/state.execution-loop.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8771, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15437), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8771")
        for task in [
            TaskAssignmentPayload(
                task_id="task-exec-01",
                terminal_id="terminal-exec-01",
                instance_id="bb-exec-1",
                script_name="follow",
                parameters={"target_handle": "user_exec_a"},
                priority=10,
            ),
            TaskAssignmentPayload(
                task_id="task-exec-02",
                terminal_id="terminal-exec-01",
                instance_id="bb-exec-1",
                script_name="chat",
                parameters={"target_handle": "user_exec_b"},
                priority=5,
            ),
        ]:
            nas_client.create_task(task)

        runtime = TerminalRuntime(
            terminal_id="terminal-exec-01",
            hostname="workstation-exec",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15437"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        tasks = nas_client.list_tasks("terminal-exec-01")
        logs = nas_client.list_logs()
        task_events = nas_client.list_task_events("task-exec-01")
        task_attempts = nas_client.list_task_attempts("task-exec-01")
        task_report = nas_client.get_task_report("task-exec-01")

        print(
            json.dumps(
                {
                    "cycle_results": cycle,
                    "task_statuses": [item["status"] for item in tasks["items"]],
                    "task_run_ids": [item["parameters"].get("run_id") for item in tasks["items"]],
                    "log_levels": [item["level"] for item in logs["items"]],
                    "log_messages": [item["message"] for item in logs["items"]],
                    "task_event_types": [item["event_type"] for item in task_events["items"]],
                    "task_attempt_statuses": [item["status"] for item in task_attempts["items"]],
                    "task_report_attempt_count": len(task_report["attempts"]),
                    "task_report_step_count": task_report["attempts"][0]["step_count"] if task_report["attempts"] else None,
                },
                separators=(",", ":"),
            )
        )
    finally:
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()
        time.sleep(0.2)
        if state_path.exists():
            try:
                state_path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
