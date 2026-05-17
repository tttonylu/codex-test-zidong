"""Minimal NAS HTTP server for terminal registration and state sync."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote_plus

from nas_control_plane.dashboard_html import DASHBOARD_HTML
from nas_control_plane.services import (
    AuditLogRepository,
    AuditService,
    JsonStateStore,
    TaskDispatchService,
    TaskRepository,
    TerminalRegistryService,
    TerminalStateRepository,
)
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    state_path: str | Path = "nas_control_plane/state.json",
    now_fn: Callable[[], datetime] | None = None,
) -> ThreadingHTTPServer:
    """Create an HTTP server instance backed by a JSON state store."""

    store = JsonStateStore(state_path)
    terminal_repository = TerminalStateRepository(store)
    task_repository = TaskRepository(store)
    audit_repository = AuditLogRepository(store)

    registry = TerminalRegistryService(repository=terminal_repository)
    tasks = TaskDispatchService(repository=task_repository, now_fn=now_fn)
    audit = AuditService(repository=audit_repository)

    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "BPlusNAS/0.1"

        def do_GET(self) -> None:  # noqa: N802
            path = self._path_without_query()

            if path == "/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if path == "/dashboard":
                self._send_html(HTTPStatus.OK, DASHBOARD_HTML)
                return

            if path == "/terminals":
                payload = [
                    _record_to_dict(record)
                    for record in registry.list_terminals(
                        status=self._query_param("status"),
                        operator_name=self._query_param("operator_name"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/instances":
                payload = [
                    _record_to_dict(record)
                    for record in registry.list_instances(
                        terminal_id=self._query_param("terminal_id"),
                        runtime_status=self._query_param("runtime_status"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/logs":
                payload = [
                    _record_to_dict(record)
                    for record in audit.query_logs(
                        terminal_id=self._query_param("terminal_id"),
                        task_id=self._query_param("task_id"),
                        level=self._query_param("level"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/tasks":
                payload = [
                    _record_to_dict(record)
                    for record in tasks.query_tasks(
                        terminal_id=self._query_param("terminal_id"),
                        status=self._query_param("status"),
                        script_name=self._query_param("script_name"),
                        retryable=_parse_bool(self._query_param("retryable")),
                        final=_parse_bool(self._query_param("final")),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path.startswith("/task/"):
                task_id = path.split("/task/", 1)[1]
                self._send_json(HTTPStatus.OK, _record_to_dict(tasks.get_task(task_id)))
                return

            if path.startswith("/terminal/"):
                terminal_id = path.split("/terminal/", 1)[1]
                self._send_json(HTTPStatus.OK, _record_to_dict(registry.get_terminal(terminal_id)))
                return

            if path.startswith("/instance/"):
                instance_id = path.split("/instance/", 1)[1]
                self._send_json(HTTPStatus.OK, _record_to_dict(registry.get_instance(instance_id)))
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()

                if self.path == "/register":
                    record = registry.register_terminal(_parse_registration(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/heartbeat":
                    record = registry.record_heartbeat(_parse_heartbeat(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/instances/sync":
                    terminal_id = payload["terminal_id"]
                    snapshots = [_parse_snapshot(item) for item in payload.get("items", [])]
                    records = registry.sync_instances(terminal_id, snapshots)
                    self._send_json(
                        HTTPStatus.OK,
                        {"terminal_id": terminal_id, "items": [_record_to_dict(record) for record in records]},
                    )
                    return

                if self.path == "/tasks":
                    record = tasks.create_task(_parse_task(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/tasks/claim":
                    terminal_id = payload["terminal_id"]
                    max_tasks = payload.get("max_tasks")
                    records = tasks.claim_tasks(terminal_id, limit=int(max_tasks) if max_tasks is not None else None)
                    self._send_json(
                        HTTPStatus.OK,
                        {"terminal_id": terminal_id, "items": [_record_to_dict(record) for record in records]},
                    )
                    return

                if self.path == "/tasks/result":
                    result = _parse_action_result(payload)
                    task_record = tasks.record_result(result)
                    log_record = audit.record_action_result(result)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "task": _record_to_dict(task_record),
                            "log": _record_to_dict(log_record),
                        },
                    )
                    return

                if self.path == "/tasks/retry":
                    task_id = payload["task_id"]
                    record = tasks.retry_task(task_id, requested_by=payload.get("requested_by"))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/tasks/cancel":
                    task_id = payload["task_id"]
                    record = tasks.cancel_task(task_id, requested_by=payload.get("requested_by"))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/tasks/running":
                    run = _parse_script_run(payload)
                    task_record = tasks.mark_running(run)
                    self._send_json(HTTPStatus.OK, _record_to_dict(task_record))
                    return
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"missing field: {exc.args[0]}"})
                return
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """Silence default request logging to keep local runs clean."""

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            if not raw_body:
                return {}
            return json.loads(raw_body)

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status: HTTPStatus, body: str) -> None:
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _query_param(self, name: str) -> str | None:
            raw_path = self.path.split("?", 1)
            if len(raw_path) == 1:
                return None

            for item in raw_path[1].split("&"):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                if key == name:
                    return unquote_plus(value)
            return None

        def _path_without_query(self) -> str:
            return self.path.split("?", 1)[0]

    return ThreadingHTTPServer((host, port), RequestHandler)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    state_path: str | Path = "nas_control_plane/state.json",
) -> None:
    """Start the NAS server and block forever."""

    server = create_server(host=host, port=port, state_path=state_path)
    print(f"nas_control_plane listening on http://{host}:{port}")
    server.serve_forever()


def _parse_registration(payload: dict[str, Any]) -> TerminalRegistrationPayload:
    return TerminalRegistrationPayload(
        terminal_id=payload["terminal_id"],
        hostname=payload["hostname"],
        operator_name=payload["operator_name"],
        agent_version=payload["agent_version"],
        capabilities=list(payload.get("capabilities", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def _parse_heartbeat(payload: dict[str, Any]) -> HeartbeatPayload:
    reported_at_raw = payload["reported_at"]
    return HeartbeatPayload(
        terminal_id=payload["terminal_id"],
        reported_at=datetime.fromisoformat(reported_at_raw),
        status=payload["status"],
        active_instance_count=int(payload["active_instance_count"]),
        queued_task_count=int(payload["queued_task_count"]),
        metadata=dict(payload.get("metadata", {})),
    )


def _parse_snapshot(payload: dict[str, Any]) -> InstanceSnapshotPayload:
    return InstanceSnapshotPayload(
        terminal_id=payload["terminal_id"],
        instance_id=payload["instance_id"],
        profile_id=payload["profile_id"],
        handle=payload.get("handle"),
        runtime_status=payload["runtime_status"],
        window_id=payload.get("window_id"),
        remark=payload.get("remark"),
        metadata=dict(payload.get("metadata", {})),
    )


def _parse_task(payload: dict[str, Any]) -> TaskAssignmentPayload:
    return TaskAssignmentPayload(
        task_id=payload["task_id"],
        terminal_id=payload["terminal_id"],
        instance_id=payload.get("instance_id"),
        script_name=payload["script_name"],
        parameters=dict(payload.get("parameters", {})),
        priority=int(payload.get("priority", 0)),
        retry_limit=int(payload.get("retry_limit", 0)),
        close_after_actions=bool(payload.get("close_after_actions", False)),
        requested_by=payload.get("requested_by"),
        metadata=dict(payload.get("metadata", {})),
    )


def _parse_action_result(payload: dict[str, Any]) -> ActionResultPayload:
    emitted_at_raw = payload.get("emitted_at")
    emitted_at = datetime.fromisoformat(emitted_at_raw) if emitted_at_raw else datetime.utcnow()
    return ActionResultPayload(
        run_id=payload["run_id"],
        task_id=payload["task_id"],
        terminal_id=payload["terminal_id"],
        status=payload["status"],
        summary=payload["summary"],
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        retryable=payload.get("retryable"),
        final=payload.get("final"),
        details=dict(payload.get("details", {})),
        emitted_at=emitted_at,
    )


def _parse_script_run(payload: dict[str, Any]) -> ScriptRunPayload:
    started_at_raw = payload.get("started_at")
    finished_at_raw = payload.get("finished_at")
    return ScriptRunPayload(
        run_id=payload["run_id"],
        task_id=payload["task_id"],
        terminal_id=payload["terminal_id"],
        instance_id=payload.get("instance_id"),
        script_name=payload["script_name"],
        status=payload["status"],
        started_at=datetime.fromisoformat(started_at_raw) if started_at_raw else None,
        finished_at=datetime.fromisoformat(finished_at_raw) if finished_at_raw else None,
        metadata=dict(payload.get("metadata", {})),
        step_count=int(payload.get("step_count", 0)),
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        retryable=payload.get("retryable"),
        final=payload.get("final"),
    )


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {raw}")


def _record_to_dict(record: Any) -> dict[str, Any]:
    data = asdict(record)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


if __name__ == "__main__":
    run_server()
