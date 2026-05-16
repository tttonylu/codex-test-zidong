"""Local verification script for BitBrowser scan plus NAS sync."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nas_control_plane.server import create_server
from terminal_agent.demo_scan_and_sync import run_scan_and_sync_demo


class MockBitBrowserHandler(BaseHTTPRequestHandler):
    """Small local mock that exposes the BitBrowser endpoints used by the demo."""

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
                                "id": "bb-1",
                                "remark": "User_A",
                                "status": 1,
                                "name": "Browser A",
                                "seq": 11,
                                "groupId": "g1",
                            },
                            {
                                "id": "bb-2",
                                "remark": "user_b",
                                "status": 0,
                                "name": "Browser B",
                                "seq": 12,
                                "groupId": "g1",
                            },
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
    nas = create_server(port=8769)
    bitbrowser = ThreadingHTTPServer(("127.0.0.1", 15435), MockBitBrowserHandler)

    nas_thread = threading.Thread(target=nas.serve_forever, daemon=True)
    bit_thread = threading.Thread(target=bitbrowser.serve_forever, daemon=True)
    nas_thread.start()
    bit_thread.start()

    try:
        time.sleep(0.3)
        result = run_scan_and_sync_demo(
            nas_base_url="http://127.0.0.1:8769",
            bitbrowser_base_url="http://127.0.0.1:15435",
        )
        print(json.dumps(result, separators=(",", ":")))
    finally:
        bitbrowser.shutdown()
        nas.shutdown()
        bitbrowser.server_close()
        nas.server_close()


if __name__ == "__main__":
    main()
