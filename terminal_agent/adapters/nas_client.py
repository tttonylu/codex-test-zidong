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
    PluginDispatchRequestPayload,
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
        preferred_terminal_id: str | None = None,
        dispatch_mode: str | None = None,
        queue_dispatch_status: str | None = None,
        queue_dispatch_accepted: bool | None = None,
        status: str | None = None,
        script_name: str | None = None,
        retryable: bool | None = None,
        final: bool | None = None,
        wait_reason: str | None = None,
        blocked_by_instance_id: str | None = None,
        retry_kind: str | None = None,
        terminal_affinity: str | None = None,
        recovery_claim_terminal_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch tasks using optional filter parameters."""

        params: dict[str, str] = {}
        if terminal_id is not None:
            params["terminal_id"] = terminal_id
        if preferred_terminal_id is not None:
            params["preferred_terminal_id"] = preferred_terminal_id
        if dispatch_mode is not None:
            params["dispatch_mode"] = dispatch_mode
        if queue_dispatch_status is not None:
            params["queue_dispatch_status"] = queue_dispatch_status
        if queue_dispatch_accepted is not None:
            params["queue_dispatch_accepted"] = str(queue_dispatch_accepted).lower()
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
        if retry_kind is not None:
            params["retry_kind"] = retry_kind
        if terminal_affinity is not None:
            params["terminal_affinity"] = terminal_affinity
        if recovery_claim_terminal_id is not None:
            params["recovery_claim_terminal_id"] = recovery_claim_terminal_id
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

    def claim_queue_tasks(
        self,
        *,
        terminal_id: str,
        max_tasks: int | None = None,
        queue_topic: str | None = None,
    ) -> dict[str, Any]:
        """Claim queued queue_pull deliveries assigned to one terminal."""

        payload: dict[str, Any] = {"terminal_id": terminal_id}
        if max_tasks is not None:
            payload["max_tasks"] = max_tasks
        if queue_topic is not None:
            payload["queue_topic"] = queue_topic
        return self._post_json("/queue/claim", payload)

    def ack_queue_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> dict[str, Any]:
        """Acknowledge one claimed queue delivery."""

        return self._post_json(
            "/queue/ack",
            {
                "terminal_id": terminal_id,
                "queue_topic": queue_topic,
                "delivery_id": delivery_id,
                "claim_lease_id": claim_lease_id,
            },
        )

    def defer_queue_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        """Return one claimed queue delivery back to the NAS queue."""

        return self._post_json(
            "/queue/defer",
            {
                "terminal_id": terminal_id,
                "queue_topic": queue_topic,
                "delivery_id": delivery_id,
                "claim_lease_id": claim_lease_id,
                "reason": reason,
            },
        )

    def extend_queue_claim_lease(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> dict[str, Any]:
        """Refresh one claimed queue delivery lease."""

        return self._post_json(
            "/queue/lease/extend",
            {
                "terminal_id": terminal_id,
                "queue_topic": queue_topic,
                "delivery_id": delivery_id,
                "claim_lease_id": claim_lease_id,
            },
        )

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

    def report_plugin_creator(
        self,
        *,
        creator_id: str,
        handle: str | None,
        source: str,
        terminal_id: str | None = None,
        profile_id: str | None = None,
        plugin_name: str | None = None,
        dedupe_key: str | None = None,
    ) -> dict[str, Any]:
        """Report one creator/blogger identifier from a plugin-facing interface."""

        return self._post_json(
            "/plugin/report-creator",
            {
                "creator_id": creator_id,
                "handle": handle,
                "source": source,
                "terminal_id": terminal_id,
                "profile_id": profile_id,
                "plugin_name": plugin_name,
                "dedupe_key": dedupe_key,
            },
        )

    def add_plugin_ammo_target(
        self,
        *,
        target_value: str,
        target_type: str = "handle",
        source: str = "plugin",
        creator_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add one ammo target for plugin distribution."""

        return self._post_json(
            "/plugin/ammo/add",
            {
                "target_value": target_value,
                "target_type": target_type,
                "source": source,
                "creator_id": creator_id,
                "metadata": dict(metadata or {}),
            },
        )

    def register_plugin_account(
        self,
        *,
        account_id: str,
        profile_id: str,
        handle: str | None,
        terminal_id: str | None = None,
        plugin_name: str | None = None,
        capability_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register one plugin-facing account inventory record."""

        return self._post_json(
            "/plugin/account/register",
            {
                "account_id": account_id,
                "profile_id": profile_id,
                "handle": handle,
                "terminal_id": terminal_id,
                "plugin_name": plugin_name,
                "capability_tags": list(capability_tags or []),
                "metadata": dict(metadata or {}),
            },
        )

    def claim_plugin_ammo_target(
        self,
        *,
        account_id: str,
        plugin_name: str | None = None,
        target_type: str | None = None,
        action_type: str | None = None,
        stat_date: str | None = None,
    ) -> dict[str, Any]:
        """Claim the next available ammo target for one plugin-facing account."""

        return self._post_json(
            "/plugin/ammo/claim",
            {
                "account_id": account_id,
                "plugin_name": plugin_name,
                "target_type": target_type,
                "action_type": action_type,
                "stat_date": stat_date,
            },
        )

    def consume_plugin_ammo_target(self, *, target_id: str, task_id: str | None = None) -> dict[str, Any]:
        """Mark one ammo target as consumed."""

        return self._post_json(
            "/plugin/ammo/consume",
            {
                "target_id": target_id,
                "task_id": task_id,
            },
        )

    def record_plugin_action(
        self,
        *,
        account_id: str | None,
        terminal_id: str | None,
        plugin_name: str | None,
        script_name: str,
        action_type: str,
        success: bool,
        metadata: dict[str, Any] | None = None,
        stat_date: str | None = None,
    ) -> dict[str, Any]:
        """Record one plugin-facing action into the daily aggregate table."""

        return self._post_json(
            "/plugin/action-log",
            {
                "account_id": account_id,
                "terminal_id": terminal_id,
                "plugin_name": plugin_name,
                "script_name": script_name,
                "action_type": action_type,
                "success": success,
                "metadata": dict(metadata or {}),
                "stat_date": stat_date,
            },
        )

    def list_plugin_creators(self) -> dict[str, Any]:
        """List plugin creator inbox items."""

        return self._get_json("/plugin/creators")

    def list_plugin_ammo(self, *, status: str | None = None) -> dict[str, Any]:
        """List plugin ammo targets and summary."""

        path = "/plugin/ammo"
        if status is not None:
            path = f"/plugin/ammo?{urlencode({'status': status})}"
        return self._get_json(path)

    def list_plugin_accounts(self, *, status: str | None = None) -> dict[str, Any]:
        """List plugin-facing account inventory rows."""

        path = "/plugin/accounts"
        if status is not None:
            path = f"/plugin/accounts?{urlencode({'status': status})}"
        return self._get_json(path)

    def set_plugin_account_status(
        self,
        *,
        account_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update one plugin account availability state."""

        return self._post_json(
            "/plugin/account/status",
            {
                "account_id": account_id,
                "status": status,
                "metadata": dict(metadata or {}),
            },
        )

    def evaluate_plugin_account_eligibility(
        self,
        *,
        account_id: str,
        plugin_name: str | None = None,
        action_type: str | None = None,
        stat_date: str | None = None,
    ) -> dict[str, Any]:
        """Check whether one plugin account may receive another action dispatch."""

        return self._post_json(
            "/plugin/account/eligibility",
            {
                "account_id": account_id,
                "plugin_name": plugin_name,
                "action_type": action_type,
                "stat_date": stat_date,
            },
        )

    def list_plugin_daily_stats(self, *, stat_date: str | None = None) -> dict[str, Any]:
        """List daily aggregated plugin stats."""

        path = "/plugin/stats/daily"
        if stat_date is not None:
            path = f"/plugin/stats/daily?{urlencode({'stat_date': stat_date})}"
        return self._get_json(path)

    def upsert_plugin_campaign(
        self,
        *,
        campaign_id: str,
        plugin_name: str,
        script_name: str,
        action_type: str,
        copy_items: list[dict[str, Any]] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one plugin campaign/copy bundle."""

        return self._post_json(
            "/plugin/campaign/upsert",
            {
                "campaign_id": campaign_id,
                "plugin_name": plugin_name,
                "script_name": script_name,
                "action_type": action_type,
                "copy_items": list(copy_items or []),
                "status": status,
                "metadata": dict(metadata or {}),
            },
        )

    def list_plugin_campaigns(
        self,
        *,
        plugin_name: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List plugin campaigns."""

        params: dict[str, str] = {}
        if plugin_name is not None:
            params["plugin_name"] = plugin_name
        if status is not None:
            params["status"] = status
        path = "/plugin/campaigns"
        if params:
            path = f"/plugin/campaigns?{urlencode(params)}"
        return self._get_json(path)

    def upsert_plugin_dispatch_rule(
        self,
        *,
        rule_id: str,
        account_id: str,
        plugin_name: str,
        script_name: str,
        action_plan: list[dict[str, Any]] | None = None,
        campaign_id: str | None = None,
        terminal_id: str | None = None,
        instance_id: str | None = None,
        target_type: str = "handle",
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one plugin auto-dispatch rule."""

        return self._post_json(
            "/plugin/dispatch-rule/upsert",
            {
                "rule_id": rule_id,
                "account_id": account_id,
                "plugin_name": plugin_name,
                "script_name": script_name,
                "action_plan": list(action_plan or []),
                "campaign_id": campaign_id,
                "terminal_id": terminal_id,
                "instance_id": instance_id,
                "target_type": target_type,
                "status": status,
                "metadata": dict(metadata or {}),
            },
        )

    def list_plugin_dispatch_rules(
        self,
        *,
        account_id: str | None = None,
        plugin_name: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List plugin auto-dispatch rules."""

        params: dict[str, str] = {}
        if account_id is not None:
            params["account_id"] = account_id
        if plugin_name is not None:
            params["plugin_name"] = plugin_name
        if status is not None:
            params["status"] = status
        path = "/plugin/dispatch-rules"
        if params:
            path = f"/plugin/dispatch-rules?{urlencode(params)}"
        return self._get_json(path)

    def cleanup_plugin_stats(self) -> dict[str, Any]:
        """Run plugin daily stats retention cleanup immediately."""

        return self._post_json("/plugin/stats/cleanup", {})

    def dispatch_plugin_task(self, payload: PluginDispatchRequestPayload) -> dict[str, Any]:
        """Claim ammo and create one NAS task in a single plugin-facing request."""

        return self._post_json("/plugin/dispatch", payload.to_dict())

    def pull_plugin_task(
        self,
        *,
        terminal_id: str | None,
        instance_id: str | None,
        account_id: str | None,
        script_name: str | None,
        plugin_name: str | None = None,
    ) -> dict[str, Any]:
        """Pull one queued business task for a plugin runtime."""

        return self._post_json(
            "/plugin/task/pull",
            {
                "terminal_id": terminal_id,
                "instance_id": instance_id,
                "account_id": account_id,
                "script_name": script_name,
                "plugin_name": plugin_name,
            },
        )

    def sync_instance_remark(
        self,
        *,
        instance_id: str,
        current_account_handle: str | None,
        remark: str | None,
        remark_sync_status: str,
        remark_sync_error: str | None = None,
    ) -> dict[str, Any]:
        """Update NAS-side instance remark/account observability fields."""

        return self._post_json(
            "/instance/remark-sync",
            {
                "instance_id": instance_id,
                "current_account_handle": current_account_handle,
                "remark": remark,
                "remark_sync_status": remark_sync_status,
                "remark_sync_error": remark_sync_error,
            },
        )

    def request_instance_restart(self, *, instance_id: str, reason: str) -> dict[str, Any]:
        """Mark one instance as restart-requested on the NAS side."""

        return self._post_json(
            "/instance/restart",
            {
                "instance_id": instance_id,
                "reason": reason,
            },
        )

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
