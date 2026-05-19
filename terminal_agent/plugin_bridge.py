from __future__ import annotations

# Engine command queue — dashboard pushes commands, extension polls them
_engine_commands: list[dict[str, str]] = []

# Current task cache — the last successfully pulled task, served to content scripts
_current_task: dict[str, Any] | None = None
_current_task_id: str | None = None

# Action plan sequencer — drives content scripts step by step
_current_action_index: int = 0
_current_action_plan: list = []
_task_progress_status: str = "idle"  # idle | in_progress | action_completed | all_completed | failed

_engine_commands: list[dict[str, str]] = []
import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from shared.protocol import HeartbeatPayload
from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.runtime import TerminalRuntime
from terminal_agent.runtime.health_monitor import HealthMonitor


def create_plugin_bridge_server(
    *,
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
    bitbrowser_client: BitBrowserClient,
    health_monitor: HealthMonitor | None = None,
    host: str = "127.0.0.1",
    port: int = 54346,
) -> ThreadingHTTPServer:
    """Create a small local HTTP bridge for plugin-originated identity events."""

    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "BPlusPluginBridge/0.1"

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return
            if self.path == "/plugin/engine/pending":
                cmd = _engine_commands[:]
                _engine_commands.clear()
                self._send_json(HTTPStatus.OK, {"commands": cmd})
                return
            if self.path == "/plugin/current-task":
                if _current_task is not None:
                    self._send_json(HTTPStatus.OK, {"task": _current_task})
                else:
                    self._send_json(HTTPStatus.OK, {"task": None})
                return
            if self.path == "/plugin/task/status":
                self._send_json(HTTPStatus.OK, {
                    "task_id": _current_task_id,
                    "task": _current_task,
                    "action_index": _current_action_index,
                    "action_plan": _current_action_plan,
                    "progress": _task_progress_status,
                    "next_action": _current_action_plan[_current_action_index] if _current_action_plan and _current_action_index < len(_current_action_plan) else None,
                    "completed_count": _current_action_index,
                    "total_count": len(_current_action_plan),
                })
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
                if self.path == "/ext/user_id":
                    response = _handle_legacy_user_identity(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                        bitbrowser_client=bitbrowser_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path == "/ext/action_log":
                    response = _handle_legacy_action_log(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path in {"/ext/heartbeat", "/report"}:
                    response = _handle_legacy_heartbeat(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path in {"/log_action"}:
                    response = _handle_legacy_action_log(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path in {"/api/user-id-report"}:
                    response = _handle_legacy_user_identity(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                        bitbrowser_client=bitbrowser_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path == "/plugin/task/pull":
                    response = _handle_plugin_task_pull(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path == "/ext/dom_health":
                    response = _handle_dom_health(
                        payload=payload,
                        health_monitor=health_monitor,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path == "/plugin/instance/restart":
                    response = _handle_instance_restart(
                        payload=payload,
                        runtime=runtime,
                        nas_client=nas_client,
                        bitbrowser_client=bitbrowser_client,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if self.path == "/plugin/engine/start":
                    cmd = {"command": "start", "terminal_id": payload.get("terminal_id", "*")}
                    if _current_task_id is not None and _current_task is not None:
                        cmd["task_id"] = _current_task_id
                        cmd["script_name"] = _current_task.get("script_name")
                        cmd["action_plan"] = _current_task.get("action_plan", [])
                        cmd["target"] = _current_task.get("target", {})
                        cmd["copy_payload"] = _current_task.get("copy_payload", {})
                    _engine_commands.append(cmd)
                    self._send_json(HTTPStatus.OK, {"status": "command_queued", "command": "start", "task_id": _current_task_id})
                    return

                if self.path == "/plugin/engine/stop":
                    _engine_commands.append({"command": "stop", "terminal_id": payload.get("terminal_id", "*")})
                    self._send_json(HTTPStatus.OK, {"status": "command_queued", "command": "stop"})
                    return

                # ── Action plan sequencer endpoints ──
                if self.path == "/plugin/task/next-action":
                    if _current_task is None or not _current_action_plan:
                        self._send_json(HTTPStatus.OK, {"action": None, "status": "no_task", "progress": "idle"})
                        return
                    if _current_action_index >= len(_current_action_plan):
                        self._send_json(HTTPStatus.OK, {
                            "action": None, "status": "all_completed",
                            "progress": "all_completed",
                            "task_id": _current_task_id,
                            "action_plan": _current_action_plan,
                            "completed_count": len(_current_action_plan),
                            "total_count": len(_current_action_plan),
                        })
                        return
                    current_action = _current_action_plan[_current_action_index]
                    target = _current_task.get("target", {})
                    self._send_json(HTTPStatus.OK, {
                        "action": current_action,
                        "action_index": _current_action_index,
                        "status": "in_progress",
                        "progress": "in_progress",
                        "task_id": _current_task_id,
                        "target": target,
                        "copy_payload": _current_task.get("copy_payload"),
                        "action_plan": _current_action_plan,
                        "completed_count": _current_action_index,
                        "total_count": len(_current_action_plan),
                    })
                    return

                if self.path == "/plugin/task/complete-action":
                    if _current_task is None or not _current_action_plan:
                        self._send_json(HTTPStatus.OK, {"action": None, "status": "no_task"})
                        return

                    completed_action = payload.get("action") or (_current_action_plan[_current_action_index] if _current_action_index < len(_current_action_plan) else "unknown")
                    success = bool(payload.get("success", True))
                    details = dict(payload.get("details", {}))

                    # Report this action to NAS via action log
                    _report_action_to_nas(
                        nas_client=nas_client,
                        runtime=runtime,
                        action=completed_action,
                        action_index=_current_action_index,
                        success=success,
                        details=details,
                    )

                    _current_action_index += 1

                    # Check if all actions done
                    if _current_action_index >= len(_current_action_plan):
                        _task_progress_status = "all_completed"
                        # Mark task as completed on NAS
                        _complete_task_on_nas(
                            nas_client=nas_client,
                            runtime=runtime,
                            task_id=_current_task_id,
                            action_plan=_current_action_plan,
                        )
                        self._send_json(HTTPStatus.OK, {
                            "action": None, "status": "all_completed",
                            "progress": "all_completed",
                            "task_id": _current_task_id,
                            "completed_count": len(_current_action_plan),
                            "total_count": len(_current_action_plan),
                        })
                        return

                    # Return next action
                    next_action = _current_action_plan[_current_action_index]
                    target = _current_task.get("target", {})
                    _task_progress_status = "in_progress"
                    self._send_json(HTTPStatus.OK, {
                        "action": next_action,
                        "action_index": _current_action_index,
                        "status": "next_action",
                        "progress": "in_progress",
                        "task_id": _current_task_id,
                        "target": target,
                        "copy_payload": _current_task.get("copy_payload"),
                        "action_plan": _current_action_plan,
                        "completed_count": _current_action_index,
                        "total_count": len(_current_action_plan),
                    })
                    return

                if self.path == "/plugin/task/fail-action":
                    if _current_task is None or not _current_action_plan:
                        self._send_json(HTTPStatus.OK, {"action": None, "status": "no_task"})
                        return

                    failed_action = payload.get("action") or (_current_action_plan[_current_action_index] if _current_action_index < len(_current_action_plan) else "unknown")
                    error_code = str(payload.get("error_code", "unknown"))
                    error_message = str(payload.get("error_message", ""))
                    details = dict(payload.get("details", {}))

                    # Report failure to NAS
                    _report_action_to_nas(
                        nas_client=nas_client,
                        runtime=runtime,
                        action=failed_action,
                        action_index=_current_action_index,
                        success=False,
                        details={**details, "error_code": error_code, "error_message": error_message},
                    )

                    _current_action_index += 1

                    if _current_action_index >= len(_current_action_plan):
                        _task_progress_status = "all_completed"
                        _complete_task_on_nas(
                            nas_client=nas_client,
                            runtime=runtime,
                            task_id=_current_task_id,
                            action_plan=_current_action_plan,
                        )
                        self._send_json(HTTPStatus.OK, {
                            "action": None, "status": "all_completed",
                            "progress": "all_completed",
                            "task_id": _current_task_id,
                            "completed_count": len(_current_action_plan),
                            "total_count": len(_current_action_plan),
                        })
                        return

                    next_action = _current_action_plan[_current_action_index]
                    target = _current_task.get("target", {})
                    self._send_json(HTTPStatus.OK, {
                        "action": next_action,
                        "action_index": _current_action_index,
                        "status": "next_action_after_failure",
                        "progress": "in_progress",
                        "task_id": _current_task_id,
                        "target": target,
                        "action_plan": _current_action_plan,
                        "completed_count": _current_action_index,
                        "total_count": len(_current_action_plan),
                    })
                    return

                if self.path == "/plugin/login-success":
                    browser_id = bitbrowser_client.resolve_browser_id(
                        payload.get("browser_id") or payload.get("bit_id") or payload.get("window_id"),
                        allow_single_running_fallback=True,
                    )
                    handle = _normalize_handle(payload.get("handle"))
                    remark = str(payload.get("remark") or _remark_from_identity(runtime, browser_id, handle))
                    profile_id = str(payload.get("profile_id") or _profile_id_from_handle(handle, browser_id))
                    updated = _update_runtime_identity(
                        runtime=runtime,
                        nas_client=nas_client,
                        bitbrowser_client=bitbrowser_client,
                        browser_id=browser_id,
                        handle=handle,
                        remark=remark,
                        profile_id=profile_id,
                        update_bitbrowser=True,
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "status": "updated",
                            "instance_id": updated.instance_id,
                            "handle": updated.handle,
                            "remark": updated.remark,
                            "profile_id": updated.profile_id,
                        },
                    )
                    return
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"missing field: {exc.args[0]}"})
                return
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            """Silence request logging."""

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), RequestHandler)


def _normalize_handle(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text.lstrip("@").lower()


def _remark_from_handle(handle: str | None) -> str:
    if handle is None:
        raise ValueError("login-success requires handle or explicit remark")
    return handle


def _remark_from_identity(runtime: TerminalRuntime, browser_id: str, handle: str | None) -> str:
    """Build an operator-facing remark for one BitBrowser instance."""

    terminal_id = runtime.registration_payload().terminal_id
    short_terminal = terminal_id[-8:] if len(terminal_id) > 8 else terminal_id
    short_instance = browser_id[-6:] if len(browser_id) > 6 else browser_id
    account = f"@{handle}" if handle else "@unknown"
    return f"{account} | {short_terminal} | {short_instance}"


def _window_name_from_identity(handle: str | None) -> str:
    """Build the visible BitBrowser window name."""

    if handle is None:
        return "unknown_account"
    return f"@{handle}"


def _profile_id_from_handle(handle: str | None, browser_id: str) -> str:
    if handle is None:
        return browser_id
    return f"@{handle}#bitbrowser"


def _handle_legacy_user_identity(
    *,
    payload: dict[str, Any],
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
    bitbrowser_client: BitBrowserClient,
) -> dict[str, Any]:
    """Accept the old `/ext/user_id` payload and map it to current runtime + NAS semantics."""

    browser_id = bitbrowser_client.resolve_browser_id(
        payload.get("bit_id")
        or payload.get("browser_id")
        or payload.get("window_id")
        or payload.get("profile_id"),
        allow_single_running_fallback=True,
    )

    handle = _normalize_handle(payload.get("handle"))
    if handle is None:
        raise ValueError("ext/user_id requires handle")

    profile_id = str(payload.get("profile_id") or _profile_id_from_handle(handle, browser_id))
    remark = str(payload.get("remark") or handle)
    source = str(payload.get("source") or payload.get("plugin_name") or "x-matrix-bot")
    plugin_name = str(payload.get("plugin_name") or source)
    dedupe_key = str(payload.get("dedupe_key") or f"{handle}|{browser_id}|identity")

    updated = _update_runtime_identity(
        runtime=runtime,
        nas_client=nas_client,
        bitbrowser_client=bitbrowser_client,
        browser_id=browser_id,
        handle=handle,
        remark=remark,
        profile_id=profile_id,
        update_bitbrowser=False,
    )
    creator_record = nas_client.report_plugin_creator(
        creator_id=handle,
        handle=handle,
        source=source,
        terminal_id=runtime.registration_payload().terminal_id,
        profile_id=profile_id,
        plugin_name=plugin_name,
        dedupe_key=dedupe_key,
    )
    return {
        "ok": True,
        "status": "updated",
        "instance_id": updated.instance_id,
        "handle": updated.handle,
        "remark": updated.remark,
        "profile_id": updated.profile_id,
        "creator_record": creator_record,
    }


def _handle_legacy_action_log(
    *,
    payload: dict[str, Any],
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
) -> dict[str, Any]:
    """Accept the old `/ext/action_log` payload and map it to the current daily stat surface."""

    raw_action_type = str(payload.get("action_type") or "unknown").strip()
    action_type = raw_action_type.lower()
    account_id = _coerce_account_id(payload)
    handle = _coerce_handle_from_account_id(account_id)
    terminal_id = str(payload.get("terminal_id") or runtime.registration_payload().terminal_id)
    plugin_name = str(payload.get("plugin_name") or _plugin_name_from_action(action_type))
    script_name = str(payload.get("script_name") or _script_name_from_action(action_type))
    success = not bool(payload.get("failed", False))

    metadata = {
        "legacy_bot_id": payload.get("bot_id"),
        "legacy_target": payload.get("target"),
        "legacy_count": payload.get("count"),
        "legacy_day_count": payload.get("day_count"),
        "legacy_type": payload.get("type"),
        "legacy_detail": payload.get("detail"),
        "failed": payload.get("failed"),
        "error_code": payload.get("error_code"),
        "error_message": payload.get("error_message"),
        "task_id": payload.get("task_id") or _current_task_id,
        "action_plan": payload.get("action_plan") or (_current_task.get("action_plan") if _current_task else None),
        "action_index": payload.get("action_index"),
        "target_handle": payload.get("target_handle"),
        "target_url": payload.get("target_url"),
    }

    if account_id:
        try:
            nas_client.register_plugin_account(
                account_id=account_id,
                profile_id=account_id,
                handle=handle,
                terminal_id=terminal_id,
                plugin_name=plugin_name,
                capability_tags=[script_name],
                metadata={"imported_from": "legacy_ext_action_log"},
            )
        except RuntimeError:
            pass

    record = nas_client.record_plugin_action(
        account_id=account_id or None,
        terminal_id=terminal_id,
        plugin_name=plugin_name,
        script_name=script_name,
        action_type=action_type,
        success=success,
        metadata=metadata,
    )
    return {
        "ok": True,
        "status": "recorded",
        "record": record,
    }


def _handle_legacy_heartbeat(
    *,
    payload: dict[str, Any],
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
) -> dict[str, Any]:
    """Accept legacy plugin heartbeat/report payloads and map them to current terminal heartbeat semantics."""

    instance_id = str(
        payload.get("bit_id")
        or payload.get("browser_id")
        or payload.get("window_id")
        or payload.get("profile_id")
        or payload.get("worker_id")
        or ""
    ).strip()
    handle = _normalize_handle(payload.get("handle"))
    profile_id = str(payload.get("profile_id") or _profile_id_from_handle(handle, instance_id or "plugin-heartbeat"))
    status_text = str(payload.get("status") or payload.get("engine") or "plugin_heartbeat").strip() or "plugin_heartbeat"
    detail = str(payload.get("detail") or "").strip()

    if instance_id:
        remark = str(payload.get("remark") or handle or payload.get("worker_id") or instance_id)
        runtime.update_instance_identity(
            instance_id=instance_id,
            handle=handle,
            remark=remark,
            profile_id=profile_id,
            runtime_status="running",
        )
    runtime.merge_runtime_metadata(
        {
            "task_source_mode": "plugin_bridge",
            "task_source_status": "active",
            "task_source_queue_topic": None,
            "plugin_last_heartbeat_status": status_text,
            "plugin_last_heartbeat_detail": detail or None,
            "plugin_last_worker_id": payload.get("worker_id"),
        }
    )

    runtime_heartbeat = runtime.heartbeat_payload()
    heartbeat = HeartbeatPayload(
        terminal_id=runtime.registration_payload().terminal_id,
        reported_at=datetime.utcnow(),
        status="online",
        active_instance_count=len(runtime.instance_manager.list_instances()),
        queued_task_count=runtime_heartbeat.queued_task_count,
        metadata={
            **runtime_heartbeat.metadata,
            "plugin_status_text": status_text,
            "plugin_status_detail": detail or None,
            "plugin_worker_id": payload.get("worker_id"),
            "plugin_engine": payload.get("engine"),
            "plugin_window_short_id": payload.get("window_short_id"),
        },
    )
    response = nas_client.send_heartbeat(heartbeat)
    nas_client.sync_instances(
        terminal_id=runtime.registration_payload().terminal_id,
        payloads=runtime.instance_snapshot_payloads(),
    )
    runtime.mark_instances_synced()
    return {
        "ok": True,
        "status": "accepted",
        "heartbeat": response,
    }


def _handle_plugin_task_pull(
    *,
    payload: dict[str, Any],
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
) -> dict[str, Any]:
    """Return one queued business task payload for the current plugin runtime.

    On success, caches the task locally so content scripts can read it
    via the lightweight GET /plugin/current-task endpoint.
    """
    global _current_task, _current_task_id

    terminal_id = str(payload.get("terminal_id") or runtime.registration_payload().terminal_id)
    instance_id = str(payload.get("instance_id") or payload.get("bit_id") or payload.get("browser_id") or "").strip() or None
    account_id = _coerce_account_id(payload)
    script_name = str(payload.get("script_name") or payload.get("engine") or "follow").strip() or None
    response = nas_client.pull_plugin_task(
        terminal_id=terminal_id,
        instance_id=instance_id,
        account_id=account_id,
        script_name=script_name,
        plugin_name=str(payload.get("plugin_name") or payload.get("source") or "content_follow.js"),
    )

    # Cache the task for content scripts if accepted
    if response and response.get("accepted") and response.get("task"):
        _current_task = response["task"]
        _current_task_id = _current_task.get("task_id")
        # Reset action plan sequencer
        _current_action_plan = list(_current_task.get("action_plan") or [])
        _current_action_index = 0
        _task_progress_status = "in_progress" if _current_action_plan else "idle"
    else:
        _current_task = None
        _current_task_id = None
        _current_action_plan = []
        _current_action_index = 0
        _task_progress_status = "idle"

    return response


def _update_runtime_identity(
    *,
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
    bitbrowser_client: BitBrowserClient,
    browser_id: str,
    handle: str | None,
    remark: str,
    profile_id: str,
    update_bitbrowser: bool,
):
    """Update local runtime identity, optionally push remark to BitBrowser, then sync NAS."""

    sync_status = "skipped"
    sync_error: str | None = None
    if update_bitbrowser:
        try:
            bitbrowser_client.update_window_name(browser_id, _window_name_from_identity(handle))
            bitbrowser_client.update_remark(browser_id, remark)
        except RuntimeError as exc:
            raise
        sync_status = "ok"
    updated = runtime.update_instance_identity(
        instance_id=browser_id,
        handle=handle,
        remark=remark,
        profile_id=profile_id,
        runtime_status="running",
    )
    if update_bitbrowser:
        try:
            nas_client.sync_instance_remark(
                instance_id=browser_id,
                current_account_handle=handle,
                remark=remark,
                remark_sync_status=sync_status,
                remark_sync_error=sync_error,
            )
        except RuntimeError as exc:
            sync_status = "compat_fallback"
            sync_error = str(exc)
            runtime.update_instance_identity(
                instance_id=browser_id,
                handle=handle,
                remark=remark,
                profile_id=profile_id,
                runtime_status="running",
            )
            runtime.merge_runtime_metadata(
                {
                    "instance_remark_sync_warning": sync_error,
                    "instance_remark_sync_status": sync_status,
                }
            )
    nas_client.sync_instances(
        terminal_id=runtime.registration_payload().terminal_id,
        payloads=runtime.instance_snapshot_payloads(),
    )
    runtime.mark_instances_synced()
    return updated


def _handle_instance_restart(
    *,
    payload: dict[str, Any],
    runtime: TerminalRuntime,
    nas_client: NasControlPlaneClient,
    bitbrowser_client: BitBrowserClient,
) -> dict[str, Any]:
    """Close and reopen one BitBrowser instance, then sync the restart request."""

    browser_id = str(payload["browser_id"])
    reason = str(payload.get("reason") or "plugin_requested_restart")
    try:
        bitbrowser_client.close_browser(browser_id)
    except RuntimeError:
        pass
    bitbrowser_client.open_browser(browser_id)
    runtime.update_instance_identity(
        instance_id=browser_id,
        handle=None,
        remark=str(payload.get("remark")) if payload.get("remark") is not None else None,
        profile_id=str(payload.get("profile_id")) if payload.get("profile_id") is not None else browser_id,
        runtime_status="restarting",
    )
    nas_client.request_instance_restart(instance_id=browser_id, reason=reason)
    nas_client.sync_instances(
        terminal_id=runtime.registration_payload().terminal_id,
        payloads=runtime.instance_snapshot_payloads(),
    )
    runtime.mark_instances_synced()
    return {"ok": True, "status": "restarted", "instance_id": browser_id, "reason": reason}


def _coerce_account_id(payload: dict[str, Any]) -> str:
    raw = payload.get("account_id")
    if raw is None:
        raw = payload.get("bot_id")
    if raw is None:
        return ""
    text = str(raw).strip()
    return text


def _coerce_handle_from_account_id(account_id: str) -> str | None:
    if not account_id:
        return None
    text = account_id.strip()
    if text.startswith("@") and "#guard" in text:
        return text[1:].split("#", 1)[0].lower()
    if text.startswith("@"):
        return text[1:].lower()
    return text.lower() or None


def _plugin_name_from_action(action_type: str) -> str:
    mapping = {
        "follow": "content_follow.js",
        "followed": "content_follow.js",
        "chat": "content_chat.js",
        "ice": "content_chat.js",
        "icebreaker": "content_chat.js",
        "ad": "content_chat.js",
        "corpse": "content_chat.js",
        "reject": "content_chat.js",
    }
    return mapping.get(action_type, "x-matrix-bot")


def _script_name_from_action(action_type: str) -> str:
    mapping = {
        "follow": "follow",
        "followed": "follow",
        "chat": "chat",
        "ice": "chat",
        "icebreaker": "chat",
        "ad": "chat",
        "corpse": "chat",
        "reject": "chat",
    }
    return mapping.get(action_type, "plugin")


def _handle_dom_health(
    *,
    payload: dict[str, Any],
    health_monitor: HealthMonitor | None = None,
) -> dict[str, Any]:
    """Accept a DOM health report from the Chrome extension content script.

    The extension periodically checks whether expected page elements exist.
    This endpoint records the signal for the health monitor's staleness check.
    """
    instance_id = str(payload.get("instance_id") or payload.get("browser_id") or "")
    alive = bool(payload.get("alive") or payload.get("dom_alive") or False)

    if health_monitor is not None:
        health_monitor.record_dom_health(instance_id, alive)
    return {"ok": True, "instance_id": instance_id, "alive": alive}


def _report_action_to_nas(
    *,
    nas_client: NasControlPlaneClient,
    runtime: TerminalRuntime,
    action: str,
    action_index: int,
    success: bool,
    details: dict | None = None,
) -> None:
    """Report one completed action to NAS via the action-log API.

    Uses the cached task_id and target to provide full context.
    The NAS side binds this result back to the task's result_details.action_results.
    """
    try:
        terminal_id = runtime.registration_payload().terminal_id
        target = (_current_task.get("target") or {}) if _current_task else {}
        target_handle = target.get("handle") if isinstance(target, dict) else str(target)

        action_type = action.lower().replace(" ", "_")
        script_name = _script_name_from_action(action_type)

        payload = {
            "account_id": _current_task.get("account_id") if _current_task else None,
            "terminal_id": terminal_id,
            "script_name": script_name,
            "plugin_name": _plugin_name_from_action(action_type),
            "action_type": action_type,
            "success": success,
            "metadata": {
                "task_id": _current_task_id,
                "action_index": action_index,
                "action_plan": _current_action_plan,
                "target_handle": target_handle,
                **dict(details or {}),
            },
        }
        # Use the NAS client's internal POST method
        from urllib.request import Request as UReq
        import json
        data = json.dumps(payload).encode()
        req = UReq(f"{nas_client._base_url}/plugin/action-log", data=data,
                   headers={"Content-Type": "application/json"},
                   method="POST")
        import urllib.request
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        print(f"[bridge] _report_action_to_nas failed: {exc}", flush=True)


def _complete_task_on_nas(
    *,
    nas_client: NasControlPlaneClient,
    runtime: TerminalRuntime,
    task_id: str | None,
    action_plan: list,
) -> None:
    """Mark the task as completed on NAS when all actions are done."""
    if task_id is None:
        return
    try:
        result_payload = {
            "task_id": task_id,
            "terminal_id": runtime.registration_payload().terminal_id,
            "status": "completed",
            "summary": f"action_plan completed: {action_plan}",
            "details": {
                "action_plan": action_plan,
                "completed_count": len(action_plan),
                "progress_status": "action_plan_completed",
            },
        }
        from urllib.request import Request as UReq
        import json
        data = json.dumps(result_payload).encode()
        req = UReq(f"{nas_client._base_url}/tasks/result", data=data,
                   headers={"Content-Type": "application/json"},
                   method="POST")
        import urllib.request
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        print(f"[bridge] _complete_task_on_nas failed: {exc}", flush=True)
