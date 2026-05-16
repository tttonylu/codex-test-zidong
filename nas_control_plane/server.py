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
    SqliteTaskRepository,
    SqliteTerminalStateRepository,
    TaskDispatchService,
    TerminalRegistryService,
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
    """返回一个内嵌的 NAS 运营视图页面。"""

    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NAS \\u8fd0\\u8425\\u89c6\\u56fe</title>
  <style>
    :root {
      --panel: rgba(255, 251, 245, 0.92);
      --panel-strong: #fffdf9;
      --line: #dccfb8;
      --text: #1f2937;
      --muted: #6b7280;
      --accent-strong: #d97706;
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
    .shell { max-width: 1560px; margin: 0 auto; padding: 24px; }
    .hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 18px;
    }
    .hero h1 { margin: 0 0 8px; font-size: 32px; font-weight: 800; }
    .hero p { margin: 0; color: var(--muted); max-width: 820px; line-height: 1.6; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
    .panel {
      background: var(--panel);
      border: 1px solid rgba(220, 207, 184, 0.9);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
      backdrop-filter: blur(14px);
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 16px 18px 0;
    }
    .panel-head h2, .panel-head h3 { margin: 0; font-size: 18px; }
    .panel-head .sub { color: var(--muted); font-size: 12px; line-height: 1.5; }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .summary-card { padding: 16px 18px; min-height: 108px; }
    .summary-card .label { font-size: 13px; color: var(--muted); margin-bottom: 10px; }
    .summary-card .value { font-size: 30px; font-weight: 800; }
    .summary-card .meta { margin-top: 8px; font-size: 12px; color: var(--muted); line-height: 1.5; }
    .creation-grid, .filters-grid, .log-filters, .detail-grid {
      display: grid;
      gap: 10px;
      padding: 16px;
    }
    .creation-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .filters-grid { grid-template-columns: 1.2fr 1fr 1fr auto auto; }
    .log-filters { grid-template-columns: 1fr 1fr auto auto; padding-top: 8px; }
    .detail-grid { grid-template-columns: 1fr 1fr; padding: 0; }
    .field { display: flex; flex-direction: column; gap: 6px; }
    .field-wide { grid-column: span 2; }
    .field label { font-size: 12px; color: var(--muted); }
    input, select, button, textarea {
      font: inherit;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      color: var(--text);
    }
    input, select, textarea { width: 100%; padding: 10px 12px; }
    textarea { resize: vertical; min-height: 72px; }
    .toggle {
      display: flex; gap: 8px; align-items: center; min-height: 42px;
      padding: 0 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-strong);
    }
    .toggle input { width: auto; margin: 0; }
    button {
      padding: 10px 14px;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(120, 53, 15, 0.12); }
    button.primary { background: linear-gradient(135deg, var(--accent-strong) 0%, #f59e0b 100%); color: #fff; border-color: var(--accent-strong); }
    button.ghost { background: rgba(255, 255, 255, 0.8); }
    button.warn { background: #fff7ed; border-color: #fdba74; color: var(--warn); }
    button.danger { background: #fef2f2; border-color: #fca5a5; color: var(--bad); }
    button:disabled { cursor: not-allowed; opacity: 0.58; transform: none; box-shadow: none; }
    .creation-actions { display: flex; justify-content: flex-end; gap: 10px; padding: 0 16px 16px; }
    .feedback {
      margin: 0 16px 16px; padding: 12px 14px; border-radius: 14px;
      font-size: 13px; line-height: 1.5; display: none;
    }
    .feedback.show { display: block; }
    .feedback.info { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
    .feedback.success { background: #ecfdf5; color: #166534; border: 1px solid #a7f3d0; }
    .feedback.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
    .layout {
      display: grid;
      grid-template-columns: 1.45fr 1fr;
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }
    .stack { display: grid; gap: 18px; }
    .table-wrap { overflow: auto; padding: 14px 16px 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td {
      text-align: left; padding: 10px 8px; border-bottom: 1px solid rgba(220, 207, 184, 0.65); vertical-align: top;
    }
    th {
      position: sticky; top: 0; background: rgba(255, 250, 243, 0.98); z-index: 1; color: var(--muted); font-weight: 600; white-space: nowrap;
    }
    tr.task-row, tr.terminal-row, tr.log-row { cursor: pointer; }
    tr.task-row:hover, tr.terminal-row:hover, tr.log-row:hover { background: rgba(245, 158, 11, 0.08); }
    tr.task-row.active, tr.terminal-row.active, tr.log-row.active { background: rgba(217, 119, 6, 0.12); }
    .badge {
      display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
      font-size: 12px; font-weight: 700; white-space: nowrap;
    }
    .badge.pending { background: #f3f4f6; color: #4b5563; }
    .badge.running { background: #dbeafe; color: #1d4ed8; }
    .badge.good { background: #dcfce7; color: #166534; }
    .badge.warn { background: #fff7ed; color: #b45309; }
    .badge.bad { background: #fee2e2; color: #b91c1c; }
    .detail-panel { padding: 16px; position: sticky; top: 18px; }
    .kv {
      padding: 12px; background: rgba(255, 255, 255, 0.62);
      border-radius: 14px; border: 1px solid rgba(220, 207, 184, 0.75);
    }
    .kv .k { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .kv .v { font-size: 14px; font-weight: 600; word-break: break-word; }
    .detail-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
    .detail-section { margin-top: 16px; }
    .detail-section h3 { margin: 0 0 10px; font-size: 15px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      padding: 6px 10px; border-radius: 999px; background: rgba(217, 119, 6, 0.08);
      color: #92400e; font-size: 12px; font-weight: 700;
    }
    .timeline { display: flex; flex-direction: column; gap: 8px; }
    .timeline-item {
      padding: 10px 12px; border-radius: 12px; background: rgba(255, 255, 255, 0.66);
      border: 1px solid rgba(220, 207, 184, 0.75); font-size: 13px; line-height: 1.55;
    }
    .timeline-item .meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .notice { color: var(--muted); font-size: 13px; padding: 16px; line-height: 1.6; }
    .code { font-family: var(--mono); font-size: 12px; }
    .split-detail { display: grid; gap: 18px; }
    @media (max-width: 1240px) {
      .creation-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .layout { grid-template-columns: 1fr; }
      .detail-panel { position: static; }
    }
    @media (max-width: 760px) {
      .shell { padding: 14px; }
      .hero { flex-direction: column; }
      .summary-grid, .creation-grid, .filters-grid, .detail-grid, .detail-actions, .log-filters { grid-template-columns: 1fr; }
      .field-wide { grid-column: auto; }
      .creation-actions { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <h1>NAS \\u8fd0\\u8425\\u89c6\\u56fe</h1>
        <p>\\u7528\\u4e8e\\u67e5\\u770b\\u7ec8\\u7aef\\u72b6\\u6001\\u3001\\u7b5b\\u9009\\u4efb\\u52a1\\u3001\\u5206\\u6790\\u5931\\u8d25\\u539f\\u56e0\\uff0c\\u5e76\\u76f4\\u63a5\\u521b\\u5efa\\u3001\\u53d6\\u6d88\\u6216\\u91cd\\u8bd5\\u4efb\\u52a1\\u3002\\u5f53\\u524d\\u9875\\u9762\\u76f4\\u63a5\\u590d\\u7528\\u73b0\\u6709 NAS control API\\uff0c\\u4e0d\\u589e\\u52a0\\u989d\\u5916\\u4e2d\\u95f4\\u5c42\\u3002</p>
      </div>
      <div class="toolbar">
        <button class="ghost" id="refresh-all">\\u5237\\u65b0\\u5168\\u90e8</button>
        <button class="primary" id="auto-refresh-toggle">\\u81ea\\u52a8\\u5237\\u65b0\\uff1a\\u5f00</button>
      </div>
    </section>

    <section class="summary-grid" id="summary-grid">
      <div class="panel summary-card"><div class="label">\\u7ec8\\u7aef\\u603b\\u6570</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">\\u4efb\\u52a1\\u603b\\u6570</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">\\u5931\\u8d25\\u4efb\\u52a1</div><div class="value">-</div></div>
      <div class="panel summary-card"><div class="label">\\u65e5\\u5fd7\\u603b\\u6570</div><div class="value">-</div></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>\\u521b\\u5efa\\u4efb\\u52a1</h2>
          <div class="sub">\\u652f\\u6301 <code>follow</code>\\u3001<code>chat</code>\\u3001<code>probe</code> \\u4e09\\u7c7b\\u4efb\\u52a1\\uff0c\\u5e76\\u5728\\u524d\\u7aef\\u6309\\u7edf\\u4e00\\u89c4\\u5219\\u6784\\u9020 <code>action_plan</code> \\u540e\\u63d0\\u4ea4\\u5230 <code>/tasks</code>\\u3002</div>
        </div>
      </div>
      <div class="creation-grid">
        <div class="field">
          <label for="create-script-name">\\u4efb\\u52a1\\u7c7b\\u578b</label>
          <select id="create-script-name">
            <option value="follow">follow</option>
            <option value="chat">chat</option>
            <option value="probe">probe</option>
          </select>
        </div>
        <div class="field">
          <label for="create-task-id">\\u4efb\\u52a1 ID</label>
          <input id="create-task-id" placeholder="\\u7559\\u7a7a\\u5219\\u81ea\\u52a8\\u751f\\u6210" />
        </div>
        <div class="field">
          <label for="create-terminal-id">terminal_id</label>
          <input id="create-terminal-id" placeholder="\\u4f8b\\u5982 terminal-a" />
        </div>
        <div class="field">
          <label for="create-instance-id">instance_id</label>
          <input id="create-instance-id" placeholder="\\u4f8b\\u5982 bb-follow-1" />
        </div>
        <div class="field">
          <label for="create-priority">priority</label>
          <input id="create-priority" type="number" min="0" value="0" />
        </div>
        <div class="field">
          <label for="create-retry-limit">retry_limit</label>
          <input id="create-retry-limit" type="number" min="0" value="0" />
        </div>
        <div class="field field-wide">
          <label for="create-target-value" id="create-target-label">\\u76ee\\u6807\\u8d26\\u53f7</label>
          <input id="create-target-value" placeholder="\\u4f8b\\u5982 matrix_ops" />
        </div>
        <div class="field">
          <label for="create-requested-by">requested_by</label>
          <input id="create-requested-by" value="dashboard" />
        </div>
        <div class="field">
          <label for="create-annotate-toggle">\\u9644\\u52a0\\u5907\\u6ce8</label>
          <div class="toggle">
            <input id="create-annotate-toggle" type="checkbox" />
            <span>\\u521b\\u5efa\\u4efb\\u52a1\\u65f6\\u9644\\u5e26 remark</span>
          </div>
        </div>
        <div class="field field-wide">
          <label for="create-note">\\u521b\\u5efa\\u5907\\u6ce8</label>
          <textarea id="create-note" placeholder="\\u53ef\\u9009\\u3002\\u7528\\u4e8e\\u8bb0\\u5f55\\u64cd\\u4f5c\\u80cc\\u666f\\uff0c\\u4e0d\\u4f1a\\u8986\\u76d6 action_plan\\u3002"></textarea>
        </div>
      </div>
      <div id="create-feedback" class="feedback"></div>
      <div class="creation-actions">
        <button class="ghost" id="create-reset-btn">\\u91cd\\u7f6e\\u8868\\u5355</button>
        <button class="primary" id="create-task-btn">\\u63d0\\u4ea4\\u4efb\\u52a1</button>
      </div>
    </section>

    <section class="panel" style="margin-top: 18px;">
      <div class="filters-grid">
        <input id="filter-terminal" placeholder="\\u6309 terminal_id \\u7b5b\\u9009" />
        <select id="filter-status">
          <option value="">\\u5168\\u90e8\\u4efb\\u52a1\\u72b6\\u6001</option>
          <option value="queued">queued / \\u6392\\u961f\\u4e2d</option>
          <option value="dispatched">dispatched / \\u5df2\\u6d3e\\u53d1</option>
          <option value="running">running / \\u6267\\u884c\\u4e2d</option>
          <option value="completed">completed / \\u5df2\\u5b8c\\u6210</option>
          <option value="failed">failed / \\u5931\\u8d25</option>
          <option value="cancelled">cancelled / \\u5df2\\u53d6\\u6d88</option>
        </select>
        <select id="filter-script">
          <option value="">\\u5168\\u90e8\\u811a\\u672c\\u7c7b\\u578b</option>
          <option value="follow">follow</option>
          <option value="chat">chat</option>
          <option value="probe">probe</option>
          <option value="extract">extract</option>
        </select>
        <button class="ghost" id="apply-filters">\\u5e94\\u7528\\u7b5b\\u9009</button>
        <button class="ghost" id="clear-filters">\\u6e05\\u7a7a\\u7b5b\\u9009</button>
      </div>
    </section>

    <section class="layout">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>\\u4efb\\u52a1\\u5217\\u8868</h2>
              <div class="sub" id="task-list-meta">\\u6b63\\u5728\\u52a0\\u8f7d</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>\\u4efb\\u52a1 ID</th>
                  <th>\\u7ec8\\u7aef</th>
                  <th>\\u811a\\u672c</th>
                  <th>\\u72b6\\u6001</th>
                  <th>\\u4f18\\u5148\\u7ea7</th>
                  <th>\\u5c1d\\u8bd5</th>
                  <th>\\u6700\\u540e\\u9519\\u8bef\\u7801</th>
                  <th>\\u521b\\u5efa\\u65f6\\u95f4</th>
                </tr>
              </thead>
              <tbody id="task-table-body"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>\\u7ec8\\u7aef\\u6982\\u89c8</h2>
              <div class="sub">\\u70b9\\u51fb\\u7ec8\\u7aef\\u53ef\\u67e5\\u770b\\u5b9e\\u4f8b\\u3001\\u5fc3\\u8df3\\u4e0e\\u76f8\\u5173\\u65e5\\u5fd7\\u3002</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>\\u7ec8\\u7aef ID</th>
                  <th>\\u4e3b\\u673a\\u540d</th>
                  <th>\\u72b6\\u6001</th>
                  <th>\\u64cd\\u4f5c\\u5458</th>
                  <th>\\u7248\\u672c</th>
                  <th>\\u6700\\u540e\\u5fc3\\u8df3</th>
                </tr>
              </thead>
              <tbody id="terminal-table-body"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>\\u65e5\\u5fd7\\u67e5\\u8be2</h2>
              <div class="sub" id="log-list-meta">\\u9ed8\\u8ba4\\u663e\\u793a\\u5168\\u90e8\\u65e5\\u5fd7\\uff0c\\u4e5f\\u53ef\\u7ed3\\u5408\\u7ec8\\u7aef\\u6216 level \\u7b5b\\u9009\\u3002</div>
            </div>
          </div>
          <div class="log-filters">
            <input id="log-terminal-filter" placeholder="\\u6309 terminal_id \\u7b5b\\u9009\\u65e5\\u5fd7" />
            <select id="log-level-filter">
              <option value="">\\u5168\\u90e8 level</option>
              <option value="info">info</option>
              <option value="warning">warning</option>
              <option value="error">error</option>
            </select>
            <button class="ghost" id="apply-log-filters">\\u5237\\u65b0\\u65e5\\u5fd7</button>
            <button class="ghost" id="clear-log-filters">\\u6e05\\u7a7a\\u65e5\\u5fd7\\u7b5b\\u9009</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>log_id</th>
                  <th>terminal</th>
                  <th>level</th>
                  <th>message</th>
                  <th>task_id</th>
                  <th>emitted_at</th>
                </tr>
              </thead>
              <tbody id="log-table-body"></tbody>
            </table>
          </div>
        </section>
      </div>

      <aside class="split-detail">
        <section class="panel detail-panel">
          <div class="panel-head">
            <div>
              <h2>\\u4efb\\u52a1\\u8be6\\u60c5</h2>
              <div class="sub" id="detail-subtitle">\\u8bf7\\u9009\\u62e9\\u5de6\\u4fa7\\u4efb\\u52a1</div>
            </div>
          </div>
          <div style="margin-top: 14px;">
            <textarea id="control-reason" rows="3" placeholder="\\u63a7\\u5236\\u5907\\u6ce8\\u3002\\u7559\\u7a7a\\u65f6\\u4f1a\\u4f7f\\u7528\\u9ed8\\u8ba4\\u539f\\u56e0\\u3002"></textarea>
          </div>
          <div class="detail-actions">
            <button class="warn" id="retry-task-btn" disabled>\\u91cd\\u8bd5\\u4efb\\u52a1</button>
            <button class="danger" id="cancel-task-btn" disabled>\\u53d6\\u6d88\\u4efb\\u52a1</button>
          </div>
          <div id="detail-body" class="notice">\\u8bf7\\u9009\\u62e9\\u4e00\\u4e2a\\u4efb\\u52a1\\u67e5\\u770b\\u8bca\\u65ad\\u3001\\u52a8\\u4f5c\\u8ba1\\u5212\\u3001\\u6267\\u884c\\u5c1d\\u8bd5\\u548c\\u4e8b\\u4ef6\\u65f6\\u95f4\\u7ebf\\u3002</div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>\\u7ec8\\u7aef\\u8be6\\u60c5</h2>
              <div class="sub" id="terminal-detail-subtitle">\\u8bf7\\u9009\\u62e9\\u5de6\\u4fa7\\u7ec8\\u7aef</div>
            </div>
          </div>
          <div id="terminal-detail-body" class="notice">\\u8bf7\\u9009\\u62e9\\u4e00\\u4e2a\\u7ec8\\u7aef\\u67e5\\u770b\\u5fc3\\u8df3\\u3001\\u5b9e\\u4f8b\\u548c\\u5173\\u8054\\u65e5\\u5fd7\\u3002</div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>\\u65e5\\u5fd7\\u8be6\\u60c5</h2>
              <div class="sub" id="log-detail-subtitle">\\u8bf7\\u9009\\u62e9\\u4e00\\u6761\\u65e5\\u5fd7</div>
            </div>
          </div>
          <div id="log-detail-body" class="notice">\\u53ef\\u67e5\\u770b\\u65e5\\u5fd7 message\\u3001run_id \\u548c details \\u5185\\u5bb9\\u3002</div>
        </section>
      </aside>
    </section>
  </div>

  <script>
    const TEXT = {
      dashboard: "\\u8fd0\\u8425\\u89c6\\u56fe",
      taskSelect: "\\u8bf7\\u9009\\u62e9\\u5de6\\u4fa7\\u4efb\\u52a1",
      terminalSelect: "\\u8bf7\\u9009\\u62e9\\u5de6\\u4fa7\\u7ec8\\u7aef",
      logSelect: "\\u8bf7\\u9009\\u62e9\\u4e00\\u6761\\u65e5\\u5fd7",
      requestFailed: "\\u8bf7\\u6c42\\u5931\\u8d25",
      noTask: "\\u5f53\\u524d\\u6ca1\\u6709\\u5339\\u914d\\u7684\\u4efb\\u52a1\\u3002",
      noTerminal: "\\u5f53\\u524d\\u6ca1\\u6709\\u7ec8\\u7aef\\u6ce8\\u518c\\u8bb0\\u5f55\\u3002",
      noLogs: "\\u5f53\\u524d\\u6ca1\\u6709\\u5339\\u914d\\u7684\\u65e5\\u5fd7\\u3002",
      noInstances: "\\u6682\\u65e0\\u5b9e\\u4f8b\\u8bb0\\u5f55",
      retryReason: "\\u8fd0\\u8425\\u9875\\u53d1\\u8d77\\u91cd\\u8bd5",
      cancelReason: "\\u8fd0\\u8425\\u9875\\u53d1\\u8d77\\u53d6\\u6d88",
    };

    const state = {
      selectedTaskId: null,
      selectedTerminalId: null,
      selectedLogId: null,
      autoRefresh: true,
    };

    function statusBadgeKind(status) {
      if (status === "completed") return "good";
      if (status === "failed" || status === "cancelled") return "bad";
      if (status === "running" || status === "dispatched" || status === "online") return "running";
      if (status === "queued") return "warn";
      return "pending";
    }

    function statusText(status) {
      const map = {
        queued: "\\u6392\\u961f\\u4e2d",
        dispatched: "\\u5df2\\u6d3e\\u53d1",
        running: "\\u6267\\u884c\\u4e2d",
        completed: "\\u5df2\\u5b8c\\u6210",
        failed: "\\u5931\\u8d25",
        cancelled: "\\u5df2\\u53d6\\u6d88",
        online: "\\u5728\\u7ebf",
        offline: "\\u79bb\\u7ebf",
      };
      return map[status] || status || "-";
    }

    function healthText(health) {
      const map = {
        healthy: "\\u5065\\u5eb7",
        retry_pending: "\\u7b49\\u5f85\\u91cd\\u8bd5",
        retryable_failure: "\\u53ef\\u91cd\\u8bd5\\u5931\\u8d25",
        terminal_failure: "\\u7ec8\\u6001\\u5931\\u8d25",
        cancelled: "\\u5df2\\u53d6\\u6d88",
        in_progress: "\\u8fdb\\u884c\\u4e2d",
        pending: "\\u5f85\\u5904\\u7406",
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

    function jsonBlock(value) {
      return "<pre class=\\"code\\">" + escapeHtml(JSON.stringify(value ?? {}, null, 2)) + "</pre>";
    }

    async function getJson(path, options) {
      const response = await fetch(path, options);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || (TEXT.requestFailed + ": " + response.status));
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

    function currentLogQuery() {
      const query = new URLSearchParams();
      const terminalId = document.getElementById("log-terminal-filter").value.trim();
      const level = document.getElementById("log-level-filter").value;
      if (terminalId) query.set("terminal_id", terminalId);
      if (level) query.set("level", level);
      return query.toString() ? "/logs?" + query.toString() : "/logs";
    }

    function generateTaskId(scriptName) {
      return "task-" + scriptName + "-" + Date.now();
    }

    function buildActionPlan(scriptName, targetValue, annotateRemark) {
      if (scriptName === "follow") {
        const plan = [{ name: "navigate_profile", kind: "navigate", params: { target_url: "https://x.com/" + targetValue, queue: true } }];
        if (annotateRemark) {
          plan.push({ name: "annotate_follow_target", kind: "annotate", params: { remark: "follow:" + targetValue } });
        }
        return plan;
      }
      if (scriptName === "chat") {
        const plan = [{ name: "navigate_compose", kind: "navigate", params: { target_url: "https://x.com/messages/compose?recipient_id=" + targetValue, queue: true } }];
        if (annotateRemark) {
          plan.push({ name: "annotate_chat_target", kind: "annotate", params: { remark: "chat:" + targetValue } });
        }
        return plan;
      }
      const plan = [{ name: "navigate_probe_target", kind: "navigate", params: { target_url: targetValue, queue: true } }];
      if (annotateRemark) {
        plan.push({ name: "annotate_probe_target", kind: "annotate", params: { remark: "probe:" + targetValue } });
      }
      return plan;
    }

    function buildTaskPayloadFromForm() {
      const scriptName = document.getElementById("create-script-name").value;
      const taskId = document.getElementById("create-task-id").value.trim() || generateTaskId(scriptName);
      const terminalId = document.getElementById("create-terminal-id").value.trim();
      const instanceIdRaw = document.getElementById("create-instance-id").value.trim();
      const targetValue = document.getElementById("create-target-value").value.trim();
      const priority = Number(document.getElementById("create-priority").value || 0);
      const retryLimit = Number(document.getElementById("create-retry-limit").value || 0);
      const annotateRemark = document.getElementById("create-annotate-toggle").checked;
      const requestedBy = document.getElementById("create-requested-by").value.trim() || "dashboard";
      const note = document.getElementById("create-note").value.trim();

      if (!terminalId) throw new Error("terminal_id \\u4e0d\\u80fd\\u4e3a\\u7a7a");
      if (!targetValue) throw new Error(scriptName === "probe" ? "\\u76ee\\u6807 URL \\u4e0d\\u80fd\\u4e3a\\u7a7a" : "\\u76ee\\u6807\\u8d26\\u53f7\\u4e0d\\u80fd\\u4e3a\\u7a7a");

      const parameters = { retry_limit: retryLimit, annotate_remark: annotateRemark, action_plan: buildActionPlan(scriptName, targetValue, annotateRemark) };
      if (scriptName === "probe") parameters.target_url = targetValue;
      else parameters.target_handle = targetValue;
      if (note) parameters.dashboard_note = note;
      if (requestedBy) parameters.requested_by = requestedBy;

      const payload = { task_id: taskId, terminal_id: terminalId, script_name: scriptName, parameters, priority };
      if (instanceIdRaw) payload.instance_id = instanceIdRaw;
      return payload;
    }

    function setCreateFeedback(message, kind) {
      const node = document.getElementById("create-feedback");
      node.textContent = message;
      node.className = "feedback show " + kind;
    }

    function clearCreateFeedback() {
      const node = document.getElementById("create-feedback");
      node.textContent = "";
      node.className = "feedback";
    }

    function syncCreateFormByScript() {
      const scriptName = document.getElementById("create-script-name").value;
      const targetLabel = document.getElementById("create-target-label");
      const targetInput = document.getElementById("create-target-value");
      if (scriptName === "probe") {
        targetLabel.textContent = "\\u76ee\\u6807 URL";
        targetInput.placeholder = "\\u4f8b\\u5982 https://x.com/home";
      } else if (scriptName === "chat") {
        targetLabel.textContent = "\\u76ee\\u6807\\u8d26\\u53f7 / recipient_id";
        targetInput.placeholder = "\\u4f8b\\u5982 risk_user";
      } else {
        targetLabel.textContent = "\\u76ee\\u6807\\u8d26\\u53f7";
        targetInput.placeholder = "\\u4f8b\\u5982 matrix_ops";
      }
      if (!document.getElementById("create-task-id").value.trim()) {
        document.getElementById("create-task-id").placeholder = "\\u7559\\u7a7a\\u5219\\u81ea\\u52a8\\u751f\\u6210\\uff0c\\u4f8b\\u5982 " + generateTaskId(scriptName);
      }
    }

    async function createTaskFromForm() {
      try {
        const payload = buildTaskPayloadFromForm();
        setCreateFeedback("\\u6b63\\u5728\\u521b\\u5efa\\u4efb\\u52a1 " + payload.task_id + " ...", "info");
        const task = await getJson("/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setCreateFeedback("\\u4efb\\u52a1\\u5df2\\u521b\\u5efa: " + task.task_id, "success");
        state.selectedTaskId = task.task_id;
        document.getElementById("create-task-id").value = "";
        await refreshAll();
        await loadTaskReport(task.task_id, { silent: false });
      } catch (error) {
        setCreateFeedback(error.message || String(error), "error");
      }
    }

    function resetCreateForm() {
      document.getElementById("create-script-name").value = "follow";
      document.getElementById("create-task-id").value = "";
      document.getElementById("create-terminal-id").value = "";
      document.getElementById("create-instance-id").value = "";
      document.getElementById("create-target-value").value = "";
      document.getElementById("create-priority").value = "0";
      document.getElementById("create-retry-limit").value = "0";
      document.getElementById("create-requested-by").value = "dashboard";
      document.getElementById("create-annotate-toggle").checked = false;
      document.getElementById("create-note").value = "";
      clearCreateFeedback();
      syncCreateFormByScript();
    }

    async function refreshAll() {
      const [summary, terminals, tasks, logs] = await Promise.all([
        getJson("/summary"),
        getJson("/terminals"),
        getJson(currentTaskQuery()),
        getJson(currentLogQuery()),
      ]);
      renderSummary(summary);
      renderTerminals(terminals.items || []);
      renderTasks(tasks.items || []);
      renderLogs(logs.items || []);
      if (state.selectedTaskId) {
        try {
          await loadTaskReport(state.selectedTaskId, { silent: true });
        } catch (error) {
          if (String(error.message || error).includes("task not found")) {
            state.selectedTaskId = null;
            document.getElementById("detail-subtitle").textContent = TEXT.taskSelect;
            document.getElementById("detail-body").textContent = "\\u9009\\u4e2d\\u7684\\u4efb\\u52a1\\u5df2\\u4e0d\\u5b58\\u5728\\uff0c\\u8bf7\\u91cd\\u65b0\\u9009\\u62e9\\u3002";
          } else {
            throw error;
          }
        }
      }
      if (state.selectedTerminalId) {
        try {
          await loadTerminalDetail(state.selectedTerminalId, { silent: true });
        } catch (error) {
          if (String(error.message || error).includes("terminal not found")) {
            state.selectedTerminalId = null;
            document.getElementById("terminal-detail-subtitle").textContent = TEXT.terminalSelect;
            document.getElementById("terminal-detail-body").textContent = "\\u9009\\u4e2d\\u7684\\u7ec8\\u7aef\\u5df2\\u4e0d\\u5b58\\u5728\\uff0c\\u8bf7\\u91cd\\u65b0\\u9009\\u62e9\\u3002";
          } else {
            throw error;
          }
        }
      }
    }

    function renderSummary(summary) {
      const terminalCount = Number(summary?.registry?.terminal_count || 0);
      const taskCount = Number(summary?.tasks?.task_count || 0);
      const failedCount = Number(summary?.tasks?.status_counts?.failed || 0);
      const logCount = Number(summary?.audit?.log_count || 0);
      document.getElementById("summary-grid").innerHTML = `
        <div class="panel summary-card"><div class="label">\\u7ec8\\u7aef\\u603b\\u6570</div><div class="value">${terminalCount}</div><div class="meta">\\u5728\\u7ebf\\u72b6\\u6001\\u6765\\u81ea\\u7ec8\\u7aef\\u6ce8\\u518c\\u4e0e\\u5fc3\\u8df3\\u3002</div></div>
        <div class="panel summary-card"><div class="label">\\u4efb\\u52a1\\u603b\\u6570</div><div class="value">${taskCount}</div><div class="meta">\\u6309\\u670d\\u52a1\\u7aef\\u6c47\\u603b\\u7edf\\u8ba1\\uff0c\\u4e0d\\u53d7\\u5f53\\u524d\\u7b5b\\u9009\\u5f71\\u54cd\\u3002</div></div>
        <div class="panel summary-card"><div class="label">\\u5931\\u8d25\\u4efb\\u52a1</div><div class="value">${failedCount}</div><div class="meta">\\u5efa\\u8bae\\u4f18\\u5148\\u6253\\u5f00\\u5931\\u8d25\\u8be6\\u60c5\\u68c0\\u67e5\\u53ef\\u91cd\\u8bd5\\u6027\\u3002</div></div>
        <div class="panel summary-card"><div class="label">\\u65e5\\u5fd7\\u603b\\u6570</div><div class="value">${logCount}</div><div class="meta">\\u53ef\\u7ed3\\u5408\\u4efb\\u52a1\\u8be6\\u60c5\\u6216\\u7ec8\\u7aef\\u8be6\\u60c5\\u6392\\u67e5\\u3002</div></div>
      `;
    }

    function renderTasks(items) {
      const body = document.getElementById("task-table-body");
      document.getElementById("task-list-meta").textContent = "\\u5f53\\u524d\\u7b5b\\u9009\\u7ed3\\u679c " + items.length + " \\u6761";
      if (!items.length) {
        body.innerHTML = '<tr><td colspan="8" class="notice">' + TEXT.noTask + '</td></tr>';
        return;
      }
      body.innerHTML = items.map((item) => {
        const activeClass = state.selectedTaskId === item.task_id ? "active" : "";
        return `
          <tr class="task-row ${activeClass}" data-task-id="${escapeHtml(item.task_id)}">
            <td class="code">${escapeHtml(item.task_id)}</td>
            <td class="code">${escapeHtml(item.terminal_id)}</td>
            <td>${escapeHtml(item.script_name)}</td>
            <td><span class="badge ${statusBadgeKind(item.status)}">${escapeHtml(statusText(item.status))}</span></td>
            <td>${escapeHtml(item.priority)}</td>
            <td>${escapeHtml(item.attempt_count)} / ${escapeHtml(item.max_attempts)}</td>
            <td class="code">${escapeHtml(item.last_error_code || "-")}</td>
            <td>${escapeHtml(formatTime(item.created_at))}</td>
          </tr>`;
      }).join("");
      for (const row of body.querySelectorAll(".task-row")) {
        row.addEventListener("click", () => loadTaskReport(row.dataset.taskId));
      }
    }

    function renderTerminals(items) {
      const body = document.getElementById("terminal-table-body");
      if (!items.length) {
        body.innerHTML = '<tr><td colspan="6" class="notice">' + TEXT.noTerminal + '</td></tr>';
        return;
      }
      body.innerHTML = items.map((item) => {
        const activeClass = state.selectedTerminalId === item.terminal_id ? "active" : "";
        return `
          <tr class="terminal-row ${activeClass}" data-terminal-id="${escapeHtml(item.terminal_id)}">
            <td class="code">${escapeHtml(item.terminal_id)}</td>
            <td>${escapeHtml(item.hostname)}</td>
            <td><span class="badge ${statusBadgeKind(item.status)}">${escapeHtml(statusText(item.status))}</span></td>
            <td>${escapeHtml(item.operator_name)}</td>
            <td class="code">${escapeHtml(item.agent_version)}</td>
            <td>${escapeHtml(formatTime(item.last_seen_at))}</td>
          </tr>`;
      }).join("");
      for (const row of body.querySelectorAll(".terminal-row")) {
        row.addEventListener("click", () => loadTerminalDetail(row.dataset.terminalId, { syncLogFilter: true }));
      }
    }

    function renderLogs(items) {
      const body = document.getElementById("log-table-body");
      document.getElementById("log-list-meta").textContent = "\\u5f53\\u524d\\u65e5\\u5fd7\\u7ed3\\u679c " + items.length + " \\u6761";
      if (!items.length) {
        body.innerHTML = '<tr><td colspan="6" class="notice">' + TEXT.noLogs + '</td></tr>';
        return;
      }
      body.innerHTML = items.map((item) => {
        const activeClass = state.selectedLogId === item.log_id ? "active" : "";
        return `
          <tr class="log-row ${activeClass}" data-log-id="${escapeHtml(item.log_id)}">
            <td class="code">${escapeHtml(item.log_id)}</td>
            <td class="code">${escapeHtml(item.terminal_id || "-")}</td>
            <td>${escapeHtml(item.level || "-")}</td>
            <td>${escapeHtml(item.message || "-")}</td>
            <td class="code">${escapeHtml(item.task_id || "-")}</td>
            <td>${escapeHtml(formatTime(item.emitted_at))}</td>
          </tr>`;
      }).join("");
      for (const row of body.querySelectorAll(".log-row")) {
        row.addEventListener("click", () => loadLogDetail(row.dataset.logId));
      }
    }

    async function loadTaskReport(taskId, options = {}) {
      const report = await getJson("/tasks/" + encodeURIComponent(taskId) + "/report");
      state.selectedTaskId = taskId;
      renderTaskDetail(report);
      if (!options.silent) document.getElementById("detail-subtitle").textContent = "\\u5f53\\u524d\\u4efb\\u52a1\\uff1a" + taskId;
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
      const attemptsHtml = attempts.length ? attempts.map((item) => `
        <div class="timeline-item">
          <div><strong>\\u7b2c ${escapeHtml(item.attempt_number)} \\u6b21</strong> | ${escapeHtml(statusText(item.status))}</div>
          <div>\\u5931\\u8d25\\u5206\\u7c7b\\uff1a${escapeHtml(item.failure_category || "-")} | \\u5931\\u8d25\\u6b65\\u9aa4\\uff1a${escapeHtml(item.failed_step_name || "-")}</div>
          <div>error_code\\uff1a<span class="code">${escapeHtml(item.error_code || "-")}</span> | step_count\\uff1a${escapeHtml(item.step_count || 0)}</div>
          <div class="meta">run_id=${escapeHtml(item.run_id || "-")} | ${escapeHtml(formatTime(item.finished_at || item.started_at))}</div>
        </div>`).join("") : '<div class="notice">\\u6682\\u65e0\\u6267\\u884c\\u5c1d\\u8bd5\\u3002</div>';
      const eventsHtml = events.length ? events.slice().reverse().map((item) => `
        <div class="timeline-item">
          <div><strong>${escapeHtml(item.event_type)}</strong> | ${escapeHtml(statusText(item.status))}</div>
          <div>${escapeHtml(item.message || "-")}</div>
          <div class="meta">${escapeHtml(formatTime(item.emitted_at))}</div>
        </div>`).join("") : '<div class="notice">\\u6682\\u65e0\\u4e8b\\u4ef6\\u65f6\\u95f4\\u7ebf\\u3002</div>';
      const latestLogHtml = latestLog && Object.keys(latestLog).length ? `
        <div class="timeline-item">
          <div><strong>${escapeHtml(latestLog.level || "-")}</strong> | ${escapeHtml(latestLog.message || "-")}</div>
          <div class="meta">${escapeHtml(formatTime(latestLog.emitted_at))}</div>
        </div>` : '<div class="notice">\\u6682\\u65e0\\u65e5\\u5fd7\\u3002</div>';
      document.getElementById("detail-body").innerHTML = `
        <div class="detail-grid">
          <div class="kv"><div class="k">\\u4efb\\u52a1\\u72b6\\u6001</div><div class="v"><span class="badge ${statusBadgeKind(task.status)}">${escapeHtml(statusText(task.status))}</span></div></div>
          <div class="kv"><div class="k">\\u5065\\u5eb7\\u72b6\\u6001</div><div class="v">${escapeHtml(healthText(diagnostics.health_status))}</div></div>
          <div class="kv"><div class="k">\\u811a\\u672c\\u7c7b\\u578b</div><div class="v">${escapeHtml(task.script_name || "-")}</div></div>
          <div class="kv"><div class="k">\\u7ec8\\u7aef / \\u5b9e\\u4f8b</div><div class="v code">${escapeHtml(task.terminal_id || "-")} / ${escapeHtml(task.instance_id || "-")}</div></div>
          <div class="kv"><div class="k">\\u5c1d\\u8bd5\\u6b21\\u6570</div><div class="v">${escapeHtml(task.attempt_count || 0)} / ${escapeHtml(task.max_attempts || 0)}</div></div>
          <div class="kv"><div class="k">\\u6700\\u540e\\u9519\\u8bef\\u7801</div><div class="v code">${escapeHtml(task.last_error_code || "-")}</div></div>
          <div class="kv"><div class="k">\\u6700\\u540e\\u9519\\u8bef\\u6d88\\u606f</div><div class="v">${escapeHtml(task.last_error_message || "-")}</div></div>
          <div class="kv"><div class="k">\\u5efa\\u8bae\\u52a8\\u4f5c</div><div class="v">${escapeHtml(summary.recommended_action || "-")}</div></div>
        </div>
        <div class="detail-section"><h3>\\u8ba1\\u5212\\u52a8\\u4f5c</h3><div class="chips">${actionNames.length ? actionNames.map((name) => `<span class="chip">${escapeHtml(name)}</span>`).join("") : '<span class="chip">\\u6682\\u65e0\\u52a8\\u4f5c\\u8ba1\\u5212</span>'}</div></div>
        <div class="detail-section"><h3>\\u6700\\u65b0\\u65e5\\u5fd7</h3>${latestLogHtml}</div>
        <div class="detail-section"><h3>\\u6267\\u884c\\u5c1d\\u8bd5</h3><div class="timeline">${attemptsHtml}</div></div>
        <div class="detail-section"><h3>\\u4e8b\\u4ef6\\u65f6\\u95f4\\u7ebf</h3><div class="timeline">${eventsHtml}</div></div>`;
    }

    async function loadTerminalDetail(terminalId, options = {}) {
      const [terminal, instances, logs] = await Promise.all([
        getJson("/terminals/" + encodeURIComponent(terminalId)),
        getJson("/instances?terminal_id=" + encodeURIComponent(terminalId)),
        getJson("/logs?terminal_id=" + encodeURIComponent(terminalId)),
      ]);
      state.selectedTerminalId = terminalId;
      if (options.syncLogFilter) document.getElementById("log-terminal-filter").value = terminalId;
      renderTerminalDetail(terminal, instances.items || [], logs.items || []);
      document.getElementById("terminal-detail-subtitle").textContent = "\\u5f53\\u524d\\u7ec8\\u7aef\\uff1a" + terminalId;
      for (const row of document.querySelectorAll(".terminal-row")) {
        row.classList.toggle("active", row.dataset.terminalId === state.selectedTerminalId);
      }
      if (options.syncLogFilter) await refreshLogs();
    }

    function renderTerminalDetail(terminal, instances, logs) {
      const instanceHtml = instances.length ? instances.map((item) => `
        <div class="timeline-item">
          <div><strong>${escapeHtml(item.instance_id)}</strong> | ${escapeHtml(item.runtime_status || "-")}</div>
          <div>profile_id=${escapeHtml(item.profile_id || "-")} | handle=${escapeHtml(item.handle || "-")}</div>
          <div class="meta">window_id=${escapeHtml(item.window_id || "-")} | remark=${escapeHtml(item.remark || "-")}</div>
        </div>`).join("") : '<div class="notice">' + TEXT.noInstances + '</div>';
      const logHtml = logs.length ? logs.slice(0, 5).map((item) => `
        <div class="timeline-item">
          <div><strong>${escapeHtml(item.level || "-")}</strong> | ${escapeHtml(item.message || "-")}</div>
          <div class="meta">${escapeHtml(formatTime(item.emitted_at))} | task_id=${escapeHtml(item.task_id || "-")}</div>
        </div>`).join("") : '<div class="notice">\\u8be5\\u7ec8\\u7aef\\u6682\\u65e0\\u65e5\\u5fd7\\u3002</div>';
      document.getElementById("terminal-detail-body").innerHTML = `
        <div class="detail-grid">
          <div class="kv"><div class="k">terminal_id</div><div class="v code">${escapeHtml(terminal.terminal_id || "-")}</div></div>
          <div class="kv"><div class="k">\\u72b6\\u6001</div><div class="v"><span class="badge ${statusBadgeKind(terminal.status)}">${escapeHtml(statusText(terminal.status))}</span></div></div>
          <div class="kv"><div class="k">hostname</div><div class="v">${escapeHtml(terminal.hostname || "-")}</div></div>
          <div class="kv"><div class="k">operator</div><div class="v">${escapeHtml(terminal.operator_name || "-")}</div></div>
          <div class="kv"><div class="k">agent_version</div><div class="v code">${escapeHtml(terminal.agent_version || "-")}</div></div>
          <div class="kv"><div class="k">last_seen_at</div><div class="v">${escapeHtml(formatTime(terminal.last_seen_at))}</div></div>
        </div>
        <div class="detail-section"><h3>metadata</h3>${jsonBlock(terminal.metadata || {})}</div>
        <div class="detail-section"><h3>\\u5b9e\\u4f8b\\u5217\\u8868</h3><div class="timeline">${instanceHtml}</div></div>
        <div class="detail-section"><h3>\\u6700\\u8fd1\\u65e5\\u5fd7</h3><div class="timeline">${logHtml}</div></div>`;
    }

    async function refreshLogs() {
      const logs = await getJson(currentLogQuery());
      renderLogs(logs.items || []);
    }

    async function loadLogDetail(logId) {
      const log = await getJson("/logs/" + encodeURIComponent(logId));
      state.selectedLogId = logId;
      document.getElementById("log-detail-subtitle").textContent = "\\u5f53\\u524d\\u65e5\\u5fd7\\uff1a" + logId;
      document.getElementById("log-detail-body").innerHTML = `
        <div class="detail-grid">
          <div class="kv"><div class="k">log_id</div><div class="v code">${escapeHtml(log.log_id || "-")}</div></div>
          <div class="kv"><div class="k">level</div><div class="v">${escapeHtml(log.level || "-")}</div></div>
          <div class="kv"><div class="k">terminal_id</div><div class="v code">${escapeHtml(log.terminal_id || "-")}</div></div>
          <div class="kv"><div class="k">task_id</div><div class="v code">${escapeHtml(log.task_id || "-")}</div></div>
          <div class="kv"><div class="k">run_id</div><div class="v code">${escapeHtml(log.run_id || "-")}</div></div>
          <div class="kv"><div class="k">emitted_at</div><div class="v">${escapeHtml(formatTime(log.emitted_at))}</div></div>
        </div>
        <div class="detail-section"><h3>message</h3><div class="timeline-item">${escapeHtml(log.message || "-")}</div></div>
        <div class="detail-section"><h3>details</h3>${jsonBlock(log.details || {})}</div>`;
      for (const row of document.querySelectorAll(".log-row")) {
        row.classList.toggle("active", row.dataset.logId === state.selectedLogId);
      }
    }

    async function controlSelectedTask(action) {
      if (!state.selectedTaskId) return;
      const reasonInput = document.getElementById("control-reason");
      const reason = reasonInput.value.trim() || (action === "retry" ? TEXT.retryReason : TEXT.cancelReason);
      try {
        await getJson("/tasks/control", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_id: state.selectedTaskId, action, reason, requested_by: "dashboard" }),
        });
        await refreshAll();
        await loadTaskReport(state.selectedTaskId, { silent: true });
      } catch (error) {
        window.alert(error.message || String(error));
      }
    }

    function bindEvents() {
      document.getElementById("create-script-name").addEventListener("change", syncCreateFormByScript);
      document.getElementById("create-task-btn").addEventListener("click", createTaskFromForm);
      document.getElementById("create-reset-btn").addEventListener("click", resetCreateForm);
      document.getElementById("apply-filters").addEventListener("click", refreshAll);
      document.getElementById("clear-filters").addEventListener("click", async () => {
        document.getElementById("filter-terminal").value = "";
        document.getElementById("filter-status").value = "";
        document.getElementById("filter-script").value = "";
        await refreshAll();
      });
      document.getElementById("apply-log-filters").addEventListener("click", refreshLogs);
      document.getElementById("clear-log-filters").addEventListener("click", async () => {
        document.getElementById("log-terminal-filter").value = "";
        document.getElementById("log-level-filter").value = "";
        await refreshLogs();
      });
      document.getElementById("refresh-all").addEventListener("click", refreshAll);
      document.getElementById("retry-task-btn").addEventListener("click", () => controlSelectedTask("retry"));
      document.getElementById("cancel-task-btn").addEventListener("click", () => controlSelectedTask("cancel"));
      document.getElementById("auto-refresh-toggle").addEventListener("click", () => {
        state.autoRefresh = !state.autoRefresh;
        document.getElementById("auto-refresh-toggle").textContent = "\\u81ea\\u52a8\\u5237\\u65b0\\uff1a" + (state.autoRefresh ? "\\u5f00" : "\\u5173");
      });
    }

    async function bootstrap() {
      bindEvents();
      resetCreateForm();
      await refreshAll();
      window.setInterval(() => {
        if (state.autoRefresh) refreshAll().catch((error) => console.error(error));
      }, 5000);
    }

    bootstrap().catch((error) => {
      document.getElementById("detail-body").innerHTML = '<div class="notice">\\u9875\\u9762\\u521d\\u59cb\\u5316\\u5931\\u8d25\\uff1a' + escapeHtml(error.message || String(error)) + '</div>';
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    run_server()
