"""Verification script for NAS JSON persistence across server recreation."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nas_control_plane.server import create_server
from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.runtime import TerminalAgentLoop, TerminalRuntime


class MockBitBrowserHandler(BaseHTTPRequestHandler):
    """Mock BitBrowser endpoints used by the persistence demo."""

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
                                "id": "bb-persist-1",
                                "remark": "Persist_User",
                                "status": 1,
                                "name": "Persist Browser",
                                "seq": 41,
                                "groupId": "g-persist",
                            }
                        ]
                    },
                }
            else:
                body = {"success": True, "data": {"list": []}}
        elif self.path == "/browser/open":
            body = {
                "success": True,
                "data": {
                    "id": payload.get("id"),
                    "args": payload.get("args", []),
                    "queue": payload.get("queue", True),
                    "ws": "ws://127.0.0.1:53325/devtools/browser/mock-persist",
                    "http": "127.0.0.1:53325",
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
    state_path = Path("nas_control_plane/state.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    nas = create_server(port=8772, state_path=state_path)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15441), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)

        nas_client = NasControlPlaneClient("http://127.0.0.1:8772")
        nas_client.create_task(
            TaskAssignmentPayload(
                task_id="task-persist-01",
                terminal_id="terminal-persist-01",
                instance_id="bb-persist-1",
                script_name="follow",
                parameters={"target_handle": "persist_user"},
                priority=1,
            )
        )

        runtime = TerminalRuntime(
            terminal_id="terminal-persist-01",
            hostname="workstation-persist",
            operator_name="codex",
            agent_version="0.1.0",
            capabilities=["bitbrowser.scan", "task.execute"],
        )
        loop = TerminalAgentLoop(
            runtime=runtime,
            nas_client=nas_client,
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15441"),
            sleep_fn=lambda _: None,
        )
        loop.run(cycles=1, interval_seconds=0)
    finally:
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()

    reloaded = create_server(port=8773, state_path=state_path)
    reload_thread = threading.Thread(target=reloaded.serve_forever, daemon=True)
    reload_thread.start()

    try:
        time.sleep(0.3)
        reloaded_client = NasControlPlaneClient("http://127.0.0.1:8773")
        terminals = reloaded_client.list_terminals()
        instances = reloaded_client.list_instances()
        tasks = reloaded_client.list_tasks("terminal-persist-01")
        logs = reloaded_client.list_logs()
        with sqlite3.connect(state_path) as connection:
            table_rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        table_names = [row[0] for row in table_rows]
        print(
            json.dumps(
                {
                    "terminal_count": len(terminals["items"]),
                    "instance_count": len(instances["items"]),
                    "task_statuses": [item["status"] for item in tasks["items"]],
                    "log_count": len(logs["items"]),
                    "tables": table_names,
                },
                separators=(",", ":"),
            )
        )
    finally:
        reloaded.shutdown()
        reloaded.server_close()
        reload_thread.join(timeout=1)
        time.sleep(0.2)
        if state_path.exists():
            try:
                state_path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
