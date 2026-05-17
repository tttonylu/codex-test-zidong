"""Recovery policy helpers for task failure handling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    """Normalized handling policy for one failure code."""

    retryable: bool
    recommended_action: str
    retry_delay_seconds: int = 0
    category: str = "unknown"


_POLICIES: dict[str, RecoveryPolicy] = {
    "bitbrowser.request_failed": RecoveryPolicy(
        retryable=True,
        recommended_action="retry_later",
        retry_delay_seconds=30,
        category="transient_infra",
    ),
    "bitbrowser.open_failed": RecoveryPolicy(
        retryable=True,
        recommended_action="retry_later",
        retry_delay_seconds=15,
        category="transient_infra",
    ),
    "bitbrowser.close_failed": RecoveryPolicy(
        retryable=False,
        recommended_action="manual_check_window_state",
        retry_delay_seconds=0,
        category="terminal_cleanup",
    ),
    "bitbrowser.remark_update_failed": RecoveryPolicy(
        retryable=True,
        recommended_action="retry_later",
        retry_delay_seconds=60,
        category="terminal_sync",
    ),
    "worker.missing_instance_id": RecoveryPolicy(
        retryable=False,
        recommended_action="fix_task_assignment",
        retry_delay_seconds=0,
        category="task_data",
    ),
    "worker.missing_bitbrowser_client": RecoveryPolicy(
        retryable=False,
        recommended_action="fix_terminal_runtime",
        retry_delay_seconds=0,
        category="terminal_runtime",
    ),
    "worker.unsupported_script": RecoveryPolicy(
        retryable=False,
        recommended_action="fix_task_definition",
        retry_delay_seconds=0,
        category="task_definition",
    ),
}


def resolve_recovery_policy(error_code: str | None) -> RecoveryPolicy:
    """Return the handling policy for one failure code."""

    if error_code is None:
        return RecoveryPolicy(
            retryable=False,
            recommended_action="inspect_task_result",
            retry_delay_seconds=0,
            category="unknown",
        )
    return _POLICIES.get(
        error_code,
        RecoveryPolicy(
            retryable=False,
            recommended_action="inspect_unknown_failure",
            retry_delay_seconds=0,
            category="unknown",
        ),
    )
