"""Terminal agent loop for sync, claim, and concurrent slot execution."""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable

from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.runtime.health_monitor import HealthActionKind
from terminal_agent.runtime.task_sources import HttpClaimTaskSource, TaskSource
from terminal_agent.scripts import ScriptWorkerRegistry, WorkerExecution
from terminal_agent.runtime.terminal_runtime import TerminalRuntime


class TerminalAgentLoop:
    """Runs a terminal-side polling loop with concurrent local worker slots."""

    def __init__(
        self,
        runtime: TerminalRuntime,
        nas_client: NasControlPlaneClient,
        bitbrowser_client: BitBrowserClient,
        worker_registry: ScriptWorkerRegistry | None = None,
        task_source: TaskSource | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._nas_client = nas_client
        self._bitbrowser_client = bitbrowser_client
        self._worker_registry = worker_registry or ScriptWorkerRegistry()
        self._task_source = task_source or HttpClaimTaskSource(nas_client)
        self._sleep_fn = sleep_fn or time.sleep
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, runtime.claim_capacity() or 1),
            thread_name_prefix="terminal-slot",
        )
        self._active_futures: dict[concurrent.futures.Future[WorkerExecution], str] = {}

    def bootstrap(self) -> None:
        """Register the terminal before entering the loop."""

        self._nas_client.register_terminal(self._runtime.registration_payload())

    def run_cycle(self) -> dict[str, int]:
        """Run one sync cycle: scan, heartbeat, sync, drain completions, then claim work."""

        scanned = self._bitbrowser_client.scan_instances()
        self._runtime.refresh_instances_from_scan(scanned)
        replayed = self._replay_result_outbox()
        completed = self._drain_completed_executions()
        heartbeat = self._runtime.heartbeat_payload()
        self._send_heartbeat_and_ack_recovery(heartbeat)
        self._nas_client.sync_instances(
            terminal_id=self._runtime.registration_payload().terminal_id,
            payloads=self._runtime.instance_snapshot_payloads(),
        )
        self._runtime.mark_instances_synced()

        self._check_instance_health(scanned)
        self._execute_pending_restarts()

        claimed_assignments = self._task_source.claim(self._runtime)
        for item in claimed_assignments:
            slot = self._runtime.assign_task_to_slot(item)
            execution = self._worker_registry.prepare_execution(
                item,
                terminal_hostname=self._runtime.registration_payload().hostname,
                bitbrowser_client=self._bitbrowser_client,
                metadata={
                    "agent_version": self._runtime.registration_payload().agent_version,
                    "slot_id": slot.slot_id,
                    "delivery_id": item.delivery_id,
                    "claim_lease_id": item.claim_lease_id,
                },
            )
            slot.run = execution.run
            self._runtime.mark_slot_started(slot.slot_id, execution.run.run_id)
            self._nas_client.mark_task_running(execution.run)
            future = self._executor.submit(self._worker_registry.finish_execution, execution)
            self._active_futures[future] = slot.slot_id

        return {
            "scanned_instances": len(scanned),
            "claimed_tasks": len(claimed_assignments),
            "reported_results": replayed + completed,
            "running_tasks": len(self._active_futures),
        }

    def run(self, cycles: int = 1, interval_seconds: float = 5.0) -> list[dict[str, int]]:
        """Run multiple cycles with a fixed interval."""

        results: list[dict[str, int]] = []
        self.bootstrap()
        for index in range(cycles):
            results.append(self.run_cycle())
            if index < cycles - 1:
                self._sleep_fn(interval_seconds)
        final_completed = self._wait_for_all_running()
        if final_completed:
            heartbeat = self._runtime.heartbeat_payload()
            self._send_heartbeat_and_ack_recovery(heartbeat)
            results.append(
                {
                    "scanned_instances": 0,
                    "claimed_tasks": 0,
                    "reported_results": final_completed,
                    "running_tasks": len(self._active_futures),
                }
            )
        return results

    def shutdown(self) -> None:
        """Stop background worker threads after the loop is no longer needed."""

        self._executor.shutdown(wait=True)

    def _drain_completed_executions(self) -> int:
        completed = 0
        done_futures = [future for future in self._active_futures if future.done()]
        for future in done_futures:
            slot_id = self._active_futures[future]
            execution = future.result()
            if execution.result is None:
                raise RuntimeError(f"worker execution finished without result: {slot_id}")
            try:
                self._nas_client.submit_task_result(execution.result)
            except Exception:
                self._runtime.enqueue_result_outbox(execution.result)
                task_status = "completed" if execution.result.status == "completed" else "failed"
                self._runtime.release_slot(slot_id, task_status=task_status)
                self._active_futures.pop(future, None)
                continue
            task_status = "completed" if execution.result.status == "completed" else "failed"
            self._runtime.release_slot(slot_id, task_status=task_status)
            self._active_futures.pop(future, None)
            completed += 1
        return completed

    def _wait_for_all_running(self) -> int:
        if not self._active_futures:
            return 0
        concurrent.futures.wait(list(self._active_futures))
        return self._drain_completed_executions()

    def _send_heartbeat_and_ack_recovery(self, heartbeat) -> None:
        response = self._nas_client.send_heartbeat(heartbeat)
        accepted_ids = list(response.get("accepted_recovered_task_ids", []))
        self._runtime.ack_recovered_task_ids(accepted_ids)

    def _check_instance_health(self, scanned_instances) -> None:
        """Run the health monitor and record any triggered actions."""
        hm = self._runtime.health_monitor
        if hm is None:
            return
        running_instance_ids = [
            inst.instance_id for inst in scanned_instances
            if inst.runtime_status == "running"
        ]
        if not running_instance_ids:
            return
        pid_map = self._bitbrowser_client.get_browser_pids(running_instance_ids)
        slots = self._runtime.running_slots()
        actions = hm.check_all(slots=slots, pid_map=pid_map)
        for action in actions:
            self._runtime.register_health_action(action)

    def _execute_pending_restarts(self) -> None:
        """Close->open any instances flagged for restart by health monitor."""
        for instance_id, reason in self._runtime.restart_requested_instances():
            # Fail any slot currently running on this instance
            for slot in self._runtime.running_slots():
                if slot.bound_instance_id == instance_id:
                    self._runtime.release_slot(slot.slot_id, task_status="failed")
            try:
                self._bitbrowser_client.close_browser(instance_id)
            except Exception:
                pass
            self._sleep_fn(5)  # BitBrowser API recommends 5s after close
            try:
                self._bitbrowser_client.open_browser(instance_id)
            except Exception:
                continue
            self._runtime.update_instance_identity(
                instance_id=instance_id,
                handle=None,
                remark=None,
                runtime_status="running",
            )
            self._nas_client.request_instance_restart(
                instance_id=instance_id, reason=reason
            )
            self._nas_client.sync_instances(
                terminal_id=self._runtime.registration_payload().terminal_id,
                payloads=self._runtime.instance_snapshot_payloads(),
            )
            self._runtime.mark_instances_synced()
            self._runtime.ack_restart_executed(instance_id)

    def _replay_result_outbox(self) -> int:
        replayed = 0
        for item in self._runtime.result_outbox_items():
            try:
                self._nas_client.submit_task_result(item)
            except Exception:
                continue
            self._runtime.ack_result_outbox_item(item.run_id)
            replayed += 1
        return replayed
