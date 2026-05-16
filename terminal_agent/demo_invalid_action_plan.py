"""Verification script for invalid action_plan rejection."""

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
    """Mock BitBrowser endpoints used by the invalid action plan demo."""

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
                            "id": "bb-invalid-1",
                            "remark": "Invalid_User",
                            "status": 1,
                            "name": "Invalid Browser",
                            "seq": 1,
                            "groupId": "g-invalid",
                        }
                    ]
                },
            }
        else:
            body = {"success": True, "data": payload}

        out = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence local mock request logging."""


def main() -> None:
    state_path = Path("nas_control_plane/state.invalid-action-plan.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8781, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15443), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        nas_client = NasControlPlaneClient("http://127.0.0.1:8781")
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-invalid-01",
                terminal_id="terminal-invalid-01",
                instance_id="bb-invalid-1",
                script_name="follow",
                parameters={"target_handle": "invalid_user", "action_plan": "not-a-list"},
                priority=1,
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-invalid-01",
            hostname="workstation-invalid",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15443"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        report = nas_client.get_task_report("task-invalid-01")
        attempt = report["attempts"][0] if report["attempts"] else {}

        print(
            json.dumps(
                {
                    "cycle_results": cycle,
                    "task_status": report["task"]["status"],
                    "error_code": report["task"]["last_error_code"],
                    "error_message": report["task"]["last_error_message"],
                    "step_count": attempt.get("details", {}).get("step_count"),
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
