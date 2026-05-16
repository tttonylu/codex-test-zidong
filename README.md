# Codex Matrix BPlus

This repository is a standalone prototype for a matrix-style NAS and terminal-agent control plane.
It is not a drop-in replacement for older project directories.

## Current Scope

The prototype currently includes:

- NAS-side terminal and instance registry
- SQLite-backed task persistence
- task dispatch, running, result, cancel, and retry flows
- audit logs
- task event timeline
- aggregated task attempt views
- combined task diagnostic report view
- a minimal CLI for management queries and task controls

## Main Modules

- `nas_control_plane/`
  NAS-side HTTP server, persistence, task state, audit logs, and CLI
- `terminal_agent/`
  terminal runtime, BitBrowser adapter, NAS client, worker execution loop
- `shared/`
  protocol payloads shared by NAS and terminal sides
- `docs/`
  project structure and architecture notes

## Useful Commands

Run the NAS server:

```bash
python -m nas_control_plane.server
```

Use the CLI against a running NAS server:

```bash
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 summary
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 task-report --task-id task-1
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 cancel-task --task-id task-1 --reason "manual stop"
```

Run selected verification demos:

```bash
python -m nas_control_plane.demo_task_report
python -m nas_control_plane.demo_task_attempts
python -m terminal_agent.demo_execution_loop
```
