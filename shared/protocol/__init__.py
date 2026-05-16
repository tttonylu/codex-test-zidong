"""Protocol payload definitions shared across the system."""

from .payloads import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)

__all__ = [
    "ActionResultPayload",
    "HeartbeatPayload",
    "InstanceSnapshotPayload",
    "ScriptRunPayload",
    "TaskAssignmentPayload",
    "TerminalRegistrationPayload",
]
