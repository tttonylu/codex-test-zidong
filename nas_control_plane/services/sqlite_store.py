"""SQLite-backed storage primitives for the NAS control plane."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class SqliteStateStore:
    """Owns a SQLite database file and ensures the schema exists."""

    LATEST_SCHEMA_VERSION = 3

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        """Return a SQLite connection with row access by column name."""

        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            self._ensure_migration_table(connection)
            current_version = self._current_schema_version(connection)
            for version, migration in _migrations():
                if version <= current_version:
                    continue
                migration(connection)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (?)
                    ON CONFLICT(version) DO NOTHING
                    """,
                    (version,),
                )

    def _ensure_migration_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY
            )
            """
        )

    def _current_schema_version(self, connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def _migrations():
    return [
        (1, _migration_001_initial_schema),
        (2, _migration_002_task_semantics),
        (3, _migration_003_task_events),
    ]


def _migration_001_initial_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS terminals (
            terminal_id TEXT PRIMARY KEY,
            hostname TEXT NOT NULL,
            operator_name TEXT NOT NULL,
            status TEXT NOT NULL,
            agent_version TEXT NOT NULL,
            last_seen_at TEXT,
            capabilities_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS instances (
            instance_id TEXT PRIMARY KEY,
            terminal_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            handle TEXT,
            runtime_status TEXT NOT NULL,
            window_id TEXT,
            remark TEXT,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            terminal_id TEXT NOT NULL,
            script_name TEXT NOT NULL,
            status TEXT NOT NULL,
            instance_id TEXT,
            priority INTEGER NOT NULL,
            parameters_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS logs (
            log_id TEXT PRIMARY KEY,
            terminal_id TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            emitted_at TEXT NOT NULL,
            task_id TEXT,
            run_id TEXT,
            details_json TEXT NOT NULL
        );
        """
    )


def _migration_002_task_semantics(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE tasks ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE tasks ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE tasks ADD COLUMN retryable INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE tasks ADD COLUMN final INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE tasks ADD COLUMN last_error_code TEXT;
        ALTER TABLE tasks ADD COLUMN last_error_message TEXT;
        ALTER TABLE tasks ADD COLUMN cancel_reason TEXT;
        """
    )

    rows = connection.execute(
        """
        SELECT task_id, status, parameters_json
        FROM tasks
        """
    ).fetchall()
    for row in rows:
        parameters = json.loads(str(row["parameters_json"]))
        status = str(row["status"])
        if parameters.get("max_attempts") is not None:
            max_attempts = max(1, int(parameters["max_attempts"]))
        elif parameters.get("retry_limit") is not None:
            max_attempts = max(1, int(parameters["retry_limit"]) + 1)
        else:
            max_attempts = 1

        retry_count = max(0, int(parameters.get("retry_count", 0)))
        attempt_count = retry_count + 1 if status in {"dispatched", "running", "completed", "failed", "cancelled"} else retry_count
        last_error_message = (
            str(parameters["last_error"])
            if parameters.get("last_error") is not None
            else None
        )
        cancel_reason = (
            str(parameters["cancel_reason"])
            if parameters.get("cancel_reason") is not None
            else None
        )
        retryable = status == "failed" and attempt_count < max_attempts
        final = status in {"completed", "cancelled"} or (status == "failed" and not retryable)

        connection.execute(
            """
            UPDATE tasks
            SET attempt_count = ?,
                max_attempts = ?,
                retryable = ?,
                final = ?,
                last_error_message = ?,
                cancel_reason = ?
            WHERE task_id = ?
            """,
            (
                attempt_count,
                max_attempts,
                1 if retryable else 0,
                1 if final else 0,
                last_error_message,
                cancel_reason,
                str(row["task_id"]),
            ),
        )


def _migration_003_task_events(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS task_events (
            event_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            terminal_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            emitted_at TEXT NOT NULL,
            run_id TEXT,
            message TEXT,
            details_json TEXT NOT NULL
        )
        """
    )
