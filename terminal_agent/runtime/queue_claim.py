"""Queue-claim provider contracts for future terminal-side pull consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import NasControlPlaneClient


@dataclass(frozen=True, slots=True)
class QueueClaimResult:
    """Outcome of attempting one queue-backed claim cycle."""

    status: str
    queue_topic: str | None = None
    assignments: list[TaskAssignmentPayload] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueueDeliveryActionResult:
    """Outcome of one queue-delivery follow-up action such as ack or defer."""

    accepted: bool
    status: str
    queue_topic: str | None = None
    delivery_id: str | None = None
    claim_lease_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class QueueClaimProvider(Protocol):
    """Contract for terminal-side queue consumption without binding to a transport."""

    def claim(self, *, terminal_id: str, max_tasks: int | None, queue_topic: str | None) -> QueueClaimResult:
        """Attempt to receive assignments from a queue-backed source."""

    def ack_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        """Acknowledge one successfully handled queue delivery."""

    def defer_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
        reason: str | None,
    ) -> QueueDeliveryActionResult:
        """Release one queue delivery back to the transport for later retry."""

    def extend_claim_lease(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        """Extend or refresh one in-flight queue delivery lease."""


class NoopQueueClaimProvider:
    """Placeholder provider used before a real queue consumer exists."""

    def claim(self, *, terminal_id: str, max_tasks: int | None, queue_topic: str | None) -> QueueClaimResult:
        return QueueClaimResult(
            status="not_implemented",
            queue_topic=queue_topic,
            assignments=[],
            details={
                "terminal_id": terminal_id,
                "max_tasks": max_tasks,
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
        return QueueDeliveryActionResult(
            accepted=False,
            status="not_implemented",
            queue_topic=queue_topic,
            delivery_id=delivery_id,
            claim_lease_id=claim_lease_id,
            details={"terminal_id": terminal_id, "action": "ack"},
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
        return QueueDeliveryActionResult(
            accepted=False,
            status="not_implemented",
            queue_topic=queue_topic,
            delivery_id=delivery_id,
            claim_lease_id=claim_lease_id,
            details={"terminal_id": terminal_id, "action": "defer", "reason": reason},
        )

    def extend_claim_lease(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        return QueueDeliveryActionResult(
            accepted=False,
            status="not_implemented",
            queue_topic=queue_topic,
            delivery_id=delivery_id,
            claim_lease_id=claim_lease_id,
            details={"terminal_id": terminal_id, "action": "extend_claim_lease"},
        )


class NasQueueClaimProvider:
    """Queue claim provider backed by NAS queue transport HTTP endpoints."""

    def __init__(self, nas_client: NasControlPlaneClient) -> None:
        self._nas_client = nas_client

    def claim(self, *, terminal_id: str, max_tasks: int | None, queue_topic: str | None) -> QueueClaimResult:
        response = self._nas_client.claim_queue_tasks(
            terminal_id=terminal_id,
            max_tasks=max_tasks,
            queue_topic=queue_topic,
        )
        return QueueClaimResult(
            status=str(response.get("status", "idle")),
            queue_topic=str(response["queue_topic"]) if response.get("queue_topic") is not None else queue_topic,
            assignments=[_assignment_from_dict(item) for item in response.get("items", [])],
            details=dict(response.get("details", {})),
        )

    def ack_delivery(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        return _action_result_from_dict(
            self._nas_client.ack_queue_delivery(
                terminal_id=terminal_id,
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
            )
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
        return _action_result_from_dict(
            self._nas_client.defer_queue_delivery(
                terminal_id=terminal_id,
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
                reason=reason,
            )
        )

    def extend_claim_lease(
        self,
        *,
        terminal_id: str,
        queue_topic: str | None,
        delivery_id: str | None,
        claim_lease_id: str | None,
    ) -> QueueDeliveryActionResult:
        return _action_result_from_dict(
            self._nas_client.extend_queue_claim_lease(
                terminal_id=terminal_id,
                queue_topic=queue_topic,
                delivery_id=delivery_id,
                claim_lease_id=claim_lease_id,
            )
        )


def _assignment_from_dict(payload: dict[str, object]) -> TaskAssignmentPayload:
    return TaskAssignmentPayload(
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        script_name=str(payload["script_name"]),
        parameters=dict(payload.get("parameters", {})),
        priority=int(payload.get("priority", 0)),
        retry_limit=int(payload.get("retry_limit", 0)),
        close_after_actions=bool(payload.get("close_after_actions", False)),
        requested_by=str(payload["requested_by"]) if payload.get("requested_by") is not None else None,
        metadata=dict(payload.get("metadata", {})),
        dispatch_mode=str(payload.get("dispatch_mode", "queue_pull")),
        queue_topic=str(payload["queue_topic"]) if payload.get("queue_topic") is not None else None,
        delivery_id=str(payload["delivery_id"]) if payload.get("delivery_id") is not None else None,
        claim_lease_id=str(payload["claim_lease_id"]) if payload.get("claim_lease_id") is not None else None,
    )


def _action_result_from_dict(payload: dict[str, object]) -> QueueDeliveryActionResult:
    return QueueDeliveryActionResult(
        accepted=bool(payload.get("accepted", False)),
        status=str(payload.get("status", "unknown")),
        queue_topic=str(payload["queue_topic"]) if payload.get("queue_topic") is not None else None,
        delivery_id=str(payload["delivery_id"]) if payload.get("delivery_id") is not None else None,
        claim_lease_id=str(payload["claim_lease_id"]) if payload.get("claim_lease_id") is not None else None,
        details=dict(payload.get("details", {})),
    )
