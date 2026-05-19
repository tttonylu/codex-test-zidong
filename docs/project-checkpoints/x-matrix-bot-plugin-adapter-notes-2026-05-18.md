# X-Matrix-Bot Plugin Adapter Notes

## Purpose
- Keep one editable copy of the browser plugin inside the current workspace.
- Point the plugin at the current NAS control plane and local plugin bridge instead of the old legacy backend.

## Working Copy
- Plugin source copied from:
  - `C:\codex-自动化\opencode\X-Matrix-Bot`
- Editable workspace copy:
  - `C:\codex-matrix-bplus\docs\vendor\X-Matrix-Bot`

## Current Wiring
- Default NAS base:
  - `http://192.168.0.100:3210`
- Default local bridge:
  - `http://127.0.0.1:54346`

## Compatibility Layer
- Old plugin identity reporting:
  - `/ext/user_id`
- Old plugin action log:
  - `/ext/action_log`
- These are now accepted by:
  - `terminal_agent/plugin_bridge.py`
- The bridge maps them into:
  - terminal runtime identity refresh
  - NAS instance sync
  - NAS plugin creator intake
  - NAS plugin daily action stats

## What Was Adjusted In The Plugin Copy
- `config.js`
  - default NAS address changed to `3210`
- `background.js`
  - default NAS address changed to `3210`
  - legacy `fetch_task` switched to `/plugin/creators`
  - legacy identity fallback switched to `/ext/user_id`
  - legacy action-log fallback switched to `/ext/action_log`
- `offscreen.js`
  - default NAS address changed to `3210`
- `options.js`
  - default NAS address changed to `3210`
- `content_id_extractor.js`
  - NAS fallback address changed to `3210`

## Manual Load Path
1. Open Chromium / Chrome / BitBrowser extension developer mode.
2. Load unpacked extension from:
   - `C:\codex-matrix-bplus\docs\vendor\X-Matrix-Bot`
3. Ensure local plugin bridge is running:
   - `python -m terminal_agent.run_plugin_bridge`
4. Ensure NAS control plane is reachable at:
   - `http://192.168.0.100:3210`

## Current Boundary
- This is a compatibility-first adapter pass.
- It is enough to connect the old plugin to the current mainline without rebuilding the entire plugin execution model today.
- The next deeper step is to replace more of the old plugin protocol with direct `/plugin/*` semantics instead of only relying on bridge compatibility.
