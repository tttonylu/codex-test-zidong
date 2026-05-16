"""Helpers for building standardized task action plans."""

from __future__ import annotations

from typing import Any

from shared.protocol import TaskAssignmentPayload


def build_follow_action_plan(
    *,
    target_handle: str,
    annotate_remark: bool = False,
) -> list[dict[str, Any]]:
    """Build a normalized action plan for a follow task."""

    plan: list[dict[str, Any]] = [
        {
            "name": "navigate_profile",
            "kind": "navigate",
            "params": {"target_url": f"https://x.com/{target_handle}", "queue": True},
        }
    ]
    if annotate_remark:
        plan.append(
            {
                "name": "annotate_follow_target",
                "kind": "annotate",
                "params": {"remark": f"follow:{target_handle}"},
            }
        )
    return plan


def build_chat_action_plan(
    *,
    target_handle: str,
    annotate_remark: bool = False,
) -> list[dict[str, Any]]:
    """Build a normalized action plan for a chat task."""

    plan: list[dict[str, Any]] = [
        {
            "name": "navigate_compose",
            "kind": "navigate",
            "params": {"target_url": f"https://x.com/messages/compose?recipient_id={target_handle}", "queue": True},
        }
    ]
    if annotate_remark:
        plan.append(
            {
                "name": "annotate_chat_target",
                "kind": "annotate",
                "params": {"remark": f"chat:{target_handle}"},
            }
        )
    return plan


def build_probe_action_plan(
    *,
    target_url: str,
    annotate_remark: bool = False,
) -> list[dict[str, Any]]:
    """Build a normalized action plan for a probe task."""

    plan: list[dict[str, Any]] = [
        {
            "name": "navigate_probe_target",
            "kind": "navigate",
            "params": {"target_url": target_url, "queue": True},
        }
    ]
    if annotate_remark:
        plan.append(
            {
                "name": "annotate_probe_target",
                "kind": "annotate",
                "params": {"remark": f"probe:{target_url}"},
            }
        )
    return plan


def build_follow_task_payload(
    *,
    task_id: str,
    terminal_id: str,
    target_handle: str,
    instance_id: str | None = None,
    priority: int = 0,
    retry_limit: int = 0,
    annotate_remark: bool = False,
) -> TaskAssignmentPayload:
    """Build a standardized follow task payload."""

    return TaskAssignmentPayload(
        task_id=task_id,
        terminal_id=terminal_id,
        instance_id=instance_id,
        script_name="follow",
        parameters={
            "target_handle": target_handle,
            "retry_limit": retry_limit,
            "annotate_remark": annotate_remark,
            "action_plan": build_follow_action_plan(
                target_handle=target_handle,
                annotate_remark=annotate_remark,
            ),
        },
        priority=priority,
    )


def build_chat_task_payload(
    *,
    task_id: str,
    terminal_id: str,
    target_handle: str,
    instance_id: str | None = None,
    priority: int = 0,
    retry_limit: int = 0,
    annotate_remark: bool = False,
) -> TaskAssignmentPayload:
    """Build a standardized chat task payload."""

    return TaskAssignmentPayload(
        task_id=task_id,
        terminal_id=terminal_id,
        instance_id=instance_id,
        script_name="chat",
        parameters={
            "target_handle": target_handle,
            "retry_limit": retry_limit,
            "annotate_remark": annotate_remark,
            "action_plan": build_chat_action_plan(
                target_handle=target_handle,
                annotate_remark=annotate_remark,
            ),
        },
        priority=priority,
    )


def build_probe_task_payload(
    *,
    task_id: str,
    terminal_id: str,
    target_url: str,
    instance_id: str | None = None,
    priority: int = 0,
    retry_limit: int = 0,
    annotate_remark: bool = False,
) -> TaskAssignmentPayload:
    """Build a standardized probe task payload."""

    return TaskAssignmentPayload(
        task_id=task_id,
        terminal_id=terminal_id,
        instance_id=instance_id,
        script_name="probe",
        parameters={
            "target_url": target_url,
            "retry_limit": retry_limit,
            "annotate_remark": annotate_remark,
            "action_plan": build_probe_action_plan(
                target_url=target_url,
                annotate_remark=annotate_remark,
            ),
        },
        priority=priority,
    )
