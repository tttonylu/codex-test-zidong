"""Create .env, data dir, then docker compose up on NAS."""

import os
import sys
import time

import paramiko

HOST = "192.168.0.100"
USER = "qq409648402"
PASSWORD = "Qq254673346."
REMOTE_CODE = "/vol2/1000/codex"
COMPOSE_DIR = f"{REMOTE_CODE}/deploy/nas-control-plane"


def ssh_run(client, command, timeout=30, sudo=False):
    if sudo:
        escaped = command.replace("'", "'\\''")
        command = f"echo '{PASSWORD}' | sudo -S bash -c '{escaped}'"
    i, o, e = client.exec_command(command, timeout=timeout)
    exit_code = o.channel.recv_exit_status()
    return exit_code, o.read().decode(), e.read().decode()


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD)
print("✓ Connected")

# 1. Create .env
print("\n📝 Creating .env...")
env_content = """# Dedicated container identity for 飞牛 OS / fnOS deployment
COMPOSE_PROJECT_NAME=codex_matrix_bplus_nas
XMATRIX_NAS_CONTAINER_NAME=codex-matrix-bplus-nas-control
XMATRIX_DEPLOYMENT_MARKER=codex-matrix-bplus
XMATRIX_NAS_PORT=3210

# State volume mount inside the NAS workspace
XMATRIX_NAS_STATE_DIR=./data
XMATRIX_NAS_STATE_FILE=/data/state.json
"""
sftp = c.open_sftp()
with sftp.open(f"{COMPOSE_DIR}/.env", "w") as f:
    f.write(env_content)
print("  ✓ .env created")

# 2. Create data dir
ec, out, err = ssh_run(c, f"mkdir -p {COMPOSE_DIR}/data", sudo=True)
print(f"  ✓ data/ directory: exit={ec}")

# 3. Stop old container if running
print("\n🛑 Stopping old containers...")
for d in [f"{REMOTE_CODE}/nas-control-plane", COMPOSE_DIR]:
    ec, out, err = ssh_run(c, f"cd {d} && docker compose down 2>/dev/null; cd {d} && docker-compose down 2>/dev/null; echo done", sudo=True)
    print(f"  {d}: {out.strip()[:100]}")

# 4. Build and start new container
print("\n🐳 Building and starting new container...")
ec, out, err = ssh_run(c, f"cd {COMPOSE_DIR} && docker compose up -d --build", sudo=True, timeout=180)
print(f"  exit={ec}")
if out.strip():
    print(f"  stdout: {out.strip()[:500]}")
if err.strip():
    print(f"  stderr: {err.strip()[:500]}")
if ec != 0:
    print("  ❌ Build failed, aborting")
    sys.exit(1)

# 5. Wait for health
print("\n⏳ Waiting for container to be healthy...")
for i in range(15):
    time.sleep(4)
    ec, out, err = ssh_run(c, f"docker ps --filter name=codex-matrix-bplus-nas-control --format '{{{{.Names}}}}'", sudo=True)
    name = out.strip()
    if name:
        ec2, hout, herr = ssh_run(c, f"docker inspect --format='{{{{.State.Status}}}}' codex-matrix-bplus-nas-control", sudo=True)
        status = hout.strip()
        ec3, hout2, herr2 = ssh_run(c, f"docker inspect --format='{{{{.State.Health.Status}}}}' codex-matrix-bplus-nas-control 2>/dev/null || echo no_health", sudo=True)
        health = hout2.strip()
        print(f"  [{i+1}/15] Status={status} Health={health}")
        if status == "running" and (health == "healthy" or "no_health" in health):
            print("  ✓ Container is running!")
            break
    else:
        print(f"  [{i+1}/15] Waiting for container...")
        ec, out, err = ssh_run(c, f"docker ps -a --filter name=codex-matrix-bplus --format '{{{{.Names}}}} {{{{.Status}}}}'", sudo=True)
        if out.strip():
            print(f"    Found: {out.strip()}")

# 6. Verify
print("\n🔍 Verifying endpoints...")
time.sleep(3)
endpoints = [
    ("healthz", "http://127.0.0.1:8765/healthz"),
    ("blacklist", "http://127.0.0.1:8765/blacklist"),
    ("dashboard", "http://127.0.0.1:8765/dashboard | head -c 300"),
]
for name, url_cmd in endpoints:
    ec, out, err = ssh_run(c, f"curl -sf {url_cmd}", sudo=True, timeout=10)
    if ec == 0:
        print(f"  ✓ /{name}: {out.strip()[:200]}")
    else:
        # Try via host port
        url_3210 = url_cmd.replace("8765", "3210")
        ec, out, err = ssh_run(c, f"curl -sf {url_3210}", sudo=True, timeout=10)
        if ec == 0:
            print(f"  ✓ /{name} (port 3210): {out.strip()[:200]}")
        else:
            print(f"  ✗ /{name} failed")

print("\n✅ 部署完成！")
print(f"   http://192.168.0.100:3210/dashboard")
sftp.close()
c.close()
