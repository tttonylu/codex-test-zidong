# Manual Dashboard Link Check

## Scope
- Confirm the deployed NAS dashboard opens correctly at `/` and shows the expected Chinese operator UI.
- Record the first visible manual verification state after seeded test data was added.

## Observed State
- Dashboard root opens normally on `http://192.168.0.100:3210/`.
- Chinese labels display correctly in the task, terminal, and plugin panels.
- `task-web-01` is visible in the task list.
- `task-web-queue-01` is visible in the task list.
- `terminal-web-01` is visible in the terminal list.
- The selected `task-web-queue-01` detail panel shows:
  - `dispatch mode = queue_pull`
  - `queue dispatch status = queued`
  - `queue dispatch accepted = true`
  - `queue topic = terminal.dispatch.terminal-web-01`
  - `terminal = terminal-web-01`

## Notes
- This check confirms the dashboard link path and the seeded task visibility.
- Further checks can continue from this state without re-seeding data unless the container is recreated.
