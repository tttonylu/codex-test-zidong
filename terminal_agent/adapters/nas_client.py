"""Minimal HTTP client for talking to the NAS control plane."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from typing import Any
from urllib import error, request

from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TaskControlPayload,
    TerminalRegistrationPayload,
)


class NasControlPlaneClient:
    """Sends terminal state to the NAS control plane over HTTP."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def register_terminal(self, payload: TerminalRegistrationPayload) -> dict[str, Any]:
        """Send a terminal registration payload."""

        return self._post_json("/register", payload.to_dict())

    def send_heartbeat(self, payload: HeartbeatPayload) -> dict[str, Any]:
        """Send a heartbeat payload."""

        return self._post_json("/heartbeat", payload.to_dict())

    def sync_instances(
        self,
        terminal_id: str,
        payloads: list[InstanceSnapshotPayload],
    ) -> dict[str, Any]:
        """Send the full current instance snapshot for one terminal."""

        body = {
            "terminal_id": terminal_id,
            "items": [payload.to_dict() for payload in payloads],
        }
        return self._post_json("/instances/sync", body)

    def list_terminals(self, status: str | None = None) -> dict[str, Any]:
        """Fetch the current terminal view from the NAS."""

        path = "/terminals"
        if status is not None:
            path = f"/terminals?{urlencode({'status': status})}"
        return self._get_json(path)

    def get_terminal(self, terminal_id: str) -> dict[str, Any]:
        """Fetch one terminal by id from the NAS."""

        return self._get_json(f"/terminals/{terminal_id}")

    def list_instances(
        self,
        terminal_id: str | None = None,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the current instance view from the NAS."""

        query: dict[str, str] = {}
        if terminal_id is not None:
            query["terminal_id"] = terminal_id
        if runtime_status is not None:
            query["runtime_status"] = runtime_status
        path = "/instances"
        if query:
            path = f"/instances?{urlencode(query)}"
        return self._get_json(path)

    def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Fetch one instance by id from the NAS."""

        return self._get_json(f"/instances/{instance_id}")

    def create_task(self, payload: TaskAssignmentPayload) -> dict[str, Any]:
        """Create a task on the NAS side."""

        return self._post_json("/tasks", payload.to_dict())

    def list_tasks(self, terminal_id: str | None = None) -> dict[str, Any]:
        """Fetch current task state, optionally filtered by terminal."""

        query: dict[str, str] = {}
        if terminal_id is not None:
            query["terminal_id"] = terminal_id
        path = "/tasks"
        if query:
            path = f"/tasks?{urlencode(query)}"
        return self._get_json(path)

    def list_tasks_filtered(
        self,
        terminal_id: str | None = None,
        status: str | None = None,
        script_name: str | None = None,
    ) -> dict[str, Any]:
        """Fetch task state with optional management filters."""

        query: dict[str, str] = {}
        if terminal_id is not None:
            query["terminal_id"] = terminal_id
        if status is not None:
            query["status"] = status
        if script_name is not None:
            query["script_name"] = script_name
        path = "/tasks"
        if query:
            path = f"/tasks?{urlencode(query)}"
        return self._get_json(path)

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Fetch one task by id from the NAS."""

        return self._get_json(f"/tasks/{task_id}")

    def list_task_events(self, task_id: str | None = None) -> dict[str, Any]:
        """Fetch task lifecycle timeline entries."""

        path = "/task-events"
        if task_id is not None:
            path = f"/tasks/{task_id}/events"
        return self._get_json(path)

    def list_task_attempts(self, task_id: str) -> dict[str, Any]:
        """Fetch aggregated execution attempts for one task."""

        return self._get_json(f"/tasks/{task_id}/attempts")

    def get_task_report(self, task_id: str) -> dict[str, Any]:
        """Fetch a combined diagnostic report for one task."""

        return self._get_json(f"/tasks/{task_id}/report")

    def claim_tasks(self, terminal_id: str) -> dict[str, Any]:
        """Claim queued tasks assigned to one terminal."""

        return self._post_json("/tasks/claim", {"terminal_id": terminal_id})

    def control_task(self, payload: TaskControlPayload) -> dict[str, Any]:
        """Apply a control-plane action to one task."""

        return self._post_json("/tasks/control", payload.to_dict())

    def submit_task_result(self, payload: ActionResultPayload) -> dict[str, Any]:
        """Submit one task execution result back to the NAS."""

        return self._post_json("/tasks/result", payload.to_dict())

    def mark_task_running(self, payload: ScriptRunPayload) -> dict[str, Any]:
        """Mark a task as running on the NAS side."""

        return self._post_json("/tasks/running", payload.to_dict())

    def list_logs(self) -> dict[str, Any]:
        """Fetch audit log entries from the NAS."""

        return self._get_json("/logs")

    def list_logs_filtered(
        self,
        terminal_id: str | None = None,
        task_id: str | None = None,
        level: str | None = None,
    ) -> dict[str, Any]:
        """Fetch audit log entries with optional management filters."""

        query: dict[str, str] = {}
        if terminal_id is not None:
            query["terminal_id"] = terminal_id
        if task_id is not None:
            query["task_id"] = task_id
        if level is not None:
            query["level"] = level
        path = "/logs"
        if query:
            path = f"/logs?{urlencode(query)}"
        return self._get_json(path)

    def get_log(self, log_id: str) -> dict[str, Any]:
        """Fetch one audit log entry by id from the NAS."""

        return self._get_json(f"/logs/{log_id}")

    def get_summary(self) -> dict[str, Any]:
        """Fetch a compact NAS-side management summary."""

        return self._get_json("/summary")

    def healthcheck(self) -> dict[str, Any]:
        """Check whether the NAS service is healthy."""

        return self._get_json("/healthz")

    def _get_json(self, path: str) -> dict[str, Any]:
        req = request.Request(f"{self._base_url}{path}", method="GET")
        return self._read_json(req)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self._base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._read_json(req)

    def _read_json(self, req: request.Request) -> dict[str, Any]:
        try:
            with request.urlopen(req, timeout=5) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"NAS request failed: {exc.code} {raw}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"NAS request failed: {exc.reason}") from exc

        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))
