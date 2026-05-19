"""Memory API routes for the NAS control plane.

Adds mem0-powered memory endpoints to the NAS HTTP server.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

from shared.memory import WorkspaceMemoryService


class MemoryRouter:
    """Mixin-style router that dispatches ``/memory/*`` requests."""

    def __init__(self, memory_service: WorkspaceMemoryService | None = None) -> None:
        self._memory = memory_service or WorkspaceMemoryService()

    # ── public access for server.py injection ──────────────────

    @property
    def memory(self) -> WorkspaceMemoryService:
        return self._memory

    # ── dispatch ───────────────────────────────────────────────

    def dispatch_memory(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Return True if the path was handled."""
        # ── GET ──────────────────────────────────────────────
        if handler.command == "GET":
            if path == "/memory":
                self._handle_list(handler)
                return True
            if path.startswith("/memory/") and len(path) > len("/memory/"):
                mem_id = path.split("/memory/", 1)[1]
                if "/" not in mem_id:
                    self._handle_get(handler, mem_id)
                    return True

        # ── POST ─────────────────────────────────────────────
        if handler.command == "POST":
            if path == "/memory/add":
                self._handle_add(handler)
                return True
            if path == "/memory/search":
                self._handle_search(handler)
                return True
            if path == "/memory/remember":
                self._handle_remember(handler)
                return True

        # ── DELETE ───────────────────────────────────────────
        if handler.command == "DELETE":
            if path.startswith("/memory/") and len(path) > len("/memory/"):
                mem_id = path.split("/memory/", 1)[1]
                if "/" not in mem_id:
                    self._handle_delete(handler, mem_id)
                    return True
            if path == "/memory":
                self._handle_delete_all(handler)
                return True

        return False

    # ── handlers ───────────────────────────────────────────────

    def _read_body(self, handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        length = int(handler.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = handler.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, handler: BaseHTTPRequestHandler, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=True, default=str).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _handle_add(self, handler: BaseHTTPRequestHandler) -> None:
        body = self._read_body(handler)
        messages = body.get("messages", body.get("message", ""))
        result = self._memory.add(
            messages,
            user_id=body.get("user_id"),
            agent_id=body.get("agent_id"),
            run_id=body.get("run_id"),
            metadata=body.get("metadata"),
            infer=body.get("infer", True),
        )
        self._send_json(handler, {"ok": True, "result": result})

    def _handle_search(self, handler: BaseHTTPRequestHandler) -> None:
        body = self._read_body(handler)
        query = body.get("query", "")
        if not query:
            self._send_json(handler, {"ok": False, "error": "query is required"}, HTTPStatus.BAD_REQUEST)
            return
        result = self._memory.search(
            query,
            user_id=body.get("user_id"),
            agent_id=body.get("agent_id"),
            run_id=body.get("run_id"),
            top_k=body.get("top_k", 10),
        )
        self._send_json(handler, {"ok": True, "results": result.get("results", [])})

    def _handle_list(self, handler: BaseHTTPRequestHandler) -> None:
        params = _parse_query_params(handler.path)
        filters: dict[str, Any] = {}
        if "user_id" in params:
            filters["user_id"] = params["user_id"]
        if "agent_id" in params:
            filters["agent_id"] = params["agent_id"]
        if "run_id" in params:
            filters["run_id"] = params["run_id"]
        top_k = int(params.get("top_k", 50))
        results = self._memory.get_all(filters=filters or None, top_k=top_k)
        self._send_json(handler, {"ok": True, "results": results, "count": len(results)})

    def _handle_get(self, handler: BaseHTTPRequestHandler, mem_id: str) -> None:
        result = self._memory.get(mem_id)
        if result is None:
            self._send_json(handler, {"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(handler, {"ok": True, "result": result})

    def _handle_remember(self, handler: BaseHTTPRequestHandler) -> None:
        body = self._read_body(handler)
        fact = body.get("fact", "")
        if not fact:
            self._send_json(handler, {"ok": False, "error": "fact is required"}, HTTPStatus.BAD_REQUEST)
            return
        result = self._memory.remember_fact(
            fact,
            user_id=body.get("user_id"),
            agent_id=body.get("agent_id"),
            tags=body.get("tags"),
        )
        self._send_json(handler, {"ok": True, "result": result})

    def _handle_delete(self, handler: BaseHTTPRequestHandler, mem_id: str) -> None:
        self._memory.delete(mem_id)
        self._send_json(handler, {"ok": True})

    def _handle_delete_all(self, handler: BaseHTTPRequestHandler) -> None:
        body = self._read_body(handler)
        self._memory.delete_all(
            user_id=body.get("user_id"),
            agent_id=body.get("agent_id"),
            run_id=body.get("run_id"),
        )
        self._send_json(handler, {"ok": True})


def _parse_query_params(path: str) -> dict[str, str]:
    """Extract query parameters from a request path."""
    if "?" not in path:
        return {}
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(path)
    return {k: v[0] for k, v in parse_qs(parsed.query).items()}
