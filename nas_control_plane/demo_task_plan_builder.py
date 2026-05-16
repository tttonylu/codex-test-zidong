"""Verification script for standardized NAS-side action plan builders."""

from __future__ import annotations

import json

from nas_control_plane.services import (
    build_chat_action_plan,
    build_follow_action_plan,
    build_probe_action_plan,
)


def main() -> None:
    follow_plan = build_follow_action_plan(target_handle="builder_user", annotate_remark=True)
    chat_plan = build_chat_action_plan(target_handle="builder_user", annotate_remark=False)
    probe_plan = build_probe_action_plan(target_url="https://x.com/home", annotate_remark=True)

    print(
        json.dumps(
            {
                "follow_steps": [item["name"] for item in follow_plan],
                "chat_steps": [item["name"] for item in chat_plan],
                "probe_steps": [item["name"] for item in probe_plan],
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
