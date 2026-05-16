"""Quick verification script for the real probe worker BitBrowser call path."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import BitBrowserClient
from terminal_agent.scripts import ScriptWorkerRegistry


class MockBitBrowserHandler(BaseHTTPRequestHandler):
    """Mock BitBrowser endpoints used by the probe worker."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8")) if raw else {}

        if self.path == "/browser/open":
            body = {
                "success": True,
                "data": {
                    "id": payload.get("id"),
                    "args": payload.get("args", []),
                    "queue": payload.get("queue", True),
                    "ws": "ws://127.0.0.1:53325/devtools/browser/mock",
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
        """Silence local mock logging."""


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 15438), MockBitBrowserHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        time.sleep(0.2)
        registry = ScriptWorkerRegistry()
        execution = registry.execute(
            TaskAssignmentPayload(
                task_id="task-probe-01",
                terminal_id="terminal-probe-01",
                instance_id="browser-probe-01",
                script_name="probe",
                parameters={"target_url": "https://x.com/explore"},
                priority=1,
            ),
            terminal_hostname="workstation-probe",
            bitbrowser_client=BitBrowserClient("http://127.0.0.1:15438"),
        )
        print(
            json.dumps(
                {
                    "run_status": execution.run.status,
                    "result_status": execution.result.status,
                    "summary": execution.result.summary,
                    "step_count": execution.result.details.get("step_count"),
                    "step_names": [step["name"] for step in execution.result.details.get("steps", [])],
                    "details": execution.result.details,
                },
                separators=(",", ":"),
            )
        )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
