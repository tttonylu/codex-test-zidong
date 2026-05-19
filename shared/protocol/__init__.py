"""Protocol payload definitions shared across the system."""

from .payloads import (
    ActionResultPayload,
    HeartbeatPayload,
    InstanceSnapshotPayload,
    PluginDispatchRequestPayload,
    PluginTaskPullResponsePayload,
    ScriptRunPayload,
    TaskAssignmentPayload,
    TerminalRegistrationPayload,
)

__all__ = [
    "ActionResultPayload",
    "HeartbeatPayload",
    "InstanceSnapshotPayload",
    "PluginDispatchRequestPayload",
    "PluginTaskPullResponsePayload",
    "ScriptRunPayload",
    "TaskAssignmentPayload",
    "TerminalRegistrationPayload",
]
