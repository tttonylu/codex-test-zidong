"""Verification script for section-level JSON store updates."""

from __future__ import annotations

import json
from pathlib import Path

from nas_control_plane.services import JsonStateStore


def main() -> None:
    path = Path("nas_control_plane/state.sections.demo.json")
    if path.exists():
        path.unlink()

    try:
        store = JsonStateStore(path)
        store.write_section("terminals", {"terminal-a": {"status": "online"}})
        store.write_section("tasks", {"task-a": {"status": "queued"}})
        store.write_section("logs", [{"log_id": "log-a", "message": "ok"}])

        on_disk = json.loads(path.read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "terminals": on_disk.get("terminals"),
                    "tasks": on_disk.get("tasks"),
                    "logs": on_disk.get("logs"),
                    "keys": sorted(on_disk.keys()),
                },
                separators=(",", ":"),
            )
        )
    finally:
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    main()
