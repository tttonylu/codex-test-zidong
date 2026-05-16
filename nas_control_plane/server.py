"""Minimal NAS HTTP server for terminal registration and state sync."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from nas_control_plane.services import (
    AuditService,
    SqliteAuditLogRepository,
    SqliteStateStore,
    SqliteTaskEventRepository,
    TaskDispatchService,
    SqliteTaskRepository,
    TerminalRegistryService,
    SqliteTerminalStateRepository,
)
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TaskControlPayload,
    TerminalRegistrationPayload,
)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    state_path: str | Path = "nas_control_plane/state.sqlite3",
) -> ThreadingHTTPServer:
    """Create an HTTP server instance backed by a SQLite state store."""

    store = SqliteStateStore(state_path)
    terminal_repository = SqliteTerminalStateRepository(store)
    task_repository = SqliteTaskRepository(store)
    audit_repository = SqliteAuditLogRepository(store)
    task_event_repository = SqliteTaskEventRepository(store)

    registry = TerminalRegistryService(repository=terminal_repository)
    tasks = TaskDispatchService(repository=task_repository)
    audit = AuditService(repository=audit_repository)

    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "BPlusNAS/0.1"

        def do_GET(self) -> None:  # noqa: N802
            route, query = self._route()

            if route == "/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if route == "/terminals":
                status = _query_value(query, "status")
                terminals = [_record_to_dict(record) for record in registry.list_terminals(status=status)]
                self._send_json(HTTPStatus.OK, {"items": terminals})
                return

            if route.startswith("/terminals/"):
                terminal_id = route.rsplit("/", 1)[-1]
                record = registry.get_terminal(terminal_id)
                if record is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "terminal not found"})
                    return
                self._send_json(HTTPStatus.OK, _record_to_dict(record))
                return

            if route == "/instances":
                terminal_id = _query_value(query, "terminal_id")
                runtime_status = _query_value(query, "runtime_status")
                instances = [
                    _record_to_dict(record)
                    for record in registry.list_instances(
                        terminal_id=terminal_id,
                        runtime_status=runtime_status,
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": instances})
                return

            if route.startswith("/instances/"):
                instance_id = route.rsplit("/", 1)[-1]
                record = registry.get_instance(instance_id)
                if record is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "instance not found"})
                    return
                self._send_json(HTTPStatus.OK, _record_to_dict(record))
                return

            if route == "/logs":
                terminal_id = _query_value(query, "terminal_id")
                task_id = _query_value(query, "task_id")
                level = _query_value(query, "level")
                logs = [
                    _record_to_dict(record)
                    for record in audit.list_logs_filtered(
                        terminal_id=terminal_id,
                        task_id=task_id,
                        level=level,
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": logs})
                return

            if route.startswith("/logs/"):
                log_id = route.rsplit("/", 1)[-1]
                record = audit.get_log(log_id)
                if record is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "log not found"})
                    return
                self._send_json(HTTPStatus.OK, _record_to_dict(record))
                return

            if route == "/tasks":
                terminal_id = _query_value(query, "terminal_id")
                status = _query_value(query, "status")
                script_name = _query_value(query, "script_name")
                items = [
                    _record_to_dict(record)
                    for record in tasks.list_tasks_filtered(
                        terminal_id=terminal_id,
                        status=status,
                        script_name=script_name,
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": items})
                return

            if route == "/task-events":
                task_id = _query_value(query, "task_id")
                items = [_record_to_dict(record) for record in tasks.list_task_events(task_id=task_id)]
                self._send_json(HTTPStatus.OK, {"items": items})
                return

            if route == "/task-attempts":
                task_id = _query_value(query, "task_id")
                if not task_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing query param: task_id"})
                    return
                items = [_record_to_dict(record) for record in tasks.list_task_attempts(task_id=task_id)]
                self._send_json(HTTPStatus.OK, {"items": items})
                return

            if route.endswith("/report") and route.startswith("/tasks/"):
                parts = route.strip("/").split("/")
                if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "report":
                    task_id = parts[1]
                    task = tasks.get_task(task_id)
                    if task is None:
                        self._send_json(HTTPStatus.NOT_FOUND, {"error": "task not found"})
                        return
                    latest_log = audit.latest_log_for_task(task_id)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "task": _record_to_dict(task),
                            "attempts": [_record_to_dict(item) for item in tasks.list_task_attempts(task_id)],
                            "events": [_record_to_dict(item) for item in tasks.list_task_events(task_id)],
                            "latest_log": _record_to_dict(latest_log) if latest_log is not None else None,
                        },
                    )
                    return

            if route.endswith("/events") and route.startswith("/tasks/"):
                parts = route.strip("/").split("/")
                if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "events":
                    task_id = parts[1]
                    items = [_record_to_dict(record) for record in tasks.list_task_events(task_id=task_id)]
                    self._send_json(HTTPStatus.OK, {"items": items})
                    return

            if route.endswith("/attempts") and route.startswith("/tasks/"):
                parts = route.strip("/").split("/")
                if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "attempts":
                    task_id = parts[1]
                    items = [_record_to_dict(record) for record in tasks.list_task_attempts(task_id=task_id)]
                    self._send_json(HTTPStatus.OK, {"items": items})
                    return

            if route.startswith("/tasks/"):
                task_id = route.rsplit("/", 1)[-1]
                record = tasks.get_task(task_id)
                if record is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "task not found"})
                    return
                self._send_json(HTTPStatus.OK, _record_to_dict(record))
                return

            if route == "/summary":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "registry": registry.summary(),
                        "tasks": tasks.summary(),
                        "audit": audit.summary(),
                    },
                )
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
                route, _ = self._route()

                if route == "/register":
                    record = registry.register_terminal(_parse_registration(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if route == "/heartbeat":
                    record = registry.record_heartbeat(_parse_heartbeat(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if route == "/instances/sync":
                    terminal_id = payload["terminal_id"]
                    snapshots = [_parse_snapshot(item) for item in payload.get("items", [])]
                    records = registry.sync_instances(terminal_id, snapshots)
                    self._send_json(
                        HTTPStatus.OK,
                        {"terminal_id": terminal_id, "items": [_record_to_dict(record) for record in records]},
                    )
                    return

                if route == "/tasks":
                    record = tasks.create_task(_parse_task(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if route == "/tasks/claim":
                    terminal_id = payload["terminal_id"]
                    records = tasks.claim_tasks(terminal_id)
                    self._send_json(
                        HTTPStatus.OK,
                        {"terminal_id": terminal_id, "items": [_record_to_dict(record) for record in records]},
                    )
                    return

                if route == "/tasks/control":
                    record = tasks.control_task(_parse_task_control(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if route == "/tasks/result":
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

                if route == "/tasks/running":
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

        def _route(self) -> tuple[str, dict[str, list[str]]]:
            parsed = urlparse(self.path)
            return parsed.path, parse_qs(parsed.query)

    return ThreadingHTTPServer((host, port), RequestHandler)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    state_path: str | Path = "nas_control_plane/state.sqlite3",
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
    )


def _parse_task_control(payload: dict[str, Any]) -> TaskControlPayload:
    return TaskControlPayload(
        task_id=payload["task_id"],
        action=payload["action"],
        reason=payload.get("reason"),
        requested_by=payload.get("requested_by"),
        metadata=dict(payload.get("metadata", {})),
    )


def _record_to_dict(record: Any) -> dict[str, Any]:
    data = asdict(record)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def _query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values:
        return None
    return values[0]


if __name__ == "__main__":
    run_server()
