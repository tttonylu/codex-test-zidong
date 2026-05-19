# Plugin Script Runtime Inventory And Stats Baseline

## Goal
- Land the first plugin-script-facing runtime inventory surface behind the NAS control plane.
- Treat plugin interfaces as the primary contract for:
  - creator/blogger ID intake
  - ammo library storage and distribution
  - account inventory
  - daily action aggregation
  - 15-day retention cleanup

## Landed
- Added creator inbox model and persistence:
  - `CreatorInboxRecord`
  - `creator_inbox` state section
- Added ammo library model and persistence:
  - `AmmoTargetRecord`
  - `ammo_targets` state section
- Added account inventory model and persistence:
  - `AccountInventoryRecord`
  - `account_inventory` state section
- Added daily action aggregate model and persistence:
  - `DailyActionStatRecord`
  - `daily_action_stats` state section
- Added plugin runtime service:
  - `nas_control_plane.services.plugin_runtime.PluginRuntimeService`
- Added plugin-facing NAS endpoints:
  - `POST /plugin/report-creator`
  - `POST /plugin/ammo/add`
  - `POST /plugin/account/register`
  - `POST /plugin/ammo/claim`
  - `POST /plugin/ammo/consume`
  - `POST /plugin/action-log`
  - `POST /plugin/stats/cleanup`
  - `GET /plugin/creators`
  - `GET /plugin/ammo`
  - `GET /plugin/stats/daily`
- Added terminal-side client helpers in:
  - `terminal_agent.adapters.NasControlPlaneClient`

## Current Semantics
- Plugin scripts can report creator/blogger IDs into a dedupe-capable inbox.
- NAS can store ammo targets separately from task records and assign them to registered accounts.
- Plugin action reporting writes daily aggregated stats instead of unbounded per-event growth.
- Daily aggregated stats keep only the latest 15 days.
- This baseline is inventory/reporting-focused; it does not yet auto-generate mainline tasks from ammo claims.

## Verified
- `python -m nas_control_plane.demo_plugin_runtime_flow`
- `python -m nas_control_plane.demo_plugin_daily_stats_retention`
- `python -m compileall nas_control_plane terminal_agent shared`

## Not Done Yet
- No dashboard controls for plugin inventory
- No automatic `ammo -> task` dispatch bridge
- No plugin-side JS implementation against these endpoints yet
- No richer campaign/advert copy management yet
- No account cooldown / rate-limit policy yet

## Next Step
- Wire plugin-facing JS/reporting clients to these NAS endpoints.
- Add `ammo claim -> task create` bridge when plugin-side contracts are fixed.
- Add operator query views for creator inbox, account inventory, and daily stats.
