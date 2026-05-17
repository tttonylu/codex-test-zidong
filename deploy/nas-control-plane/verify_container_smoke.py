"""Container-level smoke for the NAS control-plane compose deployment."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def _wait_for_health(url: str, timeout_seconds: int = 30) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"container smoke health check timed out: {last_error}")


def _load_env_file(env_path: Path) -> dict[str, str]:
    env_map: dict[str, str] = {}
    with env_path.open("r", encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                env_map[key.strip()] = value.strip()
    return env_map


def _inspect_container_env(container_name: str) -> dict[str, str]:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("docker executable not found")
    result = subprocess.run(
        [docker, "inspect", container_name, "--format", "{{json .Config.Env}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker inspect failed")
    env_items = json.loads(result.stdout.strip() or "[]")
    env_map: dict[str, str] = {}
    for item in env_items:
        if "=" in item:
            key, value = item.split("=", 1)
            env_map[key] = value
    return env_map


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    compose_dir = repo_root / "deploy" / "nas-control-plane"
    env_path = compose_dir / ".env"
    if not env_path.exists():
        raise SystemExit(f"missing compose env file: {env_path}")

    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=compose_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    env_map = _load_env_file(env_path)
    port = int(env_map.get("XMATRIX_NAS_PORT", "8765"))
    host = "127.0.0.1"
    health = _wait_for_health(f"http://{host}:{port}/healthz")
    with urlopen(f"http://{host}:{port}/dashboard", timeout=5) as response:
        dashboard_html = response.read().decode("utf-8")
    container_env = _inspect_container_env(env_map["XMATRIX_NAS_CONTAINER_NAME"])

    smoke = {
        "health_status": health.get("status"),
        "dashboard_contains_title": "NAS Web Console" in dashboard_html,
        "compose_project": env_map.get("COMPOSE_PROJECT_NAME"),
        "container_name": env_map.get("XMATRIX_NAS_CONTAINER_NAME"),
        "marker": container_env.get("XMATRIX_DEPLOYMENT_MARKER"),
        "marker_matches_env": container_env.get("XMATRIX_DEPLOYMENT_MARKER") == env_map.get("XMATRIX_DEPLOYMENT_MARKER"),
    }
    print(json.dumps(smoke, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
