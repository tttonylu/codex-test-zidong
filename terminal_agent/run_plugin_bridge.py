"""Runnable local HTTP bridge for plugin-originated BitBrowser events."""

from __future__ import annotations

import os
import threading
import time

from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.plugin_bridge import _engine_commands, create_plugin_bridge_server
from terminal_agent.runtime import TerminalRuntime
from terminal_agent.runtime.health_monitor import HealthMonitor


def run_plugin_bridge() -> None:
    """Start the local plugin bridge with environment-driven defaults."""

    terminal_id = os.environ.get("XMATRIX_TERMINAL_ID", "terminal-plugin-bridge-01")
    hostname = os.environ.get("XMATRIX_TERMINAL_HOSTNAME", "localhost")
    operator_name = os.environ.get("XMATRIX_OPERATOR_NAME", "plugin-bridge")
    agent_version = os.environ.get("XMATRIX_AGENT_VERSION", "0.1.0")
    capabilities_raw = os.environ.get(
        "XMATRIX_TERMINAL_CAPABILITIES",
        "bitbrowser.scan,plugin.bridge,task.execute",
    )
    capabilities = [item.strip() for item in capabilities_raw.split(",") if item.strip()]
    max_parallel_tasks = int(os.environ.get("XMATRIX_MAX_PARALLEL_TASKS", "1"))
    runtime_state_path = os.environ.get("XMATRIX_TERMINAL_STATE_PATH")

    nas_base_url = os.environ.get("XMATRIX_NAS_BASE_URL", "http://192.168.0.100:3210")
    bitbrowser_base_url = os.environ.get("XMATRIX_BITBROWSER_BASE_URL", "http://127.0.0.1:54345")
    bridge_host = os.environ.get("XMATRIX_PLUGIN_BRIDGE_HOST", "127.0.0.1")
    bridge_port = int(os.environ.get("XMATRIX_PLUGIN_BRIDGE_PORT", "54346"))
    sync_interval_seconds = float(os.environ.get("XMATRIX_PLUGIN_BRIDGE_SYNC_INTERVAL_SECONDS", "5"))

    health_monitor = HealthMonitor()

    runtime = TerminalRuntime(
        terminal_id=terminal_id,
        hostname=hostname,
        operator_name=operator_name,
        agent_version=agent_version,
        capabilities=capabilities,
        max_parallel_tasks=max_parallel_tasks,
        state_path=runtime_state_path,
        health_monitor=health_monitor,
    )
    nas_client = NasControlPlaneClient(nas_base_url)
    bitbrowser_client = BitBrowserClient(bitbrowser_base_url)

    try:
        runtime.refresh_instances_from_scan(bitbrowser_client.scan_instances())
    except RuntimeError:
        pass

    try:
        nas_client.register_terminal(runtime.registration_payload())
        nas_client.sync_instances(
            terminal_id=runtime.registration_payload().terminal_id,
            payloads=runtime.instance_snapshot_payloads(),
        )
        runtime.mark_instances_synced()
    except RuntimeError:
        pass

    stop_event = threading.Event()

    def sync_loop() -> None:
        """Keep terminal and BitBrowser instance state fresh on the NAS side with health checks."""

        while not stop_event.wait(sync_interval_seconds):
            try:
                scanned = bitbrowser_client.scan_instances()
                runtime.refresh_instances_from_scan(scanned)
            except RuntimeError:
                continue

            # -- dashboard batch-action response (open/close/stop requests) --
            try:
                nas_instances = nas_client.list_instances(terminal_id=terminal_id)
                for nas_inst in (nas_instances.get("items") or []):
                    iid = nas_inst.get("instance_id", "")
                    runtime_status = nas_inst.get("runtime_status", "")
                    metadata = nas_inst.get("metadata") or {}
                    if runtime_status == "open_requested":
                        try:
                            bitbrowser_client.close_browser(iid)
                        except RuntimeError:
                            pass
                        import time as _time
                        _time.sleep(2)
                        bitbrowser_client.open_browser(iid, args=["https://x.com/home", "https://x.com/home"])
                        _engine_commands.append({"command": "start", "instance_id": iid})
                        nas_client.request_instance_restart(instance_id=iid, reason="dashboard_batch_open")
                        runtime.update_instance_identity(
                            instance_id=iid, handle=None, remark=None,
                            runtime_status="running",
                        )
                    elif runtime_status == "close_requested" or metadata.get("close_requested"):
                        _engine_commands.append({"command": "stop", "instance_id": iid})
                        try:
                            bitbrowser_client.close_browser(iid)
                        except RuntimeError:
                            pass
                        nas_client.request_instance_restart(instance_id=iid, reason="dashboard_batch_close")
                        runtime.update_instance_identity(
                            instance_id=iid, handle=None, remark=None,
                            runtime_status="stopped",
                        )
                    elif runtime_status == "stop_requested" or metadata.get("stop_requested"):
                        _engine_commands.append({"command": "stop", "instance_id": iid})
                        nas_client.request_instance_restart(instance_id=iid, reason="dashboard_batch_stop")
            except RuntimeError:
                pass

            # -- health check --
            try:
                running_ids = [inst.instance_id for inst in scanned if inst.runtime_status == "running"]
                if running_ids and health_monitor is not None:
                    pid_map = bitbrowser_client.get_browser_pids(running_ids)
                    slots = runtime.running_slots()
                    actions = health_monitor.check_all(slots=slots, pid_map=pid_map)
                    for action in actions:
                        runtime.register_health_action(action)
                    # Execute pending restarts
                    for instance_id, reason in runtime.restart_requested_instances():
                        for slot in runtime.running_slots():
                            if slot.bound_instance_id == instance_id:
                                runtime.release_slot(slot.slot_id, task_status="failed")
                        try:
                            bitbrowser_client.close_browser(instance_id)
                        except RuntimeError:
                            pass
                        import time as _time
                        _time.sleep(5)
                        try:
                            bitbrowser_client.open_browser(instance_id)
                        except RuntimeError:
                            continue
                        runtime.update_instance_identity(
                            instance_id=instance_id, handle=None, remark=None,
                            runtime_status="running",
                        )
                        nas_client.request_instance_restart(instance_id=instance_id, reason=reason)
                        runtime.ack_restart_executed(instance_id)
            except RuntimeError:
                pass

            try:
                nas_client.send_heartbeat(runtime.heartbeat_payload())
                nas_client.sync_instances(
                    terminal_id=runtime.registration_payload().terminal_id,
                    payloads=runtime.instance_snapshot_payloads(),
                )
                runtime.mark_instances_synced()
            except RuntimeError:
                continue

    sync_thread = threading.Thread(target=sync_loop, name="plugin-bridge-sync", daemon=True)
    sync_thread.start()

    server = create_plugin_bridge_server(
        runtime=runtime,
        nas_client=nas_client,
        bitbrowser_client=bitbrowser_client,
        health_monitor=health_monitor,
        host=bridge_host,
        port=bridge_port,
    )
    print(f"plugin_bridge listening on http://{bridge_host}:{bridge_port}")
    try:
        server.serve_forever()
    finally:
        stop_event.set()
        sync_thread.join(timeout=max(1.0, sync_interval_seconds + 1.0))


if __name__ == "__main__":
    run_plugin_bridge()
