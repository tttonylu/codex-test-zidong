# Mainline Review Brief

## Scope
- Review the mainline after:
  - terminal true concurrent worker / slot model
  - terminal restart recovery / recovery handoff
  - pending-state split and retry-kind observability
  - fnOS NAS deployment skeleton
  - `claim_http | queue_pull` skeleton boundaries

## Current Mainline State
- Terminal execution still runs through the existing HTTP claim loop by default.
- Terminal slot concurrency, persistence, affinity, and restart recovery are already landed.
- NAS recovery reclaim / handoff / observability are already landed.
- `queue_pull` is no longer only a pure skeleton marker: it now has a NAS-backed local transport baseline with persisted delivery state, query coverage, and local claim/lease behavior.
- `claim_http` still remains the default active execution path.

## Status Matrix
| Area | Current State | Active In Mainline | Verified | Main Files | Remaining Gap |
| --- | --- | --- | --- | --- | --- |
| Terminal concurrent slots | landed | yes | yes | `terminal_agent/runtime/terminal_runtime.py`, `terminal_agent/runtime/agent_loop.py` | no new blocker in this phase |
| Slot persistence / restart recovery | landed | yes | yes | `terminal_agent/runtime/repositories.py`, `terminal_agent/runtime/store.py` | no new blocker in this phase |
| NAS recovery reclaim / handoff | landed | yes | yes | `nas_control_plane/services/tasks.py`, `nas_control_plane/server.py` | accepted-only ack landed |
| Pending-state split / retry kind | landed | yes | yes | `nas_control_plane/services/tasks.py`, `nas_control_plane/views.py` | no new blocker in this phase |
| Deployment skeleton for fnOS NAS | landed | yes | yes | `deploy/nas-control-plane/`, `nas_control_plane/Dockerfile` | still needs final human deployment pass on target NAS |
| `claim_http` dispatch path | landed | yes | yes | `terminal_agent/adapters/nas_client.py`, `nas_control_plane/services/tasks.py` | keep as default until queue transport is real |
| `queue_pull` task persistence/query | landed | no | yes | `shared/protocol/payloads.py`, `nas_control_plane/services/dispatch.py` | transport is inactive; inactive wait semantics now preserved |
| Queue provider contracts | landed | no | yes | `nas_control_plane/services/queue_dispatch.py`, `terminal_agent/runtime/queue_claim.py` | no real provider implementation; publish/ack/defer/lease hooks reserved |
| Queue task source placeholder | landed | no | yes | `terminal_agent/runtime/task_sources.py` | no real consumer |
| Queue observability in text/CLI/dashboard | landed | no | yes | `nas_control_plane/views.py`, `nas_control_plane/cli.py`, `nas_control_plane/dashboard_html.py` | still needs human UI review |
| Terminal slot observability on NAS | landed | yes | yes | `terminal_agent/runtime/terminal_runtime.py`, `nas_control_plane/server.py` | use dedicated NAS-side demo, not `demo_concurrent_slots` |

## Consolidated Status Matrix
| Track | Sub-item | State | Evidence | Notes |
| --- | --- | --- | --- | --- |
| Terminal execution | real concurrent slot pool | done | `terminal_agent.demo_concurrent_slots` | mainline behavior |
| Terminal execution | slot affinity | done | `terminal_agent.demo_slot_affinity_selection` | least-used fallback retained |
| Terminal execution | submit failure retention | done | `terminal_agent.demo_result_submit_failure_retains_slot` | durable outbox replay landed |
| Terminal recovery | local slot persistence | done | `terminal_agent.demo_slot_recovery_persistence` | unfinished slots recover on restart |
| Terminal recovery | accepted-only recovery ack | done | `nas_control_plane.demo_recovery_ack_partial_acceptance`, `terminal_agent.demo_recovery_ack_only_accepted_ids` | missing ids stay pending locally |
| NAS recovery | recovery requeue | done | `nas_control_plane.demo_terminal_recovery_requeue` | priority path active |
| NAS recovery | cross-terminal handoff | done | `nas_control_plane.demo_recovery_terminal_handoff` | recovery claim terminal visible |
| Queue skeleton | HTTP claim boundary | done | `nas_control_plane.demo_dispatch_mode_boundaries` | `queue_pull` excluded from `/tasks/claim` |
| Queue skeleton | inactive queue wait semantics | done | `nas_control_plane.demo_queue_task_inactive_wait_reason` | preserved across normal claim cycle |
| Queue skeleton | runtime source metadata reset | done | `terminal_agent.demo_http_claim_task_source_metadata_reset` | clears stale queue metadata |
| Queue skeleton | claim follow-up hooks | done | `terminal_agent.demo_queue_claim_provider_contract` | ack/defer/lease-extension contract reserved |
| Queue skeleton | dispatch publish semantics reserve | done | `nas_control_plane.demo_noop_queue_dispatch_provider` | retryable/wait_reason/provider markers reserved |
| Queue baseline | dispatch outcome observability | done | `nas_control_plane.demo_queue_dispatch_observability`, `nas_control_plane.demo_dispatch_mode_query_filters`, `nas_control_plane.demo_query_filters` | dispatch outcome fields queryable and visible |
| Queue baseline | boolean filter coercion | done | `nas_control_plane.demo_queue_dispatch_http_filters`, `nas_control_plane.demo_cli_queue_dispatch_filters` | no `is`-based bool filter leak |
| Queue baseline | lease expiry task redelivery sync | done | `nas_control_plane.demo_local_queue_lease_expiry_requeues_task` | expired lease requeues both delivery and task |
| Observability | dashboard dispatch controls | done | `nas_control_plane.demo_dashboard_dispatch_observability` | includes `filter-task-dispatch-mode` |
| Observability | NAS slot snapshot | done | `nas_control_plane.demo_terminal_slot_observability` | use dedicated NAS proof |
| Plugin runtime | creator/ammo/account/stats inventory | done | `nas_control_plane.demo_plugin_runtime_flow`, `nas_control_plane.demo_plugin_daily_stats_retention` | plugin-facing baseline landed |
| Plugin runtime | ammo -> task dispatch bridge | done | `nas_control_plane.demo_plugin_dispatch_task_flow` | plugin path can create mainline tasks |
| Plugin runtime | task result -> ammo lifecycle | done | `nas_control_plane.demo_plugin_task_result_ammo_lifecycle` | success consume / final fail release |
| Plugin runtime | local BitBrowser login-success bridge | done | `terminal_agent.demo_plugin_login_success_remark_refresh` | remark and identity refresh immediate |
| Plugin runtime | CLI/dashboard observability | done | `nas_control_plane.demo_cli_plugin_runtime_views`, `nas_control_plane.demo_dashboard_plugin_runtime_observability` | operator query surface present |
| Deployment | fnOS docker skeleton | done | `deploy/nas-control-plane/verify_deployment.py` | human deployment still pending |
| Remaining risk | queue delivery durability | open | doc-only | next phase item |
| Remaining risk | real queue transport | open | doc-only | keep `claim_http` default |

## What Is Already Landed
- Terminal concurrent slot execution and recovery:
  - `terminal_agent/runtime/terminal_runtime.py`
  - `terminal_agent/runtime/agent_loop.py`
  - `terminal_agent/runtime/repositories.py`
  - `terminal_agent/runtime/store.py`
- NAS recovery/retry/query/control:
  - `nas_control_plane/services/tasks.py`
  - `nas_control_plane/services/repositories.py`
  - `nas_control_plane/server.py`
  - `nas_control_plane/views.py`
  - `nas_control_plane/cli.py`
  - `nas_control_plane/dashboard_html.py`
- Queue skeleton boundaries:
  - `nas_control_plane/services/dispatch.py`
  - `nas_control_plane/services/queue_dispatch.py`
  - `terminal_agent/runtime/task_sources.py`
  - `terminal_agent/runtime/queue_claim.py`

## Verified
- compile:
  - `python -m compileall nas_control_plane terminal_agent shared deploy docs`
- concurrency / recovery demos:
  - `python -m terminal_agent.demo_concurrent_slots`
  - `python -m terminal_agent.demo_slot_affinity_selection`
  - `python -m terminal_agent.demo_slot_recovery_persistence`
  - `python -m terminal_agent.demo_slot_recovery_reset`
  - `python -m nas_control_plane.demo_recovery_priority_claim`
  - `python -m nas_control_plane.demo_terminal_recovery_requeue`
  - `python -m nas_control_plane.demo_recovery_terminal_handoff`
- deployment smoke:
  - `python deploy/nas-control-plane/verify_deployment.py`
- queue skeleton / observability demos:
  - `python -m nas_control_plane.demo_dispatch_mode_boundaries`
  - `python -m nas_control_plane.demo_dispatch_mode_query_filters`
- `python -m nas_control_plane.demo_noop_queue_dispatch_provider`
- `python -m nas_control_plane.demo_queue_dispatch_observability`
- `python -m nas_control_plane.demo_queue_task_inactive_wait_reason`
- `python -m nas_control_plane.demo_local_queue_lease_expiry_requeues_task`
- `python -m terminal_agent.demo_queue_pull_task_source_placeholder`
- `python -m terminal_agent.demo_queue_claim_provider_contract`
- `python -m terminal_agent.demo_http_claim_task_source_metadata_reset`
- `python -m terminal_agent.demo_result_submit_failure_retains_slot`
- `python -m nas_control_plane.demo_terminal_task_source_observability`
- `python -m nas_control_plane.demo_dashboard_dispatch_observability`
- `python -m nas_control_plane.demo_recovery_ack_partial_acceptance`
- `python -m terminal_agent.demo_recovery_ack_only_accepted_ids`
- `python -m nas_control_plane.demo_terminal_slot_observability`

## Explicit Non-Goals In Current Mainline
- No Redis integration
- No real queue consumer
- No publish/ack/lease transport behavior
- No switch away from current `claim_http` default execution loop
- No queue claim/ack/lease persistence implementation

## Review Focus
- Check that queue skeleton code does not alter the current `claim_http` execution semantics.
- Check that `queue_pull` tasks are persisted, queryable, and excluded from HTTP claim.
- Check that observability surfaces are consistent across:
  - text views
  - CLI filters
  - dashboard filters/details
  - runtime metadata
- Check that provider contracts are clean boundaries and not premature transport coupling.

## Pre-Manual-Review Entry
- Run the consolidated bundle first:
  - `python -m nas_control_plane.demo_pre_manual_review_bundle`
- Then use the focused manual hint:
  - `python -m nas_control_plane.demo_dashboard_manual_review_hint`
- When a live dashboard pass is needed, start:
  - `python -m nas_control_plane.demo_dashboard_live_verify`

## Expected Entry Signals
- bundle output should contain:
  - `result_outbox_replay`
  - `recovery_ack_partial`
  - `queue_dispatch_http_filters`
  - `dashboard_dispatch_markers`
  - `deployment_smoke`
- manual hint output should contain:
  - `start_command`
  - `review_checklist`
  - `expected_dispatch_mode = queue_pull`
  - `expected_queue_dispatch_status = queued`
  - `expected_queue_dispatch_accepted = true`
- live dashboard run should print a JSON line first with:
  - `dashboard_url`
  - `queue_task_id`
  - `queue_dispatch_status`

## Residual Risk
- Dashboard runtime behavior has source-level verification and deployment smoke coverage, but not a final human UI pass in this phase.
- The current queue path is a local transport baseline, not an external queue integration.
- Cross-process/external transport durability, dedupe, and visibility-timeout behavior still cannot be validated until a real provider is implemented.

## Related Docs
- `docs/project-checkpoints/terminal-concurrency-and-recovery-phase-2026-05-18.md`
- `docs/project-checkpoints/queue-mode-skeleton-boundary-2026-05-18.md`
- `docs/project-checkpoints/nas-control-plane-deployment-and-queue-next-phase-2026-05-18.md`
- `docs/project-checkpoints/dispatch-protocol-reserve-2026-05-18.md`
- `docs/project-checkpoints/real-queue-integration-remaining-work-2026-05-18.md`
