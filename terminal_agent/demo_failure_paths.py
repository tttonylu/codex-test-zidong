"""Verification script for terminal worker failure paths."""

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


class MockBitBrowserFailureHandler(BaseHTTPRequestHandler):
    """Small local mock for failure-path verification."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8")) if raw else {}

        if self.path == "/health":
            body = {"success": True}
        elif self.path == "/browser/list":
            body = {
                "success": True,
                "data": {
                    "list": [
                        {
                            "id": "bb-failure-1",
                            "remark": "Failure_User",
                            "status": 1,
                            "name": "Failure Browser",
                            "seq": 91,
                            "groupId": "g-failure",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            body = {"success": True, "data": {"id": payload.get("id"), "args": payload.get("args", [])}}
        elif self.path == "/browser/close":
            if payload.get("id") == "bb-close-fail-1":
                body = {"success": False, "msg": "close failed for demo"}
            else:
                body = {"success": True, "data": {"id": payload.get("id"), "closed": True}}
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
    state_path = Path("nas_control_plane/state.failure-paths.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8779, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15444), MockBitBrowserFailureHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        client = NasControlPlaneClient("http://127.0.0.1:8779")
        runtime = TerminalRuntime(
            terminal_id="terminal-failure-01",
            hostname="workstation-failure",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        client.register_terminal(runtime.registration_payload())

        tasks = [
            TaskAssignmentPayload(
                task_id="task-failure-missing-instance",
                terminal_id="terminal-failure-01",
                instance_id=None,
                script_name="follow",
                parameters={"target_handle": "failure_user"},
                priority=9,
                retry_limit=1,
                close_after_actions=False,
                requested_by="demo",
            ),
            TaskAssignmentPayload(
                task_id="task-failure-unsupported-script",
                terminal_id="terminal-failure-01",
                instance_id="bb-failure-1",
                script_name="unknown_script",
                parameters={"target_handle": "failure_user"},
                priority=8,
                retry_limit=1,
                close_after_actions=False,
                requested_by="demo",
            ),
            TaskAssignmentPayload(
                task_id="task-failure-close",
                terminal_id="terminal-failure-01",
                instance_id="bb-close-fail-1",
                script_name="follow",
                parameters={"target_handle": "failure_user"},
                priority=7,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            ),
        ]
        for item in tasks:
            client.create_task(item)

        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15444"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        results = client.query_tasks(terminal_id="terminal-failure-01")["items"]

        print(
            json.dumps(
                {
                    "cycle": cycle,
                    "items": [
                        {
                            "task_id": item["task_id"],
                            "status": item["status"],
                            "retryable": item["retryable"],
                            "final": item["final"],
                            "error_code": item["last_error_code"],
                        }
                        for item in results
                    ],
                },
                separators=(",", ":"),
            )
        )
    finally:
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()
        if state_path.exists():
            state_path.unlink()


if __name__ == "__main__":
    main()
