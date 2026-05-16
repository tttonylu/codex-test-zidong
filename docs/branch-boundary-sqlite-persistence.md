# Branch Boundary: `codex/sqlite-persistence`

## Summary

This branch is no longer a narrow persistence experiment.
It has grown into an integrated NAS task-management slice that spans:

- NAS-side persistence
- NAS-side query and control APIs
- shared protocol contracts
- terminal-side worker execution structure
- CLI operations and diagnostics

It is still isolated from `main`, but it is already large enough to behave like a candidate subsystem branch rather than a small feature branch.

## What This Branch Owns

### 1. NAS persistence and state model

- SQLite storage and migrations
- repository implementations for terminals, instances, tasks, logs, and task events
- richer `TaskRecord` lifecycle fields such as:
  - `attempt_count`
  - `max_attempts`
  - `retryable`
  - `final`
  - `last_error_code`
  - `last_error_message`

### 2. NAS query and control surface

- management query endpoints for terminals, instances, tasks, and logs
- task control endpoints for:
  - `cancel`
  - `retry`
- task timeline, attempt aggregation, and combined report endpoints

### 3. Shared workflow semantics

- richer action result payloads
- retry/final/error-code semantics
- task-control payloads

### 4. Terminal-side task execution structure

- worker step tracking
- normalized browser actions
- action-plan validation
- structured worker failures and classification

### 5. Operator-facing tooling

- CLI for:
  - summary and state queries
  - task control
  - task creation from standardized action plans
  - task diagnostics with human-readable summaries

## What This Branch Does Not Own

These areas should not be expanded casually on this branch unless we intentionally decide to turn it into the primary integration branch.

### 1. Full product UI

There is no web management console yet.
This branch currently owns CLI diagnostics only.

### 2. General browser automation platform design

The branch supports a normalized action plan model, but it does not yet define a full long-term automation DSL or planner architecture.

### 3. Broad multi-domain orchestration

Current work is still tightly centered on:

- NAS control plane
- terminal agent execution
- BitBrowser-backed instance actions

It is not yet a complete orchestration framework for all future agent types.

### 4. Merge-ready mainline cleanup

This branch contains:

- many demos
- evolving docs
- architecture experiments

It should not be merged to `main` as one large block without a decomposition plan.

## Current Collision Risk With `main`

There is no direct branch conflict right now, but there is architectural overlap risk.

The risk comes from three facts:

1. It modifies NAS, shared protocol, and terminal execution together.
2. It defines lifecycle semantics, not just storage details.
3. It now contains operational tooling and diagnostics that look like product-facing behavior.

That means further unchecked growth will make this branch the de facto new mainline for task management.

## Recommended Boundary Going Forward

Treat `codex/sqlite-persistence` as an integration branch for one theme only:

- NAS task management and diagnostics

Within that theme, acceptable future work includes:

- report refinement
- diagnostics refinement
- task creation normalization
- retry/control semantics
- action-plan validation

Avoid adding unrelated product surfaces here, such as:

- a large web frontend
- unrelated scheduling systems
- non-task orchestration domains
- cross-cutting refactors outside NAS/task flow

## Recommended Next Split

If we want cleaner long-term integration, split future work into smaller branches after this point:

### Branch A: `nas/reporting`

Owns:

- report DTO cleanup
- CLI formatting
- log/task/attempt diagnostic summaries

### Branch B: `terminal/action-plans`

Owns:

- worker action-plan execution
- browser action adapters
- invalid-plan validation paths

### Branch C: `nas/web-console`

Owns:

- any future UI
- server routes needed only for browser presentation

## Suggested Decision

Do not keep expanding this branch indefinitely.

Best next move:

1. finish one more bounded slice if needed
2. treat this branch as a staging branch for NAS task-management architecture
3. start subsequent work in narrower follow-up branches
