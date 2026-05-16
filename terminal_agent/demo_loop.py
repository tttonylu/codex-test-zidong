"""Local verification script for the periodic agent loop."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
                                "id": "bb-loop-1",
                                "remark": "User_Loop",
                                "status": 1,
                                "name": "Loop Browser A",
                                "seq": 21,
                                "groupId": "g-loop",
                            }
                        ]
                    },
                }
            else:
                body = {"success": True, "data": {"list": []}}
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
    nas = create_server(port=8770)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15436), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8770")
        task = TaskAssignmentPayload(
            task_id="task-loop-01",
            terminal_id="terminal-loop-01",
            instance_id=None,
            script_name="follow",
            parameters={"target_handle": "user_loop"},
            priority=10,
        )
        nas_client.create_task(task)

        runtime = TerminalRuntime(
            terminal_id="terminal-loop-01",
            hostname="workstation-loop",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15436"),
            sleep_fn=lambda _: None,
        )
        cycle_results = loop.run(cycles=2, interval_seconds=0)
        tasks = nas_client.list_tasks("terminal-loop-01")
        terminals = nas_client.list_terminals()
        instances = nas_client.list_instances()

        print(
            json.dumps(
                {
                    "cycle_results": cycle_results,
                    "task_statuses": [item["status"] for item in tasks["items"]],
                    "terminal_count": len(terminals["items"]),
                    "instance_count": len(instances["items"]),
                },
                separators=(",", ":"),
            )
        )
    finally:
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()


if __name__ == "__main__":
    main()
