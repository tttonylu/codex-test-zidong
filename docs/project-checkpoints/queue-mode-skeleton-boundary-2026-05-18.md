# Queue Mode Skeleton Boundary

## Goal
- Add the next-stage `claim_http | queue_pull` service boundary without introducing Redis or any real queue transport yet.

## Landed
- Added NAS dispatch helpers:
  - `nas_control_plane/services/dispatch.py`
  - `normalize_dispatch_mode()`
  - `dispatch_mode_descriptor()`
  - `task_uses_http_claim()`
- `TaskDispatchService.create_task()` now normalizes and persists `dispatch_mode`.
- `TaskDispatchService.claim_tasks()` now only exposes tasks whose dispatch mode is compatible with HTTP claim.
- Added terminal-side task source boundary:
  - `terminal_agent/runtime/task_sources.py`
  - `TaskSource`
  - `HttpClaimTaskSource`
  - `QueuePullTaskSource` (no-op placeholder)
- Added explicit future queue provider contracts:
  - `nas_control_plane/services/queue_dispatch.py`
  - `QueueDispatchProvider`
  - `NoopQueueDispatchProvider`
  - dispatch result reserve:
    - `retryable`
    - `wait_reason`
    - `details.provider`
  - `terminal_agent/runtime/queue_claim.py`
  - `QueueClaimProvider`
  - `NoopQueueClaimProvider`
  - queue consumer follow-up actions:
    - `ack_delivery()`
    - `defer_delivery()`
    - `extend_claim_lease()`
- `TerminalAgentLoop` no longer hardcodes NAS claim logic internally; it now consumes a pluggable task source while keeping current behavior unchanged by default.
- Terminal runtime persistence now preserves queue-related assignment fields during slot recovery reload.
- Operator-facing task text views now render `dispatch_path`.
- Operator-facing task text views now render `queue_dispatch_status` and `queue_dispatch_accepted`.
- Dashboard task details now render `dispatch mode`, `dispatch path`, `queue topic`, `delivery ID`, and `claim lease ID`.
- Dashboard task filters now include `queue_dispatch_status` and `queue_dispatch_accepted`.
- Dashboard terminal details now render `task source mode`, `task source status`, and `task source queue topic`.
- task queries now support `dispatch_mode`, `queue_dispatch_status`, and `queue_dispatch_accepted` filtering across service, HTTP API, CLI, and dashboard filter controls.

## Verified
- `queue_pull` tasks remain persisted and queryable.
- `queue_pull` tasks are not returned by NAS HTTP claim.
- `queue_pull` inactive semantics now survive normal HTTP claim cycles.
- existing terminal polling flow still uses `HttpClaimTaskSource` and remains compatible with current mainline behavior.
- `QueuePullTaskSource` reports `task_source_status = not_implemented` and does not accidentally claim work.
- queue claim provider contract now reserves ack / defer / lease-extension hooks without activating real transport behavior.
- Dashboard source/dispatch observability markers are present in the shipped HTML.
- `dispatch_mode=claim_http|queue_pull` can be filtered directly from task queries.
- queue placeholder behavior is now routed through explicit provider contracts instead of being hardcoded inside the task source.
- queue dispatch provider contract now reserves publish-side `retryable` / `wait_reason` semantics before any real transport is enabled.
- queue task records now carry explicit provider dispatch outcome fields even before real transport exists.
- queue tasks now carry explicit inactive semantics while transport is not implemented.
- HTTP task source explicitly rewrites task-source runtime metadata back to `claim_http`.
- failed result submission now persists a local durable result outbox item for later replay.
- heartbeat recovery ack now only clears `accepted_recovered_task_ids`, not every recovered id in a successful response.

## Demo
- `python -m nas_control_plane.demo_dispatch_mode_boundaries`
- `python -m terminal_agent.demo_queue_pull_task_source_placeholder`
- `python -m nas_control_plane.demo_dashboard_dispatch_observability`
- `python -m nas_control_plane.demo_dispatch_mode_query_filters`
- `python -m nas_control_plane.demo_noop_queue_dispatch_provider`
- `python -m nas_control_plane.demo_queue_dispatch_observability`
- `python -m terminal_agent.demo_queue_claim_provider_contract`
- `python -m nas_control_plane.demo_queue_task_inactive_wait_reason`
- `python -m terminal_agent.demo_http_claim_task_source_metadata_reset`
- `python -m terminal_agent.demo_result_submit_failure_retains_slot`
- `python -m nas_control_plane.demo_recovery_ack_partial_acceptance`
- `python -m terminal_agent.demo_recovery_ack_only_accepted_ids`

## Not Done Yet
- No Redis transport
- No queue consumer
- No ACK / lease timeout implementation
- No queue-backed terminal loop wiring beyond the explicit placeholder source
- No real queue dispatch implementation behind the provider contracts
- no durable queue-delivery claim/ack persistence yet

## Next Step
- Keep current mainline on `claim_http` while preserving the queue contracts as inactive boundaries.
- When real queue transport is introduced later, wire it behind:
  - `nas_control_plane.services.queue_dispatch.QueueDispatchProvider`
  - `terminal_agent.runtime.queue_claim.QueueClaimProvider`
- Add only the minimum transport-specific pieces next time:
  - publish
  - claim/consume
  - ack/lease timeout
  - replay/dedupe

## Related Docs
- `docs/project-checkpoints/mainline-review-brief-terminal-concurrency-and-queue-skeleton-2026-05-18.md`
- `docs/project-checkpoints/real-queue-integration-remaining-work-2026-05-18.md`
