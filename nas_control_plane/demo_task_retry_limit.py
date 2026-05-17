"""Verification script for task retry limit enforcement."""

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
            body = {
                "success": True,
                "data": {
                    "list": [
                        {
                            "id": "bb-retry-1",
                            "remark": "Retry_User",
                            "status": 1,
                            "name": "Retry Browser",
                            "seq": 51,
                            "groupId": "g-retry",
                        }
                    ]
                },
            }
        elif self.path == "/browser/open":
            # 中文说明：这里故意让 open 失败，专门压测 retry 上限链路。
            body = {"success": False, "msg": "open failed for retry demo"}
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
    nas = create_server(port=8774)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15439), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8774")
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-retry-limit-01",
                terminal_id="terminal-retry-01",
                instance_id="bb-retry-1",
                script_name="follow",
                parameters={"target_handle": "retry_user"},
                priority=9,
                retry_limit=1,
                close_after_actions=True,
                requested_by="demo",
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-retry-01",
            hostname="workstation-retry",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15439"),
            sleep_fn=lambda _: None,
        )

        first_cycle = loop.run(cycles=1, interval_seconds=0)
        first_retry = nas_client.retry_task("task-retry-limit-01", requested_by="demo")
        second_cycle = loop.run(cycles=1, interval_seconds=0)
        blocked_retry = nas_client.retry_task("task-retry-limit-01", requested_by="demo")

        tasks = nas_client.list_tasks("terminal-retry-01")
        print(
            json.dumps(
                {
                    "first_cycle": first_cycle,
                    "second_cycle": second_cycle,
                    "first_retry_status": first_retry["status"],
                    "blocked_retry_status": blocked_retry["status"],
                    "task_status": tasks["items"][0]["status"],
                    "task_attempt_count": tasks["items"][0]["attempt_count"],
                    "task_retryable": tasks["items"][0]["retryable"],
                    "task_final": tasks["items"][0]["final"],
                    "retry_blocked_reason": tasks["items"][0]["parameters"].get("retry_blocked_reason"),
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
