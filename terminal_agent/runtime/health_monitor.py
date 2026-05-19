"""Instance health monitoring for automatic restart/recovery.

Monitors per-instance health signals:
- Script execution duration (slot-level timeout)
- DOM health signal from plugin bridge (page-level aliveness)
- Process memory usage (OS-level, Windows tasklist / psutil)

Escalates to instance restart when thresholds are breached,
then relies on the existing NAS recovery pipeline for task recovery.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from terminal_agent.models import ScriptSlot


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class HealthCheckConfig:
    """Thresholds and intervals for instance health monitoring.

    All durations are in seconds.  Cycle-related thresholds are measured
    in number of ``run_cycle()`` calls.
    """

    #: If a slot stays ``running`` longer than this, flag as timeout.
    script_timeout_seconds: int = 600  # 10 min

    #: BitBrowser process memory above this (MB) triggers restart.
    memory_threshold_mb: int = 800

    #: How many consecutive check cycles without a DOM health signal
    #: before considering the page stuck.
    max_consecutive_stale_dom: int = 3

    #: Minimum cycles between restarts of the *same* instance.
    restart_cooldown_cycles: int = 6

    #: Max automatic restarts per instance before giving up and
    #: leaving the instance in ``terminal_failure``.
    max_restarts_before_stop: int = 3


# ---------------------------------------------------------------------------
# Health action types
# ---------------------------------------------------------------------------


class HealthActionKind:
    NONE = "none"
    WARN = "warn"
    RESTART = "restart"


@dataclass
class HealthAction:
    """One recommended action for one instance, returned by the monitor."""

    instance_id: str
    action: str  # HealthActionKind.*
    reason: str


# ---------------------------------------------------------------------------
# Per-instance transient tracking
# ---------------------------------------------------------------------------


@dataclass
class InstanceHealthRecord:
    """Transient (in-memory) health tracking state for one BitBrowser instance.

    Lost on terminal restart — this is acceptable because slot recovery
    already handles task-level persistence through the existing outbox +
    NAS recovery pipeline.  The health record only prevents *repeated*
    rapid restarts within one terminal session.
    """

    instance_id: str

    # DOM health
    last_dom_healthy_at: float = 0.0  # time.time()
    consecutive_stale_dom_cycles: int = 0

    # Memory
    memory_peak_mb: float = 0.0

    # Restart tracking (cooldown)
    last_restart_cycle: int = -100
    restart_count: int = 0


# ---------------------------------------------------------------------------
# The monitor
# ---------------------------------------------------------------------------


class HealthMonitor:
    """Periodic instance-level health checker.

    Usage::

        monitor = HealthMonitor(config)
        # inside agent loop, each cycle:
        actions = monitor.check_all(slots=slot_list, pid_map={...})
        for action in actions:
            if action.action == HealthActionKind.RESTART:
                runtime.mark_instance_restart(...)
    """

    def __init__(self, config: HealthCheckConfig | None = None) -> None:
        self._config = config or HealthCheckConfig()
        self._records: dict[str, InstanceHealthRecord] = {}
        self._cycle_count: int = 0

    # -- public api ---------------------------------------------------------

    def record_dom_health(self, instance_id: str, alive: bool) -> None:
        """Accept a DOM health report from the plugin bridge.

        The extension's content script calls ``/ext/dom_health`` every
        few seconds.  ``alive=True`` means the DOM contained expected
        page elements (the page isn't white-screened).
        """
        record = self._get_or_create(instance_id)
        if alive:
            record.last_dom_healthy_at = time.time()
            record.consecutive_stale_dom_cycles = 0
        else:
            record.consecutive_stale_dom_cycles += 1

    def check_all(
        self,
        slots: list[ScriptSlot],
        pid_map: dict[str, int],  # instance_id → OS pid
        now: float | None = None,
    ) -> list[HealthAction]:
        """Run all health checks and return recommended actions.

        Parameters
        ----------
        slots:
            All current :class:`ScriptSlot` objects (including idle ones).
        pid_map:
            Mapping from instance id (BitBrowser browser id) to OS process id.
            Obtained by calling ``/browser/pids``.
        now:
            Override current time (Unix timestamp).  Defaults to ``time.time()``.

        Returns
        -------
        list[HealthAction]
            Actions for ``agent_loop`` to execute.  Empty list means
            everything is healthy.
        """
        self._cycle_count += 1
        now = now if now is not None else time.time()

        # Group slots by bound instance
        slots_by_instance: dict[str, list[ScriptSlot]] = {}
        for slot in slots:
            iid = slot.bound_instance_id
            if iid:
                slots_by_instance.setdefault(iid, []).append(slot)

        # Union of all instances we know about: slots + PID map + health records
        health_ids: set[str] = set()
        for iid, rec in self._records.items():
            if rec.consecutive_stale_dom_cycles > 0 or rec.memory_peak_mb > 0:
                health_ids.add(iid)
        all_ids: set[str] = set(slots_by_instance.keys()) | set(pid_map.keys()) | health_ids

        actions: list[HealthAction] = []
        for instance_id in sorted(all_ids):
            action = self._check_one(
                instance_id=instance_id,
                slots=slots_by_instance.get(instance_id, []),
                pid=pid_map.get(instance_id),
                now=now,
            )
            if action is not None:
                actions.append(action)

        return actions

    # -- per-instance check -------------------------------------------------

    def _check_one(
        self,
        instance_id: str,
        slots: list[ScriptSlot],
        pid: int | None,
        now: float,
    ) -> HealthAction | None:
        """Run all checks against one instance.  Returns ``None`` if healthy."""
        record = self._get_or_create(instance_id)

        # --- hard stop after too many restarts ----------------------------
        if record.restart_count >= self._config.max_restarts_before_stop:
            return HealthAction(
                instance_id=instance_id,
                action=HealthActionKind.WARN,
                reason=f"实例已自动重启{record.restart_count}次，超过上限，停止自动重启",
            )

        # --- cooldown ------------------------------------------------------
        cycles_since_last_restart = self._cycle_count - record.last_restart_cycle
        if cycles_since_last_restart < self._config.restart_cooldown_cycles:
            return None  # still in cooldown — skip checks to avoid noisy warnings

        triggers: list[str] = []

        # 1. Script timeout -------------------------------------------------
        running_slots = [s for s in slots if s.status == "running"]
        for slot in running_slots:
            start = slot.started_at or slot.assigned_at
            if start is None:
                continue
            # start is a timezone-naive datetime assumed to be UTC
            start_ts = _datetime_to_timestamp(start)
            elapsed = now - start_ts
            if elapsed > self._config.script_timeout_seconds:
                minutes = int(elapsed // 60)
                triggers.append(f"脚本超时({minutes}分钟) slot={slot.slot_id} task={slot.task_id or '?'}")

        # 2. DOM health staleness -------------------------------------------
        if record.consecutive_stale_dom_cycles >= self._config.max_consecutive_stale_dom:
            triggers.append(
                f"DOM无响应(连续{record.consecutive_stale_dom_cycles}个周期)"
            )

        # 3. Process memory -------------------------------------------------
        if pid is not None:
            memory_mb = _get_process_memory_mb(pid)
            if memory_mb is not None:
                if memory_mb > record.memory_peak_mb:
                    record.memory_peak_mb = memory_mb
                if memory_mb > self._config.memory_threshold_mb:
                    triggers.append(f"内存过高({memory_mb:.0f}MB) pid={pid}")

        if not triggers:
            return None

        # --- escalate -------------------------------------------------------
        record.last_restart_cycle = self._cycle_count
        record.restart_count += 1
        return HealthAction(
            instance_id=instance_id,
            action=HealthActionKind.RESTART,
            reason="; ".join(triggers),
        )

    # -- helpers ------------------------------------------------------------

    def _get_or_create(self, instance_id: str) -> InstanceHealthRecord:
        rec = self._records.get(instance_id)
        if rec is None:
            rec = InstanceHealthRecord(instance_id=instance_id)
            self._records[instance_id] = rec
        return rec


# ---------------------------------------------------------------------------
# OS-level helpers
# ---------------------------------------------------------------------------


def _get_process_memory_mb(pid: int) -> float | None:
    """Return the working-set size of *pid* in MB, or ``None`` if unavailable.

    On Windows uses ``tasklist`` (built-in, no extra deps).
    On other platforms tries ``psutil`` if installed; otherwise returns None.
    """
    if sys.platform == "win32":
        return _tasklist_memory_mb(pid)

    # Unix / macOS — optional psutil
    try:
        import psutil as _psutil  # noqa: F811
    except ImportError:
        return None

    try:
        proc = _psutil.Process(pid)
        rss_bytes = proc.memory_info().rss
        return rss_bytes / (1024 * 1024)
    except (_psutil.NoSuchProcess, _psutil.AccessDenied, OSError):
        return None


def _tasklist_memory_mb(pid: int) -> float | None:
    """Query the Windows ``tasklist`` command for a single PID."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid}"],
            capture_output=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None

    stdout = result.stdout
    if result.returncode != 0 or not stdout:
        return None
    try:
        text = stdout.decode("utf-8", errors="replace").strip()
    except (ValueError, AttributeError):
        return None
    if not text:
        return None

    # tasklist CSV: "chrome.exe","12345","Console","1","123,456 K"
    try:
        # Remove surrounding quotes and split
        fields = text.strip().strip('"').split('","')
        if len(fields) < 5:
            # Maybe locale-dependent formatting; try splitting at K/M suffix
            return _parse_memory_from_text(text)
        mem_field = fields[-1].strip()
        return _parse_memory_field(mem_field)
    except (ValueError, IndexError):
        return _parse_memory_from_text(text)


def _parse_memory_field(mem_field: str) -> float | None:
    """Parse a single memory field like ``\"123,456 K\"`` or ``120.5 MB``."""
    val = mem_field.strip().rstrip('"')
    if val.endswith(" K") or val.endswith(" KB"):
        try:
            return float(val[:-2].strip().replace(",", "")) / 1024  # KB → MB
        except (ValueError, TypeError):
            return None
    if val.endswith(" M") or val.endswith(" MB"):
        try:
            return float(val[:-2].strip().replace(",", ""))
        except (ValueError, TypeError):
            return None
    return None


def _parse_memory_from_text(text: str) -> float | None:
    """Fallback: search for any ``<digits>,<digits> K`` or ``<digits> MB``
    pattern in the raw tasklist output."""
    import re

    # Try "1,234,567 K"
    m = re.search(r"([\d,]+)\s*K\b", text)
    if m:
        try:
            return float(m.group(1).replace(",", "")) / 1024
        except (ValueError, TypeError):
            pass
    # Try "120 MB"
    m = re.search(r"([\d,.]+)\s*M(?:B)?\b", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except (ValueError, TypeError):
            pass
    return None

    return None


def _datetime_to_timestamp(dt: datetime) -> float:
    """Convert a possibly-naive UTC datetime to a Unix timestamp."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).timestamp()
    return dt.timestamp()
