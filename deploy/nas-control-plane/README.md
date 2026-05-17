# NAS Control Plane Deployment

## Target

- NAS target: 飞牛 OS / fnOS
- Deployment mode: 图形化 Docker / Compose
- Isolation rule: use a dedicated project name and dedicated container name so this control plane does not mix with any other NAS containers

## Identity

- Compose project: `codex_matrix_bplus_nas`
- Container: `codex-matrix-bplus-nas-control`
- Marker: `codex-matrix-bplus`

## Files

- `docker-compose.yml`
- `.env.example`

## First deployment

1. Copy `.env.example` to `.env`
2. Ensure the `data/` directory exists beside `docker-compose.yml`
3. In 飞牛 OS Docker UI, import this compose project from `deploy/nas-control-plane/docker-compose.yml`
4. Confirm the container name is still `codex-matrix-bplus-nas-control`
5. Start the stack and verify `/healthz`
6. Then perform one real write-path smoke check:
   - register one terminal
   - create one task
   - confirm the mounted state file is updated
7. Run the container-level smoke:
   - `python deploy/nas-control-plane/verify_container_smoke.py`
   - this will run `docker compose up -d --build` against the same compose project and container name
   - it does not automatically `down` the stack after the check

## Update rule

Do not rely on restart alone when compose fields changed.

Use a recreate flow in the Docker UI so environment, mounts, and image changes are actually applied.

## Design constraints

- NAS stays lightweight: API, state, dashboard, audit
- Heavy browser execution remains on terminal machines
- Persistent state is stored in the mounted `/data/state.json`
- Current container entrypoint runs the built-in Python HTTP server directly.
- If the NAS control plane later migrates to Flask/FastAPI, then switch the container runtime to Gunicorn/Uvicorn at that time rather than pretending WSGI is already in place.
- `verify_deployment.py` is a lightweight smoke script, not the final deployment acceptance gate.
- `verify_container_smoke.py` is a deployment-side smoke that mutates the existing compose stack; use it when you want to verify the built image and container env actually landed.
- `verify_deployment.py` now binds a random local port for each run. This avoids false negatives when a stale local NAS process is already occupying a previously hard-coded port such as `8793`.
- Current smoke also checks queue-boundary observability:
  - `queue_pull` task create returns `queue_dispatch_status` / `queue_dispatch_accepted`
  - HTTP query can filter by queue dispatch outcome
  - dashboard HTML contains queue dispatch filter controls
