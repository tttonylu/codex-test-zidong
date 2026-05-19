# Mainline Status Matrix

## Scope
- This checkpoint records the current mainline state after the plugin-facing runtime baseline and dashboard observability pass.
- It is intentionally narrow: a status matrix for what is landed, what is verified, and what remains deferred.

## Matrix
| Area | State | Verified | Notes |
| --- | --- | --- | --- |
| Terminal concurrent slots | landed | yes | main execution path still uses the existing HTTP claim loop by default |
| Terminal restart recovery | landed | yes | accepted-only recovery ack is the current behavior |
| NAS queue boundary | landed | yes | `queue_pull` remains a boundary / observability path, not a real transport |
| Deployment skeleton for fnOS NAS | landed | yes | Docker / compose identity remains isolated for NAS deployment |
| Plugin creator intake | landed | yes | creator/blogger push intake is routed through the NAS plugin runtime |
| Ammo inventory | landed | yes | ammo storage / claim / consume is available in the plugin runtime baseline |
| Account inventory | landed | yes | account registration and status updates are available |
| Daily action stats | landed | yes | 15-day retention cleanup is in place |
| Plugin task dispatch bridge | landed | yes | plugin dispatch can create NAS tasks and bind ammo |
| BitBrowser login-success remark refresh | landed | yes | login updates remark and instance identity together |
| Dashboard plugin observability | landed | yes | plugin runtime section and task dispatch observability are visible |
| Dashboard dispatch observability | landed | yes | dispatch mode / path / queue fields are visible in Chinese UI |
| Real queue transport | deferred | no | still not implemented; keep `claim_http` as default |

## Current Verification Bundle
- `python -m nas_control_plane.demo_pre_manual_review_bundle`
- `python -m nas_control_plane.demo_dashboard_live_verify`
- `python -m nas_control_plane.demo_plugin_runtime_flow`
- `python -m nas_control_plane.demo_plugin_dispatch_task_flow`
- `python -m nas_control_plane.demo_plugin_dispatch_policy_controls`
- `python -m nas_control_plane.demo_plugin_task_result_ammo_lifecycle`
- `python -m nas_control_plane.demo_plugin_daily_stats_retention`
- `python -m nas_control_plane.demo_dashboard_plugin_runtime_observability`

## Next Boundary
- Keep mainline flow stable.
- Do not expand homepage redesign yet.
- Move future work toward plugin-script integration depth and the eventual NAS-side container handoff.
