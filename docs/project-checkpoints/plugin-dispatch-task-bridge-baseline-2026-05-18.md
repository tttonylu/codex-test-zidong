# Plugin Dispatch Task Bridge Baseline

## Goal
- Turn plugin-facing ammo distribution into a real mainline task creation path.
- Keep plugin scripts as the primary runtime contract while preserving `claim_http` as the default execution path.

## Landed
- Added plugin inventory read methods in `PluginRuntimeService`:
  - `list_creator_items()`
  - `list_accounts()`
  - `get_account()`
- Added ammo-task binding helpers:
  - `bind_ammo_target_to_task()`
  - `release_ammo_target()`
- Added NAS plugin-facing endpoint:
  - `POST /plugin/dispatch`
- Added plugin-facing query endpoint:
  - `GET /plugin/accounts`
- Added client helpers in `terminal_agent.adapters.NasControlPlaneClient`:
  - `dispatch_plugin_task(...)`
  - `list_plugin_creators()`
  - `list_plugin_ammo(...)`
  - `list_plugin_accounts(...)`
  - `list_plugin_daily_stats(...)`
  - `cleanup_plugin_stats()`
- Added runnable local bridge entrypoint:
  - `python -m terminal_agent.run_plugin_bridge`

## Current Semantics
- One plugin dispatch request now:
  - claims one available ammo target for an account
  - creates one NAS task carrying account/ammo/plugin metadata
  - binds the ammo target to the created task ID
- If task creation fails after ammo claim, the ammo target is released back to `available`.
- Default mainline execution still remains `claim_http`; this bridge only changes how plugin-originated work enters the task system.

## Verified
- `python -m nas_control_plane.demo_plugin_dispatch_task_flow`
- `python -m nas_control_plane.demo_plugin_task_result_ammo_lifecycle`
- `python -m nas_control_plane.demo_cli_plugin_runtime_views`
- `python -m nas_control_plane.demo_dashboard_plugin_runtime_observability`
- `python -m nas_control_plane.demo_plugin_dispatch_policy_controls`
- `python -m nas_control_plane.demo_cli_plugin_policy_views`
- `python -m terminal_agent.demo_plugin_login_success_remark_refresh`
- `python -m compileall nas_control_plane terminal_agent shared`

## Not Done Yet
- No plugin-side JS client package yet
- No dashboard live panel for campaign-specific controls yet

## Follow-up Update
- Plugin task result lifecycle is now coupled back into ammo state:
  - `completed` -> `consumed`
  - retryable/non-final failure -> remain `assigned`
  - final failure / cancel -> released back to `available`
- CLI text views now expose:
  - `plugin-creators`
  - `plugin-accounts`
  - `plugin-stats`
  - plugin/account/ammo fields inside task detail
- Dashboard source now exposes:
  - plugin runtime summary
  - creator/account/stat raw views
  - account status filter
  - cancel response compatibility after `/tasks/cancel` response shape change
- Policy controls now expose:
  - account status override
  - cooldown gating
  - action-level daily limit gating
  - campaign/copy bundle persistence
  - campaign copy injection into plugin-created task parameters

## Status Matrix
| Track | Sub-item | State | Verified | Notes |
| --- | --- | --- | --- | --- |
| Plugin inventory | creator inbox | done | yes | dedupe-capable intake behind NAS |
| Plugin inventory | ammo library | done | yes | available/assigned/consumed tracked |
| Plugin inventory | account inventory | done | yes | terminal/plugin capability tags stored |
| Plugin metrics | daily aggregate + 15-day retention | done | yes | aggregated rows only |
| Plugin dispatch | ammo -> task create | done | yes | `POST /plugin/dispatch` |
| Plugin lifecycle | success -> consume ammo | done | yes | result bridge landed |
| Plugin lifecycle | retryable failure holds ammo | done | yes | stays assigned |
| Plugin lifecycle | final failure / cancel releases ammo | done | yes | release reason persisted |
| Plugin policy | account cooldown / availability gate | done | yes | `account_unavailable` and `account_cooldown` enforced |
| Plugin policy | action daily limit gate | done | yes | `daily_limit_reached` enforced |
| Plugin policy | campaign/copy bundle storage | done | yes | persisted and queryable |
| Local plugin bridge | login-success -> BitBrowser remark refresh | done | yes | local HTTP bridge + runtime sync |
| Operator observability | CLI plugin runtime views | done | yes | creators/accounts/stats/task metadata |
| Operator observability | CLI campaign view | done | yes | `plugin-campaigns` text view |
| Operator observability | dashboard plugin runtime source markers | done | yes | source-level marker verification |
| Remaining gap | plugin-side JS client package | open | no | contract exists, implementation absent |
| Remaining gap | richer ammo/copy bundle management | open | no | later phase |
| Remaining gap | dashboard live panel for campaigns/policy reasons | open | no | current dashboard plugin panel remains raw/state-first |

## Next Step
- Add a stable plugin callback contract doc for local bridge and NAS dispatch endpoints.
- Extend dashboard from raw plugin state into campaign/policy-focused operator controls.
- Prepare final pre-manual-review bundle for plugin-runtime and fnOS deployment handoff.
