"""Repository layer for terminal-local runtime sections."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.protocol import ActionResultPayload, ScriptRunPayload, TaskAssignmentPayload
from terminal_agent.models import LocalTask, ScriptSlot
from terminal_agent.runtime.store import JsonStateStore


class TerminalRuntimeRepository:
    """Reads and writes terminal-local slots and accepted task state."""

    def __init__(self, store: JsonStateStore) -> None:
        self._store = store

    def load_slots(self) -> dict[str, ScriptSlot]:
        return {
            slot_id: _slot_from_dict(item)
            for slot_id, item in self._store.read_section("slots").items()
        }

    def save_slots(self, records: dict[str, ScriptSlot]) -> None:
        self._store.write_section(
            "slots",
            {slot_id: _slot_to_dict(item) for slot_id, item in records.items()},
        )

    def load_tasks(self) -> dict[str, LocalTask]:
        return {
            task_id: _task_from_dict(item)
            for task_id, item in self._store.read_section("tasks").items()
        }

    def save_tasks(self, records: dict[str, LocalTask]) -> None:
        self._store.write_section(
            "tasks",
            {task_id: _task_to_dict(item) for task_id, item in records.items()},
        )

    def load_runtime(self) -> dict[str, Any]:
        return dict(self._store.read_section("runtime"))

    def save_runtime(self, record: dict[str, Any]) -> None:
        self._store.write_section("runtime", dict(record))

    def load_result_outbox(self) -> list[ActionResultPayload]:
        return [_result_from_dict(item) for item in self._store.read_section("result_outbox")]

    def save_result_outbox(self, items: list[ActionResultPayload]) -> None:
        self._store.write_section("result_outbox", [item.to_dict() for item in items])


def _task_to_dict(task: LocalTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "script_name": task.script_name,
        "status": task.status,
        "instance_id": task.instance_id,
        "priority": task.priority,
        "retry_limit": task.retry_limit,
        "close_after_actions": task.close_after_actions,
        "requested_by": task.requested_by,
        "parameters": dict(task.parameters),
        "received_at": task.received_at.isoformat(),
    }


def _task_from_dict(payload: dict[str, Any]) -> LocalTask:
    return LocalTask(
        task_id=str(payload["task_id"]),
        script_name=str(payload["script_name"]),
        status=str(payload["status"]),
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        priority=int(payload.get("priority", 0)),
        retry_limit=int(payload.get("retry_limit", 0)),
        close_after_actions=bool(payload.get("close_after_actions", False)),
        requested_by=str(payload["requested_by"]) if payload.get("requested_by") is not None else None,
        parameters=dict(payload.get("parameters", {})),
        received_at=datetime.fromisoformat(str(payload["received_at"])),
    )


def _slot_to_dict(slot: ScriptSlot) -> dict[str, Any]:
    return {
        "slot_id": slot.slot_id,
        "status": slot.status,
        "script_name": slot.script_name,
        "bound_instance_id": slot.bound_instance_id,
        "run_id": slot.run_id,
        "task_id": slot.task_id,
        "assignment": slot.assignment.to_dict() if slot.assignment is not None else None,
        "run": slot.run.to_dict() if slot.run is not None else None,
        "assigned_at": slot.assigned_at.isoformat() if slot.assigned_at else None,
        "started_at": slot.started_at.isoformat() if slot.started_at else None,
        "finished_at": slot.finished_at.isoformat() if slot.finished_at else None,
        "metadata": dict(slot.metadata),
    }


def _slot_from_dict(payload: dict[str, Any]) -> ScriptSlot:
    return ScriptSlot(
        slot_id=str(payload["slot_id"]),
        status=str(payload["status"]),
        script_name=str(payload["script_name"]) if payload.get("script_name") is not None else None,
        bound_instance_id=str(payload["bound_instance_id"]) if payload.get("bound_instance_id") is not None else None,
        run_id=str(payload["run_id"]) if payload.get("run_id") is not None else None,
        task_id=str(payload["task_id"]) if payload.get("task_id") is not None else None,
        assignment=_assignment_from_dict(payload.get("assignment")),
        run=_run_from_dict(payload.get("run")),
        assigned_at=datetime.fromisoformat(str(payload["assigned_at"])) if payload.get("assigned_at") else None,
        started_at=datetime.fromisoformat(str(payload["started_at"])) if payload.get("started_at") else None,
        finished_at=datetime.fromisoformat(str(payload["finished_at"])) if payload.get("finished_at") else None,
        metadata=dict(payload.get("metadata", {})),
    )


def _assignment_from_dict(payload: dict[str, Any] | None) -> TaskAssignmentPayload | None:
    if payload is None:
        return None
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


def _run_from_dict(payload: dict[str, Any] | None) -> ScriptRunPayload | None:
    if payload is None:
        return None
    return ScriptRunPayload(
        run_id=str(payload["run_id"]),
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        script_name=str(payload["script_name"]),
        status=str(payload["status"]),
        started_at=datetime.fromisoformat(str(payload["started_at"])) if payload.get("started_at") else None,
        finished_at=datetime.fromisoformat(str(payload["finished_at"])) if payload.get("finished_at") else None,
        metadata=dict(payload.get("metadata", {})),
        step_count=int(payload.get("step_count", 0)),
        error_code=str(payload["error_code"]) if payload.get("error_code") is not None else None,
        error_message=str(payload["error_message"]) if payload.get("error_message") is not None else None,
        retryable=payload.get("retryable"),
        final=payload.get("final"),
    )


def _result_from_dict(payload: dict[str, Any]) -> ActionResultPayload:
    return ActionResultPayload(
        run_id=str(payload["run_id"]),
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        status=str(payload["status"]),
        summary=str(payload["summary"]),
        error_code=str(payload["error_code"]) if payload.get("error_code") is not None else None,
        error_message=str(payload["error_message"]) if payload.get("error_message") is not None else None,
        retryable=payload.get("retryable"),
        final=payload.get("final"),
        details=dict(payload.get("details", {})),
        emitted_at=datetime.fromisoformat(str(payload["emitted_at"])),
        delivery_id=str(payload["delivery_id"]) if payload.get("delivery_id") is not None else None,
        claim_lease_id=str(payload["claim_lease_id"]) if payload.get("claim_lease_id") is not None else None,
    )
