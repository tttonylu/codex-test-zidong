"""Helpers for building standardized task action plans."""

from __future__ import annotations

from typing import Any


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
