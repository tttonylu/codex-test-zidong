"""Verification script for NAS management queries and text views."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nas_control_plane.server import create_server
from nas_control_plane.views import (
    render_collection,
    render_instance_summary,
    render_log_summary,
    render_task_summary,
    render_terminal_summary,
)
from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.runtime import TerminalAgentLoop, TerminalRuntime


def _from_dict(payload: dict[str, object]) -> object:
    """Convert a JSON response item back to a light-weight namespace."""

    from types import SimpleNamespace

    return SimpleNamespace(**payload)


class MockBitBrowserHandler(BaseHTTPRequestHandler):
    """Small local mock for BitBrowser scan endpoints."""

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
                            "id": "bb-mgmt-1",
                            "remark": "Mgmt_User",
                            "status": 1,
                            "name": "Mgmt Browser",
                            "seq": 61,
                            "groupId": "g-mgmt",
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
                    "ws": "ws://127.0.0.1:53325/devtools/browser/mock-mgmt",
                    "http": "127.0.0.1:53325",
                },
            }
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
    state_path = Path("nas_control_plane/state.management-queries.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8775, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15440), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8775")
        nas_client.register_terminal(
            TerminalRuntime(
                terminal_id="terminal-mgmt-01",
                hostname="workstation-mgmt",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
            ).registration_payload()
        )
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-mgmt-01",
                terminal_id="terminal-mgmt-01",
                instance_id="bb-mgmt-1",
                script_name="follow",
                parameters={"target_handle": "mgmt_user"},
                priority=7,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-mgmt-02",
                terminal_id="terminal-mgmt-01",
                instance_id="bb-mgmt-1",
                script_name="chat",
                parameters={"target_handle": "mgmt_user_b"},
                priority=3,
                retry_limit=2,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-mgmt-01",
            hostname="workstation-mgmt",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
            max_parallel_tasks=1,
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15440"),
            sleep_fn=lambda _: None,
        )
        loop.run(cycles=1, interval_seconds=0)

        terminals = nas_client.list_terminals()["items"]
        instances = nas_client.list_instances()["items"]
        tasks = nas_client.query_tasks(terminal_id="terminal-mgmt-01")["items"]
        logs = nas_client.query_logs(terminal_id="terminal-mgmt-01")["items"]

        print(
            "\n\n".join(
                [
                    render_collection("Terminals", [render_terminal_summary(_from_dict(item)) for item in terminals]),
                    render_collection("Instances", [render_instance_summary(_from_dict(item)) for item in instances]),
                    render_collection("Tasks", [render_task_summary(_from_dict(item)) for item in tasks]),
                    render_collection("Logs", [render_log_summary(_from_dict(item)) for item in logs]),
                ]
            )
        )
    finally:
        loop.shutdown()
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()
        if state_path.exists():
            state_path.unlink()


if __name__ == "__main__":
    main()
