"""Dispatch-mode helpers and provider boundaries for NAS task routing."""

from __future__ import annotations

from dataclasses import dataclass

from nas_control_plane.models import TaskRecord

CLAIM_HTTP_DISPATCH_MODE = "claim_http"
QUEUE_PULL_DISPATCH_MODE = "queue_pull"
SUPPORTED_DISPATCH_MODES = {CLAIM_HTTP_DISPATCH_MODE, QUEUE_PULL_DISPATCH_MODE}


@dataclass(frozen=True, slots=True)
class DispatchModeDescriptor:
    """Describes one dispatch mode boundary without binding to an implementation."""

    mode: str
    uses_http_claim: bool
    requires_queue_consumer: bool


def normalize_dispatch_mode(raw: str | None) -> str:
    """Return one supported dispatch mode or raise for unknown input."""

    mode = str(raw or CLAIM_HTTP_DISPATCH_MODE).strip() or CLAIM_HTTP_DISPATCH_MODE
    if mode not in SUPPORTED_DISPATCH_MODES:
        raise ValueError(f"unsupported dispatch_mode: {mode}")
    return mode


def dispatch_mode_descriptor(mode: str | None) -> DispatchModeDescriptor:
    """Return the provider boundary flags for one dispatch mode."""

    normalized = normalize_dispatch_mode(mode)
    if normalized == QUEUE_PULL_DISPATCH_MODE:
        return DispatchModeDescriptor(
            mode=normalized,
            uses_http_claim=False,
            requires_queue_consumer=True,
        )
    return DispatchModeDescriptor(
        mode=normalized,
        uses_http_claim=True,
        requires_queue_consumer=False,
    )


def task_dispatch_mode(record: TaskRecord) -> str:
    """Read the persisted dispatch mode from one task record."""

    parameters = record.parameters or {}
    return normalize_dispatch_mode(parameters.get("dispatch_mode"))


def task_uses_http_claim(record: TaskRecord) -> bool:
    """Return whether one task should be exposed to HTTP claim loops."""

    return dispatch_mode_descriptor(task_dispatch_mode(record)).uses_http_claim
