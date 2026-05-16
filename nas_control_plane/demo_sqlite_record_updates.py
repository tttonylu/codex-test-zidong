"""Verification script for record-level SQLite persistence paths."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from nas_control_plane.services import (
    AuditService,
    SqliteAuditLogRepository,
    SqliteStateStore,
    SqliteTaskRepository,
    SqliteTerminalStateRepository,
    TaskDispatchService,
    TerminalRegistryService,
)
from shared.protocol import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)


def main() -> None:
    db_path = Path("nas_control_plane/state.record-updates.demo.sqlite3")
    if db_path.exists():
        db_path.unlink()

    try:
        store = SqliteStateStore(db_path)
        registry = TerminalRegistryService(repository=SqliteTerminalStateRepository(store))
        tasks = TaskDispatchService(repository=SqliteTaskRepository(store))
        audit = AuditService(repository=SqliteAuditLogRepository(store))

        registry.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-record-1",
                hostname="host-record-1",
                operator_name="alice",
                agent_version="0.1.0",
                capabilities=["scan"],
                metadata={"zone": "a"},
            )
        )
        registry.record_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-record-1",
                reported_at=_dt("2026-05-16T12:00:00"),
                status="online",
                active_instance_count=2,
                queued_task_count=1,
                metadata={"load": "low"},
            )
        )
        registry.sync_instances(
            "terminal-record-1",
            [
                InstanceSnapshotPayload(
                    terminal_id="terminal-record-1",
                    instance_id="instance-record-1",
                    profile_id="@user1#bitbrowser",
                    handle="user1",
                    runtime_status="running",
                    window_id="win-1",
                    remark="user1",
                    metadata={"seq": 1},
                ),
                InstanceSnapshotPayload(
                    terminal_id="terminal-record-1",
                    instance_id="instance-record-2",
                    profile_id="@user2#bitbrowser",
                    handle="user2",
                    runtime_status="idle",
                    window_id="win-2",
                    remark="user2",
                    metadata={"seq": 2},
                ),
            ],
        )
        registry.sync_instances(
            "terminal-record-1",
            [
                InstanceSnapshotPayload(
                    terminal_id="terminal-record-1",
                    instance_id="instance-record-1",
                    profile_id="@user1#bitbrowser",
                    handle="user1",
                    runtime_status="running",
                    window_id="win-1b",
                    remark="user1",
                    metadata={"seq": 10},
                )
            ],
        )

        tasks.create_task(
            TaskAssignmentPayload(
                task_id="task-record-1",
                terminal_id="terminal-record-1",
                instance_id="instance-record-1",
                script_name="follow",
                parameters={"target_handle": "user1"},
                priority=1,
            )
        )
        claimed = tasks.claim_tasks("terminal-record-1")
        tasks.mark_running(
            ScriptRunPayload(
                run_id="run-task-record-1",
                task_id="task-record-1",
                terminal_id="terminal-record-1",
                instance_id="instance-record-1",
                script_name="follow",
                status="running",
                started_at=_dt("2026-05-16T12:05:00"),
            )
        )
        result = ActionResultPayload(
            run_id="run-task-record-1",
            task_id="task-record-1",
            terminal_id="terminal-record-1",
            status="completed",
            summary="follow executed",
            details={"result": "ok"},
            emitted_at=_dt("2026-05-16T12:06:00"),
        )
        tasks.record_result(result)
        audit.record_action_result(result)

        with sqlite3.connect(db_path) as connection:
            terminal_rows = connection.execute("SELECT COUNT(*) FROM terminals").fetchone()[0]
            instance_rows = connection.execute("SELECT COUNT(*) FROM instances").fetchone()[0]
            task_rows = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            log_rows = connection.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            remaining_instances = [
                row[0]
                for row in connection.execute("SELECT instance_id FROM instances ORDER BY instance_id").fetchall()
            ]
            task_status = connection.execute(
                "SELECT status FROM tasks WHERE task_id = ?",
                ("task-record-1",),
            ).fetchone()[0]
            terminal_status = connection.execute(
                "SELECT status FROM terminals WHERE terminal_id = ?",
                ("terminal-record-1",),
            ).fetchone()[0]

        print(
            json.dumps(
                {
                    "claimed_count": len(claimed),
                    "terminal_rows": terminal_rows,
                    "instance_rows": instance_rows,
                    "task_rows": task_rows,
                    "log_rows": log_rows,
                    "remaining_instances": remaining_instances,
                    "task_status": task_status,
                    "terminal_status": terminal_status,
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


def _dt(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


if __name__ == "__main__":
    main()
