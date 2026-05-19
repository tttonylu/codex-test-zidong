"""Local SSE proxy that filters out {"type":"ping"} keep-alive events."""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

UPSTREAM_BASE = os.environ.get("UPSTREAM_URL", "https://thisis.best/v1").rstrip("/")
STRIP_PREFIX = os.environ.get("STRIP_PREFIX", "/v1").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "18765"))

HEADERS_TO_REMOVE = {"host", "connection", "transfer-encoding", "content-encoding"}


class ProxyHandler(BaseHTTPRequestHandler):
    def _upstream_path(self) -> str:
        path = self.path
        if STRIP_PREFIX and path.startswith(STRIP_PREFIX):
            path = path[len(STRIP_PREFIX):]
        return f"{UPSTREAM_BASE}{path}"

    def _build_upstream_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for k, v in self.headers.items():
            if k.lower() not in HEADERS_TO_REMOVE:
                headers[k] = v
        if API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"
        return headers

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 0:
            return self.rfile.read(length)
        return None

    def _filter_stream(self, upstream_resp) -> None:
        self.send_response(upstream_resp.status)
        for k, v in upstream_resp.headers.items():
            if k.lower() not in HEADERS_TO_REMOVE:
                self.send_header(k, v)
        self.end_headers()

        buf = b""
        while True:
            chunk = upstream_resp.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.startswith(b"data: ") and line.strip() == b"data: {\"type\":\"ping\"}":
                    continue
                self.wfile.write(line + b"\n")
                self.wfile.flush()
        if buf:
            self.wfile.write(buf)
            self.wfile.flush()

    def _forward(self, body: bytes | None) -> None:
        headers = self._build_upstream_headers()
        req = Request(self._upstream_path(), data=body, headers=headers, method=self.command)
        try:
            resp = urlopen(req, timeout=120)
        except HTTPError as e:
            resp = e

        content_type = resp.headers.get("Content-Type", "")
        if "text/event-stream" in content_type and resp.status == 200:
            self._filter_stream(resp)
        else:
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in HEADERS_TO_REMOVE:
                    self.send_header(k, v)
            self.end_headers()
            chunk = resp.read(8192)
            while chunk:
                self.wfile.write(chunk)
                chunk = resp.read(8192)
            self.wfile.flush()

    def do_GET(self) -> None:
        self._forward(None)

    def do_POST(self) -> None:
        body = self._read_body()
        self._forward(body)

    def do_DELETE(self) -> None:
        self._forward(None)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[SSE Proxy] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", LISTEN_PORT), ProxyHandler)
    print(f"SSE Proxy listening on http://127.0.0.1:{LISTEN_PORT} -> {UPSTREAM_BASE}")
    print(f"Filtering out ping events. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
