"""Bounded tool-call caching with state-keyed invalidation (Stage 26).

Provides BoundedToolCache:
- Caches safe read/observation tools (read_file, get_status, search_similar_code, get_code_neighbors, get_code_subgraph)
- Never caches mutations (edit_file, write_file) or submission (submit_patch)
- Cache keys include exact tool name, normalized arguments digest, and repository state ID
- Targeted invalidation: mutating a file invalidates only affected reads, status, and tests
- Strict capacity bounds with deterministic LRU eviction
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from local.budgeting.models import CacheEntry, CacheKey, ToolCallCategory
from local.budgeting.normalization import (
    classify_tool_category,
    compute_arguments_digest,
    normalize_arguments,
)
from local.context_compaction.fingerprints import normalize_path

# Tools explicitly permitted to be cached under unchanged state
SAFE_CACHEABLE_TOOLS = frozenset({
    "read_file",
    "get_status",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
})


class BoundedToolCache:
    """Run-scoped, bounded cache for safe read/observation tool outputs.
    
    Hard safety guarantees:
    - Mutations and submissions are strictly non-cacheable.
    - Cache keys strictly bind to the repository state digest.
    - Targeted invalidation on file mutation preserves unrelated static reads while
      instantly purging stale reads, repository status, and affected tests.
    """

    DEFAULT_MAX_ENTRIES = 200

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be at least 1, got {max_entries}")
        self.max_entries = max_entries
        # key_string -> CacheEntry
        self._cache: dict[str, CacheEntry] = {}
        self._access_seq: int = 0
        # Metrics counters
        self.hits_count = 0
        self.misses_count = 0
        self.evictions_count = 0
        self.invalidations_count = 0

    def make_cache_key(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        repository_state_id: str,
        index_version: str = "",
    ) -> CacheKey:
        """Constructs a deterministic, state-bound CacheKey."""
        clean_tool = tool_name.strip().lower()
        norm_args = normalize_arguments(clean_tool, arguments)
        args_digest = compute_arguments_digest(clean_tool, norm_args)
        target_path = norm_args.get("path") or norm_args.get("file_path") or ""

        return CacheKey(
            tool_name=clean_tool,
            arguments_digest=args_digest,
            repository_state_id=repository_state_id,
            target_path=normalize_path(target_path) if target_path else "",
            index_version=index_version,
        )

    def is_tool_cacheable(self, tool_name: str) -> bool:
        """Determines if a tool is eligible for bounded caching."""
        clean_tool = tool_name.strip().lower()
        category = classify_tool_category(clean_tool)
        if category in (ToolCallCategory.MUTATION, ToolCallCategory.SUBMISSION):
            return False
        return clean_tool in SAFE_CACHEABLE_TOOLS

    def get(self, key: CacheKey) -> Any | None:
        """Retrieves cached result if present and valid. Updates LRU access metadata."""
        if not self.is_tool_cacheable(key.tool_name):
            self.misses_count += 1
            return None

        key_str = key.to_string()
        entry = self._cache.get(key_str)
        if entry is not None:
            # Check state validity
            if entry.key.repository_state_id != key.repository_state_id:
                # State shifted: purge entry
                del self._cache[key_str]
                self.invalidations_count += 1
                self.misses_count += 1
                return None

            self._access_seq += 1
            setattr(entry, "_access_seq", self._access_seq)
            entry.last_accessed = datetime.now(timezone.utc).isoformat()
            entry.access_count += 1
            self.hits_count += 1
            return entry.result_payload

        self.misses_count += 1
        return None

    def put(
        self,
        key: CacheKey,
        result_payload: Any,
        associated_paths: list[str] | None = None,
    ) -> CacheEntry | None:
        """Stores a result payload in the cache. Evicts LRU if capacity exceeded."""
        if not self.is_tool_cacheable(key.tool_name):
            return None

        # Evict LRU if capacity reached and adding new key
        key_str = key.to_string()
        if key_str not in self._cache and len(self._cache) >= self.max_entries:
            self._evict_lru()

        paths = list(associated_paths or [])
        if key.target_path and key.target_path not in paths:
            paths.append(key.target_path)

        entry = CacheEntry(
            key=key,
            result_payload=result_payload,
            associated_paths=paths,
        )
        self._access_seq += 1
        setattr(entry, "_access_seq", self._access_seq)
        self._cache[key_str] = entry
        return entry

    def _evict_lru(self) -> None:
        """Evicts the least recently accessed cache entry."""
        if not self._cache:
            return
        # Find entry with oldest access sequence or timestamp
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: getattr(self._cache[k], "_access_seq", 0),
        )
        del self._cache[oldest_key]
        self.evictions_count += 1

    def invalidate_for_mutation(
        self,
        mutated_path: str,
        new_repository_state_id: str,
    ) -> int:
        """Performs targeted cache invalidation after a file modification.
        
        Invalidates:
        1. Any cached read_file on mutated_path
        2. Any get_status / repo tree cache
        3. Any entry whose associated_paths contains mutated_path
        
        Preserves:
        - Unrelated file reads on other paths
        
        Returns:
            Number of entries invalidated.
        """
        norm_mutated = normalize_path(mutated_path)
        to_delete: list[str] = []

        for key_str, entry in self._cache.items():
            # 1. Direct path match
            if entry.key.target_path and entry.key.target_path == norm_mutated:
                to_delete.append(key_str)
                continue

            # 2. Associated paths match
            if norm_mutated in entry.associated_paths:
                to_delete.append(key_str)
                continue

            # 3. get_status cache is invalidated because workspace changed
            if entry.key.tool_name == "get_status":
                to_delete.append(key_str)
                continue

            # 4. Old repository state digest for repo-wide tools
            if entry.key.tool_name in ("run_command", "search_similar_code", "get_code_subgraph", "get_code_neighbors") and entry.key.repository_state_id != new_repository_state_id:
                to_delete.append(key_str)
                continue

        for k in to_delete:
            del self._cache[k]

        count = len(to_delete)
        self.invalidations_count += count
        return count

    def invalidate_all(self) -> None:
        """Clears all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        self.invalidations_count += count

    def size(self) -> int:
        """Returns number of active cache entries."""
        return len(self._cache)
