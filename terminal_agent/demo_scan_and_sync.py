"""End-to-end demo that scans BitBrowser and syncs results to the NAS."""

from __future__ import annotations

from datetime import datetime

from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.models import LocalTask
from terminal_agent.runtime import TerminalRuntime


def run_scan_and_sync_demo(
    nas_base_url: str = "http://127.0.0.1:8765",
    bitbrowser_base_url: str = "http://127.0.0.1:54345",
) -> dict[str, object]:
    """Scan BitBrowser instances and push them through the NAS sync chain."""

    runtime = TerminalRuntime(
        terminal_id="terminal-scan-01",
        hostname="workstation-scan",
        operator_name="codex",
        agent_version="0.1.0",
        capabilities=["bitbrowser.scan", "task.execute"],
    )
    nas_client = NasControlPlaneClient(nas_base_url)
    bitbrowser_client = BitBrowserClient(bitbrowser_base_url)

    runtime.accept_tasks([LocalTask(task_id="task-scan-01", script_name="probe", status="queued")])
    scanned_instances = bitbrowser_client.scan_instances()
    runtime.refresh_instances_from_scan(scanned_instances)

    health = nas_client.healthcheck()
    bitbrowser_health = bitbrowser_client.healthcheck()
    registered = nas_client.register_terminal(runtime.registration_payload())
    heartbeat = nas_client.send_heartbeat(runtime.heartbeat_payload(datetime(2026, 5, 16, 12, 5, 0)))
    synced = nas_client.sync_instances(
        terminal_id="terminal-scan-01",
        payloads=runtime.instance_snapshot_payloads(),
    )
    terminals = nas_client.list_terminals()
    instances = nas_client.list_instances()

    return {
        "nas_health": health["status"],
        "bitbrowser_health": bool(bitbrowser_health.get("success")),
        "registered": registered["status"],
        "heartbeat": heartbeat["status"],
        "scanned_instances": len(scanned_instances),
        "synced_instances": len(synced["items"]),
        "terminal_count": len(terminals["items"]),
        "instance_count": len(instances["items"]),
    }


if __name__ == "__main__":
    print(run_scan_and_sync_demo())
