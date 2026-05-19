"""Minimal NAS HTTP server for terminal registration and state sync."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote_plus

from nas_control_plane.dashboard_html import DASHBOARD_HTML
from nas_control_plane.memory_router import MemoryRouter
from nas_control_plane.models import BlacklistRecord, InstanceRecord, TaskRecord
from nas_control_plane.services import (
    AccountInventoryRepository,
    AmmoTargetRepository,
    AuditLogRepository,
    BlacklistRepository,
    AuditService,
    CreatorInboxRepository,
    DailyActionStatRepository,
    JsonStateStore,
    LocalQueueDispatchProvider,
    PluginAutoDispatchRepository,
    PluginRuntimeService,
    PluginCampaignRepository,
    QueueDeliveryRepository,
    QueueDeliveryTransportService,
    TaskDispatchService,
    TaskRepository,
    TerminalRegistryService,
    TerminalStateRepository,
)
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    PluginTaskPullResponsePayload,
    PluginDispatchRequestPayload,
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
    queue_delivery_repository = QueueDeliveryRepository(store)
    creator_repository = CreatorInboxRepository(store)
    ammo_repository = AmmoTargetRepository(store)
    account_repository = AccountInventoryRepository(store)
    stat_repository = DailyActionStatRepository(store)
    campaign_repository = PluginCampaignRepository(store)
    auto_dispatch_repository = PluginAutoDispatchRepository(store)
    audit_repository = AuditLogRepository(store)
    blacklist_repository = BlacklistRepository(store)

    registry = TerminalRegistryService(repository=terminal_repository)
    queue_transport = QueueDeliveryTransportService(
        task_repository=task_repository,
        delivery_repository=queue_delivery_repository,
        now_fn=now_fn,
    )
    tasks = TaskDispatchService(
        repository=task_repository,
        now_fn=now_fn,
        queue_transport=queue_transport,
        queue_dispatch_provider=LocalQueueDispatchProvider(queue_transport),
    )
    plugin_runtime = PluginRuntimeService(
        creator_repository=creator_repository,
        ammo_repository=ammo_repository,
        account_repository=account_repository,
        stat_repository=stat_repository,
        campaign_repository=campaign_repository,
        auto_dispatch_repository=auto_dispatch_repository,
        now_fn=now_fn,
    )
    audit = AuditService(repository=audit_repository)
    memory_router = MemoryRouter(memory_service=None)  # auto-detect workspace

    # API token for request authentication
    EXPECTED_TOKEN = os.environ.get("XMATRIX_API_TOKEN", "xm2026_a1b2c3d4e5")

    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "BPlusNAS/0.1"

        def _check_token(self) -> bool:
            """Validate X-API-Token header. Returns False if invalid (response already sent)."""
            token = self.headers.get("X-API-Token", "")
            if token == EXPECTED_TOKEN:
                return True
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid or missing API token"})
            return False

        def do_GET(self) -> None:  # noqa: N802
            path = self._path_without_query()

            # Public endpoints (no token required)
            if path == "/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if path.startswith("/static/") and path != "/static/":
                # Token check for static files
                if not self._check_token():
                    return
                STATIC_DIR = (Path(__file__).parent / "static").resolve()
                static_dir_str = str(STATIC_DIR) + os.sep
                # removeprefix is Python 3.9+
                relative_part = path.removeprefix("/static/")
                static_path = (STATIC_DIR / relative_part).resolve()
                # Ensure the resolved path is within the static directory
                if not str(static_path).startswith(static_dir_str):
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                    return
                if static_path.suffix not in {".html", ".js", ".css"}:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "file type not allowed"})
                    return
                if not static_path.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                content = static_path.read_bytes()
                mime_map = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
                content_type = mime_map.get(static_path.suffix, "text/plain")
                self._send_content(HTTPStatus.OK, content, content_type)
                return

            if path in {"/", "/dashboard"}:
                self._send_html(HTTPStatus.OK, DASHBOARD_HTML)
                return

            # Token check for all other API routes
            if not self._check_token():
                return

            # Memory endpoints
            if memory_router.dispatch_memory(self, path):
                return

            if path == "/terminals":
                payload = [
                    _record_to_dict(record)
                    for record in registry.list_terminals(
                        status=self._query_param("status"),
                        operator_name=self._query_param("operator_name"),
                        min_active_task_count=_parse_int(self._query_param("min_active_task_count")),
                        max_parallel_tasks=_parse_int(self._query_param("max_parallel_tasks")),
                        blocked_instance_id=self._query_param("blocked_instance_id"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/blacklist":
                records = blacklist_repository.load_all()
                payload = [_record_to_dict(record) for record in records.values()]
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

            if path == "/api/profiles":
                now = datetime.utcnow()
                today_str = now.date().isoformat()
                sixty_seconds_ago = (now.timestamp()) - 60
                instances = registry.list_instances()
                terminals = {t.terminal_id: t for t in registry.list_terminals()}
                daily_stats = plugin_runtime.list_daily_stats(stat_date=today_str)
                all_tasks_running = tasks.query_tasks(status="running")
                running_by_instance: dict[str, list[TaskRecord]] = {}
                for task in all_tasks_running:
                    iid = task.instance_id
                    if iid is not None:
                        running_by_instance.setdefault(iid, []).append(task)

                profiles: list[dict[str, Any]] = []
                for instance in instances:
                    terminal = terminals.get(instance.terminal_id)
                    last_seen_ts: float | None = None
                    if terminal is not None and terminal.last_seen_at is not None:
                        last_seen_ts = terminal.last_seen_at.timestamp()

                    running_tasks = running_by_instance.get(instance.instance_id, [])
                    engine: str | None = None
                    if running_tasks:
                        engine = running_tasks[0].script_name

                    status = "offline"
                    runtime_status_lower = (instance.runtime_status or "").lower()
                    if "error" in runtime_status_lower:
                        status = "error"
                    elif last_seen_ts is not None and last_seen_ts >= sixty_seconds_ago:
                        status = "online"

                    instances_stats: dict[str, int] = {
                        "added": 0, "ice": 0, "ad": 0, "corpse": 0, "reject": 0,
                    }
                    for stat in daily_stats:
                        if stat.account_id == instance.profile_id:
                            action = stat.action_type
                            if action in instances_stats:
                                instances_stats[action] += stat.success_count

                    profiles.append({
                        "profile_id": instance.profile_id,
                        "handle": instance.handle,
                        "screen_name": instance.metadata.get("screen_name", instance.handle),
                        "agent_id": instance.terminal_id,
                        "window_id": instance.window_id,
                        "engine": engine,
                        "status": status,
                        "last_seen_ts": last_seen_ts,
                        "memory_mb": instance.metadata.get("memory_mb"),
                        "logged_in": instance.metadata.get("logged_in", True),
                        "daily_stats": instances_stats,
                    })
                self._send_json(HTTPStatus.OK, profiles)
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

            if path == "/plugin/creators":
                payload = [_record_to_dict(record) for record in plugin_runtime.list_creator_items()]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/plugin/ammo":
                payload = [
                    _record_to_dict(record)
                    for record in plugin_runtime.list_ammo_targets(status=self._query_param("status"))
                ]
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "items": payload,
                        "summary": plugin_runtime.ammo_summary(),
                    },
                )
                return

            if path == "/plugin/stats/daily":
                payload = [
                    _record_to_dict(record)
                    for record in plugin_runtime.list_daily_stats(stat_date=self._query_param("stat_date"))
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/plugin/accounts":
                payload = [
                    _record_to_dict(record)
                    for record in plugin_runtime.list_accounts(status=self._query_param("status"))
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/plugin/campaigns":
                payload = [
                    _record_to_dict(record)
                    for record in plugin_runtime.list_campaigns(
                        plugin_name=self._query_param("plugin_name"),
                        status=self._query_param("status"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/plugin/dispatch-rules":
                payload = [
                    _record_to_dict(record)
                    for record in plugin_runtime.list_auto_dispatch_rules(
                        account_id=self._query_param("account_id"),
                        plugin_name=self._query_param("plugin_name"),
                        status=self._query_param("status"),
                    )
                ]
                self._send_json(HTTPStatus.OK, {"items": payload})
                return

            if path == "/api/stats/detail":
                today_str = datetime.utcnow().date().isoformat()
                stats = plugin_runtime.list_daily_stats(stat_date=today_str)
                aggregated: dict[str, dict[str, int]] = {}
                for stat in stats:
                    worker_id = stat.account_id or "-"
                    if worker_id not in aggregated:
                        aggregated[worker_id] = {"added": 0, "ice": 0, "ad": 0, "corpse": 0, "reject": 0}
                    action = stat.action_type
                    if action in aggregated[worker_id]:
                        aggregated[worker_id][action] += stat.success_count
                detail: list[dict[str, Any]] = []
                for worker_id, counts in aggregated.items():
                    total = sum(counts.values())
                    success_count = counts.get("added", 0) + counts.get("ice", 0) + counts.get("ad", 0)
                    total_actions = total
                    success_rate = "0%"
                    if total_actions > 0:
                        success_rate = f"{int(success_count / total_actions * 100)}%"
                    detail.append({
                        "worker_id": worker_id,
                        "added": counts["added"],
                        "ice": counts["ice"],
                        "ad": counts["ad"],
                        "corpse": counts["corpse"],
                        "reject": counts["reject"],
                        "total": total,
                        "success_rate": success_rate,
                    })
                self._send_json(HTTPStatus.OK, {"ok": True, "detail": detail})
                return

            if path == "/api/dashboard_data":
                running_tasks = tasks.list_tasks()
                follow_count = sum(1 for t in running_tasks if t.script_name == "follow" and t.status == "running")
                chat_count = sum(1 for t in running_tasks if t.script_name == "chat" and t.status == "running")
                # Calculate success rate from completed vs failed tasks
                all_tasks = tasks.list_tasks()
                completed = [t for t in all_tasks if t.status == "completed" and t.script_name in ("follow", "chat")]
                failed = [t for t in all_tasks if t.status == "failed" and t.script_name in ("follow", "chat")]
                total_done = len(completed) + len(failed)
                success_rate = "0%"
                if total_done > 0:
                    success_rate = f"{int(len(completed) / total_done * 100)}%"
                ammo_summary = plugin_runtime.ammo_summary()
                self._send_json(HTTPStatus.OK, {
                    "stats": {
                        "follow": follow_count,
                        "chat": chat_count,
                        "follow_change": 0,
                        "chat_change": 0,
                        "rate": success_rate,
                    },
                    "ammo_remaining": ammo_summary.get("available", 0),
                    "ammo_worked": ammo_summary.get("consumed", 0),
                })
                return

            if path == "/tasks":
                payload = [
                    _record_to_dict(record)
                    for record in tasks.query_tasks(
                        terminal_id=self._query_param("terminal_id"),
                        preferred_terminal_id=self._query_param("preferred_terminal_id"),
                        dispatch_mode=self._query_param("dispatch_mode"),
                        queue_dispatch_status=self._query_param("queue_dispatch_status"),
                        queue_dispatch_accepted=_parse_bool(self._query_param("queue_dispatch_accepted")),
                        status=self._query_param("status"),
                        script_name=self._query_param("script_name"),
                        retryable=_parse_bool(self._query_param("retryable")),
                        final=_parse_bool(self._query_param("final")),
                        wait_reason=self._query_param("wait_reason"),
                        blocked_by_instance_id=self._query_param("blocked_by_instance_id"),
                        retry_kind=self._query_param("retry_kind"),
                        terminal_affinity=self._query_param("terminal_affinity"),
                        recovery_claim_terminal_id=self._query_param("recovery_claim_terminal_id"),
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
            path = self.path
            # Memory endpoints (consume body themselves)
            if memory_router.dispatch_memory(self, path):
                return

            try:
                payload = self._read_json()

                if self.path == "/register":
                    record = registry.register_terminal(_parse_registration(payload))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/heartbeat":
                    record = registry.record_heartbeat(_parse_heartbeat(payload))
                    recovered_task_ids = list(record.metadata.get("recovered_task_ids", []))
                    accepted_recovered_task_ids: list[str] = []
                    missing_recovered_task_ids: list[str] = []
                    for task_id in recovered_task_ids:
                        try:
                            task_record = tasks.mark_recovered(task_id, recovered_from_terminal_id=record.terminal_id)
                            accepted_recovered_task_ids.append(task_record.task_id)
                            audit.record(
                                terminal_id=record.terminal_id,
                                level="info",
                                message="task recovered from terminal restart",
                                task_id=task_record.task_id,
                                details={
                                    "recovered_from_terminal_id": record.terminal_id,
                                    "recovered_task_id": task_record.task_id,
                                    "recovered_task_status": task_record.status,
                                },
                            )
                        except KeyError:
                            missing_recovered_task_ids.append(task_id)
                            audit.record(
                                terminal_id=record.terminal_id,
                                level="warn",
                                message="recovered task missing on NAS",
                                task_id=task_id,
                                details={"recovered_from_terminal_id": record.terminal_id},
                            )
                    payload = _record_to_dict(record)
                    payload["accepted_recovered_task_ids"] = accepted_recovered_task_ids
                    payload["missing_recovered_task_ids"] = missing_recovered_task_ids
                    self._send_json(HTTPStatus.OK, payload)
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
                    blocked_instance_ids = {
                        str(item)
                        for item in payload.get("blocked_instance_ids", [])
                        if item is not None
                    }
                    records = tasks.claim_tasks(
                        terminal_id,
                        limit=int(max_tasks) if max_tasks is not None else None,
                        blocked_instance_ids=blocked_instance_ids,
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {"terminal_id": terminal_id, "items": [_record_to_dict(record) for record in records]},
                    )
                    return

                if self.path == "/tasks/result":
                    result = _parse_action_result(payload)
                    task_record = tasks.record_result(result)
                    ammo_record = None
                    ammo_target_id = task_record.parameters.get("ammo_target_id")
                    if ammo_target_id is not None:
                        ammo_record = plugin_runtime.sync_task_result_for_ammo(
                            target_id=str(ammo_target_id),
                            task_id=task_record.task_id,
                            task_status=task_record.status,
                            retryable=task_record.retryable,
                            final=task_record.final,
                            error_code=task_record.last_error_code,
                        )
                    if result.delivery_id is not None:
                        queue_transport.ack_delivery(
                            terminal_id=result.terminal_id,
                            queue_topic=result.details.get("queue_topic") if isinstance(result.details, dict) else None,
                            delivery_id=result.delivery_id,
                            claim_lease_id=result.claim_lease_id,
                        )
                    log_record = audit.record_action_result(result)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "task": _record_to_dict(task_record),
                            "ammo": _record_to_dict(ammo_record) if ammo_record is not None else None,
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
                    ammo_record = None
                    ammo_target_id = record.parameters.get("ammo_target_id")
                    if ammo_target_id is not None and record.status == "cancelled":
                        ammo_record = plugin_runtime.release_ammo_target(
                            target_id=str(ammo_target_id),
                            reason="cancelled",
                        )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "task": _record_to_dict(record),
                            "ammo": _record_to_dict(ammo_record) if ammo_record is not None else None,
                        },
                    )
                    return

                if self.path == "/tasks/running":
                    run = _parse_script_run(payload)
                    task_record = tasks.mark_running(run)
                    self._send_json(HTTPStatus.OK, _record_to_dict(task_record))
                    return

                if self.path == "/plugin/report-creator":
                    record = plugin_runtime.report_creator(
                        creator_id=str(payload["creator_id"]),
                        handle=str(payload["handle"]) if payload.get("handle") is not None else None,
                        source=str(payload.get("source", "plugin")),
                        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
                        profile_id=str(payload["profile_id"]) if payload.get("profile_id") is not None else None,
                        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                        dedupe_key=str(payload["dedupe_key"]) if payload.get("dedupe_key") is not None else None,
                        raw_payload=dict(payload),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/ammo/add":
                    record = plugin_runtime.add_ammo_target(
                        target_value=str(payload["target_value"]),
                        target_type=str(payload.get("target_type", "handle")),
                        source=str(payload.get("source", "plugin")),
                        creator_id=str(payload["creator_id"]) if payload.get("creator_id") is not None else None,
                        metadata=dict(payload.get("metadata", {})),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/account/register":
                    record = plugin_runtime.register_account(
                        account_id=str(payload["account_id"]),
                        profile_id=str(payload["profile_id"]),
                        handle=str(payload["handle"]) if payload.get("handle") is not None else None,
                        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
                        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                        capability_tags=list(payload.get("capability_tags", [])),
                        metadata=dict(payload.get("metadata", {})),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/account/status":
                    record = plugin_runtime.set_account_status(
                        account_id=str(payload["account_id"]),
                        status=str(payload["status"]),
                        metadata=dict(payload.get("metadata", {})),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/account/eligibility":
                    result = plugin_runtime.evaluate_account_eligibility(
                        account_id=str(payload["account_id"]),
                        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                        action_type=str(payload["action_type"]) if payload.get("action_type") is not None else None,
                        stat_date=str(payload["stat_date"]) if payload.get("stat_date") is not None else None,
                    )
                    self._send_json(HTTPStatus.OK, result)
                    return

                if self.path == "/plugin/ammo/claim":
                    record = plugin_runtime.claim_ammo_target(
                        account_id=str(payload["account_id"]),
                        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                        target_type=str(payload["target_type"]) if payload.get("target_type") is not None else None,
                        action_type=str(payload["action_type"]) if payload.get("action_type") is not None else None,
                        stat_date=str(payload["stat_date"]) if payload.get("stat_date") is not None else None,
                    )
                    self._send_json(HTTPStatus.OK, {"item": _record_to_dict(record) if record is not None else None})
                    return

                if self.path == "/plugin/ammo/consume":
                    record = plugin_runtime.mark_ammo_consumed(
                        target_id=str(payload["target_id"]),
                        task_id=str(payload["task_id"]) if payload.get("task_id") is not None else None,
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/action-log":
                    existing_metadata = dict(payload.get("metadata", {}))
                    action_metadata = {
                        **existing_metadata,
                        "detail": payload.get("detail") if payload.get("detail") is not None else existing_metadata.get("detail"),
                        "failed": payload.get("failed") if payload.get("failed") is not None else existing_metadata.get("failed"),
                        "error_code": (
                            payload.get("error_code")
                            if payload.get("error_code") is not None
                            else existing_metadata.get("error_code")
                        ),
                        "error_message": (
                            payload.get("error_message")
                            if payload.get("error_message") is not None
                            else existing_metadata.get("error_message")
                        ),
                        "task_id": payload.get("task_id") if payload.get("task_id") is not None else existing_metadata.get("task_id"),
                        "action_index": (
                            payload.get("action_index")
                            if payload.get("action_index") is not None
                            else existing_metadata.get("action_index")
                        ),
                        "target_handle": (
                            payload.get("target_handle")
                            if payload.get("target_handle") is not None
                            else existing_metadata.get("target_handle")
                        ),
                        "target_url": (
                            payload.get("target_url")
                            if payload.get("target_url") is not None
                            else existing_metadata.get("target_url")
                        ),
                    }
                    record = plugin_runtime.record_daily_action(
                        account_id=str(payload["account_id"]) if payload.get("account_id") is not None else None,
                        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
                        plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                        script_name=str(payload["script_name"]),
                        action_type=str(payload["action_type"]),
                        success=bool(payload.get("success", True)),
                        metadata=action_metadata,
                        stat_date=str(payload["stat_date"]) if payload.get("stat_date") is not None else None,
                    )
                    task_record = None
                    task_id = str(action_metadata["task_id"]) if action_metadata.get("task_id") is not None else None
                    if task_id is not None:
                        task_record = tasks.append_plugin_action_event(
                            task_id=task_id,
                            action_name=str(payload["action_type"]),
                            success=bool(payload.get("success", True)),
                            summary=str(action_metadata.get("detail") or payload["action_type"]),
                            metadata=action_metadata,
                        )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "stat": _record_to_dict(record),
                            "task": _record_to_dict(task_record) if task_record is not None else None,
                        },
                    )
                    return

                if self.path == "/plugin/campaign/upsert":
                    record = plugin_runtime.upsert_campaign(
                        campaign_id=str(payload["campaign_id"]),
                        plugin_name=str(payload["plugin_name"]),
                        script_name=str(payload["script_name"]),
                        action_type=str(payload["action_type"]),
                        copy_items=list(payload.get("copy_items", [])),
                        status=str(payload.get("status", "active")),
                        metadata=dict(payload.get("metadata", {})),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/dispatch-rule/upsert":
                    record = plugin_runtime.upsert_auto_dispatch_rule(
                        rule_id=str(payload["rule_id"]),
                        account_id=str(payload["account_id"]),
                        plugin_name=str(payload["plugin_name"]),
                        script_name=str(payload["script_name"]),
                        action_plan=list(payload.get("action_plan", [])),
                        campaign_id=str(payload["campaign_id"]) if payload.get("campaign_id") is not None else None,
                        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
                        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
                        target_type=str(payload.get("target_type", "handle")),
                        status=str(payload.get("status", "active")),
                        metadata=dict(payload.get("metadata", {})),
                    )
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/plugin/dispatch":
                    dispatch = _parse_plugin_dispatch(payload)
                    self._send_json(
                        HTTPStatus.OK,
                        _dispatch_plugin_task(
                            dispatch_payload=dispatch,
                            plugin_runtime=plugin_runtime,
                            tasks=tasks,
                        ),
                    )
                    return

                if self.path == "/plugin/task/pull":
                    terminal_id = str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None
                    instance_id = str(payload["instance_id"]) if payload.get("instance_id") is not None else None
                    account_id = str(payload["account_id"]) if payload.get("account_id") is not None else None
                    script_name = str(payload["script_name"]) if payload.get("script_name") is not None else None
                    tasks_found = tasks.query_tasks(
                        terminal_id=terminal_id,
                        status="queued",
                        script_name=script_name,
                    )
                    selected = None
                    for item in tasks_found:
                        params = item.parameters or {}
                        dispatch_origin = params.get("dispatch_origin")
                        if dispatch_origin not in {None, "plugin_runtime", "nas_direct"}:
                            continue
                        if account_id is not None and str(params.get("account_id") or "") != account_id:
                            continue
                        if instance_id is not None and item.instance_id not in {None, instance_id}:
                            continue
                        selected = item
                        break
                    if selected is None and account_id is not None:
                        rule = plugin_runtime.select_auto_dispatch_rule(
                            account_id=account_id,
                            plugin_name=str(payload["plugin_name"]) if payload.get("plugin_name") is not None else None,
                            script_name=script_name,
                            terminal_id=terminal_id,
                            instance_id=instance_id,
                        )
                        if rule is not None:
                            auto_task_id = f"task-auto-{account_id}-{len(tasks.list_tasks()) + 1}"
                            dispatch_payload = PluginDispatchRequestPayload(
                                task_id=auto_task_id,
                                account_id=rule.account_id,
                                plugin_name=rule.plugin_name,
                                script_name=rule.script_name,
                                target={},
                                action_plan=list(rule.action_plan),
                                campaign_id=rule.campaign_id,
                                copy_payload=None,
                                target_type=rule.target_type,
                                terminal_id=rule.terminal_id or terminal_id,
                                instance_id=rule.instance_id or instance_id,
                                priority=int(rule.metadata.get("priority", 0)),
                                retry_limit=int(rule.metadata.get("retry_limit", 0)),
                                close_after_actions=bool(rule.metadata.get("close_after_actions", False)),
                                requested_by=str(rule.metadata.get("requested_by") or "plugin_auto_dispatch"),
                                dispatch_mode=str(rule.metadata.get("dispatch_mode", "claim_http")),
                                queue_topic=str(rule.metadata.get("queue_topic")) if rule.metadata.get("queue_topic") is not None else None,
                                parameters={
                                    **dict(rule.metadata.get("parameters", {}))
                                },
                                metadata={
                                    **dict(rule.metadata),
                                    "dispatch_rule_id": rule.rule_id,
                                    "dispatch_generated_by": "plugin_task_pull",
                                },
                            )
                            dispatch_result = _dispatch_plugin_task(
                                dispatch_payload=dispatch_payload,
                                plugin_runtime=plugin_runtime,
                                tasks=tasks,
                            )
                            if dispatch_result["accepted"] and dispatch_result["task"] is not None:
                                selected = tasks.get_task(dispatch_result["task"]["task_id"])
                    if selected is None:
                        self._send_json(HTTPStatus.OK, {"accepted": False, "task": None})
                        return

                    params = dict(selected.parameters)
                    task_payload = PluginTaskPullResponsePayload(
                        task_id=selected.task_id,
                        account_id=str(params.get("account_id") or ""),
                        plugin_name=str(params.get("plugin_name") or ""),
                        script_name=selected.script_name,
                        target=dict(params.get("target") or {}),
                        action_plan=list(params.get("action_plan") or []),
                        campaign_id=str(params["campaign_id"]) if params.get("campaign_id") is not None else None,
                        copy_payload=dict(params.get("copy_payload") or {}) if params.get("copy_payload") is not None else None,
                        terminal_id=selected.terminal_id,
                        instance_id=selected.instance_id,
                        status=selected.status,
                        parameters=params,
                    )
                    self._send_json(HTTPStatus.OK, {"accepted": True, "task": task_payload.to_dict()})
                    return

                if self.path == "/instance/remark-sync":
                    instance_id = str(payload["instance_id"])
                    record = registry.get_instance(instance_id)
                    metadata = {
                        **dict(record.metadata),
                        "current_account_handle": payload.get("current_account_handle"),
                        "remark_sync_status": str(payload.get("remark_sync_status", "ok")),
                        "remark_sync_error": payload.get("remark_sync_error"),
                        "last_remark_sync_at": datetime.utcnow().isoformat(),
                    }
                    updated = InstanceSnapshotPayload(
                        terminal_id=record.terminal_id,
                        instance_id=record.instance_id,
                        profile_id=record.profile_id,
                        handle=str(payload["current_account_handle"]) if payload.get("current_account_handle") is not None else record.handle,
                        runtime_status=record.runtime_status,
                        window_id=record.window_id,
                        remark=str(payload["remark"]) if payload.get("remark") is not None else record.remark,
                        metadata=metadata,
                    )
                    synced = registry.sync_instances(record.terminal_id, [updated] + [
                        InstanceSnapshotPayload(
                            terminal_id=item.terminal_id,
                            instance_id=item.instance_id,
                            profile_id=item.profile_id,
                            handle=item.handle,
                            runtime_status=item.runtime_status,
                            window_id=item.window_id,
                            remark=item.remark,
                            metadata=dict(item.metadata),
                        )
                        for item in registry.list_instances(terminal_id=record.terminal_id)
                        if item.instance_id != instance_id
                    ])
                    self._send_json(
                        HTTPStatus.OK,
                        {"items": [_record_to_dict(item) for item in synced]},
                    )
                    return

                if self.path == "/instance/restart":
                    instance_id = str(payload["instance_id"])
                    record = registry.get_instance(instance_id)
                    metadata = {
                        **dict(record.metadata),
                        "restart_requested": True,
                        "restart_reason": str(payload.get("reason") or "manual_restart"),
                        "restart_requested_at": datetime.utcnow().isoformat(),
                        "instance_health_status": "restart_requested",
                    }
                    updated = InstanceSnapshotPayload(
                        terminal_id=record.terminal_id,
                        instance_id=record.instance_id,
                        profile_id=record.profile_id,
                        handle=record.handle,
                        runtime_status="restart_requested",
                        window_id=record.window_id,
                        remark=record.remark,
                        metadata=metadata,
                    )
                    synced = registry.sync_instances(record.terminal_id, [updated] + [
                        InstanceSnapshotPayload(
                            terminal_id=item.terminal_id,
                            instance_id=item.instance_id,
                            profile_id=item.profile_id,
                            handle=item.handle,
                            runtime_status=item.runtime_status,
                            window_id=item.window_id,
                            remark=item.remark,
                            metadata=dict(item.metadata),
                        )
                        for item in registry.list_instances(terminal_id=record.terminal_id)
                        if item.instance_id != instance_id
                    ])
                    self._send_json(
                        HTTPStatus.OK,
                        {"accepted": True, "items": [_record_to_dict(item) for item in synced]},
                    )
                    return

                if self.path == "/plugin/stats/cleanup":
                    removed = plugin_runtime.cleanup_expired_stats()
                    self._send_json(HTTPStatus.OK, {"removed": removed})
                    return

                if self.path == "/queue/claim":
                    result = queue_transport.claim(
                        terminal_id=payload["terminal_id"],
                        max_tasks=int(payload["max_tasks"]) if payload.get("max_tasks") is not None else None,
                        queue_topic=payload.get("queue_topic"),
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "status": result.status,
                            "queue_topic": result.queue_topic,
                            "details": result.details,
                            "items": [item.to_dict() for item in result.assignments],
                        },
                    )
                    return

                if self.path == "/queue/ack":
                    result = queue_transport.ack_delivery(
                        terminal_id=payload["terminal_id"],
                        queue_topic=payload.get("queue_topic"),
                        delivery_id=payload.get("delivery_id"),
                        claim_lease_id=payload.get("claim_lease_id"),
                    )
                    self._send_json(HTTPStatus.OK, _queue_action_result_to_dict(result))
                    return

                if self.path == "/queue/defer":
                    result = queue_transport.defer_delivery(
                        terminal_id=payload["terminal_id"],
                        queue_topic=payload.get("queue_topic"),
                        delivery_id=payload.get("delivery_id"),
                        claim_lease_id=payload.get("claim_lease_id"),
                        reason=payload.get("reason"),
                    )
                    self._send_json(HTTPStatus.OK, _queue_action_result_to_dict(result))
                    return

                if self.path == "/blacklist/add":
                    if not self._check_token():
                        return
                    target_id = f"bl-{blacklist_repository.load_all().__len__() + 1}"
                    record = blacklist_repository.add(BlacklistRecord(
                        target_id=str(payload.get("target_id", target_id)),
                        target_value=str(payload["target_value"]),
                        target_type=str(payload.get("target_type", "handle")),
                        reason=str(payload["reason"]) if payload.get("reason") is not None else None,
                        source=str(payload.get("source", "manual")),
                    ))
                    self._send_json(HTTPStatus.OK, _record_to_dict(record))
                    return

                if self.path == "/blacklist/remove":
                    if not self._check_token():
                        return
                    target_id = str(payload["target_id"])
                    blacklist_repository.remove(target_id)
                    self._send_json(HTTPStatus.OK, {"removed": target_id})
                    return

                if self.path == "/instances/batch-action":
                    action = str(payload["action"])
                    instance_ids = list(payload.get("instance_ids", []))
                    results: list[dict[str, Any]] = []
                    for instance_id in instance_ids:
                        try:
                            instance = registry.get_instance(instance_id)
                        except KeyError:
                            results.append({"instance_id": instance_id, "accepted": False, "error": "instance not found"})
                            continue
                        if action == "stop":
                            metadata = {**dict(instance.metadata), "stop_requested": True, "stop_requested_at": datetime.utcnow().isoformat()}
                            updated = InstanceSnapshotPayload(
                                terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                                profile_id=instance.profile_id, handle=instance.handle,
                                runtime_status="stop_requested", window_id=instance.window_id,
                                remark=instance.remark, metadata=metadata,
                            )
                            registry.sync_instances(instance.terminal_id, [updated] + [
                                InstanceSnapshotPayload(
                                    terminal_id=item.terminal_id, instance_id=item.instance_id,
                                    profile_id=item.profile_id, handle=item.handle,
                                    runtime_status=item.runtime_status, window_id=item.window_id,
                                    remark=item.remark, metadata=dict(item.metadata),
                                )
                                for item in registry.list_instances(terminal_id=instance.terminal_id)
                                if item.instance_id != instance_id
                            ])
                            results.append({"instance_id": instance_id, "accepted": True, "action": "stop"})
                        elif action == "close":
                            metadata = {**dict(instance.metadata), "close_requested": True, "close_requested_at": datetime.utcnow().isoformat()}
                            updated = InstanceSnapshotPayload(
                                terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                                profile_id=instance.profile_id, handle=instance.handle,
                                runtime_status="close_requested", window_id=instance.window_id,
                                remark=instance.remark, metadata=metadata,
                            )
                            registry.sync_instances(instance.terminal_id, [updated] + [
                                InstanceSnapshotPayload(
                                    terminal_id=item.terminal_id, instance_id=item.instance_id,
                                    profile_id=item.profile_id, handle=item.handle,
                                    runtime_status=item.runtime_status, window_id=item.window_id,
                                    remark=item.remark, metadata=dict(item.metadata),
                                )
                                for item in registry.list_instances(terminal_id=instance.terminal_id)
                                if item.instance_id != instance_id
                            ])
                            results.append({"instance_id": instance_id, "accepted": True, "action": "close"})
                        elif action == "open":
                            metadata = {**dict(instance.metadata), "open_requested": True, "open_requested_at": datetime.utcnow().isoformat()}
                            updated = InstanceSnapshotPayload(
                                terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                                profile_id=instance.profile_id, handle=instance.handle,
                                runtime_status="open_requested", window_id=instance.window_id,
                                remark=instance.remark, metadata=metadata,
                            )
                            registry.sync_instances(instance.terminal_id, [updated] + [
                                InstanceSnapshotPayload(
                                    terminal_id=item.terminal_id, instance_id=item.instance_id,
                                    profile_id=item.profile_id, handle=item.handle,
                                    runtime_status=item.runtime_status, window_id=item.window_id,
                                    remark=item.remark, metadata=dict(item.metadata),
                                )
                                for item in registry.list_instances(terminal_id=instance.terminal_id)
                                if item.instance_id != instance_id
                            ])
                            results.append({"instance_id": instance_id, "accepted": True, "action": "open"})
                        elif action == "auto_start":
                            # 1. Flag instance for open
                            metadata = {**dict(instance.metadata), "open_requested": True, "open_requested_at": datetime.utcnow().isoformat()}
                            updated = InstanceSnapshotPayload(
                                terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                                profile_id=instance.profile_id, handle=instance.handle,
                                runtime_status="open_requested", window_id=instance.window_id,
                                remark=instance.remark, metadata=metadata,
                            )
                            registry.sync_instances(instance.terminal_id, [updated] + [
                                InstanceSnapshotPayload(
                                    terminal_id=item.terminal_id, instance_id=item.instance_id,
                                    profile_id=item.profile_id, handle=item.handle,
                                    runtime_status=item.runtime_status, window_id=item.window_id,
                                    remark=item.remark, metadata=dict(item.metadata),
                                )
                                for item in registry.list_instances(terminal_id=instance.terminal_id)
                                if item.instance_id != instance_id
                            ])
                            # 2. Create follow + chat tasks
                            common_params = {
                                "dispatch_origin": "nas_direct",
                                "business_task_kind": "account_target_action_plan",
                            }
                            follow_task = TaskAssignmentPayload(
                                task_id=f"task-auto-{instance.instance_id}-follow-{len(tasks.list_tasks()) + 1}",
                                terminal_id=instance.terminal_id,
                                instance_id=instance.instance_id,
                                script_name="follow",
                                priority=0, retry_limit=0, close_after_actions=False,
                                requested_by="web-console",
                                dispatch_mode="claim_http",
                                parameters=dict(common_params),
                            )
                            chat_task = TaskAssignmentPayload(
                                task_id=f"task-auto-{instance.instance_id}-chat-{len(tasks.list_tasks()) + 2}",
                                terminal_id=instance.terminal_id,
                                instance_id=instance.instance_id,
                                script_name="chat",
                                priority=0, retry_limit=0, close_after_actions=False,
                                requested_by="web-console",
                                dispatch_mode="claim_http",
                                parameters=dict(common_params),
                            )
                            follow_record = tasks.create_task(follow_task)
                            chat_record = tasks.create_task(chat_task)
                            results.append({"instance_id": instance_id, "accepted": True, "action": "auto_start",
                                           "follow_task_id": follow_record.task_id, "chat_task_id": chat_record.task_id})
                        else:
                            results.append({"instance_id": instance_id, "accepted": False, "error": f"unknown action: {action}"})
                    self._send_json(HTTPStatus.OK, {"results": results})
                    return

                if self.path == "/queue/lease/extend":
                    result = queue_transport.extend_claim_lease(
                        terminal_id=payload["terminal_id"],
                        queue_topic=payload.get("queue_topic"),
                        delivery_id=payload.get("delivery_id"),
                        claim_lease_id=payload.get("claim_lease_id"),
                    )
                    self._send_json(HTTPStatus.OK, _queue_action_result_to_dict(result))
                    return

                if self.path.startswith("/api/actions/"):
                    if not self._check_token():
                        return
                    def _sync_single_instance(instance: InstanceRecord, updated: InstanceSnapshotPayload) -> None:
                        """Sync a single instance update without dropping other instances on the same terminal."""
                        registry.sync_instances(instance.terminal_id, [updated] + [
                            InstanceSnapshotPayload(
                                terminal_id=item.terminal_id, instance_id=item.instance_id,
                                profile_id=item.profile_id, handle=item.handle,
                                runtime_status=item.runtime_status, window_id=item.window_id,
                                remark=item.remark, metadata=dict(item.metadata),
                            )
                            for item in registry.list_instances(terminal_id=instance.terminal_id)
                            if item.instance_id != instance.instance_id
                        ])
                    action_path = self.path[len("/api/actions/"):]
                    profile_id = str(payload.get("profile_id", ""))

                    def _stop_script_on_instance(instance: InstanceRecord) -> None:
                        running = tasks.query_tasks(
                            terminal_id=instance.terminal_id,
                            instance_id=instance.instance_id,
                            status="running",
                        )
                        for task in running:
                            tasks.cancel_task(task.task_id, requested_by="web-console")
                        metadata = {**dict(instance.metadata), "stop_requested": True, "stop_requested_at": datetime.utcnow().isoformat()}
                        updated = InstanceSnapshotPayload(
                            terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                            profile_id=instance.profile_id, handle=instance.handle,
                            runtime_status=instance.runtime_status, window_id=instance.window_id,
                            remark=instance.remark, metadata=metadata,
                        )
                        registry.sync_instances(instance.terminal_id, [updated] + [
                            InstanceSnapshotPayload(
                                terminal_id=item.terminal_id, instance_id=item.instance_id,
                                profile_id=item.profile_id, handle=item.handle,
                                runtime_status=item.runtime_status, window_id=item.window_id,
                                remark=item.remark, metadata=dict(item.metadata),
                            )
                            for item in registry.list_instances(terminal_id=instance.terminal_id)
                            if item.instance_id != instance.instance_id
                        ])

                    def _create_task_for_instance(instance: InstanceRecord, script_name: str) -> TaskRecord:
                        task_id = f"task-api-{instance.profile_id}-{script_name}-{uuid.uuid4().hex[:8]}"
                        task_payload = TaskAssignmentPayload(
                            task_id=task_id,
                            terminal_id=instance.terminal_id,
                            instance_id=instance.instance_id,
                            script_name=script_name,
                            priority=0, retry_limit=0, close_after_actions=False,
                            requested_by="web-console",
                            dispatch_mode="claim_http",
                            parameters={
                                "dispatch_origin": "nas_direct",
                                "business_task_kind": "account_target_action_plan",
                            },
                        )
                        return tasks.create_task(task_payload)

                    def _open_window_for_instance(instance: InstanceRecord) -> None:
                        metadata = {**dict(instance.metadata), "open_requested": True, "open_requested_at": datetime.utcnow().isoformat()}
                        updated = InstanceSnapshotPayload(
                            terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                            profile_id=instance.profile_id, handle=instance.handle,
                            runtime_status="open_requested", window_id=instance.window_id,
                            remark=instance.remark, metadata=metadata,
                        )
                        registry.sync_instances(instance.terminal_id, [updated] + [
                            InstanceSnapshotPayload(
                                terminal_id=item.terminal_id, instance_id=item.instance_id,
                                profile_id=item.profile_id, handle=item.handle,
                                runtime_status=item.runtime_status, window_id=item.window_id,
                                remark=item.remark, metadata=dict(item.metadata),
                            )
                            for item in registry.list_instances(terminal_id=instance.terminal_id)
                            if item.instance_id != instance.instance_id
                        ])

                    if action_path == "start-follow":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        record = _create_task_for_instance(instance, "follow")
                        self._send_json(HTTPStatus.OK, {"ok": True, "task_id": record.task_id})
                        return

                    if action_path == "start-chat":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        record = _create_task_for_instance(instance, "chat")
                        self._send_json(HTTPStatus.OK, {"ok": True, "task_id": record.task_id})
                        return

                    if action_path == "stop-script":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        _stop_script_on_instance(instance)
                        self._send_json(HTTPStatus.OK, {"ok": True})
                        return

                    if action_path == "restart":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        _stop_script_on_instance(instance)
                        metadata = {**dict(instance.metadata), "close_requested": True, "close_requested_at": datetime.utcnow().isoformat()}
                        updated = InstanceSnapshotPayload(
                            terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                            profile_id=instance.profile_id, handle=instance.handle,
                            runtime_status="close_requested", window_id=instance.window_id,
                            remark=instance.remark, metadata=metadata,
                        )
                        registry.sync_instances(instance.terminal_id, [updated] + [
                            InstanceSnapshotPayload(
                                terminal_id=item.terminal_id, instance_id=item.instance_id,
                                profile_id=item.profile_id, handle=item.handle,
                                runtime_status=item.runtime_status, window_id=item.window_id,
                                remark=item.remark, metadata=dict(item.metadata),
                            )
                            for item in registry.list_instances(terminal_id=instance.terminal_id)
                            if item.instance_id != instance.instance_id
                        ])
                        metadata2 = {**dict(registry.get_instance(instance.instance_id).metadata), "open_requested": True, "open_requested_at": datetime.utcnow().isoformat()}
                        updated2 = InstanceSnapshotPayload(
                            terminal_id=instance.terminal_id, instance_id=instance.instance_id,
                            profile_id=instance.profile_id, handle=instance.handle,
                            runtime_status="open_requested", window_id=instance.window_id,
                            remark=instance.remark, metadata=metadata2,
                        )
                        registry.sync_instances(instance.terminal_id, [updated2] + [
                            InstanceSnapshotPayload(
                                terminal_id=item.terminal_id, instance_id=item.instance_id,
                                profile_id=item.profile_id, handle=item.handle,
                                runtime_status=item.runtime_status, window_id=item.window_id,
                                remark=item.remark, metadata=dict(item.metadata),
                            )
                            for item in registry.list_instances(terminal_id=instance.terminal_id)
                            if item.instance_id != instance.instance_id
                        ])
                        self._send_json(HTTPStatus.OK, {"ok": True})
                        return

                    if action_path == "open-window":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        _open_window_for_instance(instance)
                        self._send_json(HTTPStatus.OK, {"ok": True})
                        return

                    if action_path == "start-both":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        follow_record = _create_task_for_instance(instance, "follow")
                        chat_record = _create_task_for_instance(instance, "chat")
                        _open_window_for_instance(instance)
                        self._send_json(HTTPStatus.OK, {"ok": True, "follow_task_id": follow_record.task_id, "chat_task_id": chat_record.task_id})
                        return

                    if action_path == "auto-run":
                        try:
                            instance = _find_instance_by_profile_id(registry, profile_id)
                        except KeyError:
                            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"profile_id not found: {profile_id}"})
                            return
                        _open_window_for_instance(instance)
                        follow_record = _create_task_for_instance(instance, "follow")
                        chat_record = _create_task_for_instance(instance, "chat")
                        self._send_json(HTTPStatus.OK, {"ok": True, "follow_task_id": follow_record.task_id, "chat_task_id": chat_record.task_id})
                        return

                    if action_path == "batch":
                        action = str(payload["action"])
                        target_profile_ids: list[str] = list(payload.get("profile_ids", []))
                        agent_id: str | None = payload.get("agent_id")
                        if not target_profile_ids and agent_id:
                            target_profile_ids = [
                                record.profile_id
                                for record in registry.list_instances(terminal_id=agent_id)
                            ]
                        results: list[dict[str, Any]] = []
                        for pid in target_profile_ids:
                            try:
                                inst = _find_instance_by_profile_id(registry, pid)
                            except KeyError:
                                results.append({"profile_id": pid, "ok": False, "error": "instance not found"})
                                continue
                            try:
                                if action in {"start-follow", "start-chat", "stop-script", "restart", "open-window", "start-both", "auto-run", "stop"}:
                                    if action == "start-follow":
                                        rec = _create_task_for_instance(inst, "follow")
                                        results.append({"profile_id": pid, "ok": True, "task_id": rec.task_id})
                                    elif action == "start-chat":
                                        rec = _create_task_for_instance(inst, "chat")
                                        results.append({"profile_id": pid, "ok": True, "task_id": rec.task_id})
                                    elif action == "stop-script":
                                        _stop_script_on_instance(inst)
                                        results.append({"profile_id": pid, "ok": True})
                                    elif action == "restart":
                                        _stop_script_on_instance(inst)
                                        # Refresh instance metadata after stop_script updated it
                                        inst = registry.get_instance(inst.instance_id)
                                        metadata_c = {**dict(inst.metadata), "close_requested": True, "close_requested_at": datetime.utcnow().isoformat()}
                                        updated_c = InstanceSnapshotPayload(
                                            terminal_id=inst.terminal_id, instance_id=inst.instance_id,
                                            profile_id=inst.profile_id, handle=inst.handle,
                                            runtime_status="close_requested", window_id=inst.window_id,
                                            remark=inst.remark, metadata=metadata_c,
                                        )
                                        _sync_single_instance(inst, updated_c)
                                        inst_refreshed = registry.get_instance(inst.instance_id)
                                        metadata_o = {**dict(inst_refreshed.metadata), "open_requested": True, "open_requested_at": datetime.utcnow().isoformat()}
                                        updated_o = InstanceSnapshotPayload(
                                            terminal_id=inst.terminal_id, instance_id=inst.instance_id,
                                            profile_id=inst.profile_id, handle=inst.handle,
                                            runtime_status="open_requested", window_id=inst.window_id,
                                            remark=inst.remark, metadata=metadata_o,
                                        )
                                        _sync_single_instance(inst, updated_o)
                                        results.append({"profile_id": pid, "ok": True})
                                    elif action == "open-window":
                                        _open_window_for_instance(inst)
                                        results.append({"profile_id": pid, "ok": True})
                                    elif action == "start-both":
                                        fr = _create_task_for_instance(inst, "follow")
                                        cr = _create_task_for_instance(inst, "chat")
                                        _open_window_for_instance(inst)
                                        results.append({"profile_id": pid, "ok": True, "follow_task_id": fr.task_id, "chat_task_id": cr.task_id})
                                    elif action == "auto-run":
                                        _open_window_for_instance(inst)
                                        fr = _create_task_for_instance(inst, "follow")
                                        cr = _create_task_for_instance(inst, "chat")
                                        results.append({"profile_id": pid, "ok": True, "follow_task_id": fr.task_id, "chat_task_id": cr.task_id})
                                    elif action == "stop":
                                        running_tasks = tasks.query_tasks(
                                            terminal_id=inst.terminal_id,
                                            instance_id=inst.instance_id,
                                            status="running",
                                        )
                                        for task in running_tasks:
                                            tasks.cancel_task(task.task_id, requested_by="web-console")
                                        metadata = {**dict(inst.metadata), "stop_requested": True, "stop_requested_at": datetime.utcnow().isoformat()}
                                        updated = InstanceSnapshotPayload(
                                            terminal_id=inst.terminal_id, instance_id=inst.instance_id,
                                            profile_id=inst.profile_id, handle=inst.handle,
                                            runtime_status="stop_requested", window_id=inst.window_id,
                                            remark=inst.remark, metadata=metadata,
                                        )
                                        _sync_single_instance(inst, updated)
                                        results.append({"profile_id": pid, "ok": True})
                                    else:
                                        results.append({"profile_id": pid, "ok": False, "error": f"unknown action: {action}"})
                                else:
                                    results.append({"profile_id": pid, "ok": False, "error": f"unsupported batch action: {action}"})
                            except Exception as exc:
                                results.append({"profile_id": pid, "ok": False, "error": str(exc)})
                        self._send_json(HTTPStatus.OK, {"ok": True, "results": results})
                        return

                    self._send_json(HTTPStatus.NOT_FOUND, {"error": f"unknown action: {action_path}"})
                    return

            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"missing field: {exc.args[0]}"})
                return
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_DELETE(self) -> None:  # noqa: N802
            path = self._path_without_query()
            if not self._check_token():
                return
            if memory_router.dispatch_memory(self, path):
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

        def _send_content(self, status: HTTPStatus, raw: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
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
    host: str | None = None,
    port: int | None = None,
    state_path: str | Path | None = None,
) -> None:
    """Start the NAS server and block forever."""

    resolved_host = host or os.environ.get("XMATRIX_NAS_HOST", "127.0.0.1")
    resolved_port = port if port is not None else int(os.environ.get("XMATRIX_NAS_PORT", "8765"))
    resolved_state_path = state_path or os.environ.get("XMATRIX_NAS_STATE_PATH", "nas_control_plane/state.json")
    server = create_server(host=resolved_host, port=resolved_port, state_path=resolved_state_path)
    print(f"nas_control_plane listening on http://{resolved_host}:{resolved_port}")
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
        dispatch_mode=str(payload.get("dispatch_mode", "claim_http")),
        queue_topic=payload.get("queue_topic"),
        delivery_id=payload.get("delivery_id"),
        claim_lease_id=payload.get("claim_lease_id"),
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
        delivery_id=payload.get("delivery_id"),
        claim_lease_id=payload.get("claim_lease_id"),
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


def _parse_plugin_dispatch(payload: dict[str, Any]) -> PluginDispatchRequestPayload:
    return PluginDispatchRequestPayload(
        task_id=str(payload["task_id"]),
        account_id=str(payload["account_id"]),
        plugin_name=str(payload["plugin_name"]),
        script_name=str(payload["script_name"]),
        target=dict(payload.get("target", {})),
        action_plan=list(payload.get("action_plan", [])),
        campaign_id=str(payload["campaign_id"]) if payload.get("campaign_id") is not None else None,
        copy_payload=dict(payload["copy_payload"]) if payload.get("copy_payload") is not None else None,
        target_type=str(payload.get("target_type", "handle")),
        terminal_id=str(payload["terminal_id"]) if payload.get("terminal_id") is not None else None,
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        priority=int(payload.get("priority", 0)),
        retry_limit=int(payload.get("retry_limit", 0)),
        close_after_actions=bool(payload.get("close_after_actions", False)),
        requested_by=str(payload["requested_by"]) if payload.get("requested_by") is not None else None,
        dispatch_mode=str(payload.get("dispatch_mode", "claim_http")),
        queue_topic=str(payload["queue_topic"]) if payload.get("queue_topic") is not None else None,
        parameters=dict(payload.get("parameters", {})),
        metadata=dict(payload.get("metadata", {})),
    )


def _dispatch_plugin_task(
    *,
    dispatch_payload: PluginDispatchRequestPayload,
    plugin_runtime: PluginRuntimeService,
    tasks: TaskDispatchService,
) -> dict[str, Any]:
    """Create one NAS business task for plugin runtime execution."""

    eligibility = plugin_runtime.evaluate_account_eligibility(
        account_id=dispatch_payload.account_id,
        plugin_name=dispatch_payload.plugin_name,
        action_type=dispatch_payload.script_name,
        stat_date=(
            str(dispatch_payload.parameters.get("stat_date"))
            if dispatch_payload.parameters.get("stat_date") is not None
            else None
        ),
    )
    if not eligibility.get("eligible", False):
        return {
            "accepted": False,
            "reason": eligibility.get("reason", "account_ineligible"),
            "eligibility": eligibility,
            "task": None,
            "ammo": None,
        }

    account = plugin_runtime.get_account(dispatch_payload.account_id)
    direct_target = dict(dispatch_payload.target or {})
    has_direct_target = any(
        direct_target.get(key) not in {None, ""}
        for key in ("target_id", "handle", "url", "creator_id")
    )

    claimed_ammo = None
    if not has_direct_target:
        claimed_ammo = plugin_runtime.claim_ammo_target(
            account_id=dispatch_payload.account_id,
            plugin_name=dispatch_payload.plugin_name,
            target_type=dispatch_payload.target_type,
            action_type=dispatch_payload.script_name,
            stat_date=(
                str(dispatch_payload.parameters.get("stat_date"))
                if dispatch_payload.parameters.get("stat_date") is not None
                else None
            ),
        )
        if claimed_ammo is None:
            return {
                "accepted": False,
                "reason": "no_target_available",
                "eligibility": eligibility,
                "task": None,
                "ammo": None,
            }

    target = {
        **direct_target,
        "target_id": direct_target.get("target_id") or (claimed_ammo.target_id if claimed_ammo is not None else None),
        "handle": direct_target.get("handle") or (claimed_ammo.target_value if claimed_ammo is not None else None),
        "creator_id": direct_target.get("creator_id") or (claimed_ammo.creator_id if claimed_ammo is not None else None),
    }
    task_payload = TaskAssignmentPayload(
        task_id=dispatch_payload.task_id,
        terminal_id=dispatch_payload.terminal_id or account.terminal_id or dispatch_payload.account_id,
        instance_id=dispatch_payload.instance_id,
        script_name=dispatch_payload.script_name,
        parameters={
            **dict(dispatch_payload.parameters),
            "plugin_name": dispatch_payload.plugin_name,
            "account_id": dispatch_payload.account_id,
            "account_profile_id": account.profile_id,
            "account_handle": account.handle,
            "target": target,
            "target_id": target.get("target_id"),
            "target_handle": target.get("handle"),
            "target_url": target.get("url"),
            "action_plan": list(dispatch_payload.action_plan),
            "campaign_id": dispatch_payload.campaign_id
            or (claimed_ammo.metadata.get("campaign_id") if claimed_ammo is not None else None),
            "copy_payload": (
                dict(dispatch_payload.copy_payload)
                if dispatch_payload.copy_payload is not None
                else (claimed_ammo.metadata.get("selected_copy") if claimed_ammo is not None else None)
            ),
            "ammo_target_id": claimed_ammo.target_id if claimed_ammo is not None else None,
            "ammo_target_type": claimed_ammo.target_type if claimed_ammo is not None else None,
            "ammo_target_value": claimed_ammo.target_value if claimed_ammo is not None else None,
            "creator_id": target.get("creator_id"),
            "campaign_copy": claimed_ammo.metadata.get("selected_copy") if claimed_ammo is not None else None,
            "dispatch_origin": "plugin_runtime" if claimed_ammo is not None else "nas_direct",
            "business_task_kind": "account_target_action_plan",
            "operator_status_label": "待执行",
        },
        priority=dispatch_payload.priority,
        retry_limit=dispatch_payload.retry_limit,
        close_after_actions=dispatch_payload.close_after_actions,
        requested_by=dispatch_payload.requested_by,
        metadata={
            **dict(dispatch_payload.metadata),
            "plugin_name": dispatch_payload.plugin_name,
            "account_id": dispatch_payload.account_id,
            "ammo_target_id": claimed_ammo.target_id if claimed_ammo is not None else None,
            "preferred_terminal_id": dispatch_payload.terminal_id or account.terminal_id,
        },
        dispatch_mode=dispatch_payload.dispatch_mode,
        queue_topic=dispatch_payload.queue_topic,
    )
    try:
        task_record = tasks.create_task(task_payload)
    except Exception:
        if claimed_ammo is not None:
            plugin_runtime.release_ammo_target(
                target_id=claimed_ammo.target_id,
                reason="task_create_failed",
            )
        raise

    ammo_record = None
    if claimed_ammo is not None:
        ammo_record = plugin_runtime.bind_ammo_target_to_task(
            target_id=claimed_ammo.target_id,
            task_id=task_record.task_id,
        )
    return {
        "accepted": True,
        "eligibility": eligibility,
        "task": _record_to_dict(task_record),
        "ammo": _record_to_dict(ammo_record) if ammo_record is not None else None,
    }
def _find_instance_by_profile_id(registry: TerminalRegistryService, profile_id: str) -> InstanceRecord:
    """Return one instance by profile_id, raising KeyError if not found."""
    for record in registry.list_instances():
        if record.profile_id == profile_id:
            return record
    raise KeyError(f"instance not found for profile_id: {profile_id}")


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {raw}")


def _parse_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    return int(raw)


def _record_to_dict(record: Any) -> dict[str, Any]:
    data = asdict(record)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def _queue_action_result_to_dict(record: Any) -> dict[str, Any]:
    return {
        "accepted": record.accepted,
        "status": record.status,
        "queue_topic": record.queue_topic,
        "delivery_id": record.delivery_id,
        "claim_lease_id": record.claim_lease_id,
        "details": dict(record.details),
    }


if __name__ == "__main__":
    run_server()

