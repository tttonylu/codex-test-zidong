"""Verification script for NAS task and terminal query filters."""

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
    """Small local mock for query filter verification."""

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
                            "id": "bb-filter-1",
                            "remark": "Filter_User",
                            "status": 1,
                            "name": "Filter Browser",
                            "seq": 121,
                            "groupId": "g-filter",
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
    state_path = Path("nas_control_plane/state.query-filters.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8789, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15451), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        client = NasControlPlaneClient("http://127.0.0.1:8789")
        for index in range(1, 3):
            client.create_task(
                TaskAssignmentPayload(
                    task_id=f"task-filter-0{index}",
                    terminal_id="terminal-filter-01",
                    instance_id="bb-filter-1",
                    script_name="follow" if index == 1 else "chat",
                    parameters={"target_handle": f"filter_user_{index}"},
                    priority=10 - index,
                    retry_limit=1,
                    close_after_actions=False,
                    requested_by="demo",
                )
            )

        loop = TerminalAgentLoop(
            runtime=TerminalRuntime(
                terminal_id="terminal-filter-01",
                hostname="workstation-filter",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
                max_parallel_tasks=1,
            ),
            nas_client=client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15451"),
            sleep_fn=lambda _: None,
        )
        loop.run(cycles=1, interval_seconds=0)

        filtered_tasks = client.query_tasks(
            terminal_id="terminal-filter-01",
            wait_reason="slot_capacity_reached",
        )["items"]
        filtered_terminals = client.list_terminals(
            max_parallel_tasks=1,
            min_active_task_count=0,
        )["items"]

        print(
            json.dumps(
                {
                    "filtered_task_ids": [item["task_id"] for item in filtered_tasks],
                    "filtered_wait_reasons": [item["parameters"].get("wait_reason") for item in filtered_tasks],
                    "filtered_terminal_ids": [item["terminal_id"] for item in filtered_terminals],
                    "filtered_terminal_max_parallel_tasks": [
                        item["metadata"].get("max_parallel_tasks") for item in filtered_terminals
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
