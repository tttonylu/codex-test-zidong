"""Verification script for terminal task lifecycle ordering."""

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
    """Small local mock for lifecycle verification."""

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
                            "id": "bb-life-1",
                            "remark": "Life_User",
                            "status": 1,
                            "name": "Lifecycle Browser",
                            "seq": 41,
                            "groupId": "g-life",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            body = {"success": True, "data": {"id": payload.get("id"), "args": payload.get("args", [])}}
        elif self.path == "/browser/close":
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
    state_path = Path("nas_control_plane/state.task-lifecycle.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8778, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15443), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        client = NasControlPlaneClient("http://127.0.0.1:8778")
        runtime = TerminalRuntime(
            terminal_id="terminal-life-01",
            hostname="workstation-life",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        client.register_terminal(runtime.registration_payload())
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-life-01",
                terminal_id="terminal-life-01",
                instance_id="bb-life-1",
                script_name="follow",
                parameters={"target_handle": "life_user"},
                priority=9,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15443"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        task = client.get_task("task-life-01")
        logs = client.query_logs(task_id="task-life-01")["items"]

        print(
            json.dumps(
                {
                    "cycle": cycle,
                    "status": task["status"],
                    "attempt_count": task["attempt_count"],
                    "run_id": task["parameters"].get("run_id"),
                    "run_started_at": task["parameters"].get("run_started_at"),
                    "result_run_id": task["parameters"].get("result_run_id"),
                    "close_browser_result": task["parameters"].get("result_details", {}).get("close_browser_result"),
                    "log_count": len(logs),
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
