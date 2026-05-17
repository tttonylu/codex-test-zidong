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

    def list_terminals(
        self,
        *,
        status: str | None = None,
        operator_name: str | None = None,
        min_active_task_count: int | None = None,
        max_parallel_tasks: int | None = None,
        blocked_instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch terminals using optional filter parameters."""

        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if operator_name is not None:
            params["operator_name"] = operator_name
        if min_active_task_count is not None:
            params["min_active_task_count"] = str(min_active_task_count)
        if max_parallel_tasks is not None:
            params["max_parallel_tasks"] = str(max_parallel_tasks)
        if blocked_instance_id is not None:
            params["blocked_instance_id"] = blocked_instance_id
        path = "/terminals"
        if params:
            path = f"/terminals?{urlencode(params)}"
        return self._get_json(path)

    def get_terminal(self, terminal_id: str) -> dict[str, Any]:
        """Fetch one terminal record by identifier."""

        return self._get_json(f"/terminal/{terminal_id}")

    def list_instances(
        self,
        *,
        terminal_id: str | None = None,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        """Fetch instances using optional filter parameters."""

        params: dict[str, str] = {}
        if terminal_id is not None:
            params["terminal_id"] = terminal_id
        if runtime_status is not None:
            params["runtime_status"] = runtime_status
        path = "/instances"
        if params:
            path = f"/instances?{urlencode(params)}"
        return self._get_json(path)

    def query_instances(
        self,
        *,
        terminal_id: str | None = None,
        runtime_status: str | None = None,
    ) -> dict[str, Any]:
        """Fetch instances using optional filter parameters."""

        params: dict[str, str] = {}
        if terminal_id is not None:
            params["terminal_id"] = terminal_id
        if runtime_status is not None:
            params["runtime_status"] = runtime_status
        return self.list_instances(
            terminal_id=terminal_id,
            runtime_status=runtime_status,
        )

    def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Fetch one instance record by identifier."""

        return self._get_json(f"/instance/{instance_id}")

    def create_task(self, payload: TaskAssignmentPayload) -> dict[str, Any]:
        """Create a task on the NAS side."""

        return self._post_json("/tasks", payload.to_dict())

    def list_tasks(self, terminal_id: str | None = None) -> dict[str, Any]:
        """Fetch current task state, optionally filtered by terminal."""

        path = "/tasks"
        if terminal_id is not None:
            path = f"/tasks?{urlencode({'terminal_id': terminal_id})}"
        return self._get_json(path)

    def get_task(self, task_id: str) -> dict[str, Any]:
        """Fetch one task record by identifier."""

        return self._get_json(f"/task/{task_id}")

    def query_tasks(
        self,
        *,
        terminal_id: str | None = None,
        status: str | None = None,
        script_name: str | None = None,
        retryable: bool | None = None,
        final: bool | None = None,
        wait_reason: str | None = None,
        blocked_by_instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch tasks using optional filter parameters."""

        params: dict[str, str] = {}
        if terminal_id is not None:
            params["terminal_id"] = terminal_id
        if status is not None:
            params["status"] = status
        if script_name is not None:
            params["script_name"] = script_name
        if retryable is not None:
            params["retryable"] = str(retryable).lower()
        if final is not None:
            params["final"] = str(final).lower()
        if wait_reason is not None:
            params["wait_reason"] = wait_reason
        if blocked_by_instance_id is not None:
            params["blocked_by_instance_id"] = blocked_by_instance_id
        path = "/tasks"
        if params:
            path = f"/tasks?{urlencode(params)}"
        return self._get_json(path)

    def claim_tasks(
        self,
        terminal_id: str,
        max_tasks: int | None = None,
        blocked_instance_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Claim queued tasks assigned to one terminal."""

        payload: dict[str, Any] = {"terminal_id": terminal_id}
        if max_tasks is not None:
            payload["max_tasks"] = max_tasks
        if blocked_instance_ids:
            payload["blocked_instance_ids"] = list(blocked_instance_ids)
        return self._post_json("/tasks/claim", payload)

    def submit_task_result(self, payload: ActionResultPayload) -> dict[str, Any]:
        """Submit one task execution result back to the NAS."""

        return self._post_json("/tasks/result", payload.to_dict())

    def retry_task(self, task_id: str, requested_by: str | None = None) -> dict[str, Any]:
        """Ask NAS to queue another attempt for one task."""

        return self._post_json("/tasks/retry", {"task_id": task_id, "requested_by": requested_by})

    def cancel_task(self, task_id: str, requested_by: str | None = None) -> dict[str, Any]:
        """Ask NAS to cancel one task."""

        return self._post_json("/tasks/cancel", {"task_id": task_id, "requested_by": requested_by})

    def mark_task_running(self, payload: ScriptRunPayload) -> dict[str, Any]:
        """Mark a task as running on the NAS side."""

        return self._post_json("/tasks/running", payload.to_dict())

    def list_logs(self) -> dict[str, Any]:
        """Fetch audit log entries from the NAS."""

        return self._get_json("/logs")

    def query_logs(
        self,
        *,
        terminal_id: str | None = None,
        task_id: str | None = None,
        level: str | None = None,
    ) -> dict[str, Any]:
        """Fetch logs using optional filter parameters."""

        params: dict[str, str] = {}
        if terminal_id is not None:
            params["terminal_id"] = terminal_id
        if task_id is not None:
            params["task_id"] = task_id
        if level is not None:
            params["level"] = level
        path = "/logs"
        if params:
            path = f"/logs?{urlencode(params)}"
        return self._get_json(path)

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
