"""Verification script for SQLite schema migration behavior."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from nas_control_plane.services import SqliteStateStore


def main() -> None:
    db_path = Path("nas_control_plane/state.migrations.demo.sqlite3")
    if db_path.exists():
        db_path.unlink()

    try:
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY
                )
                """
            )

        store = SqliteStateStore(db_path)
        with store.connect() as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            versions = [
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]

        print(
            json.dumps(
                {
                    "latest_version": SqliteStateStore.LATEST_SCHEMA_VERSION,
                    "applied_versions": versions,
                    "tables": tables,
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
