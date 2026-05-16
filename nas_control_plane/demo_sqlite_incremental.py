"""Verification script for SQLite incremental repository updates."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.models import ActionLogRecord, InstanceRecord, TaskRecord, TerminalRecord
from nas_control_plane.services import (
    SqliteAuditLogRepository,
    SqliteStateStore,
    SqliteTaskRepository,
    SqliteTerminalStateRepository,
)


def main() -> None:
    db_path = Path("nas_control_plane/state.incremental.demo.sqlite3")
    if db_path.exists():
        db_path.unlink()

    try:
        store = SqliteStateStore(db_path)
        terminal_repo = SqliteTerminalStateRepository(store)
        task_repo = SqliteTaskRepository(store)
        log_repo = SqliteAuditLogRepository(store)

        terminal_repo.save_state(
            terminals={
                "terminal-a": TerminalRecord(
                    terminal_id="terminal-a",
                    hostname="host-a",
                    operator_name="alice",
                    status="online",
                    agent_version="0.1.0",
                    last_seen_at=datetime(2026, 5, 16, 10, 0, 0),
                    capabilities=["scan"],
                    metadata={"zone": "a"},
                ),
                "terminal-b": TerminalRecord(
                    terminal_id="terminal-b",
                    hostname="host-b",
                    operator_name="bob",
                    status="idle",
                    agent_version="0.1.0",
                    last_seen_at=datetime(2026, 5, 16, 10, 5, 0),
                    capabilities=["execute"],
                    metadata={"zone": "b"},
                ),
            },
            instances={
                "instance-a": InstanceRecord(
                    instance_id="instance-a",
                    terminal_id="terminal-a",
                    profile_id="@a#bitbrowser",
                    handle="user_a",
                    runtime_status="running",
                    window_id="win-a",
                    remark="user_a",
                    metadata={"seq": 1},
                ),
                "instance-b": InstanceRecord(
                    instance_id="instance-b",
                    terminal_id="terminal-b",
                    profile_id="@b#bitbrowser",
                    handle="user_b",
                    runtime_status="idle",
                    window_id="win-b",
                    remark="user_b",
                    metadata={"seq": 2},
                ),
            },
        )
        task_repo.save_tasks(
            {
                "task-a": TaskRecord(
                    task_id="task-a",
                    terminal_id="terminal-a",
                    script_name="follow",
                    status="queued",
                    instance_id="instance-a",
                    priority=1,
                    parameters={"target_handle": "user_a"},
                    created_at=datetime(2026, 5, 16, 11, 0, 0),
                ),
                "task-b": TaskRecord(
                    task_id="task-b",
                    terminal_id="terminal-b",
                    script_name="chat",
                    status="queued",
                    instance_id="instance-b",
                    priority=2,
                    parameters={"target_handle": "user_b"},
                    created_at=datetime(2026, 5, 16, 11, 5, 0),
                ),
            }
        )
        log_repo.save_logs(
            [
                ActionLogRecord(
                    log_id="log-a",
                    terminal_id="terminal-a",
                    level="info",
                    message="task a created",
                    emitted_at=datetime(2026, 5, 16, 11, 0, 1),
                    task_id="task-a",
                    run_id="run-a",
                    details={"state": "queued"},
                ),
                ActionLogRecord(
                    log_id="log-b",
                    terminal_id="terminal-b",
                    level="info",
                    message="task b created",
                    emitted_at=datetime(2026, 5, 16, 11, 5, 1),
                    task_id="task-b",
                    run_id="run-b",
                    details={"state": "queued"},
                ),
            ]
        )

        terminal_repo.save_state(
            terminals={
                "terminal-a": TerminalRecord(
                    terminal_id="terminal-a",
                    hostname="host-a-updated",
                    operator_name="alice",
                    status="online",
                    agent_version="0.2.0",
                    last_seen_at=datetime(2026, 5, 16, 12, 0, 0),
                    capabilities=["scan", "execute"],
                    metadata={"zone": "a", "rev": 2},
                ),
            },
            instances={
                "instance-a": InstanceRecord(
                    instance_id="instance-a",
                    terminal_id="terminal-a",
                    profile_id="@a#bitbrowser",
                    handle="user_a",
                    runtime_status="running",
                    window_id="win-a-2",
                    remark="user_a",
                    metadata={"seq": 10},
                ),
            },
        )
        task_repo.save_tasks(
            {
                "task-a": TaskRecord(
                    task_id="task-a",
                    terminal_id="terminal-a",
                    script_name="follow",
                    status="completed",
                    instance_id="instance-a",
                    priority=1,
                    parameters={"target_handle": "user_a", "result": "done"},
                    created_at=datetime(2026, 5, 16, 11, 0, 0),
                ),
            }
        )
        log_repo.save_logs(
            [
                ActionLogRecord(
                    log_id="log-a",
                    terminal_id="terminal-a",
                    level="info",
                    message="task a completed",
                    emitted_at=datetime(2026, 5, 16, 12, 0, 1),
                    task_id="task-a",
                    run_id="run-a",
                    details={"state": "completed"},
                )
            ]
        )

        terminals, instances = terminal_repo.load_state()
        tasks = task_repo.load_tasks()
        logs = log_repo.load_logs()

        print(
            json.dumps(
                {
                    "terminals": sorted(terminals.keys()),
                    "instances": sorted(instances.keys()),
                    "tasks": sorted(tasks.keys()),
                    "logs": [log.log_id for log in logs],
                    "terminal_a_hostname": terminals["terminal-a"].hostname,
                    "task_a_status": tasks["task-a"].status,
                    "log_a_message": logs[0].message,
                },
                separators=(",", ":"),
            )
        )
    finally:
        if db_path.exists():
            time.sleep(0.2)
            try:
                db_path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
