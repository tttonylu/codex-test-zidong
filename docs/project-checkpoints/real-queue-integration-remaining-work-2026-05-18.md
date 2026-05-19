# Real Queue Integration Remaining Work

## Current Boundary
- Mainline keeps `claim_http` as the only active execution path.
- `queue_pull` is currently a NAS-backed local transport baseline with:
  - persisted task mode
  - persisted delivery state
  - queue dispatch outcome query/filter coverage
  - local claim / ack / defer / lease baseline
  - provider boundary for future external transport

## Remaining Work Before Real Queue Mode Exists
1. External transport publish side
- replace or extend the local `QueueDispatchProvider` with a real external transport
- preserve `delivery_id` / `claim_lease_id` semantics
- define publish failure semantics and retry policy against the chosen transport

2. External transport consume side
- replace or extend the NAS-backed queue claim provider with a real external consumer
- preserve `TaskAssignmentPayload` mapping shape
- decide batch size / backpressure / idle polling semantics

3. Delivery semantics
- cross-process ack path
- external lease timeout / visibility timeout
- replay / dedupe rules
- duplicate result protection

4. Local durability
- terminal-side durable queue claim state persistence if required by the transport
- restart behavior for in-flight queue deliveries

5. Operator controls
- dashboard / CLI controls for queue-specific failures
- queue-specific diagnostics
- transport health visibility

## Rule For Next Phase
- Do not replace `claim_http` until the external transport path is minimally verifiable for publish, claim, ack, defer, lease, and replay semantics.
