"""Verification script for terminal-side slot-limited execution."""

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
    """Small local mock for slot-limited execution verification."""

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
                            "id": "bb-slot-1",
                            "remark": "Slot_User",
                            "status": 1,
                            "name": "Slot Browser",
                            "seq": 81,
                            "groupId": "g-slot",
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
    state_path = Path("nas_control_plane/state.slot-limited.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8781, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15445), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        client = NasControlPlaneClient("http://127.0.0.1:8781")
        for index in range(1, 4):
            client.create_task(
                TaskAssignmentPayload(
                    task_id=f"task-slot-0{index}",
                    terminal_id="terminal-slot-01",
                    instance_id="bb-slot-1",
                    script_name="follow",
                    parameters={"target_handle": f"slot_user_{index}"},
                    priority=10 - index,
                    retry_limit=1,
                    close_after_actions=True,
                    requested_by="demo",
                )
            )

        loop = TerminalAgentLoop(
            runtime=TerminalRuntime(
                terminal_id="terminal-slot-01",
                hostname="workstation-slot",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
                max_parallel_tasks=1,
            ),
            nas_client=client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15445"),
            sleep_fn=lambda _: None,
        )
        cycles = loop.run(cycles=3, interval_seconds=0)
        tasks = client.query_tasks(terminal_id="terminal-slot-01")["items"]

        print(
            json.dumps(
                {
                    "cycles": cycles,
                    "completed_task_ids": [item["task_id"] for item in tasks if item["status"] == "completed"],
                    "task_statuses": {item["task_id"]: item["status"] for item in tasks},
                    "attempt_counts": {item["task_id"]: item["attempt_count"] for item in tasks},
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
