# Manual Review Checklist Before Dashboard And NAS Test

## Purpose
- Provide one short review path before manual dashboard verification and fnOS / NAS deployment testing.
- Focus only on the current mainline deltas that are easiest to regress silently.

## Review Entry Points
- Main review brief:
  - `docs/project-checkpoints/mainline-review-brief-terminal-concurrency-and-queue-skeleton-2026-05-18.md`
- Concurrency / recovery checkpoint:
  - `docs/project-checkpoints/terminal-concurrency-and-recovery-phase-2026-05-18.md`
- Queue boundary checkpoint:
  - `docs/project-checkpoints/queue-mode-skeleton-boundary-2026-05-18.md`
- Deployment checkpoint:
  - `docs/project-checkpoints/nas-control-plane-deployment-and-queue-next-phase-2026-05-18.md`

## Files To Inspect First
- terminal runtime / replay:
  - `terminal_agent/runtime/agent_loop.py`
  - `terminal_agent/runtime/terminal_runtime.py`
  - `terminal_agent/runtime/repositories.py`
  - `terminal_agent/runtime/store.py`
- NAS task semantics / query / dashboard:
  - `nas_control_plane/services/tasks.py`
  - `nas_control_plane/services/queue_dispatch.py`
  - `nas_control_plane/server.py`
  - `nas_control_plane/views.py`
  - `nas_control_plane/dashboard_html.py`
  - `nas_control_plane/cli.py`

## High-Risk Review Points
1. Durable result replay
- Result submit failure should persist into local `result_outbox`.
- Replay should happen before new claim work in the next cycle.
- Replay success should remove the outbox item.

2. Recovery ack semantics
- `/heartbeat` must return `accepted_recovered_task_ids` and `missing_recovered_task_ids`.
- terminal must only ack accepted ids locally.

3. Queue placeholder boundary
- `queue_pull` tasks must never be returned from `/tasks/claim`.
- normal HTTP claim cycle must not clear `queue_transport_inactive`.

4. Queue dispatch outcome observability
- `queue_pull` task create should record:
  - `queue_dispatch_status`
  - `queue_dispatch_accepted`
- these fields should be:
  - visible in task text summary
  - queryable through HTTP / CLI
  - visible in dashboard task detail
  - filterable in dashboard task toolbar

## Fast Verification Commands
- `python -m nas_control_plane.demo_pre_manual_review_bundle`
- `python -m terminal_agent.demo_result_submit_failure_retains_slot`
- `python -m nas_control_plane.demo_recovery_ack_partial_acceptance`
- `python -m terminal_agent.demo_recovery_ack_only_accepted_ids`
- `python -m nas_control_plane.demo_queue_task_inactive_wait_reason`
- `python -m nas_control_plane.demo_queue_dispatch_http_filters`
- `python -m nas_control_plane.demo_cli_queue_dispatch_filters`
- `python -m nas_control_plane.demo_queue_dispatch_observability`
- `python -m nas_control_plane.demo_dashboard_dispatch_observability`
- `python deploy/nas-control-plane/verify_deployment.py`

## Expected Signals
- bundle command:
  - returns one JSON object containing:
    - `result_outbox_replay`
    - `recovery_ack_partial`
    - `queue_dispatch_http_filters`
    - `dashboard_dispatch_markers`
    - `deployment_smoke`
- durable outbox demo:
  - failed cycle stores one outbox item
  - restart replay clears it
- recovery ack demo:
  - accepted ids and missing ids both present
- queue dispatch HTTP filter demo:
  - only queue task is returned
- queue dispatch CLI filter demo:
  - only queue task is shown
  - output contains `queue_dispatch_status` and `queue_dispatch_accepted`
- deployment smoke:
  - queue task create succeeds
  - queue dispatch outcome fields are present
  - dashboard queue dispatch filters are present

## Manual Dashboard Check When Requested Later
- Open `nas_control_plane.demo_dashboard_live_verify`
- Confirm the seeded `queue_pull` task is visible
- Confirm task detail shows:
  - `dispatch mode = queue_pull`
  - `queue dispatch status = queued`
  - `queue dispatch accepted = true`
- Confirm toolbar filters can narrow to that task by:
  - `dispatch_mode = queue_pull`
  - `queue_dispatch_status = queued`
  - `queue_dispatch_accepted = true`

## Notes
- Current live dashboard demo now uses dynamic free ports and prints the final dashboard URL.
- Current mainline still does not enable a real queue transport.
- Current manual test should treat queue fields as boundary/observability semantics, not active transport behavior.
