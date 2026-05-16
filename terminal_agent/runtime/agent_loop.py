"""Minimal terminal agent loop for periodic sync and task polling."""

from __future__ import annotations

import time
from collections.abc import Callable

from shared.protocol import TaskAssignmentPayload
from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.scripts import ScriptWorkerRegistry, WorkerExecution
from terminal_agent.runtime.terminal_runtime import TerminalRuntime


class TerminalAgentLoop:
    """Runs a small terminal-side polling loop."""

    def __init__(
        self,
        runtime: TerminalRuntime,
        nas_client: NasControlPlaneClient,
        bitbrowser_client: BitBrowserClient,
        worker_registry: ScriptWorkerRegistry | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._nas_client = nas_client
        self._bitbrowser_client = bitbrowser_client
        self._worker_registry = worker_registry or ScriptWorkerRegistry()
        self._sleep_fn = sleep_fn or time.sleep

    def bootstrap(self) -> None:
        """Register the terminal before entering the loop."""

        self._nas_client.register_terminal(self._runtime.registration_payload())

    def run_cycle(self) -> dict[str, int]:
        """Run one sync cycle: scan, heartbeat, sync, claim tasks, and report results."""

        scanned = self._bitbrowser_client.scan_instances()
        self._runtime.refresh_instances_from_scan(scanned)
        self._nas_client.send_heartbeat(self._runtime.heartbeat_payload())
        self._nas_client.sync_instances(
            terminal_id=self._runtime.registration_payload().terminal_id,
            payloads=self._runtime.instance_snapshot_payloads(),
        )
        self._runtime.mark_instances_synced()

        claimed_response = self._nas_client.claim_tasks(self._runtime.registration_payload().terminal_id)
        claimed_assignments = [
            _task_from_dict(item)
            for item in claimed_response.get("items", [])
        ]
        self._runtime.accept_task_assignments(claimed_assignments)
        executions = []
        for item in claimed_assignments:
            run = self._worker_registry.build_run(
                item,
                terminal_hostname=self._runtime.registration_payload().hostname,
            )
            self._nas_client.mark_task_running(run)
            result = self._worker_registry.execute_run(
                item,
                run=run,
                terminal_hostname=self._runtime.registration_payload().hostname,
                bitbrowser_client=self._bitbrowser_client,
                metadata={"agent_version": self._runtime.registration_payload().agent_version},
            )
            executions.append(WorkerExecution(run=run, result=result))
        for execution in executions:
            self._nas_client.submit_task_result(execution.result)

        return {
            "scanned_instances": len(scanned),
            "claimed_tasks": len(claimed_assignments),
            "reported_results": len(executions),
        }

    def run(self, cycles: int = 1, interval_seconds: float = 5.0) -> list[dict[str, int]]:
        """Run multiple cycles with a fixed interval."""

        results: list[dict[str, int]] = []
        self.bootstrap()
        for index in range(cycles):
            results.append(self.run_cycle())
            if index < cycles - 1:
                self._sleep_fn(interval_seconds)
        return results


def _task_from_dict(payload: dict[str, object]) -> TaskAssignmentPayload:
    return TaskAssignmentPayload(
        task_id=str(payload["task_id"]),
        terminal_id=str(payload["terminal_id"]),
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        script_name=str(payload["script_name"]),
        parameters=dict(payload.get("parameters", {})),
        priority=int(payload.get("priority", 0)),
    )
