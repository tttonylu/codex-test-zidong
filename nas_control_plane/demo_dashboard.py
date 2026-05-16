"""启动一个带示例数据的 NAS 运营页，便于本地直接验证中文界面。"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from nas_control_plane.server import create_server
from nas_control_plane.services import build_chat_task_payload, build_follow_task_payload, build_probe_task_payload
from shared.protocol import ActionResultPayload, HeartbeatPayload, ScriptRunPayload, TerminalRegistrationPayload
from terminal_agent.adapters import NasControlPlaneClient


def main() -> None:
    state_path = Path("nas_control_plane/state.dashboard.demo.sqlite3")
    if state_path.exists():
        state_path.unlink()

    server = create_server(port=8783, state_path=state_path)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        time.sleep(0.2)
        client = NasControlPlaneClient("http://127.0.0.1:8783")

        client.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-a",
                hostname="ops-host-a",
                operator_name="alice",
                agent_version="0.2.0",
                capabilities=["scan", "execute"],
                metadata={"zone": "cn-east"},
            )
        )
        client.register_terminal(
            TerminalRegistrationPayload(
                terminal_id="terminal-b",
                hostname="ops-host-b",
                operator_name="bob",
                agent_version="0.2.0",
                capabilities=["scan"],
                metadata={"zone": "cn-west"},
            )
        )

        client.send_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-a",
                reported_at=datetime(2026, 5, 17, 21, 0, 0),
                status="online",
                active_instance_count=2,
                queued_task_count=1,
                metadata={"load": "medium"},
            )
        )
        client.send_heartbeat(
            HeartbeatPayload(
                terminal_id="terminal-b",
                reported_at=datetime(2026, 5, 17, 21, 1, 0),
                status="online",
                active_instance_count=1,
                queued_task_count=2,
                metadata={"load": "high"},
            )
        )

        client.create_task(
            build_follow_task_payload(
                task_id="task-dashboard-follow",
                terminal_id="terminal-a",
                instance_id="bb-follow-1",
                target_handle="matrix_ops",
                priority=3,
                retry_limit=1,
                annotate_remark=True,
            )
        )
        client.create_task(
            build_chat_task_payload(
                task_id="task-dashboard-chat",
                terminal_id="terminal-a",
                instance_id="bb-chat-1",
                target_handle="risk_user",
                priority=2,
                retry_limit=2,
                annotate_remark=True,
            )
        )
        client.create_task(
            build_probe_task_payload(
                task_id="task-dashboard-probe",
                terminal_id="terminal-b",
                instance_id="bb-probe-1",
                target_url="https://x.com/home",
                priority=1,
                retry_limit=0,
                annotate_remark=False,
            )
        )

        client.claim_tasks("terminal-a")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-dashboard-chat-a1",
                task_id="task-dashboard-chat",
                terminal_id="terminal-a",
                instance_id="bb-chat-1",
                script_name="chat",
                status="running",
                started_at=datetime(2026, 5, 17, 21, 2, 0),
            )
        )
        client.submit_task_result(
            ActionResultPayload(
                run_id="run-dashboard-chat-a1",
                task_id="task-dashboard-chat",
                terminal_id="terminal-a",
                status="failed",
                summary="chat failed",
                error_code="bitbrowser.request_failed",
                error_message="rate limited",
                retryable=True,
                final=False,
                details={
                    "error": "rate limited",
                    "step_count": 4,
                    "steps": [
                        {"name": "validate_instance_id", "status": "completed"},
                        {"name": "validate_bitbrowser_client", "status": "completed"},
                        {"name": "prepare_target", "status": "completed"},
                        {"name": "open_browser", "status": "failed"},
                    ],
                },
                emitted_at=datetime(2026, 5, 17, 21, 3, 0),
            )
        )

        client.claim_tasks("terminal-b")
        client.mark_task_running(
            ScriptRunPayload(
                run_id="run-dashboard-probe-a1",
                task_id="task-dashboard-probe",
                terminal_id="terminal-b",
                instance_id="bb-probe-1",
                script_name="probe",
                status="running",
                started_at=datetime(2026, 5, 17, 21, 4, 0),
            )
        )

        print("运营页已启动: http://127.0.0.1:8783/")
        print("按 Ctrl+C 退出")
        server_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=1)


if __name__ == "__main__":
    main()
