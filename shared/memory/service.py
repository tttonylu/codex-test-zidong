"""Workspace-scoped mem0 memory service.

Each workspace root directory gets an isolated .mem0/ storage
with its own Qdrant vector store and SQLite history database.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.configs import VectorStoreConfig

_MEM0_DIR = ".mem0"


def _find_workspace_root(marker_files: tuple[str, ...] = ("opencode.json", ".git", ".mem0")) -> Path:
    """Walk upward from cwd to find the workspace root."""
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        for marker in marker_files:
            if (parent / marker).exists():
                return parent
    return cwd


def _load_workspace_config(workspace_root: Path) -> dict[str, Any]:
    """Load .mem0/config.json. Auto-create one with defaults if missing."""
    config_path = workspace_root / _MEM0_DIR / "config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))

    # Auto-generate config for bare workspaces
    defaults = {
        "version": "1.0",
        "workspace": workspace_root.name,
        "description": "Auto-generated workspace memory config",
        "storage": {"qdrant_path": ".mem0/qdrant", "history_db": ".mem0/history.db"},
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(defaults, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return defaults


def _build_memory_config(workspace_root: Path) -> MemoryConfig:
    """Build a mem0 MemoryConfig scoped to the given workspace."""
    mem0_dir = workspace_root / _MEM0_DIR
    mem0_dir.mkdir(parents=True, exist_ok=True)

    # Ensure custom embedders are registered before mem0 imports
    import shared.memory.embedder  # noqa: F401 — registers LocalHashEmbedder

    config_data = _load_workspace_config(workspace_root)
    storage_cfg = config_data.get("storage", {})
    llm_cfg = config_data.get("llm", {})
    embedder_cfg = config_data.get("embedder", {})

    # Use workspace-local .mem0/config.json defaults if empty
    if not llm_cfg:
        llm_cfg = {
            "provider": "openai",
            "config": {
                "model": "deepseek-v4-pro",
                "openai_base_url": "https://thisis.best/v1",
                "api_key": os.environ.get("XMATRIX_API_TOKEN") or os.environ.get("OPENAI_API_KEY", "sk-placeholder"),
            },
        }
    if not embedder_cfg:
        embedder_cfg = {"provider": "local_hash", "config": {}}

    # Qdrant local path — scoped to this workspace
    qdrant_path = str(workspace_root / storage_cfg.get("qdrant_path", ".mem0/qdrant"))
    history_db = str(workspace_root / storage_cfg.get("history_db", ".mem0/history.db"))

    # Build configs
    vector_store = VectorStoreConfig(
        provider="qdrant",
        config={
            "path": qdrant_path,
            "on_disk": True,
        },
    )

    llm = None
    if llm_cfg.get("provider"):
        llm_config_raw: dict[str, Any] = dict(llm_cfg.get("config", {}))
        # Map base_url → openai_base_url for OpenAI-compatible backends
        if "base_url" in llm_config_raw and "openai_base_url" not in llm_config_raw:
            llm_config_raw["openai_base_url"] = llm_config_raw.pop("base_url")
        # Inherit API key from environment if not explicitly set
        if "api_key" not in llm_config_raw:
            llm_config_raw["api_key"] = os.environ.get("XMATRIX_API_TOKEN") or os.environ.get(
                "OPENAI_API_KEY", "sk-placeholder"
            )
        from mem0.llms.configs import LlmConfig

        llm = LlmConfig(provider=llm_cfg["provider"], config=llm_config_raw)

    embedder = None
    if embedder_cfg.get("provider"):
        provider = embedder_cfg["provider"]
        embedder_config_dict: dict[str, Any] = dict(embedder_cfg.get("config", {}))
        from mem0.embeddings.configs import EmbedderConfig

        # Use model_construct to bypass pydantic's provider allow-list
        # validation (needed for "local_hash" custom provider)
        embedder = EmbedderConfig.model_construct(provider=provider, config=embedder_config_dict)

    return MemoryConfig(
        vector_store=vector_store,
        llm=llm,
        embedder=embedder,
        history_db_path=history_db,
        version=config_data.get("version", "v1.1"),
    )


class WorkspaceMemoryService:
    """Workspace-scoped mem0 memory service.

    All memory data is stored in ``<workspace_root>/.mem0/``, keeping
    different workspaces fully isolated.

    Usage:
        memory = WorkspaceMemoryService()
        memory.add("User prefers dark mode", user_id="alice")
        results = memory.search("dark mode", user_id="alice")
    """

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        auto_init: bool = True,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve() if workspace_root else _find_workspace_root()
        self._mem: Memory | None = None
        if auto_init:
            self.initialize()

    # ── lifecycle ──────────────────────────────────────────────

    def initialize(self) -> None:
        """Lazily initialize the underlying mem0 Memory instance."""
        if self._mem is not None:
            return
        config = _build_memory_config(self._workspace_root)
        self._mem = Memory(config=config)

    @property
    def mem(self) -> Memory:
        """Access the underlying mem0 Memory instance (auto-initializes)."""
        if self._mem is None:
            self.initialize()
        assert self._mem is not None  # noqa: S101 — type-narrowing
        return self._mem

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    @property
    def mem0_dir(self) -> Path:
        return self._workspace_root / _MEM0_DIR

    def close(self) -> None:
        """Release resources held by the underlying memory store."""
        if self._mem is not None:
            self._mem.close()
            self._mem = None

    # ── CRUD ───────────────────────────────────────────────────

    def add(
        self,
        messages: str | list[dict[str, str]],
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
    ) -> dict[str, Any]:
        """Store a memory.

        Args:
            messages: A text string or list of message dicts
                (``[{"role": "user", "content": "..."}]``).
            user_id: Optional user/operator identifier.
            agent_id: Optional agent/component identifier
                (e.g. ``"nas"``, ``"terminal-t1"``).
            run_id: Optional run/session identifier.
            metadata: Arbitrary key-value metadata attached to the memory.
            infer: Whether to let the LLM extract structured memories
                from the messages. Set to ``False`` to store raw text.

        Returns:
            The created memory record (a dict with at least an ``id`` key).
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        return self.mem.add(
            messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
            infer=infer,
        )

    def search(
        self,
        query: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        top_k: int = 10,
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        """Search memories by semantic similarity.

        Args:
            query: Natural-language search query.
            user_id: Scope search to a specific user/operator.
            agent_id: Scope search to a specific agent/component.
            run_id: Scope search to a specific run/session.
            top_k: Maximum number of results.
            threshold: Minimum relevance score (0.0–1.0).

        Returns:
            A dict with a ``"results"`` list.
        """
        filters: dict[str, Any] = {}
        if user_id:
            filters["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = agent_id
        if run_id:
            filters["run_id"] = run_id
        return self.mem.search(query, top_k=top_k, filters=filters or None, threshold=threshold)

    def get_all(
        self,
        *,
        filters: dict[str, Any] | None = None,
        top_k: int = 50,
    ) -> list[dict[str, Any]]:
        """List all memories matching the given filters."""
        result = self.mem.get_all(filters=filters, top_k=top_k)
        return result.get("results", result) if isinstance(result, dict) else result

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Retrieve a single memory by its ID."""
        return self.mem.get(memory_id)

    def update(
        self,
        memory_id: str,
        data: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update an existing memory."""
        return self.mem.update(memory_id, data, metadata=metadata)

    def delete(self, memory_id: str) -> None:
        """Delete a single memory by its ID."""
        self.mem.delete(memory_id)

    def delete_all(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Delete all memories matching the given filters."""
        self.mem.delete_all(user_id=user_id, agent_id=agent_id, run_id=run_id)

    def reset(self) -> None:
        """Wipe all memories and reset the store."""
        self.mem.reset()

    # ── convenience helpers ────────────────────────────────────

    def remember_fact(
        self,
        fact: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a single fact as a memory (non-inferring).

        Use this for explicit, structured facts that don't need
        LLM extraction.
        """
        metadata = {"tags": tags or []}
        return self.add(
            fact,
            user_id=user_id,
            agent_id=agent_id,
            infer=False,
            metadata=metadata,
        )

    def search_by_tag(
        self,
        tag: str,
        *,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Search memories by a tag stored in metadata."""
        return self.get_all(filters={"tags": tag}, top_k=top_k)

    def query(
        self,
        text: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        top_k: int = 10,
        keyword_fallback: bool = True,
    ) -> list[dict[str, Any]]:
        """Hybrid query: vector search with keyword fallback.

        When the hash-based embedder is in use, this method falls
        back to keyword matching for better recall.  With a real
        embedding model (e.g., fastembed), the vector search alone
        is sufficient.

        Args:
            text: Search query text.
            user_id/agent_id: Scope filters.
            top_k: Maximum results.
            keyword_fallback: If True and vector results < top_k/2,
                supplement with keyword-matched memories.

        Returns:
            List of memory dicts, deduplicated.
        """
        vector_results = self.search(
            text,
            user_id=user_id,
            agent_id=agent_id,
            top_k=top_k,
        ).get("results", [])

        if not keyword_fallback or len(vector_results) >= top_k // 2:
            return vector_results

        # Keyword fallback: list all scoped memories and rank by overlap
        filters: dict[str, Any] = {}
        if user_id:
            filters["user_id"] = user_id
        if agent_id:
            filters["agent_id"] = agent_id
        try:
            candidates = self.get_all(filters=filters or None, top_k=500)
        except (ValueError, TypeError):
            return vector_results

        keywords = set(text.lower().split())
        scored: set[str] = {r.get("id", "") for r in vector_results}
        keyword_matches: list[tuple[int, dict[str, Any]]] = []
        for mem in candidates:
            mid = mem.get("id", "")
            if mid in scored:
                continue
            memory_text = str(mem.get("memory", "")).lower()
            score = sum(1 for kw in keywords if kw in memory_text)
            if score > 0:
                keyword_matches.append((-score, mem))

        keyword_matches.sort()
        for _, mem in keyword_matches:
            if len(vector_results) >= top_k:
                break
            vector_results.append(mem)

        return vector_results

    def count(self, *, filters: dict[str, Any] | None = None) -> int:
        """Count memories matching the given filters.

        Note: mem0 requires at least one of ``user_id``, ``agent_id``,
        or ``run_id`` in the filter.
        """
        if not filters:
            raise ValueError("count() requires at least one filter key: user_id, agent_id, or run_id")
        return len(self.get_all(filters=filters, top_k=10_000))

    def __enter__(self) -> WorkspaceMemoryService:
        self.initialize()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
