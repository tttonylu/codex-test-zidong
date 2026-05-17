"""Verification script for the NAS web console dashboard."""

from __future__ import annotations

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
        if self.path == "/health":
            body = {"success": True}
        elif self.path == "/browser/list":
            body = {
                "success": True,
                "data": {
                    "list": [
                        {
                            "id": "bb-web-1",
                            "remark": "Web_User",
                            "status": 1,
                            "name": "Web Browser",
                            "seq": 81,
                            "groupId": "g-web",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            body = {"success": True, "data": {"id": "bb-web-1", "args": []}}
        elif self.path == "/browser/close":
            body = {"success": True, "data": {"id": "bb-web-1", "closed": True}}
        else:
            self.send_response(404)
            self.end_headers()
            return

        import json

        out = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """Silence local mock request logging."""


def main() -> None:
    state_path = Path("nas_control_plane/state.dashboard-web.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8777, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15442), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        nas_client = NasControlPlaneClient("http://127.0.0.1:8777")
        nas_client.register_terminal(
            TerminalRuntime(
                terminal_id="terminal-web-01",
                hostname="workstation-web",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
                max_parallel_tasks=1,
            ).registration_payload()
        )
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-web-01",
                terminal_id="terminal-web-01",
                instance_id="bb-web-1",
                script_name="follow",
                parameters={"target_handle": "web_user"},
                priority=8,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-web-02",
                terminal_id="terminal-web-01",
                instance_id="bb-web-1",
                script_name="chat",
                parameters={"target_handle": "web_user_b"},
                priority=4,
                retry_limit=2,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        loop = TerminalAgentLoop(
            runtime=TerminalRuntime(
                terminal_id="terminal-web-01",
                hostname="workstation-web",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
                max_parallel_tasks=1,
            ),
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15442"),
            sleep_fn=lambda _: None,
        )
        loop.run(cycles=1, interval_seconds=0)

        print(
            {
                "dashboard_url": "http://127.0.0.1:8777/dashboard",
                "terminal_count": len(nas_client.list_terminals()["items"]),
                "task_count": len(nas_client.list_tasks("terminal-web-01")["items"]),
            }
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
