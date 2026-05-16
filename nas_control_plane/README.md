# NAS Control Plane

This layer owns NAS-side coordination logic and persistence.
It does not directly manage local BitBrowser window details.

Current capabilities:

- terminal registry
- instance registry
- task dispatcher
- audit log
- SQLite-backed persistence
- management query API
- task control actions (`cancel`, `retry`)
- task event timeline
- task attempt aggregation
- combined task report view

## CLI

Use the built-in CLI against a running NAS server:

```bash
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 summary
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 tasks --status failed
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 task-events --task-id task-2
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 task-attempts --task-id task-2
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 task-report --task-id task-2
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 cancel-task --task-id task-1 --reason "manual stop"
python -m nas_control_plane.cli --base-url http://127.0.0.1:8765 retry-task --task-id task-2 --reason "retry after recovery"
```
