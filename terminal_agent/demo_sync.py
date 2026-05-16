"""End-to-end local demo for the terminal-to-NAS sync path."""

from __future__ import annotations

from datetime import datetime

from terminal_agent.adapters import BitBrowserClient, NasControlPlaneClient
from terminal_agent.models import InstanceState, LocalTask
from terminal_agent.runtime import TerminalRuntime


def run_demo(base_url: str = "http://127.0.0.1:8765") -> dict[str, object]:
    """Run a local end-to-end sync demo against a NAS server."""

    runtime = TerminalRuntime(
        terminal_id="terminal-demo-01",
        hostname="workstation-demo",
        operator_name="codex",
        agent_version="0.1.0",
        capabilities=["bitbrowser.scan", "task.execute"],
    )
    client = NasControlPlaneClient(base_url)

    runtime.accept_tasks(
        [
            LocalTask(
                task_id="task-demo-01",
                script_name="follow",
                status="queued",
                parameters={"target_handle": "user_a"},
            )
        ]
    )
    runtime.refresh_instances(
        [
            InstanceState(
                instance_id="instance-demo-01",
                profile_id="profile-demo-01",
                runtime_status="running",
                handle="user_a",
                window_id="win-demo-01",
                remark="user_a",
            ),
            InstanceState(
                instance_id="instance-demo-02",
                profile_id="profile-demo-02",
                runtime_status="idle",
                handle="user_b",
                window_id="win-demo-02",
                remark="user_b",
            ),
        ]
    )

    health = client.healthcheck()
    registered = client.register_terminal(runtime.registration_payload())
    heartbeat = client.send_heartbeat(runtime.heartbeat_payload(datetime(2026, 5, 16, 12, 0, 0)))
    synced = client.sync_instances(
        terminal_id="terminal-demo-01",
        payloads=runtime.instance_snapshot_payloads(),
    )
    runtime.mark_instances_synced(datetime(2026, 5, 16, 12, 0, 5))
    terminals = client.list_terminals()
    instances = client.list_instances()

    return {
        "health": health["status"],
        "registered": registered["status"],
        "heartbeat": heartbeat["status"],
        "synced_instances": len(synced["items"]),
        "terminal_count": len(terminals["items"]),
        "instance_count": len(instances["items"]),
    }


if __name__ == "__main__":
    print(run_demo())
