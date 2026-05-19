# BitBrowser Remark Refresh On Plugin Login

## Goal
- Ensure plugin-side account/login success can immediately refresh the BitBrowser window remark.
- Avoid relying on a later scan cycle to discover the new account identity.

## Landed
- Added local plugin-facing bridge:
  - `terminal_agent.plugin_bridge.create_plugin_bridge_server()`
- Added endpoint:
  - `POST /plugin/login-success`
- Current payload shape:
  - `browser_id`
  - `handle`
  - optional `remark`
  - optional `profile_id`

## Current Behavior
- Plugin reports login success to the local terminal bridge.
- Terminal immediately calls BitBrowser `remark/update`.
- Terminal immediately updates local `InstanceState`:
  - `handle`
  - `remark`
  - `profile_id`
- Terminal immediately syncs updated instance state to NAS.

## Verified
- `python -m terminal_agent.demo_plugin_login_success_remark_refresh`
- `python -m compileall terminal_agent nas_control_plane shared`

## Why This Matters
- Matrix-mode account switching can otherwise leave stale remark data behind.
- When an account is later limited, suspended, or banned, stale window identity makes traceability and cleanup much harder.

## Next Step
- Wire plugin JS / extension-side login-success event to this local bridge.
- Optionally add richer remark formatting once the final operator convention is fixed.
