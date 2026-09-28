"""Repository-map caching with explicit state invalidation for Safe Context Compaction (Stage 25).

Caches high-level repository structural facts (frameworks, top-level layout, test dirs,
entry points, conventions) keyed strictly by a deterministic repository-state digest.
Automatically invalidates when relevant source files change.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass
class RepositoryMapEntry:
    """Cached architectural and structural facts for a specific repo state."""

    manifest_digest: str
    language_and_framework: str = ""
    top_level_structure: list[str] = field(default_factory=list)
    test_directories: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)
    custom_facts: dict[str, Any] = field(default_factory=dict)
    cached_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RepositoryMapCache:
    """Deterministic cache for repository-level facts, bound to a file manifest digest.
    
    Hard safety requirement:
    Never serves a cached map across workspace modifications that change the manifest digest.
    """

    def __init__(self) -> None:
        self._cache: dict[str, RepositoryMapEntry] = {}
        self._current_valid_digest: str | None = None

    @staticmethod
    def compute_manifest_digest(manifest: Mapping[str, str]) -> str:
        """Computes a deterministic SHA-256 digest over normalized (path: fingerprint) pairs."""
        sorted_pairs = sorted((p.replace("\\", "/"), fp) for p, fp in manifest.items())
        serialized = "|".join(f"{p}:{fp}" for p, fp in sorted_pairs)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def set_current_state(self, manifest_digest: str) -> None:
        """Sets the currently active authoritative repo state digest."""
        if self._current_valid_digest != manifest_digest:
            # State has shifted
            self._current_valid_digest = manifest_digest

    def put_map(
        self,
        manifest_digest: str,
        language_and_framework: str = "",
        top_level_structure: list[str] | None = None,
        test_directories: list[str] | None = None,
        entry_points: list[str] | None = None,
        conventions: list[str] | None = None,
        custom_facts: dict[str, Any] | None = None,
    ) -> RepositoryMapEntry:
        """Stores a new repository-map entry keyed by manifest digest."""
        entry = RepositoryMapEntry(
            manifest_digest=manifest_digest,
            language_and_framework=language_and_framework,
            top_level_structure=list(top_level_structure or []),
            test_directories=list(test_directories or []),
            entry_points=list(entry_points or []),
            conventions=list(conventions or []),
            custom_facts=dict(custom_facts or {}),
        )
        self._cache[manifest_digest] = entry
        self._current_valid_digest = manifest_digest
        return entry

    def get_map(self, manifest_digest: str) -> RepositoryMapEntry | None:
        """Retrieves cached repository map if digest matches exactly."""
        # Only return if it matches both the requested digest AND current valid digest if set
        if self._current_valid_digest is not None and manifest_digest != self._current_valid_digest:
            return None
        return self._cache.get(manifest_digest)

    def is_valid(self, manifest_digest: str) -> bool:
        """Checks if a cached map exists and is current for the given digest."""
        if self._current_valid_digest is not None and manifest_digest != self._current_valid_digest:
            return False
        return manifest_digest in self._cache

    def invalidate(self, manifest_digest: str | None = None) -> None:
        """Invalidates cache entries. If digest given, invalidates that digest; otherwise invalidates all."""
        if manifest_digest is not None:
            self._cache.pop(manifest_digest, None)
            if self._current_valid_digest == manifest_digest:
                self._current_valid_digest = None
        else:
            self._cache.clear()
            self._current_valid_digest = None

    def size(self) -> int:
        """Returns number of cached digests."""
        return len(self._cache)
