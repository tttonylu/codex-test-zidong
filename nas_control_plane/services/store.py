"""Simple JSON-backed state store for the NAS control plane."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any


class JsonStateStore:
    """Persists NAS state collections into a single JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._state = self._read_from_disk()

    def load(self) -> dict[str, Any]:
        """Return a copy of the full in-memory state document."""

        with self._lock:
            return copy.deepcopy(self._state)

    def save(self, state: dict[str, Any]) -> None:
        """Replace the full in-memory state document and persist it."""

        with self._lock:
            self._state = copy.deepcopy(state)
            self._write_to_disk()

    def read_section(self, key: str) -> Any:
        """Return a copy of one top-level state section."""

        with self._lock:
            return copy.deepcopy(self._state.get(key, self._default_state()[key]))

    def write_section(self, key: str, value: Any) -> None:
        """Replace one top-level state section and persist the full document."""

        with self._lock:
            self._state[key] = copy.deepcopy(value)
            self._write_to_disk()

    def _default_state(self) -> dict[str, Any]:
        return {
            "terminals": {},
            "instances": {},
            "tasks": {},
            "logs": [],
        }

    def _read_from_disk(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._default_state()

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        state = self._default_state()
        state.update(raw)
        return state

    def _write_to_disk(self) -> None:
        self._path.write_text(
            json.dumps(_jsonify(self._state), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def _jsonify(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return _jsonify(asdict(value))
    return value
