"""SQLite-backed repository implementations for NAS state."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from nas_control_plane.models import ActionLogRecord, InstanceRecord, TaskEventRecord, TaskRecord, TerminalRecord
from nas_control_plane.services.sqlite_store import SqliteStateStore


class SqliteTerminalStateRepository:
    """Reads and writes terminal and instance state from SQLite."""

    def __init__(self, store: SqliteStateStore) -> None:
        self._store = store

    def load_terminals(self) -> dict[str, TerminalRecord]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT * FROM terminals").fetchall()
        return {str(row["terminal_id"]): _terminal_from_row(row) for row in rows}

    def load_state(self) -> tuple[dict[str, TerminalRecord], dict[str, InstanceRecord]]:
        """Load terminal and instance state together."""

        return self.load_terminals(), self.load_instances()

    def save_terminals(self, records: dict[str, TerminalRecord]) -> None:
        with self._store.connect() as connection:
            _sync_records(
                connection=connection,
                table="terminals",
                key_column="terminal_id",
                record_ids=set(records.keys()),
            )
            connection.executemany(
                """
                INSERT INTO terminals (
                    terminal_id, hostname, operator_name, status, agent_version,
                    last_seen_at, capabilities_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(terminal_id) DO UPDATE SET
                    hostname = excluded.hostname,
                    operator_name = excluded.operator_name,
                    status = excluded.status,
                    agent_version = excluded.agent_version,
                    last_seen_at = excluded.last_seen_at,
                    capabilities_json = excluded.capabilities_json,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        record.terminal_id,
                        record.hostname,
                        record.operator_name,
                        record.status,
                        record.agent_version,
                        record.last_seen_at.isoformat() if record.last_seen_at else None,
                        json.dumps(record.capabilities, ensure_ascii=True),
                        json.dumps(record.metadata, ensure_ascii=True),
                    )
                    for record in records.values()
                ],
            )

    def upsert_terminal(self, record: TerminalRecord) -> None:
        """Insert or update one terminal record."""

        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO terminals (
                    terminal_id, hostname, operator_name, status, agent_version,
                    last_seen_at, capabilities_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(terminal_id) DO UPDATE SET
                    hostname = excluded.hostname,
                    operator_name = excluded.operator_name,
                    status = excluded.status,
                    agent_version = excluded.agent_version,
                    last_seen_at = excluded.last_seen_at,
                    capabilities_json = excluded.capabilities_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record.terminal_id,
                    record.hostname,
                    record.operator_name,
                    record.status,
                    record.agent_version,
                    record.last_seen_at.isoformat() if record.last_seen_at else None,
                    json.dumps(record.capabilities, ensure_ascii=True),
                    json.dumps(record.metadata, ensure_ascii=True),
                ),
            )

    def load_instances(self) -> dict[str, InstanceRecord]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT * FROM instances").fetchall()
        return {str(row["instance_id"]): _instance_from_row(row) for row in rows}

    def save_instances(self, records: dict[str, InstanceRecord]) -> None:
        with self._store.connect() as connection:
            _sync_records(
                connection=connection,
                table="instances",
                key_column="instance_id",
                record_ids=set(records.keys()),
            )
            connection.executemany(
                """
                INSERT INTO instances (
                    instance_id, terminal_id, profile_id, handle, runtime_status,
                    window_id, remark, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    profile_id = excluded.profile_id,
                    handle = excluded.handle,
                    runtime_status = excluded.runtime_status,
                    window_id = excluded.window_id,
                    remark = excluded.remark,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        record.instance_id,
                        record.terminal_id,
                        record.profile_id,
                        record.handle,
                        record.runtime_status,
                        record.window_id,
                        record.remark,
                        json.dumps(record.metadata, ensure_ascii=True),
                    )
                    for record in records.values()
                ],
            )

    def upsert_instance(self, record: InstanceRecord) -> None:
        """Insert or update one instance record."""

        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO instances (
                    instance_id, terminal_id, profile_id, handle, runtime_status,
                    window_id, remark, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    profile_id = excluded.profile_id,
                    handle = excluded.handle,
                    runtime_status = excluded.runtime_status,
                    window_id = excluded.window_id,
                    remark = excluded.remark,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record.instance_id,
                    record.terminal_id,
                    record.profile_id,
                    record.handle,
                    record.runtime_status,
                    record.window_id,
                    record.remark,
                    json.dumps(record.metadata, ensure_ascii=True),
                ),
            )

    def delete_instances_for_terminal_except(self, terminal_id: str, keep_instance_ids: set[str]) -> None:
        """Delete stale instances for one terminal while keeping the current scan set."""

        with self._store.connect() as connection:
            if keep_instance_ids:
                placeholders = ", ".join(["?"] * len(keep_instance_ids))
                connection.execute(
                    f"""
                    DELETE FROM instances
                    WHERE terminal_id = ?
                      AND instance_id NOT IN ({placeholders})
                    """,
                    [terminal_id, *sorted(keep_instance_ids)],
                )
            else:
                connection.execute(
                    "DELETE FROM instances WHERE terminal_id = ?",
                    (terminal_id,),
                )

    def save_state(
        self,
        terminals: dict[str, TerminalRecord],
        instances: dict[str, InstanceRecord],
    ) -> None:
        """Persist terminal and instance state in one transaction."""

        with self._store.connect() as connection:
            _sync_records(
                connection=connection,
                table="terminals",
                key_column="terminal_id",
                record_ids=set(terminals.keys()),
            )
            connection.executemany(
                """
                INSERT INTO terminals (
                    terminal_id, hostname, operator_name, status, agent_version,
                    last_seen_at, capabilities_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(terminal_id) DO UPDATE SET
                    hostname = excluded.hostname,
                    operator_name = excluded.operator_name,
                    status = excluded.status,
                    agent_version = excluded.agent_version,
                    last_seen_at = excluded.last_seen_at,
                    capabilities_json = excluded.capabilities_json,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        record.terminal_id,
                        record.hostname,
                        record.operator_name,
                        record.status,
                        record.agent_version,
                        record.last_seen_at.isoformat() if record.last_seen_at else None,
                        json.dumps(record.capabilities, ensure_ascii=True),
                        json.dumps(record.metadata, ensure_ascii=True),
                    )
                    for record in terminals.values()
                ],
            )
            _sync_records(
                connection=connection,
                table="instances",
                key_column="instance_id",
                record_ids=set(instances.keys()),
            )
            connection.executemany(
                """
                INSERT INTO instances (
                    instance_id, terminal_id, profile_id, handle, runtime_status,
                    window_id, remark, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    profile_id = excluded.profile_id,
                    handle = excluded.handle,
                    runtime_status = excluded.runtime_status,
                    window_id = excluded.window_id,
                    remark = excluded.remark,
                    metadata_json = excluded.metadata_json
                """,
                [
                    (
                        record.instance_id,
                        record.terminal_id,
                        record.profile_id,
                        record.handle,
                        record.runtime_status,
                        record.window_id,
                        record.remark,
                        json.dumps(record.metadata, ensure_ascii=True),
                    )
                    for record in instances.values()
                ],
            )


class SqliteTaskRepository:
    """Reads and writes task state from SQLite."""

    def __init__(self, store: SqliteStateStore) -> None:
        self._store = store

    def load_tasks(self) -> dict[str, TaskRecord]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT * FROM tasks").fetchall()
        return {str(row["task_id"]): _task_from_row(row) for row in rows}

    def save_tasks(self, records: dict[str, TaskRecord]) -> None:
        with self._store.connect() as connection:
            _sync_records(
                connection=connection,
                table="tasks",
                key_column="task_id",
                record_ids=set(records.keys()),
            )
            connection.executemany(
                """
                  INSERT INTO tasks (
                      task_id, terminal_id, script_name, status, instance_id,
                      priority, attempt_count, max_attempts, retryable, final,
                      last_error_code, last_error_message, cancel_reason,
                      parameters_json, created_at
                  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    script_name = excluded.script_name,
                    status = excluded.status,
                    instance_id = excluded.instance_id,
                    priority = excluded.priority,
                    attempt_count = excluded.attempt_count,
                    max_attempts = excluded.max_attempts,
                    retryable = excluded.retryable,
                    final = excluded.final,
                    last_error_code = excluded.last_error_code,
                    last_error_message = excluded.last_error_message,
                    cancel_reason = excluded.cancel_reason,
                    parameters_json = excluded.parameters_json,
                    created_at = excluded.created_at
                """,
                [
                    (
                        record.task_id,
                        record.terminal_id,
                        record.script_name,
                        record.status,
                        record.instance_id,
                        record.priority,
                        record.attempt_count,
                        record.max_attempts,
                        1 if record.retryable else 0,
                        1 if record.final else 0,
                        record.last_error_code,
                        record.last_error_message,
                        record.cancel_reason,
                        json.dumps(record.parameters, ensure_ascii=True),
                        record.created_at.isoformat(),
                    )
                    for record in records.values()
                ],
            )

    def upsert_task(self, record: TaskRecord) -> None:
        """Insert or update one task record."""

        with self._store.connect() as connection:
            connection.execute(
                """
                  INSERT INTO tasks (
                      task_id, terminal_id, script_name, status, instance_id,
                      priority, attempt_count, max_attempts, retryable, final,
                      last_error_code, last_error_message, cancel_reason,
                      parameters_json, created_at
                  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    script_name = excluded.script_name,
                    status = excluded.status,
                    instance_id = excluded.instance_id,
                    priority = excluded.priority,
                    attempt_count = excluded.attempt_count,
                    max_attempts = excluded.max_attempts,
                    retryable = excluded.retryable,
                    final = excluded.final,
                    last_error_code = excluded.last_error_code,
                    last_error_message = excluded.last_error_message,
                    cancel_reason = excluded.cancel_reason,
                    parameters_json = excluded.parameters_json,
                    created_at = excluded.created_at
                """,
                (
                    record.task_id,
                    record.terminal_id,
                    record.script_name,
                    record.status,
                    record.instance_id,
                    record.priority,
                    record.attempt_count,
                    record.max_attempts,
                    1 if record.retryable else 0,
                    1 if record.final else 0,
                    record.last_error_code,
                    record.last_error_message,
                    record.cancel_reason,
                    json.dumps(record.parameters, ensure_ascii=True),
                    record.created_at.isoformat(),
                ),
            )


class SqliteAuditLogRepository:
    """Reads and writes audit log state from SQLite."""

    def __init__(self, store: SqliteStateStore) -> None:
        self._store = store

    def load_logs(self) -> list[ActionLogRecord]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT * FROM logs ORDER BY emitted_at").fetchall()
        return [_log_from_row(row) for row in rows]

    def save_logs(self, records: list[ActionLogRecord]) -> None:
        with self._store.connect() as connection:
            _sync_records(
                connection=connection,
                table="logs",
                key_column="log_id",
                record_ids={record.log_id for record in records},
            )
            connection.executemany(
                """
                INSERT INTO logs (
                    log_id, terminal_id, level, message, emitted_at,
                    task_id, run_id, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    level = excluded.level,
                    message = excluded.message,
                    emitted_at = excluded.emitted_at,
                    task_id = excluded.task_id,
                    run_id = excluded.run_id,
                    details_json = excluded.details_json
                """,
                [
                    (
                        record.log_id,
                        record.terminal_id,
                        record.level,
                        record.message,
                        record.emitted_at.isoformat(),
                        record.task_id,
                        record.run_id,
                        json.dumps(record.details, ensure_ascii=True),
                    )
                    for record in records
                ],
            )

    def append_log(self, record: ActionLogRecord) -> None:
        """Append one log record, or update it if the id already exists."""

        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO logs (
                    log_id, terminal_id, level, message, emitted_at,
                    task_id, run_id, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    terminal_id = excluded.terminal_id,
                    level = excluded.level,
                    message = excluded.message,
                    emitted_at = excluded.emitted_at,
                    task_id = excluded.task_id,
                    run_id = excluded.run_id,
                    details_json = excluded.details_json
                """,
                (
                    record.log_id,
                    record.terminal_id,
                    record.level,
                    record.message,
                    record.emitted_at.isoformat(),
                    record.task_id,
                    record.run_id,
                    json.dumps(record.details, ensure_ascii=True),
                ),
            )


class SqliteTaskEventRepository:
    """Reads and writes task event timeline state from SQLite."""

    def __init__(self, store: SqliteStateStore) -> None:
        self._store = store

    def load_events(self) -> list[TaskEventRecord]:
        with self._store.connect() as connection:
            rows = connection.execute("SELECT * FROM task_events ORDER BY emitted_at, event_id").fetchall()
        return [_task_event_from_row(row) for row in rows]

    def append_event(self, record: TaskEventRecord) -> None:
        """Append one task event record."""

        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO task_events (
                    event_id, task_id, terminal_id, event_type, status,
                    emitted_at, run_id, message, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    task_id = excluded.task_id,
                    terminal_id = excluded.terminal_id,
                    event_type = excluded.event_type,
                    status = excluded.status,
                    emitted_at = excluded.emitted_at,
                    run_id = excluded.run_id,
                    message = excluded.message,
                    details_json = excluded.details_json
                """,
                (
                    record.event_id,
                    record.task_id,
                    record.terminal_id,
                    record.event_type,
                    record.status,
                    record.emitted_at.isoformat(),
                    record.run_id,
                    record.message,
                    json.dumps(record.details, ensure_ascii=True),
                ),
            )


def _sync_records(
    *,
    connection: Any,
    table: str,
    key_column: str,
    record_ids: set[str],
) -> None:
    existing_rows = connection.execute(f"SELECT {key_column} FROM {table}").fetchall()
    existing_ids = {str(row[0]) for row in existing_rows}
    stale_ids = sorted(existing_ids - record_ids)
    if not stale_ids:
        return

    placeholders = ", ".join(["?"] * len(stale_ids))
    connection.execute(
        f"DELETE FROM {table} WHERE {key_column} IN ({placeholders})",
        stale_ids,
    )


def _terminal_from_row(row: object) -> TerminalRecord:
    return TerminalRecord(
        terminal_id=str(row["terminal_id"]),
        hostname=str(row["hostname"]),
        operator_name=str(row["operator_name"]),
        status=str(row["status"]),
        agent_version=str(row["agent_version"]),
        last_seen_at=datetime.fromisoformat(str(row["last_seen_at"])) if row["last_seen_at"] else None,
        capabilities=list(json.loads(str(row["capabilities_json"]))),
        metadata=dict(json.loads(str(row["metadata_json"]))),
    )


def _instance_from_row(row: object) -> InstanceRecord:
    return InstanceRecord(
        instance_id=str(row["instance_id"]),
        terminal_id=str(row["terminal_id"]),
        profile_id=str(row["profile_id"]),
        handle=str(row["handle"]) if row["handle"] is not None else None,
        runtime_status=str(row["runtime_status"]),
        window_id=str(row["window_id"]) if row["window_id"] is not None else None,
        remark=str(row["remark"]) if row["remark"] is not None else None,
        metadata=dict(json.loads(str(row["metadata_json"]))),
    )


def _task_from_row(row: object) -> TaskRecord:
    parameters = dict(json.loads(str(row["parameters_json"])))
    return TaskRecord(
        task_id=str(row["task_id"]),
        terminal_id=str(row["terminal_id"]),
        script_name=str(row["script_name"]),
        status=str(row["status"]),
        instance_id=str(row["instance_id"]) if row["instance_id"] is not None else None,
        priority=int(row["priority"]),
        attempt_count=int(row["attempt_count"]) if row["attempt_count"] is not None else 0,
        max_attempts=max(1, int(row["max_attempts"])) if row["max_attempts"] is not None else 1,
        retryable=bool(row["retryable"]) if row["retryable"] is not None else False,
        final=bool(row["final"]) if row["final"] is not None else False,
        last_error_code=str(row["last_error_code"]) if row["last_error_code"] is not None else None,
        last_error_message=(
            str(row["last_error_message"])
            if row["last_error_message"] is not None
            else str(parameters["last_error"])
            if parameters.get("last_error") is not None
            else None
        ),
        cancel_reason=(
            str(row["cancel_reason"])
            if row["cancel_reason"] is not None
            else str(parameters["cancel_reason"])
            if parameters.get("cancel_reason") is not None
            else None
        ),
        parameters=parameters,
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _log_from_row(row: object) -> ActionLogRecord:
    return ActionLogRecord(
        log_id=str(row["log_id"]),
        terminal_id=str(row["terminal_id"]),
        level=str(row["level"]),
        message=str(row["message"]),
        emitted_at=datetime.fromisoformat(str(row["emitted_at"])),
        task_id=str(row["task_id"]) if row["task_id"] is not None else None,
        run_id=str(row["run_id"]) if row["run_id"] is not None else None,
        details=dict(json.loads(str(row["details_json"]))),
    )


def _task_event_from_row(row: object) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=str(row["event_id"]),
        task_id=str(row["task_id"]),
        terminal_id=str(row["terminal_id"]),
        event_type=str(row["event_type"]),
        status=str(row["status"]),
        emitted_at=datetime.fromisoformat(str(row["emitted_at"])),
        run_id=str(row["run_id"]) if row["run_id"] is not None else None,
        message=str(row["message"]) if row["message"] is not None else None,
        details=dict(json.loads(str(row["details_json"]))),
    )
