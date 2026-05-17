"""Verification script for active-task-aware claim capacity."""

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
    """Small local mock for active-slot capacity verification."""

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = {"success": True}
        elif self.path == "/browser/list":
            body = {
                "success": True,
                "data": {
                    "list": [
                        {
                            "id": "bb-capacity-1",
                            "remark": "Capacity_User",
                            "status": 1,
                            "name": "Capacity Browser",
                            "seq": 101,
                            "groupId": "g-capacity",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            body = {"success": True, "data": {"id": "bb-capacity-1", "args": []}}
        elif self.path == "/browser/close":
            body = {"success": True, "data": {"id": "bb-capacity-1", "closed": True}}
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
    state_path = Path("nas_control_plane/state.active-slot-capacity.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8782, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15446), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        client = NasControlPlaneClient("http://127.0.0.1:8782")
        client.create_task(
            TaskAssignmentPayload(
                task_id="task-capacity-01",
                terminal_id="terminal-capacity-01",
                instance_id="bb-capacity-1",
                script_name="follow",
                parameters={"target_handle": "capacity_user"},
                priority=10,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-capacity-01",
            hostname="workstation-capacity",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
            max_parallel_tasks=1,
        )
        runtime.set_active_task_count(1)
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15446"),
            sleep_fn=lambda _: None,
        )
        cycle = loop.run(cycles=1, interval_seconds=0)
        tasks = client.query_tasks(terminal_id="terminal-capacity-01")["items"]
        terminal = client.get_terminal("terminal-capacity-01")

        print(
            json.dumps(
                {
                    "cycle": cycle,
                    "task_status": tasks[0]["status"],
                    "claimed_tasks": cycle[0]["claimed_tasks"],
                    "terminal_active_task_count": terminal["metadata"].get("active_task_count"),
                    "terminal_max_parallel_tasks": terminal["metadata"].get("max_parallel_tasks"),
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
