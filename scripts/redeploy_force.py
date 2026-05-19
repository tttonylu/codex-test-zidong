"""Re-deploy: force upload and rebuild on NAS."""

import os
import sys
import time

import paramiko

HOST = "192.168.0.100"
USER = "qq409648402"
PASSWORD = "Qq254673346."
REMOTE_ROOT = "/vol2/1000/codex"
COMPOSE_DIR = f"{REMOTE_ROOT}/deploy/nas-control-plane"
CONTAINER_NAME = "codex-matrix-bplus-nas-control"

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

# Upload changed files
print("\n📤 Uploading files...")
sftp = c.open_sftp()

def upload_file(local, remote):
    """Upload one file, creating remote dirs if needed."""
    remote = remote.replace("\\", "/")
    remote_dir = os.path.dirname(remote).replace("\\", "/")
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parts = remote_dir.split("/")
        path = ""
        for part in parts:
            path += "/" + part
            try:
                sftp.stat(path)
            except FileNotFoundError:
                sftp.mkdir(path)
    sftp.put(local, remote)
    sys.stdout.write(".")
    sys.stdout.flush()

# Upload specific changed files
files_to_upload = [
    "nas_control_plane/server.py",
    "nas_control_plane/dashboard_html.py",
    "nas_control_plane/services/store.py",
    "nas_control_plane/services/repositories.py",
    "nas_control_plane/services/__init__.py",
    "nas_control_plane/models/core.py",
    "nas_control_plane/models/__init__.py",
]

for rel_path in files_to_upload:
    local = os.path.join(LOCAL_ROOT, rel_path)
    remote = os.path.join(REMOTE_ROOT, rel_path).replace("\\", "/")
    if os.path.exists(local):
        upload_file(local, remote)

sftp.close()
print("\n  ✓ All files uploaded")

# Verify the edit is on NAS
print("\n📝 Verifying key line on NAS...")
ec, out, err = ssh_run(c, f"grep -c 'common_params' {REMOTE_ROOT}/nas_control_plane/server.py", timeout=10)
if "1" in out or "2" in out:
    print("  ✓ common_params found in server.py")
else:
    ec2, out2, err2 = ssh_run(c, f"grep 'parameters=dict' {REMOTE_ROOT}/nas_control_plane/server.py", timeout=10)
    print(f"  ⚠ Checking alternatives: {out2.strip()[:200]}")
    # Check file size
    ec3, out3, err3 = ssh_run(c, f"wc -l {REMOTE_ROOT}/nas_control_plane/server.py", timeout=10)
    print(f"    Lines: {out3.strip()}")

# Force rebuild with no cache
print("\n🐳 Rebuilding (no cache)...")
ec, out, err = ssh_run(c, f"cd {COMPOSE_DIR} && docker compose build --no-cache", timeout=180, sudo=True)
print(f"  exit={ec} stdout={out.strip()[:200]} stderr={err.strip()[:200]}")
if ec != 0:
    print("  ❌ Build failed")
    sys.exit(1)

# Restart
print("🔄 Restarting container...")
ec, out, err = ssh_run(c, f"cd {COMPOSE_DIR} && docker compose down", timeout=30, sudo=True)
ec, out, err = ssh_run(c, f"cd {COMPOSE_DIR} && docker compose up -d", timeout=30, sudo=True)
print(f"  exit={ec}")

# Wait for health
print("⏳ Waiting for healthy...")
for i in range(12):
    time.sleep(5)
    ec, out, err = ssh_run(c, f"docker inspect --format='{{{{.State.Health.Status}}}}' {CONTAINER_NAME} 2>/dev/null || echo no_container", timeout=10, sudo=True)
    health = out.strip()
    print(f"  [{i+1}/12] {health}")
    if health == "healthy":
        break

# Verify
print("\n🔍 Final verification...")
ec, out, err = ssh_run(c, "curl -sf http://127.0.0.1:8765/healthz", timeout=10, sudo=True)
print(f"  /healthz: {out.strip()[:100]}")

# Verify dispatch_origin filter fix
ec, out, err = ssh_run(c, "grep 'dispatch_origin not in' /vol2/1000/codex/nas_control_plane/server.py", timeout=10)
print(f"  dispatch_origin filter: {out.strip()[:200]}")

# Check common_params
ec, out, err = ssh_run(c, "grep -c 'nas_direct' /vol2/1000/codex/nas_control_plane/server.py", timeout=10)
print(f"  nas_direct references: {out.strip()}")

print("\n✅ Done!")
c.close()
