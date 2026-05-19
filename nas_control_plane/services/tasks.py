"""Minimal in-memory task dispatch service."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta

from nas_control_plane.models import TaskRecord
from nas_control_plane.services.dispatch import normalize_dispatch_mode, task_uses_http_claim
from nas_control_plane.services.queue_dispatch import LocalQueueDispatchProvider, NoopQueueDispatchProvider, QueueDispatchProvider
from nas_control_plane.services.queue_transport import QueueDeliveryTransportService
from nas_control_plane.services.recovery import RecoveryPolicy, resolve_recovery_policy
from nas_control_plane.services.repositories import TaskRepository
from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload


class TaskDispatchService:
    """Stores and serves simple terminal-bound task assignments."""

    def __init__(
        self,
        repository: TaskRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
        queue_dispatch_provider: QueueDispatchProvider | None = None,
        queue_transport: QueueDeliveryTransportService | None = None,
    ) -> None:
        self._repository = repository
        self._now_fn = now_fn or datetime.utcnow
        self._queue_transport = queue_transport
        if queue_dispatch_provider is not None:
            self._queue_dispatch_provider = queue_dispatch_provider
        elif queue_transport is not None:
            self._queue_dispatch_provider = LocalQueueDispatchProvider(queue_transport)
        else:
            self._queue_dispatch_provider = NoopQueueDispatchProvider()
        self._tasks: dict[str, TaskRecord] = {}
        self._load_state()

    def create_task(self, payload: TaskAssignmentPayload) -> TaskRecord:
        """Create a new queued task."""

        self._load_state()
        dispatch_mode = normalize_dispatch_mode(payload.dispatch_mode)
        initial_parameters = {
            **dict(payload.parameters),
            "dispatch_mode": dispatch_mode,
            "queue_topic": payload.queue_topic,
            "delivery_id": payload.delivery_id,
            "claim_lease_id": payload.claim_lease_id,
        }
        if dispatch_mode == "queue_pull":
            initial_parameters.setdefault("wait_reason", "queue_transport_inactive")
            initial_parameters.setdefault("task_source_status", "not_implemented")
        record = TaskRecord(
            task_id=payload.task_id,
            terminal_id=payload.terminal_id,
            preferred_terminal_id=str(payload.metadata.get("preferred_terminal_id") or payload.terminal_id),
            script_name=payload.script_name,
            status="queued",
            instance_id=payload.instance_id,
            terminal_affinity=str(payload.metadata.get("terminal_affinity") or "required"),
            recovery_target_terminal_id=(
                str(payload.metadata["recovery_target_terminal_id"])
                if payload.metadata.get("recovery_target_terminal_id") is not None
                else None
            ),
            priority=payload.priority,
            retry_limit=payload.retry_limit,
            close_after_actions=payload.close_after_actions,
            requested_by=payload.requested_by,
            retry_kind=payload.metadata.get("retry_kind"),
            parameters=initial_parameters,
        )
        if dispatch_mode == "queue_pull":
            dispatch_result = self._queue_dispatch_provider.dispatch_task(record)
            updated_parameters = {
                **record.parameters,
                "queue_dispatch_accepted": dispatch_result.accepted,
                "queue_dispatch_status": dispatch_result.status,
                "queue_dispatch_retryable": dispatch_result.retryable,
                "queue_dispatch_attempted_at": self._now_fn().isoformat(),
                "queue_dispatch_details": dict(dispatch_result.details),
                "queue_topic": dispatch_result.queue_topic or record.parameters.get("queue_topic"),
                "delivery_id": dispatch_result.delivery_id or record.parameters.get("delivery_id"),
                "claim_lease_id": dispatch_result.claim_lease_id or record.parameters.get("claim_lease_id"),
                "task_source_status": dispatch_result.status,
            }
            if dispatch_result.wait_reason is not None:
                updated_parameters["wait_reason"] = dispatch_result.wait_reason
            elif dispatch_result.accepted:
                updated_parameters.pop("wait_reason", None)
            record = replace(record, parameters=updated_parameters)
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(record)
        self._tasks[record.task_id] = record
        self._save_state()
        return record

    def list_tasks(self, terminal_id: str | None = None) -> list[TaskRecord]:
        """Return all tasks, optionally filtered by terminal."""

        self._load_state()
        records = list(self._tasks.values())
        if terminal_id is None:
            return records
        return [record for record in records if record.terminal_id == terminal_id]

    def get_task(self, task_id: str) -> TaskRecord:
        """Return one task by identifier."""

        self._load_state()
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

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
    ) -> list[TaskRecord]:
        """Return tasks matching the requested filters."""

        self._load_state()
        records = self.list_tasks(terminal_id=terminal_id)
        return [
            record
            for record in records
            if _matches_task_filter(
                record,
                status=status,
                script_name=script_name,
                dispatch_mode=dispatch_mode,
                queue_dispatch_status=queue_dispatch_status,
                queue_dispatch_accepted=queue_dispatch_accepted,
                retryable=retryable,
                final=final,
                wait_reason=wait_reason,
                blocked_by_instance_id=blocked_by_instance_id,
                retry_kind=retry_kind,
                preferred_terminal_id=preferred_terminal_id,
                terminal_affinity=terminal_affinity,
                recovery_claim_terminal_id=recovery_claim_terminal_id,
            )
        ]

    def claim_tasks(
        self,
        terminal_id: str,
        limit: int | None = None,
        blocked_instance_ids: set[str] | None = None,
    ) -> list[TaskRecord]:
        """Return claimable tasks for one terminal and mark them as dispatched."""

        self._load_state()
        eligible: list[TaskRecord] = []
        claimed_instance_ids = set(blocked_instance_ids or set())
        skipped_due_to_blocked_instance: list[TaskRecord] = []
        ready_retry_pending_ids: set[str] = set()
        now = self._now_fn()
        for record in self._tasks.values():
            if record.terminal_id != terminal_id:
                continue
            if not task_uses_http_claim(record):
                continue
            if record.instance_id is not None and record.instance_id in claimed_instance_ids:
                skipped_due_to_blocked_instance.append(record)
                continue
            if record.status == "queued":
                eligible.append(record)
            elif _is_retry_pending(record):
                if retry_task_ready(record, now):
                    eligible.append(record)
                    ready_retry_pending_ids.add(record.task_id)

        claimed: list[TaskRecord] = []
        eligible.sort(key=claim_task_sort_key)
        max_items = max(0, limit) if limit is not None else None
        for record in eligible:
            if max_items is not None and len(claimed) >= max_items:
                break
            if record.instance_id is not None and record.instance_id in claimed_instance_ids:
                skipped_due_to_blocked_instance.append(record)
                continue
            updated = replace(record, status="dispatched")
            self._tasks[record.task_id] = updated
            claimed.append(updated)
            if record.instance_id is not None:
                claimed_instance_ids.add(record.instance_id)

        claimed_ids = {record.task_id for record in claimed}
        for record in self._tasks.values():
            if record.terminal_id != terminal_id or record.task_id in claimed_ids:
                continue
            if not task_uses_http_claim(record):
                continue
            parameters = dict(record.parameters)
            if record.status == "queued":
                if record in skipped_due_to_blocked_instance:
                    parameters["wait_reason"] = "instance_blocked"
                    parameters["blocked_by_instance_id"] = record.instance_id
                elif max_items is not None and len(claimed) >= max_items:
                    parameters["wait_reason"] = "slot_capacity_reached"
                    parameters["blocked_by_instance_id"] = None
                else:
                    parameters.pop("wait_reason", None)
                    parameters.pop("blocked_by_instance_id", None)
                self._tasks[record.task_id] = replace(record, parameters=parameters)
            elif _is_retry_pending(record):
                if record in skipped_due_to_blocked_instance:
                    parameters["wait_reason"] = "instance_blocked"
                    parameters["blocked_by_instance_id"] = record.instance_id
                elif record.task_id in ready_retry_pending_ids and max_items is not None and len(claimed) >= max_items:
                    parameters["wait_reason"] = "slot_capacity_reached"
                    parameters["blocked_by_instance_id"] = None
                elif record.task_id in ready_retry_pending_ids:
                    parameters.pop("wait_reason", None)
                    parameters.pop("blocked_by_instance_id", None)
                else:
                    parameters["wait_reason"] = "retry_not_ready"
                    parameters["blocked_by_instance_id"] = None
                self._tasks[record.task_id] = replace(record, parameters=parameters)
        self._save_state()
        return claimed

    def record_result(self, payload: ActionResultPayload) -> TaskRecord:
        """Update one task from a terminal execution result."""

        self._load_state()
        try:
            record = self._tasks[payload.task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {payload.task_id}") from exc

        policy = resolve_recovery_policy(payload.error_code)
        exhausted = updated_retry_limit_exhausted(record)
        retryable_requested = payload.retryable if payload.retryable is not None else policy.retryable
        final = bool(payload.final) or (payload.status != "completed" and (exhausted or not retryable_requested))
        retryable = retryable_requested and not final
        status = payload.status
        if payload.status != "completed":
            status = "retryable_failure" if retryable else "terminal_failure"

        updated = replace(
            record,
            status=status,
            retryable=retryable,
            final=final,
            last_error_code=payload.error_code,
            last_error_message=payload.error_message or None,
            retry_kind=record.retry_kind,
            parameters={
                **record.parameters,
                "result_summary": payload.summary,
                "result_details": dict(payload.details),
                "result_emitted_at": payload.emitted_at.isoformat(),
                "result_run_id": payload.run_id,
                "updated_at": self._now_fn().isoformat(),
                "last_error_code": payload.error_code,
                "last_error_message": payload.error_message,
                "delivery_id": payload.delivery_id or record.parameters.get("delivery_id"),
                "claim_lease_id": payload.claim_lease_id or record.parameters.get("claim_lease_id"),
                "failure_category": policy.category,
                "recommended_action": policy.recommended_action,
                "retry_delay_seconds": policy.retry_delay_seconds,
                "retry_available_at": None,
                "retryable": retryable,
                "final": final,
            },
        )
        self._tasks[payload.task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def retry_task(self, task_id: str, requested_by: str | None = None) -> TaskRecord:
        """Ask NAS to queue another attempt for a previously failed task."""

        self._load_state()
        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        exhausted = updated_retry_limit_exhausted(record)
        accepted = record.status in {"failed", "terminal_failure", "retryable_failure", "retry_pending"} and not exhausted
        retry_delay_seconds = _coerce_retry_delay_seconds(record.parameters.get("retry_delay_seconds"))
        now = self._now_fn()
        parameters = {
            **record.parameters,
            "retry_requested_at": now.isoformat(),
            "retry_requested_by": requested_by,
            "updated_at": now.isoformat(),
        }
        if accepted:
            parameters["retry_request_accepted"] = True
            parameters["retry_available_at"] = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
            updated = replace(
                record,
                status="manual_retry_pending",
                retryable=False,
                final=False,
                retry_kind="manual_retry",
                parameters=parameters,
            )
        else:
            parameters["retry_request_accepted"] = False
            parameters["retry_blocked_reason"] = "retry_limit_exceeded" if exhausted else "task_not_retryable"
            updated = replace(
                record,
                status="terminal_failure" if record.status != "completed" else record.status,
                retryable=False,
                final=True if record.status != "completed" else record.final,
                retry_kind=record.retry_kind,
                parameters=parameters,
            )

        self._tasks[task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def cancel_task(self, task_id: str, requested_by: str | None = None) -> TaskRecord:
        """Cancel one task when it has not reached a final completed state."""

        self._load_state()
        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        cancellable = record.status in {"queued", "dispatched", "running", "retry_pending", "manual_retry_pending", "terminal_recovery_pending"}
        parameters = {
            **record.parameters,
            "cancel_requested_at": self._now_fn().isoformat(),
            "cancel_requested_by": requested_by,
            "updated_at": self._now_fn().isoformat(),
        }
        if cancellable:
            parameters["cancel_request_accepted"] = True
            updated = replace(
                record,
                status="cancelled",
                retryable=False,
                final=True,
                parameters=parameters,
            )
        else:
            parameters["cancel_request_accepted"] = False
            parameters["cancel_blocked_reason"] = "task_already_final"
            updated = replace(
                record,
                parameters=parameters,
            )

        self._tasks[task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def mark_running(self, payload: ScriptRunPayload) -> TaskRecord:
        """Mark one claimed task as running."""

        self._load_state()
        try:
            record = self._tasks[payload.task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {payload.task_id}") from exc

        updated = replace(
            record,
            status=payload.status,
            attempt_count=record.attempt_count + 1,
            retry_kind=record.retry_kind,
            parameters={
                **record.parameters,
                "run_id": payload.run_id,
                "run_script_name": payload.script_name,
                "run_started_at": payload.started_at.isoformat() if payload.started_at else None,
                "run_step_count": payload.step_count,
                "delivery_id": payload.metadata.get("delivery_id", record.parameters.get("delivery_id")),
                "claim_lease_id": payload.metadata.get("claim_lease_id", record.parameters.get("claim_lease_id")),
                "updated_at": self._now_fn().isoformat(),
            },
        )
        self._tasks[payload.task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def append_plugin_action_event(
        self,
        *,
        task_id: str,
        action_name: str,
        success: bool,
        summary: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TaskRecord:
        """Append one plugin-stage action event into task result details."""

        self._load_state()
        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        now = self._now_fn().isoformat()
        existing_result_details = dict(record.parameters.get("result_details") or {})
        action_results = list(existing_result_details.get("action_results") or [])
        action_index = metadata.get("action_index") if metadata is not None else None
        event = {
            "action": action_name,
            "status": "completed" if success else "failed",
            "summary": summary or action_name,
            "success": success,
            "reported_at": now,
            "action_index": action_index,
            "details": dict(metadata or {}),
        }

        replaced = False
        if action_index is not None:
            for index, item in enumerate(action_results):
                if not isinstance(item, dict):
                    continue
                if item.get("action_index") == action_index:
                    action_results[index] = {
                        **item,
                        **event,
                    }
                    replaced = True
                    break
        if not replaced:
            action_results.append(event)

        ordered_results = sorted(
            action_results,
            key=lambda item: (
                item.get("action_index") if isinstance(item, dict) and item.get("action_index") is not None else 10_000,
                str(item.get("action") if isinstance(item, dict) else ""),
            ),
        )
        planned_actions = list(record.parameters.get("action_plan") or [])
        planned_action_count = len(planned_actions)
        completed_action_count = sum(
            1 for item in ordered_results if isinstance(item, dict) and item.get("status") == "completed"
        )
        failed_action_count = sum(
            1 for item in ordered_results if isinstance(item, dict) and item.get("status") == "failed"
        )
        failure_policy = _plugin_action_failure_policy(metadata if not success else None)
        if failed_action_count and completed_action_count:
            business_progress_status = "partial_failure"
        elif failed_action_count:
            business_progress_status = "action_failed"
        elif planned_action_count and completed_action_count >= planned_action_count:
            business_progress_status = "action_plan_completed"
        elif completed_action_count:
            business_progress_status = "partially_completed"
        else:
            business_progress_status = "in_progress"
        existing_result_details["action_results"] = ordered_results
        existing_result_details["plugin_stage_last_action"] = action_name
        existing_result_details["plugin_stage_last_success"] = success
        existing_result_details["plugin_stage_last_reported_at"] = now
        existing_result_details["planned_action_count"] = planned_action_count
        existing_result_details["completed_action_count"] = completed_action_count
        existing_result_details["failed_action_count"] = failed_action_count
        existing_result_details["business_progress_status"] = business_progress_status
        existing_result_details["business_retryable"] = failure_policy.retryable if failure_policy is not None else False
        existing_result_details["business_recommended_action"] = (
            failure_policy.recommended_action if failure_policy is not None else None
        )
        existing_result_details["business_failure_category"] = (
            failure_policy.category if failure_policy is not None else None
        )
        existing_result_details["business_retry_delay_seconds"] = (
            failure_policy.retry_delay_seconds if failure_policy is not None else 0
        )

        updated = replace(
            record,
            parameters={
                **record.parameters,
                "result_details": existing_result_details,
                "updated_at": now,
            },
        )
        self._tasks[task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def mark_recovered(self, task_id: str, recovered_from_terminal_id: str | None = None) -> TaskRecord:
        """Requeue one task that was abandoned during terminal recovery."""

        self._load_state()
        try:
            record = self._tasks[task_id]
        except KeyError as exc:
            raise KeyError(f"task not found: {task_id}") from exc

        parameters = {
            **record.parameters,
            "recovered_from_terminal_id": recovered_from_terminal_id,
            "recovered_at": self._now_fn().isoformat(),
            "wait_reason": "terminal_recovered",
            "blocked_by_instance_id": None,
            "recovery_priority_boost": 1000,
        }
        recovery_claim_terminal_id = _resolve_recovery_claim_terminal(record, recovered_from_terminal_id)
        if recovery_claim_terminal_id != record.terminal_id:
            parameters["recovery_handoff_from_terminal_id"] = record.terminal_id
            parameters["recovery_handoff_to_terminal_id"] = recovery_claim_terminal_id
        parameters["recovery_claim_terminal_id"] = recovery_claim_terminal_id
        updated = replace(
            record,
            terminal_id=recovery_claim_terminal_id,
            status="terminal_recovery_pending" if record.retry_limit > 0 else "queued",
            retryable=False,
            final=False,
            retry_kind="terminal_recovery",
            parameters=parameters,
        )
        self._tasks[task_id] = updated
        if self._queue_transport is not None:
            self._queue_transport.upsert_task(updated)
        self._save_state()
        return updated

    def _load_state(self) -> None:
        if self._repository is None:
            return

        self._tasks = self._repository.load_tasks()

    def _save_state(self) -> None:
        if self._repository is None:
            return

        self._repository.save_tasks(self._tasks)


def updated_retry_limit_exhausted(record: TaskRecord) -> bool:
    """Return whether one more retry would exceed the configured limit."""

    return record.attempt_count >= record.retry_limit + 1


def retry_task_ready(record: TaskRecord, now: datetime) -> bool:
    """Return whether one retry-pending task may be claimed now."""

    if not _is_retry_pending(record):
        return True

    raw = record.parameters.get("retry_available_at")
    if not raw:
        return True

    try:
        available_at = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    return available_at <= now


def claim_task_sort_key(record: TaskRecord) -> tuple[int, int, datetime]:
    """Order tasks so recovered work is claimed before ordinary queued work."""

    parameters = record.parameters or {}
    recovery_boost = int(parameters.get("recovery_priority_boost", 0) or 0)
    recovered_rank = 1 if record.retry_kind == "terminal_recovery" else 0
    return (-recovered_rank, -recovery_boost, -record.priority, record.created_at)


def _matches_task_filter(
    record: TaskRecord,
    *,
    preferred_terminal_id: str | None,
    dispatch_mode: str | None,
    queue_dispatch_status: str | None,
    queue_dispatch_accepted: bool | None,
    status: str | None,
    script_name: str | None,
    retryable: bool | None,
    final: bool | None,
    wait_reason: str | None,
    blocked_by_instance_id: str | None,
    retry_kind: str | None,
    terminal_affinity: str | None,
    recovery_claim_terminal_id: str | None,
) -> bool:
    if preferred_terminal_id is not None and record.preferred_terminal_id != preferred_terminal_id:
        return False
    if status is not None and not _status_matches(record.status, status):
        return False
    if script_name is not None and record.script_name != script_name:
        return False
    parameters = record.parameters or {}
    if dispatch_mode is not None and str(parameters.get("dispatch_mode") or "claim_http") != dispatch_mode:
        return False
    if queue_dispatch_status is not None and parameters.get("queue_dispatch_status") != queue_dispatch_status:
        return False
    if queue_dispatch_accepted is not None:
        actual_queue_dispatch_accepted = _coerce_bool(parameters.get("queue_dispatch_accepted"))
        if actual_queue_dispatch_accepted is None or actual_queue_dispatch_accepted != queue_dispatch_accepted:
            return False
    if retryable is not None and record.retryable is not retryable:
        return False
    if final is not None and record.final is not final:
        return False
    if wait_reason is not None and parameters.get("wait_reason") != wait_reason:
        return False
    if blocked_by_instance_id is not None and parameters.get("blocked_by_instance_id") != blocked_by_instance_id:
        return False
    if retry_kind is not None and record.retry_kind != retry_kind:
        return False
    if terminal_affinity is not None and record.terminal_affinity != terminal_affinity:
        return False
    if recovery_claim_terminal_id is not None and parameters.get("recovery_claim_terminal_id") != recovery_claim_terminal_id:
        return False
    return True


def _coerce_retry_delay_seconds(raw: object) -> int:
    try:
        return max(0, int(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


def _plugin_action_failure_policy(metadata: dict[str, object] | None) -> RecoveryPolicy | None:
    if metadata is None:
        return None
    error_code = metadata.get("error_code")
    if error_code is None:
        return resolve_recovery_policy(None)
    return resolve_recovery_policy(str(error_code))


def _coerce_bool(raw: object) -> bool | None:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _is_retry_pending(record: TaskRecord) -> bool:
    return record.status in {"retry_pending", "manual_retry_pending", "terminal_recovery_pending"}


def _status_matches(actual_status: str, requested_status: str) -> bool:
    if requested_status == "retry_pending":
        return actual_status in {"retry_pending", "manual_retry_pending", "terminal_recovery_pending"}
    return actual_status == requested_status


def _resolve_recovery_claim_terminal(record: TaskRecord, recovered_from_terminal_id: str | None) -> str:
    if record.terminal_affinity == "required":
        return record.terminal_id
    target = record.recovery_target_terminal_id
    if target and target != recovered_from_terminal_id:
        return target
    return record.terminal_id
