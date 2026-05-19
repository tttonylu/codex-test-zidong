"""Quickstart demo for mem0 workspace memory integration.

Usage:
    python shared/memory/demo.py

Demonstrates:
1. WorkspaceMemoryService CRUD
2. Agent-scoped memory for NAS and Terminal
3. Search with filters
4. Context manager usage
"""

from __future__ import annotations

import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

from shared.memory import WorkspaceMemoryService


def banner(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


# ── Scenario: multi-agent memory ────────────────────────────

banner("1. Creating workspace memory service")
memory = WorkspaceMemoryService()
print(f"   Workspace: {memory.workspace_root.name}")

banner("2. NAS agent remembers facts about terminals")
for i, info in enumerate([
    ("terminal-t1", "Terminal T1: follow script success rate 94%, avg latency 2.3s"),
    ("terminal-t2", "Terminal T2: chat script success rate 88%, avg latency 1.7s"),
    ("terminal-t3", "Terminal T3: recently went offline due to OOM, restarted"),
]):
    tid, fact = info
    memory.remember_fact(
        fact,
        agent_id="nas",
        tags=[f"terminal-{i+1}", tid],
    )
    print(f"   ✓ Stored memory for {tid}")

banner("3. Terminal agents remember their own state")
for i, fact in enumerate([
    "Terminal T1 booted with 8 instances, 4 slots available",
    "Terminal T1 recovered 2 unfinished tasks from previous session",
]):
    memory.remember_fact(
        fact,
        agent_id="terminal:terminal-t1",
        tags=["boot", "terminal-t1"],
    )
    print(f"   ✓ Terminal memory {i+1} stored")

banner("4. Search by agent scope")
# Search within NAS memories — use query() for keyword fallback
nas_results = memory.query("high success rate follow", agent_id="nas", top_k=3)
print("   NAS search results:")
for r in nas_results:
    print(f"     • {r.get('memory', '')[:70]}")

# Search within terminal memories
term_results = memory.query("booted", agent_id="terminal:terminal-t1", top_k=3)
print("   Terminal search results:")
for r in term_results:
    print(f"     • {r.get('memory', '')[:70]}")

banner("5. List all memories by agent")
for agent in ["nas", "terminal:terminal-t1"]:
    count = memory.count(filters={"agent_id": agent})
    print(f"   {agent}: {count} memories")

banner("6. Context manager (auto close)")
memory.close()
with WorkspaceMemoryService() as mem_ctx:
    mem_ctx.remember_fact("Context-managed fact", agent_id="ctx_demo")
    c = mem_ctx.count(filters={"agent_id": "ctx_demo"})
    print(f"   Context manager OK: {c} memories")
    mem_ctx.delete_all(agent_id="ctx_demo")

banner("7. Cleanup demo memories")
memory2 = WorkspaceMemoryService()
memory2.delete_all(agent_id="nas")
memory2.delete_all(agent_id="terminal:terminal-t1")
print("   All demo memories cleaned")
memory2.close()

banner("✓ All quickstart demos passed!")
