"""NAS-persisted queue delivery transport used by queue_pull tasks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import uuid4

from nas_control_plane.models import QueueDeliveryRecord, TaskRecord
from nas_control_plane.services.repositories import QueueDeliveryRepository, TaskRepository
from shared.protocol import TaskAssignmentPayload
from terminal_agent.runtime.queue_claim import QueueClaimResult, QueueDeliveryActionResult


class QueueDeliveryTransportService:
    """Persists queue deliveries and serves claim/ack/defer/lease operations."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository | None = None,
        delivery_repository: QueueDeliveryRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
        lease_seconds: int = 60,
    ) -> None:
        self._task_repository = task_repository
        self._delivery_repository = delivery_repository
        self._now_fn = now_fn or datetime.utcnow
        self._lease_seconds = max(5, lease_seconds)
        self._tasks = self._task_repository.load_tasks() if self._task_repository is not None else {}
        self._deliveries = self._delivery_repository.load_deliveries() if self._delivery_repository is not None else {}
        self._reconcile_orphaned_claims()

    def publish_task(self, task: TaskRecord, *, queue_topic: str | None) -> QueueDeliveryRecord:
        """Create one queued delivery for a newly published queue_pull task."""

        now = self._now_fn()
        self._tasks[task.task_id] = task
        delivery_id = f"delivery-{uuid4().hex[:12]}"
        delivery = QueueDeliveryRecord(
            delivery_id=delivery_id,
            task_id=task.task_id,
            terminal_id=task.terminal_id,
            queue_topic=queue_topic,
            status="queued",
            available_at=now,
            details={
                "dispatch_mode": task.parameters.get("dispatch_mode"),
                "script_name": task.script_name,
            },
            created_at=now,
            updated_at=now,
        )
        self._deliveries[delivery_id] = delivery
        self._save_deliveries()
        return delivery

    def claim(
        self,
        *,
        terminal_id: str,
        max_tasks: int | None,
        queue_topic: str | None,
    ) -> QueueClaimResult:
        """Claim currently available queued deliveries for one terminal."""

        now = self._now_fn()
        self._expire_claims(now)
        limit = max_tasks if max_tasks is not None else None
        claimed: list[TaskAssignmentPayload] = []
        claimed_count = 0

        deliveries = sorted(
            self._deliveries.values(),
            key=lambda item: (item.available_at or item.created_at, item.created_at, item.delivery_id),
        )
        for delivery in deliveries:
            if limit is not None and claimed_count >= max(0, limit):
                break
            if delivery.terminal_id != terminal_id:
                continue
            if queue_topic is not None and delivery.queue_topic != queue_topic:
                continue
            if delivery.status != "queued":
                continue
            if delivery.available_at is not None and delivery.available_at > now:
                continue
            task = self._tasks.get(delivery.task_id)
            if task is None:
                delivery.status = "orphaned"
                delivery.last_error = "task_missing"
                delivery.updated_at = now
                continue
            if task.status not in {"queued", "retry_pending", "manual_retry_pending", "terminal_recovery_pending"}:
                continue

            lease_id = f"lease-{uuid4().hex[:12]}"
            claimed_delivery = replace(
                delivery,
                status="claimed",
                claim_lease_id=lease_id,
                claimed_by_terminal_id=terminal_id,
                claim_expires_at=now + timedelta(seconds=self._lease_seconds),
                attempt_count=delivery.attempt_count + 1,
                updated_at=now,
            )
            self._deliveries[delivery.delivery_id] = claimed_delivery
            claimed.append(_assignment_from_task(task, claimed_delivery))
            claimed_count += 1

        self._save_deliveries()
        return QueueClaimResult(
            status="claimed" if claimed else "idle",
            queue_topic=queue_topic,
            assignments=claimed,
            details={
                "claimed_count": len(claimed),
                "lease_seconds": self._lease_seconds,
            },
        )

    def ack_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        """Finalize one claimed delivery after successful result handling."""

        return self._finish_delivery(
            terminal_id=terminal_id,
            queue_topic=queue_topic,
            delivery_id=delivery_id,
            claim_lease_id=claim_lease_id,
            target_status="acked",
            action="ack",
            last_error=None,
        )

    def defer_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
        reason: str | None,
    ) -> QueueDeliveryActionResult:
        """Return one claimed delivery back to the queued pool."""

        if delivery_id is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="missing_delivery_id",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"reason": reason},
            )
        delivery = self._deliveries.get(delivery_id)
        if delivery is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="delivery_not_found",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"reason": reason},
            )
        if not self._lease_matches(delivery, terminal_id=terminal_id, claim_lease_id=claim_lease_id):
            return QueueDeliveryActionResult(
                accepted=False,
                status="lease_mismatch",
                queue_topic=delivery.queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"reason": reason},
            )
        now = self._now_fn()
        updated = replace(
            delivery,
            status="queued",
            claimed_by_terminal_id=None,
            claim_lease_id=None,
            claim_expires_at=None,
            available_at=now,
            updated_at=now,
            last_error=reason,
        )
        self._deliveries[delivery_id] = updated
        self._save_deliveries()
        return QueueDeliveryActionResult(
            accepted=True,
            status="deferred",
            queue_topic=updated.queue_topic,
            delivery_id=updated.delivery_id,
            claim_lease_id=claim_lease_id,
            details={"reason": reason},
        )

    def extend_claim_lease(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        """Refresh the lease for one in-flight claimed delivery."""

        if delivery_id is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="missing_delivery_id",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={},
            )
        delivery = self._deliveries.get(delivery_id)
        if delivery is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="delivery_not_found",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={},
            )
        if not self._lease_matches(delivery, terminal_id=terminal_id, claim_lease_id=claim_lease_id):
            return QueueDeliveryActionResult(
                accepted=False,
                status="lease_mismatch",
                queue_topic=delivery.queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={},
            )
        now = self._now_fn()
        updated = replace(
            delivery,
            claim_expires_at=now + timedelta(seconds=self._lease_seconds),
            updated_at=now,
        )
        self._deliveries[delivery_id] = updated
        self._save_deliveries()
        return QueueDeliveryActionResult(
            accepted=True,
            status="lease_extended",
            queue_topic=updated.queue_topic,
            delivery_id=updated.delivery_id,
            claim_lease_id=updated.claim_lease_id,
            details={"lease_seconds": self._lease_seconds},
        )

    def list_deliveries(self) -> list[QueueDeliveryRecord]:
        """Return all known queue deliveries."""

        self._expire_claims(self._now_fn())
        self._save_deliveries()
        return list(self._deliveries.values())

    def upsert_task(self, task: TaskRecord) -> None:
        """Refresh the transport-local task view for one task."""

        self._tasks[task.task_id] = task

    def remove_task(self, task_id: str) -> None:
        """Drop one task from the transport-local task view."""

        self._tasks.pop(task_id, None)

    def _finish_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
        target_status: str,
        action: str,
        last_error: str | None,
    ) -> QueueDeliveryActionResult:
        if delivery_id is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="missing_delivery_id",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"action": action},
            )
        delivery = self._deliveries.get(delivery_id)
        if delivery is None:
            return QueueDeliveryActionResult(
                accepted=False,
                status="delivery_not_found",
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"action": action},
            )
        if not self._lease_matches(delivery, terminal_id=terminal_id, claim_lease_id=claim_lease_id):
            return QueueDeliveryActionResult(
                accepted=False,
                status="lease_mismatch",
                queue_topic=delivery.queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                details={"action": action},
            )
        now = self._now_fn()
        updated = replace(
            delivery,
            status=target_status,
            claimed_by_terminal_id=terminal_id,
            claim_expires_at=None,
            updated_at=now,
            last_error=last_error,
        )
        self._deliveries[delivery_id] = updated
        self._save_deliveries()
        return QueueDeliveryActionResult(
            accepted=True,
            status=target_status,
            queue_topic=updated.queue_topic,
            delivery_id=updated.delivery_id,
            claim_lease_id=updated.claim_lease_id,
            details={"action": action},
        )

    def _expire_claims(self, now: datetime) -> None:
        for delivery_id, delivery in list(self._deliveries.items()):
            if delivery.status != "claimed":
                continue
            if delivery.claim_expires_at is None or delivery.claim_expires_at > now:
                continue
            task = self._tasks.get(delivery.task_id)
            if task is not None and task.status == "running":
                self._tasks[task.task_id] = replace(
                    task,
                    status="queued",
                    parameters={
                        **task.parameters,
                        "wait_reason": "lease_expired_requeued",
                        "delivery_id": None,
                        "claim_lease_id": None,
                        "updated_at": now.isoformat(),
                    },
                )
            self._deliveries[delivery_id] = replace(
                delivery,
                status="queued",
                claimed_by_terminal_id=None,
                claim_lease_id=None,
                claim_expires_at=None,
                available_at=now,
                updated_at=now,
                last_error="lease_expired",
            )
        self._save_tasks()

    def _reconcile_orphaned_claims(self) -> None:
        if not self._tasks:
            return
        now = self._now_fn()
        changed = False
        for delivery_id, delivery in list(self._deliveries.items()):
            task = self._tasks.get(delivery.task_id)
            if task is None:
                continue
            if delivery.status == "claimed" and task.status in {"completed", "terminal_failure", "retryable_failure", "cancelled"}:
                self._deliveries[delivery_id] = replace(
                    delivery,
                    status="queued" if task.status == "retryable_failure" else "acked",
                    claimed_by_terminal_id=None,
                    claim_expires_at=None,
                    available_at=now if task.status == "retryable_failure" else delivery.available_at,
                    updated_at=now,
                )
                changed = True
        if changed:
            self._save_deliveries()

    def _lease_matches(self, delivery: QueueDeliveryRecord, *, terminal_id: str, claim_lease_id: str | None) -> bool:
        return (
            delivery.status == "claimed"
            and delivery.claimed_by_terminal_id == terminal_id
            and delivery.claim_lease_id == claim_lease_id
        )

    def _save_deliveries(self) -> None:
        if self._delivery_repository is None:
            return
        self._delivery_repository.save_deliveries(self._deliveries)

    def _save_tasks(self) -> None:
        if self._task_repository is None:
            return
        self._task_repository.save_tasks(self._tasks)


def _assignment_from_task(task: TaskRecord, delivery: QueueDeliveryRecord) -> TaskAssignmentPayload:
    parameters = {
        **dict(task.parameters),
        "dispatch_mode": "queue_pull",
        "queue_topic": delivery.queue_topic,
        "delivery_id": delivery.delivery_id,
        "claim_lease_id": delivery.claim_lease_id,
    }
    return TaskAssignmentPayload(
        task_id=task.task_id,
        terminal_id=task.terminal_id,
        instance_id=task.instance_id,
        script_name=task.script_name,
        parameters=parameters,
        priority=task.priority,
        retry_limit=task.retry_limit,
        close_after_actions=task.close_after_actions,
        requested_by=task.requested_by,
        metadata={
            "preferred_terminal_id": task.preferred_terminal_id,
            "terminal_affinity": task.terminal_affinity,
            "recovery_target_terminal_id": task.recovery_target_terminal_id,
            "retry_kind": task.retry_kind,
        },
        dispatch_mode="queue_pull",
        queue_topic=delivery.queue_topic,
        delivery_id=delivery.delivery_id,
        claim_lease_id=delivery.claim_lease_id,
    )
