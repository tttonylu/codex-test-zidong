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
    build_chat_action_plan,
    build_follow_action_plan,
    build_probe_action_plan,
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

            if route in {"/", "/dashboard"}:
                self._send_html(HTTPStatus.OK, _render_dashboard_page())
                return

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
                    task_attempts = tasks.list_task_attempts(task_id)
                    task_events = tasks.list_task_events(task_id)
                    latest_log = audit.latest_log_for_task(task_id)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "task": _record_to_dict(task),
                            "attempts": [_record_to_dict(item) for item in task_attempts],
                            "events": [_record_to_dict(item) for item in task_events],
                            "latest_log": _record_to_dict(latest_log) if latest_log is not None else None,
                            "action_summary": _build_action_summary(task, task_attempts),
                            "diagnostics": _build_task_diagnostics(task, task_attempts),
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

        def _send_html(self, status: HTTPStatus, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
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


def _build_action_summary(task: Any, attempts: list[Any]) -> dict[str, Any]:
    action_names: list[str] = []
    failed_step = None
    failed_action = None
    failure_category = None
    recommended_action = None
    seen_names: set[str] = set()
    for attempt in attempts:
        details = getattr(attempt, "details", {}) or {}
        for item in details.get("browser_action_results", []):
            name = item.get("name")
            if isinstance(name, str) and name not in seen_names:
                action_names.append(name)
                seen_names.add(name)
        if failed_step is None and details.get("failed_step") is not None:
            failed_step = details.get("failed_step")
        if failed_action is None and details.get("failed_action") is not None:
            failed_action = details.get("failed_action")
        if failure_category is None and getattr(attempt, "failure_category", None) is not None:
            failure_category = getattr(attempt, "failure_category")
        if recommended_action is None and getattr(attempt, "recommended_action", None) is not None:
            recommended_action = getattr(attempt, "recommended_action")

    if not action_names:
        for item in _resolve_task_action_plan(task):
            name = item.get("name")
            if isinstance(name, str) and name not in seen_names:
                action_names.append(name)
                seen_names.add(name)

    return {
        "action_names": action_names,
        "action_count": len(action_names),
        "failed_step": failed_step,
        "failed_action": failed_action,
        "failure_category": failure_category,
        "recommended_action": recommended_action,
    }


def _resolve_task_action_plan(task: Any) -> list[dict[str, Any]]:
    parameters = getattr(task, "parameters", {}) or {}
    raw_plan = parameters.get("action_plan")
    if isinstance(raw_plan, list):
        return [item for item in raw_plan if isinstance(item, dict)]

    script_name = getattr(task, "script_name", None)
    if script_name == "follow":
        target_handle = parameters.get("target_handle")
        if isinstance(target_handle, str) and target_handle:
            return build_follow_action_plan(
                target_handle=target_handle,
                annotate_remark=bool(parameters.get("annotate_remark", False)),
            )
    if script_name == "chat":
        target_handle = parameters.get("target_handle")
        if isinstance(target_handle, str) and target_handle:
            return build_chat_action_plan(
                target_handle=target_handle,
                annotate_remark=bool(parameters.get("annotate_remark", False)),
            )
    if script_name == "probe":
        target_url = parameters.get("target_url")
        if isinstance(target_url, str) and target_url:
            return build_probe_action_plan(
                target_url=target_url,
                annotate_remark=bool(parameters.get("annotate_remark", False)),
            )
    return []


def _build_task_diagnostics(task: Any, attempts: list[Any]) -> dict[str, Any]:
    latest_failed_attempt = None
    for attempt in reversed(attempts):
        if getattr(attempt, "status", None) == "failed":
            latest_failed_attempt = attempt
            break

    if task.status == "completed":
        health_status = "healthy"
    elif task.status == "queued" and task.retryable is False and task.final is False and task.attempt_count > 0:
        health_status = "retry_pending"
    elif task.status == "failed" and task.retryable:
        health_status = "retryable_failure"
    elif task.status == "failed":
        health_status = "terminal_failure"
    elif task.status == "cancelled":
        health_status = "cancelled"
    elif task.status in {"running", "dispatched"}:
        health_status = "in_progress"
    else:
        health_status = "pending"

    return {
        "health_status": health_status,
        "can_retry_now": bool(task.status == "failed" and task.retryable and not task.final),
        "attempts_total": len(attempts),
        "attempts_failed": len([item for item in attempts if getattr(item, "status", None) == "failed"]),
        "attempts_completed": len([item for item in attempts if getattr(item, "status", None) == "completed"]),
        "latest_failed_attempt": _record_to_dict(latest_failed_attempt) if latest_failed_attempt is not None else None,
    }


def _render_dashboard_page() -> str:
    """返回一个内嵌的最小运营页面，便于直接查看和操作任务。"""

    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NAS 运营视图</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fffaf3;
      --panel-strong: #fff;
      --line: #dccfb8;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #b45309;
      --accent-soft: #f59e0b;
      --good: #166534;
      --warn: #b45309;
      --bad: #b91c1c;
      --shadow: 0 14px 40px rgba(120, 53, 15, 0.10);
      --radius: 18px;
      --mono: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
      --sans: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(245, 158, 11, 0.18), transparent 32%),
        linear-gradient(180deg, #f7f2ea 0%, #efe8dc 100%);
      color: var(--text);
      font-family: var(--sans);
    }
    .shell {
      max-width: 1480px;
      margin: 0 auto;
      padding: 24px;
    }
    .hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 18px;
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: 32px;
      font-weight: 800;
      letter-spacing: 0.02em;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: flex-end;
    }
    .panel {
      background: rgba(255, 250, 243, 0.92);
      border: 1px solid rgba(220, 207, 184, 0.9);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
      backdrop-filter: blur(14px);
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .summary-card {
      padding: 16px 18px;
      min-height: 108px;
    }
    .summary-card .label {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 10px;
    }
    .summary-card .value {
      font-size: 30px;
      font-weight: 800;
    }
    .summary-card .meta {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
    }
    .filters {
      display: grid;
      grid-template-columns: 1.2fr 1fr 1fr auto auto;
      gap: 10px;
      padding: 16px;
      margin-bottom: 18px;
    }
    input, select, button, textarea {
      font: inherit;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      color: var(--text);
    }
    input, select, textarea {
      width: 100%;
      padding: 10px 12px;
    }
    button {
      padding: 10px 14px;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
    }
    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 18px rgba(120, 53, 15, 0.12);
    }
    button.primary {
      background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
      color: #fff;
      border-color: #d97706;
    }
    button.ghost {
      background: rgba(255, 255, 255, 0.8);
    }
    button.warn {
      background: #fff7ed;
      border-color: #fdba74;
      color: var(--warn);
    }
    button.danger {
      background: #fef2f2;
      border-color: #fca5a5;
      color: var(--bad);
    }
    .layout {
      display: grid;
      grid-template-columns: 1.45fr 1fr;
      gap: 18px;
      align-items: start;
    }
    .list-panel, .detail-panel, .terminal-panel {
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 16px 18px 0;
    }
    .panel-head h2, .panel-head h3 {
      margin: 0;
      font-size: 18px;
    }
    .panel-head .sub {
      color: var(--muted);
      font-size: 12px;
    }
    .table-wrap {
      overflow: auto;
      padding: 14px 16px 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid rgba(220, 207, 184, 0.65);
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      background: rgba(255, 250, 243, 0.98);
      z-index: 1;
      color: var(--muted);
      font-weight: 600;
    }
    tr.task-row {
      cursor: pointer;
    }
    tr.task-row:hover {
      background: rgba(245, 158, 11, 0.08);
    }
    tr.task-row.active {
      background: rgba(217, 119, 6, 0.12);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .badge.pending { background: #f3f4f6; color: #4b5563; }
    .badge.running { background: #dbeafe; color: #1d4ed8; }
    .badge.good { background: #dcfce7; color: #166534; }
    .badge.warn { background: #fff7ed; color: #b45309; }
    .badge.bad { background: #fee2e2; color: #b91c1c; }
    .detail-panel {
      padding: 16px;
      position: sticky;
      top: 18px;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
      margin-bottom: 16px;
    }
    .kv {
      padding: 12px;
      background: rgba(255, 255, 255, 0.62);
      border-radius: 14px;
      border: 1px solid rgba(220, 207, 184, 0.75);
    }
    .kv .k {
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .kv .v {
      font-size: 14px;
      font-weight: 600;
      word-break: break-word;
    }
    .detail-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 16px;
    }
    .detail-section {
      margin-top: 16px;
    }
    .detail-section h3 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(217, 119, 6, 0.08);
      color: #92400e;
      font-size: 12px;
      font-weight: 700;
    }
    .timeline {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .timeline-item {
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid rgba(220, 207, 184, 0.75);
      font-size: 13px;
    }
    .timeline-item .meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    .terminal-panel {
      margin-top: 18px;
    }
    .notice {
      color: var(--muted);
      font-size: 13px;
      padding: 16px;
    }
    .code {
      font-family: var(--mono);
      font-size: 12px;
    }
    @media (max-width: 1120px) {
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
      .detail-panel { position: static; }
    }
    @media (max-width: 760px) {
      .shell { padding: 14px; }
      .hero { flex-direction: column; }
      .summary-grid { grid-template-columns: 1fr; }
      .filters { grid-template-columns: 1fr; }
      .detail-grid, .detail-actions { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <h1>NAS 运营视图</h1>
        <p>用于查看终端状态、筛选任务、分析失败原因，并直接执行取消或重试。</p>
      </div>
      <div class="toolbar">
        <button class="ghost" id="refresh-all">刷新全部</button>
        <button class="primary" id="auto-refresh-toggle">自动刷新：开</button>
      </div>
    </section>

    <section class="summary-grid" id="summary-grid">
      <div class="panel summary-card"><div class="label">终端总数</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">任务总数</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">失败任务</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">日志总数</div><div class="value">-</div></div>
    </section>

    <section class="panel filters">
      <input id="filter-terminal" placeholder="按 terminal_id 筛选" />
      <select id="filter-status">
        <option value="">全部任务状态</option>
        <option value="queued">queued / 排队中</option>
        <option value="dispatched">dispatched / 已派发</option>
        <option value="running">running / 执行中</option>
        <option value="completed">completed / 已完成</option>
        <option value="failed">failed / 失败</option>
        <option value="cancelled">cancelled / 已取消</option>
      </select>
      <select id="filter-script">
        <option value="">全部脚本类型</option>
        <option value="follow">follow</option>
        <option value="chat">chat</option>
        <option value="probe">probe</option>
        <option value="extract">extract</option>
      </select>
      <button class="ghost" id="apply-filters">应用筛选</button>
      <button class="ghost" id="clear-filters">清空筛选</button>
    </section>

    <section class="layout">
      <div>
        <section class="panel list-panel">
          <div class="panel-head">
            <div>
              <h2>任务列表</h2>
              <div class="sub" id="task-list-meta">正在加载</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>任务 ID</th>
                  <th>终端</th>
                  <th>脚本</th>
                  <th>状态</th>
                  <th>优先级</th>
                  <th>尝试</th>
                  <th>最后错误</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody id="task-table-body"></tbody>
            </table>
          </div>
        </section>

        <section class="panel terminal-panel">
          <div class="panel-head">
            <div>
              <h2>终端概览</h2>
              <div class="sub">用于快速判断在线情况和负载分布</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>终端 ID</th>
                  <th>主机名</th>
                  <th>状态</th>
                  <th>操作员</th>
                  <th>版本</th>
                  <th>最后心跳</th>
                </tr>
              </thead>
              <tbody id="terminal-table-body"></tbody>
            </table>
          </div>
        </section>
      </div>

      <aside class="panel detail-panel">
        <div class="panel-head">
          <div>
            <h2>任务详情</h2>
            <div class="sub" id="detail-subtitle">请选择左侧任务</div>
          </div>
        </div>

        <div style="margin-top: 14px;">
          <textarea id="control-reason" rows="3" placeholder="操作备注。留空时会使用默认原因。"></textarea>
        </div>
        <div class="detail-actions">
          <button class="warn" id="retry-task-btn" disabled>重试任务</button>
          <button class="danger" id="cancel-task-btn" disabled>取消任务</button>
        </div>

        <div id="detail-body" class="notice">请选择一个任务查看诊断、动作计划、执行尝试和事件时间线。</div>
      </aside>
    </section>
  </div>

  <script>
    const state = {
      selectedTaskId: null,
      selectedReport: null,
      autoRefresh: true,
      timerId: null,
    };

    function statusBadgeKind(status) {
      if (status === "completed") return "good";
      if (status === "failed" || status === "cancelled") return "bad";
      if (status === "running" || status === "dispatched") return "running";
      if (status === "queued") return "warn";
      return "pending";
    }

    function statusText(status) {
      const map = {
        queued: "排队中",
        dispatched: "已派发",
        running: "执行中",
        completed: "已完成",
        failed: "失败",
        cancelled: "已取消",
      };
      return map[status] || status || "-";
    }

    function healthText(health) {
      const map = {
        healthy: "健康",
        retry_pending: "等待重试",
        retryable_failure: "可重试失败",
        terminal_failure: "终态失败",
        cancelled: "已取消",
        in_progress: "进行中",
        pending: "待处理",
      };
      return map[health] || health || "-";
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function formatTime(value) {
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString("zh-CN", { hour12: false });
    }

    async function getJson(path, options) {
      const response = await fetch(path, options);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || ("请求失败: " + response.status));
      }
      return payload;
    }

    function currentTaskQuery() {
      const query = new URLSearchParams();
      const terminalId = document.getElementById("filter-terminal").value.trim();
      const status = document.getElementById("filter-status").value;
      const script = document.getElementById("filter-script").value;
      if (terminalId) query.set("terminal_id", terminalId);
      if (status) query.set("status", status);
      if (script) query.set("script_name", script);
      return query.toString() ? "/tasks?" + query.toString() : "/tasks";
    }

    async function refreshAll() {
      // 统一刷新摘要、终端和任务列表，保证运营视图数据同步。
      const [summary, terminals, tasks] = await Promise.all([
        getJson("/summary"),
        getJson("/terminals"),
        getJson(currentTaskQuery()),
      ]);
      renderSummary(summary);
      renderTerminals(terminals.items || []);
      renderTasks(tasks.items || []);
      if (state.selectedTaskId) {
        await loadTaskReport(state.selectedTaskId, { silent: true });
      }
    }

    function renderSummary(summary) {
      const terminalCount = Number(summary?.registry?.terminal_count || 0);
      const taskCount = Number(summary?.tasks?.task_count || 0);
      const failedCount = Number(summary?.tasks?.status_counts?.failed || 0);
      const logCount = Number(summary?.audit?.log_count || 0);

      document.getElementById("summary-grid").innerHTML = `
        <div class="panel summary-card">
          <div class="label">终端总数</div>
          <div class="value">${terminalCount}</div>
          <div class="meta">在线状态来自终端注册与心跳。</div>
        </div>
        <div class="panel summary-card">
          <div class="label">任务总数</div>
          <div class="value">${taskCount}</div>
          <div class="meta">按当前服务端汇总，不受本页筛选影响。</div>
        </div>
        <div class="panel summary-card">
          <div class="label">失败任务</div>
          <div class="value">${failedCount}</div>
          <div class="meta">建议优先打开失败详情查看可重试性。</div>
        </div>
        <div class="panel summary-card">
          <div class="label">日志总数</div>
          <div class="value">${logCount}</div>
          <div class="meta">可结合任务详情里的最新日志排查。</div>
        </div>
      `;
    }

    function renderTasks(items) {
      const body = document.getElementById("task-table-body");
      document.getElementById("task-list-meta").textContent = `当前筛选结果 ${items.length} 条`;
      if (!items.length) {
        body.innerHTML = `<tr><td colspan="8" class="notice">当前没有匹配的任务。</td></tr>`;
        return;
      }

      body.innerHTML = items.map((item) => {
        const activeClass = state.selectedTaskId === item.task_id ? "active" : "";
        return `
          <tr class="task-row ${activeClass}" data-task-id="${escapeHtml(item.task_id)}">
            <td class="code">${escapeHtml(item.task_id)}</td>
            <td class="code">${escapeHtml(item.terminal_id)}</td>
            <td>${escapeHtml(item.script_name)}</td>
            <td><span class="badge ${statusBadgeKind(item.status)}">${statusText(item.status)}</span></td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${escapeHtml(item.attempt_count)} / ${escapeHtml(item.max_attempts)}</td>
            <td class="code">${escapeHtml(item.last_error_code || "-")}</td>
            <td>${escapeHtml(formatTime(item.created_at))}</td>
          </tr>
        `;
      }).join("");

      for (const row of body.querySelectorAll(".task-row")) {
        row.addEventListener("click", () => loadTaskReport(row.dataset.taskId));
      }
    }

    function renderTerminals(items) {
      const body = document.getElementById("terminal-table-body");
      if (!items.length) {
        body.innerHTML = `<tr><td colspan="6" class="notice">当前没有终端注册记录。</td></tr>`;
        return;
      }
      body.innerHTML = items.map((item) => `
        <tr>
          <td class="code">${escapeHtml(item.terminal_id)}</td>
          <td>${escapeHtml(item.hostname)}</td>
          <td><span class="badge ${statusBadgeKind(item.status === "online" ? "running" : item.status)}">${escapeHtml(item.status || "-")}</span></td>
          <td>${escapeHtml(item.operator_name)}</td>
          <td class="code">${escapeHtml(item.agent_version)}</td>
          <td>${escapeHtml(formatTime(item.last_seen_at))}</td>
        </tr>
      `).join("");
    }

    async function loadTaskReport(taskId, options = {}) {
      const report = await getJson(`/tasks/${encodeURIComponent(taskId)}/report`);
      state.selectedTaskId = taskId;
      state.selectedReport = report;
      renderTaskDetail(report);
      highlightSelectedTask();
      if (!options.silent) {
        document.getElementById("detail-subtitle").textContent = `当前任务：${taskId}`;
      }
    }

    function highlightSelectedTask() {
      for (const row of document.querySelectorAll(".task-row")) {
        row.classList.toggle("active", row.dataset.taskId === state.selectedTaskId);
      }
    }

    function renderTaskDetail(report) {
      const task = report.task || {};
      const diagnostics = report.diagnostics || {};
      const latestLog = report.latest_log || {};
      const summary = report.action_summary || {};
      const attempts = report.attempts || [];
      const events = report.events || [];

      document.getElementById("retry-task-btn").disabled = !Boolean(diagnostics.can_retry_now);
      document.getElementById("cancel-task-btn").disabled = !["queued", "dispatched", "running"].includes(task.status);

      const actionNames = Array.isArray(summary.action_names) ? summary.action_names : [];
      const timelineHtml = events.length
        ? events.slice().reverse().map((item) => `
            <div class="timeline-item">
              <div><strong>${escapeHtml(item.event_type)}</strong> · ${escapeHtml(statusText(item.status))}</div>
              <div>${escapeHtml(item.message || "-")}</div>
              <div class="meta">${escapeHtml(formatTime(item.emitted_at))}</div>
            </div>
          `).join("")
        : `<div class="notice">暂无事件时间线。</div>`;

      const attemptsHtml = attempts.length
        ? attempts.map((item) => `
            <div class="timeline-item">
              <div><strong>第 ${escapeHtml(item.attempt_number)} 次</strong> · ${escapeHtml(statusText(item.status))}</div>
              <div>失败分类：${escapeHtml(item.failure_category || "-")} ｜ 失败步骤：${escapeHtml(item.failed_step_name || "-")}</div>
              <div>错误码：<span class="code">${escapeHtml(item.error_code || "-")}</span> ｜ 步骤数：${escapeHtml(item.step_count || 0)}</div>
              <div class="meta">run_id=${escapeHtml(item.run_id || "-")} ｜ ${escapeHtml(formatTime(item.finished_at || item.started_at))}</div>
            </div>
          `).join("")
        : `<div class="notice">暂无执行尝试。</div>`;

      document.getElementById("detail-body").innerHTML = `
        <div class="detail-grid">
          <div class="kv"><div class="k">任务状态</div><div class="v"><span class="badge ${statusBadgeKind(task.status)}">${escapeHtml(statusText(task.status))}</span></div></div>
          <div class="kv"><div class="k">健康状态</div><div class="v">${escapeHtml(healthText(diagnostics.health_status))}</div></div>
          <div class="kv"><div class="k">脚本类型</div><div class="v">${escapeHtml(task.script_name || "-")}</div></div>
          <div class="kv"><div class="k">终端 / 实例</div><div class="v code">${escapeHtml(task.terminal_id || "-")} / ${escapeHtml(task.instance_id || "-")}</div></div>
          <div class="kv"><div class="k">尝试次数</div><div class="v">${escapeHtml(task.attempt_count || 0)} / ${escapeHtml(task.max_attempts || 0)}</div></div>
          <div class="kv"><div class="k">最后错误码</div><div class="v code">${escapeHtml(task.last_error_code || "-")}</div></div>
          <div class="kv"><div class="k">最后错误消息</div><div class="v">${escapeHtml(task.last_error_message || "-")}</div></div>
          <div class="kv"><div class="k">建议动作</div><div class="v">${escapeHtml(summary.recommended_action || "-")}</div></div>
        </div>

        <div class="detail-section">
          <h3>计划动作</h3>
          <div class="chips">
            ${actionNames.length ? actionNames.map((name) => `<span class="chip">${escapeHtml(name)}</span>`).join("") : `<span class="chip">暂无动作计划</span>`}
          </div>
        </div>

        <div class="detail-section">
          <h3>最新日志</h3>
          <div class="timeline-item">
            <div><strong>${escapeHtml(latestLog.level || "-")}</strong> · ${escapeHtml(latestLog.message || "-")}</div>
            <div class="meta">${escapeHtml(formatTime(latestLog.emitted_at))}</div>
          </div>
        </div>

        <div class="detail-section">
          <h3>执行尝试</h3>
          <div class="timeline">${attemptsHtml}</div>
        </div>

        <div class="detail-section">
          <h3>事件时间线</h3>
          <div class="timeline">${timelineHtml}</div>
        </div>
      `;
    }

    async function controlSelectedTask(action) {
      if (!state.selectedTaskId) return;
      // 操作接口直接复用现有 NAS control API，避免再造一层服务端代理。
      const reasonInput = document.getElementById("control-reason");
      const reason = reasonInput.value.trim() || (action === "retry" ? "运营页发起重试" : "运营页发起取消");
      const requestedBy = "dashboard";
      try {
        await getJson("/tasks/control", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: state.selectedTaskId,
            action,
            reason,
            requested_by: requestedBy,
          }),
        });
        await refreshAll();
        await loadTaskReport(state.selectedTaskId, { silent: true });
      } catch (error) {
        window.alert(error.message || String(error));
      }
    }

    function bindEvents() {
      document.getElementById("apply-filters").addEventListener("click", refreshAll);
      document.getElementById("clear-filters").addEventListener("click", async () => {
        document.getElementById("filter-terminal").value = "";
        document.getElementById("filter-status").value = "";
        document.getElementById("filter-script").value = "";
        await refreshAll();
      });
      document.getElementById("refresh-all").addEventListener("click", refreshAll);
      document.getElementById("retry-task-btn").addEventListener("click", () => controlSelectedTask("retry"));
      document.getElementById("cancel-task-btn").addEventListener("click", () => controlSelectedTask("cancel"));
      document.getElementById("auto-refresh-toggle").addEventListener("click", () => {
        state.autoRefresh = !state.autoRefresh;
        document.getElementById("auto-refresh-toggle").textContent = `自动刷新：${state.autoRefresh ? "开" : "关"}`;
      });
    }

    async function bootstrap() {
      bindEvents();
      await refreshAll();
      state.timerId = window.setInterval(() => {
        if (state.autoRefresh) {
          refreshAll().catch((error) => console.error(error));
        }
      }, 5000);
    }

    bootstrap().catch((error) => {
      document.getElementById("detail-body").innerHTML = `<div class="notice">页面初始化失败：${escapeHtml(error.message || String(error))}</div>`;
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    run_server()
