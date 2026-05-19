# NAS Control Plane

这一层只负责总控逻辑，不直接处理本机窗口细节。

部署目标默认指向 NAS 侧轻量控制面，最终形态需要兼容飞牛 OS / fnOS 的图形化 Docker 部署流程，并保持独立容器命名与标识隔离。

后续会放入：

- terminal registry
- instance registry
- task dispatcher
- audit log
- strategy center

## Mainline Note

- Current mainline execution still uses `claim_http`.
- `queue_pull` now has a NAS-backed local transport baseline, but it still does not replace `claim_http` as the default mainline path.
- Queue contracts currently live in:
  - `nas_control_plane/services/queue_dispatch.py`
  - `nas_control_plane/services/queue_transport.py`
  - `terminal_agent/runtime/queue_claim.py`

## Review / Verification Entry Points

- Main review brief:
  - `docs/project-checkpoints/mainline-review-brief-terminal-concurrency-and-queue-skeleton-2026-05-18.md`
- Manual review checklist before dashboard / NAS test:
  - `docs/project-checkpoints/manual-review-checklist-before-dashboard-and-nas-test-2026-05-18.md`
- Pre-review verification bundle:
  - `python -m nas_control_plane.demo_pre_manual_review_bundle`
- Direct CLI verification for queue dispatch filters:
  - `python -m nas_control_plane.demo_cli_queue_dispatch_filters`
- Local queue transport baseline verification:
  - `python -m nas_control_plane.demo_local_queue_transport_roundtrip`
  - `python -m nas_control_plane.demo_local_queue_lease_expiry`
- Plugin-script runtime inventory/stats verification:
  - `python -m nas_control_plane.demo_plugin_runtime_flow`
  - `python -m nas_control_plane.demo_plugin_daily_stats_retention`
- Plugin ammo -> task dispatch bridge verification:
  - `python -m nas_control_plane.demo_plugin_dispatch_task_flow`
  - `python -m nas_control_plane.demo_plugin_task_result_ammo_lifecycle`
  - `python -m nas_control_plane.demo_cli_plugin_runtime_views`
  - `python -m nas_control_plane.demo_plugin_dispatch_policy_controls`
  - `python -m nas_control_plane.demo_cli_plugin_policy_views`
- Local plugin bridge runtime entry:
  - `python -m terminal_agent.run_plugin_bridge`

## Live Dashboard Demo

- Start:
  - `python -m nas_control_plane.demo_dashboard_live_verify`
- The script now binds dynamic free local ports and prints a JSON line first.
- That first line includes:
  - `dashboard_url`
  - `queue_task_id`
  - `queue_dispatch_status`
- Current seeded live-demo expectations:
  - one `queue_pull` task exists
  - task detail should show:
    - `dispatch mode = queue_pull`
    - `queue dispatch status = queued`
    - `queue dispatch accepted = true`

