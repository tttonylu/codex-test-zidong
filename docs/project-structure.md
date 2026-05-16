# Project Structure

## Purpose

`codex-matrix-bplus` is a clean architecture workspace for the next-generation X-Matrix system.

This repository is not the old production project copied over as-is. Instead, it is a staging area for splitting the old coupled system into clearer layers with explicit responsibilities.

The current focus is:

- define architecture boundaries
- reserve module locations
- document shared concepts and data flow
- prepare for incremental implementation

## Architecture Overview

The target architecture is organized into four layers:

1. NAS control plane
2. terminal agent
3. instance runtime
4. script workers

Core control flow:

`NAS control plane -> terminal agent -> instance runtime -> script worker`

Core state flow:

`script worker -> instance runtime -> terminal agent -> NAS control plane`

## Repository Map

### `docs/`

Project-level architecture and reference notes.

- `architecture.md`: high-level layered architecture summary
- `bitbrowser-api.md`: BitBrowser API notes used by the terminal side
- `project-structure.md`: this document

### `nas_control_plane/`

The global control layer.

This module is meant to own cross-terminal coordination and persistent control logic. It should not directly manage local browser window details.

Planned responsibilities:

- terminal registry
- instance registry
- task dispatch
- audit logging
- strategy coordination

Subdirectories:

- `models/`: shared persistence-facing entities on the NAS side
- `services/`: orchestration and domain services on the NAS side

### `terminal_agent/`

The per-machine local control layer.

This module is intended to run on each controlled workstation and act as the local runtime coordinator between NAS, BitBrowser, native automation, and script execution.

Planned responsibilities:

- terminal registration
- BitBrowser instance scanning
- local instance mapping
- local task queue management
- script lifecycle control
- state reporting to NAS

Subdirectories:

- `runtime/`: local runtime core, schedulers, recovery, and state store
- `adapters/`: integration adapters for BitBrowser API, NAS client, and native host interfaces
- `models/`: terminal-local state models
- `scripts/`: executable worker definitions such as follow, chat, probe, and extract

### `shared/`

Cross-layer shared definitions.

This directory is reserved for definitions that should be used by both NAS and terminal-side modules.

Planned responsibilities:

- protocol payloads
- shared constants
- shared model contracts

Subdirectories:

- `protocol/`: register, heartbeat, snapshot, task assignment, and action result payload definitions

## Conceptual Layer Without a Dedicated Directory

`instance runtime` currently exists as an architectural concept rather than a top-level directory.

In this design, an instance runtime represents the execution unit for one managed account or one managed browser context. Its responsibilities currently sit across:

- `terminal_agent/runtime/`
- `terminal_agent/models/`
- `terminal_agent/scripts/`

If implementation complexity grows, this concept may later be extracted into a first-class package.

## Relationship To Legacy System

Two files in the repository mainly describe the previous system rather than the new target architecture:

- `LEGACY-README.md`
- `X-MATRIX-KB.md`

They are useful as reference material for:

- old deployment shape
- existing operational behavior
- BitBrowser integration details
- known incidents and pitfalls
- current production assumptions

These legacy documents should be treated as source material for migration, not as the final structure of this repository.

## Current Maturity

At the moment, this repository is mostly a design skeleton.

What already exists:

- top-level architecture direction
- layer boundaries
- reserved directories
- planned model and service categories

What is still missing:

- concrete code modules
- protocol definitions
- runtime implementations
- NAS API surface
- task execution workers

## Recommended Implementation Order

To turn this repository into a working system, the recommended order is:

1. define shared protocol payloads and core models
2. implement the minimal terminal agent runtime
3. implement the minimal NAS control plane endpoints
4. connect script workers after the control path is stable

### Phase 1: Shared Contracts

Start with `shared/protocol/` and the core models on both sides.

Suggested first entities:

- terminal
- instance
- task
- script run
- action result
- heartbeat

This phase should answer:

- what a terminal reports
- how an instance is identified
- how tasks are assigned
- how results are acknowledged

### Phase 2: Terminal Agent MVP

Build a minimum viable local agent that can:

- register itself
- send heartbeat
- scan BitBrowser instances
- produce instance snapshots
- receive simple tasks

### Phase 3: NAS Control Plane MVP

Build the smallest NAS-side service set that can:

- receive terminal registration
- store heartbeat and instance snapshots
- expose a basic terminal/instance view
- dispatch simple tasks

### Phase 4: Script Worker Integration

Only after the control loop is stable, plug in workers such as:

- follow worker
- chat worker
- probe worker
- extract worker

This keeps execution logic from becoming the place where architecture decisions get mixed together again.

## Practical Reading Order

For someone joining this repository, the best reading order is:

1. `README.md`
2. `docs/architecture.md`
3. `docs/project-structure.md`
4. `terminal_agent/README.md`
5. `nas_control_plane/README.md`
6. `shared/README.md`
7. `X-MATRIX-KB.md`
8. `LEGACY-README.md`

The first six explain the target design. The last two explain where the design came from.
