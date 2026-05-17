"""Verification script for instance-aware task claim mutex behavior."""

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
    """Small local mock for instance mutex claim verification."""

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
                            "id": "bb-mutex-1",
                            "remark": "Mutex_User_A",
                            "status": 1,
                            "name": "Mutex Browser A",
                            "seq": 111,
                            "groupId": "g-mutex",
                        },
                        {
                            "id": "bb-mutex-2",
                            "remark": "Mutex_User_B",
                            "status": 1,
                            "name": "Mutex Browser B",
                            "seq": 112,
                            "groupId": "g-mutex",
                        },
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
    state_path = Path("nas_control_plane/state.instance-mutex.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=0, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 0), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_port = nas.server_address[1]
        bitbrowser_port = bitbrowser.server_address[1]
        client = NasControlPlaneClient(f"http://127.0.0.1:{nas_port}")
        tasks = [
            TaskAssignmentPayload(
                task_id="task-mutex-01",
                terminal_id="terminal-mutex-01",
                instance_id="bb-mutex-1",
                script_name="follow",
                parameters={"target_handle": "mutex_user_a"},
                priority=10,
                retry_limit=1,
                close_after_actions=False,
                requested_by="demo",
            ),
            TaskAssignmentPayload(
                task_id="task-mutex-02",
                terminal_id="terminal-mutex-01",
                instance_id="bb-mutex-1",
                script_name="chat",
                parameters={"target_handle": "mutex_user_b"},
                priority=9,
                retry_limit=1,
                close_after_actions=False,
                requested_by="demo",
            ),
            TaskAssignmentPayload(
                task_id="task-mutex-03",
                terminal_id="terminal-mutex-01",
                instance_id="bb-mutex-2",
                script_name="probe",
                parameters={"target_handle": "mutex_user_c"},
                priority=8,
                retry_limit=1,
                close_after_actions=False,
                requested_by="demo",
            ),
        ]
        for item in tasks:
            client.create_task(item)

        loop = TerminalAgentLoop(
            runtime=TerminalRuntime(
                terminal_id="terminal-mutex-01",
                hostname="workstation-mutex",
                operator_name="codex",
                agent_version="0.1.0",
                capabilities=["bitbrowser.scan", "task.execute"],
                max_parallel_tasks=2,
            ),
            nas_client=client,
            bitbrowser_client=BitBrowserClient(f"http://127.0.0.1:{bitbrowser_port}"),
            sleep_fn=lambda _: None,
        )
        claim_debug: list[dict[str, object]] = []
        original_claim = client.claim_tasks

        def debug_claim(
            terminal_id: str,
            max_tasks: int | None = None,
            blocked_instance_ids: list[str] | None = None,
        ) -> dict[str, object]:
            response = original_claim(
                terminal_id,
                max_tasks=max_tasks,
                blocked_instance_ids=blocked_instance_ids,
            )
            claim_debug.append(
                {
                    "terminal_id": terminal_id,
                    "max_tasks": max_tasks,
                    "blocked_instance_ids": list(blocked_instance_ids or []),
                    "response_count": len(response.get("items", [])),
                    "response_task_ids": [item["task_id"] for item in response.get("items", [])],
                }
            )
            return response

        client.claim_tasks = debug_claim  # type: ignore[method-assign]
        first_cycle = loop.run(cycles=1, interval_seconds=0)
        after_first = client.query_tasks(terminal_id="terminal-mutex-01")["items"]
        second_cycle = loop.run(cycles=1, interval_seconds=0)
        results = client.query_tasks(terminal_id="terminal-mutex-01")["items"]

        print(
            json.dumps(
                {
                    "claim_debug": claim_debug,
                    "first_cycle": first_cycle,
                    "after_first_cycle_statuses": {item["task_id"]: item["status"] for item in after_first},
                    "second_cycle": second_cycle,
                    "task_statuses": {item["task_id"]: item["status"] for item in results},
                    "attempt_counts": {item["task_id"]: item["attempt_count"] for item in results},
                    "run_ids": {item["task_id"]: item["parameters"].get("run_id") for item in results},
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
