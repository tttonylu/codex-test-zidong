# Local Queue Transport Baseline

## Goal
- Land the first real `queue_pull` transport semantics without introducing Redis or any external queue dependency.
- Keep `claim_http` as the default active mainline path while making `queue_pull` executable behind an explicit NAS-backed local transport.

## Landed
- Added NAS-persisted queue delivery model:
  - `nas_control_plane.models.QueueDeliveryRecord`
- Added NAS queue delivery persistence:
  - `queue_deliveries` state section
  - `nas_control_plane.services.repositories.QueueDeliveryRepository`
- Added NAS local queue transport service:
  - `nas_control_plane.services.queue_transport.QueueDeliveryTransportService`
  - publish
  - claim
  - ack
  - defer
  - lease extend
  - lease expiry requeue
- Added real queue dispatch provider over the local transport:
  - `nas_control_plane.services.queue_dispatch.LocalQueueDispatchProvider`
- Wired NAS HTTP endpoints for queue transport:
  - `POST /queue/claim`
  - `POST /queue/ack`
  - `POST /queue/defer`
  - `POST /queue/lease/extend`
- Added terminal-side NAS queue claim provider:
  - `terminal_agent.runtime.queue_claim.NasQueueClaimProvider`
- Worker result payloads now carry:
  - `delivery_id`
  - `claim_lease_id`
  - `details.queue_topic`
  so NAS result handling can finalize queue deliveries.

## Current Semantics
- `claim_http` remains the default execution path.
- `queue_pull` task create now uses a real local queue transport when the standard NAS server is used.
- Queue delivery state is persisted on NAS and survives normal service operations.
- Queue claim returns real assignments with:
  - `dispatch_mode = queue_pull`
  - `delivery_id`
  - `claim_lease_id`
- Successful task result submission acks the claimed delivery on NAS.
- Expired claimed deliveries return to `queued` and can be reclaimed with a new lease.

## Verified
- `python -m nas_control_plane.demo_local_queue_transport_roundtrip`
- `python -m nas_control_plane.demo_local_queue_lease_expiry`
- `python -m compileall nas_control_plane terminal_agent shared`

## Not Done Yet
- No Redis or external queue backend
- No multi-consumer fairness tuning
- No queue-specific dead-letter policy
- No queue-delivery durable replay on terminal side beyond existing result outbox
- No switch of default mainline execution from `claim_http` to `queue_pull`

## Next Step
- Keep `claim_http` as default while expanding queue transport from local NAS-backed baseline to a real external provider only after:
  - publish semantics
  - claim semantics
  - ack / defer / lease semantics
  - recovery / replay semantics
  are all re-verified against this baseline.
