"""Queue-dispatch provider contracts for future non-HTTP task delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from nas_control_plane.models import TaskRecord
from nas_control_plane.services.queue_transport import QueueDeliveryTransportService


@dataclass(frozen=True, slots=True)
class QueueDispatchResult:
    """Outcome of attempting to publish one task into a queue-backed path."""

    accepted: bool
    status: str
    retryable: bool | None = None
    wait_reason: str | None = None
    queue_topic: str | None = None
    delivery_id: str | None = None
    claim_lease_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class QueueDispatchProvider(Protocol):
    """Contract for NAS-side queue publication without choosing a transport yet."""

    def dispatch_task(self, task: TaskRecord) -> QueueDispatchResult:
        """Attempt to publish one task to its queue-backed delivery path."""


class NoopQueueDispatchProvider:
    """Placeholder provider used before any real queue transport is integrated."""

    def dispatch_task(self, task: TaskRecord) -> QueueDispatchResult:
        parameters = task.parameters or {}
        return QueueDispatchResult(
            accepted=False,
            status="not_implemented",
            retryable=False,
            wait_reason="queue_transport_inactive",
            queue_topic=str(parameters.get("queue_topic")) if parameters.get("queue_topic") is not None else None,
            delivery_id=str(parameters.get("delivery_id")) if parameters.get("delivery_id") is not None else None,
            claim_lease_id=str(parameters.get("claim_lease_id")) if parameters.get("claim_lease_id") is not None else None,
            details={
                "dispatch_mode": parameters.get("dispatch_mode"),
                "provider": "noop",
            },
        )


class LocalQueueDispatchProvider:
    """Real queue dispatch provider backed by NAS-persisted local delivery state."""

    def __init__(self, transport: QueueDeliveryTransportService) -> None:
        self._transport = transport

    def dispatch_task(self, task: TaskRecord) -> QueueDispatchResult:
        parameters = task.parameters or {}
        queue_topic = str(parameters.get("queue_topic")) if parameters.get("queue_topic") is not None else None
        delivery = self._transport.publish_task(task, queue_topic=queue_topic)
        return QueueDispatchResult(
            accepted=True,
            status="queued",
            retryable=None,
            wait_reason=None,
            queue_topic=delivery.queue_topic,
            delivery_id=delivery.delivery_id,
            claim_lease_id=delivery.claim_lease_id,
            details={
                "dispatch_mode": parameters.get("dispatch_mode"),
                "provider": "local_queue_transport",
            },
        )
