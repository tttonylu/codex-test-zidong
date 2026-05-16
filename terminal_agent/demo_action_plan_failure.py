"""Verification script for explicit action_plan failure reporting."""

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
    """Mock BitBrowser endpoints used by the action plan failure demo."""

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
                            "id": "bb-fail-1",
                            "remark": "Fail_User",
                            "status": 1,
                            "name": "Fail Browser",
                            "seq": 1,
                            "groupId": "g-fail",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            body = {
                "success": True,
                "data": {
                    "id": payload.get("id"),
                    "args": payload.get("args", []),
                    "queue": payload.get("queue", True),
                    "ws": "ws://127.0.0.1:53325/devtools/browser/mock-fail",
                    "http": "127.0.0.1:53325",
                },
            }
        elif self.path == "/browser/remark/update":
            if payload.get("remark") == "force-failure":
                body = {"success": False, "msg": "remark update blocked"}
            else:
                body = {
                    "success": True,
                    "data": {
                        "browserIds": payload.get("browserIds", []),
                        "remark": payload.get("remark"),
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
    state_path = Path("nas_control_plane/state.action-plan-failure.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8780, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15442), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8780")
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-fail-01",
                terminal_id="terminal-fail-01",
                instance_id="bb-fail-1",
                script_name="follow",
                parameters={
                    "target_handle": "fail_user",
                    "action_plan": [
                        {
                            "name": "navigate_profile",
                            "kind": "navigate",
                            "params": {"target_url": "https://x.com/fail_user", "queue": True},
                        },
                        {
                            "name": "annotate_failure",
                            "kind": "annotate",
                            "params": {"remark": "force-failure"},
                        },
                    ],
                },
                priority=1,
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-fail-01",
            hostname="workstation-fail",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15442"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        report = nas_client.get_task_report("task-fail-01")
        attempt = report["attempts"][0] if report["attempts"] else {}

        print(
            json.dumps(
                {
                    "cycle_results": cycle,
                    "task_status": report["task"]["status"],
                    "error_code": report["task"]["last_error_code"],
                    "failed_step": attempt.get("details", {}).get("failed_step"),
                    "failed_action": attempt.get("details", {}).get("failed_action"),
                    "step_statuses": [step["status"] for step in attempt.get("details", {}).get("steps", [])],
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
