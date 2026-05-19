"""Task-source boundaries for terminal-side task intake."""

from __future__ import annotations

from typing import Protocol

from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import NasControlPlaneClient
from terminal_agent.runtime.queue_claim import NoopQueueClaimProvider, QueueClaimProvider
from terminal_agent.runtime.terminal_runtime import TerminalRuntime


class TaskSource(Protocol):
    """Provides one batch of task assignments for a terminal runtime."""

    def claim(self, runtime: TerminalRuntime) -> list[TaskAssignmentPayload]:
        """Return the next batch of assignments available for execution."""


class HttpClaimTaskSource:
    """Default source backed by NAS `/tasks/claim` HTTP polling."""

    def __init__(self, nas_client: NasControlPlaneClient) -> None:
        self._nas_client = nas_client

    def claim(self, runtime: TerminalRuntime) -> list[TaskAssignmentPayload]:
        runtime.clear_runtime_metadata_keys(["task_source_queue_topic", "task_source_details"])
        runtime.merge_runtime_metadata(
            {
                "task_source_mode": "claim_http",
                "task_source_status": "active",
            }
        )
        response = self._nas_client.claim_tasks(
            runtime.registration_payload().terminal_id,
            max_tasks=runtime.claim_capacity(),
            blocked_instance_ids=runtime.blocked_instance_ids(),
        )
        return [_task_from_dict(item) for item in response.get("items", [])]


class QueuePullTaskSource:
    """Placeholder source for a future queue-backed pull consumer."""

    def __init__(
        self,
        queue_topic: str | None = None,
        provider: QueueClaimProvider | None = None,
    ) -> None:
        self._queue_topic = queue_topic
        self._provider = provider or NoopQueueClaimProvider()

    @property
    def provider(self) -> QueueClaimProvider:
        return self._provider

    def claim(self, runtime: TerminalRuntime) -> list[TaskAssignmentPayload]:
        result = self._provider.claim(
            terminal_id=runtime.registration_payload().terminal_id,
            max_tasks=runtime.claim_capacity(),
            queue_topic=self._queue_topic,
        )
        runtime.merge_runtime_metadata(
            {
                "task_source_mode": "queue_pull",
                "task_source_queue_topic": result.queue_topic or self._queue_topic,
                "task_source_status": result.status,
                "task_source_details": dict(result.details),
            }
        )
        return list(result.assignments)


def _task_from_dict(payload: dict[str, object]) -> TaskAssignmentPayload:
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
        dispatch_mode=str(payload.get("dispatch_mode", "claim_http")),
        queue_topic=str(payload["queue_topic"]) if payload.get("queue_topic") is not None else None,
        delivery_id=str(payload["delivery_id"]) if payload.get("delivery_id") is not None else None,
        claim_lease_id=str(payload["claim_lease_id"]) if payload.get("claim_lease_id") is not None else None,
    )
