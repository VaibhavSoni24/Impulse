"""Lightweight referential safety checker for Stage 27.

Inspects repository files to verify whether a candidate artifact is referenced
by code, configuration, markdown docs, tests, or packaging manifests.
Prevents accidental deletion of legitimate fixtures or files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Set

from local.context_compaction.fingerprints import normalize_path

TEXT_EXTENSIONS = {
    ".py", ".yaml", ".yml", ".json", ".md", ".txt", ".rst", ".sh", ".toml"
}

IGNORED_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", ".idea", ".vscode"
}


class ReferenceChecker:
    """Lightweight repository reference scanner to ensure referential safety."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self._content_cache: dict[str, str] = {}
        self._initialized: bool = False

    def build_cache(self, candidate_files: Optional[list[str]] = None) -> None:
        """Loads and caches text contents of repo files for reference inspection."""
        if self._initialized:
            return

        for root, dirs, files in os.walk(self.repo_root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for f in files:
                ext = Path(f).suffix.lower()
                if ext in TEXT_EXTENSIONS:
                    full_p = Path(root) / f
                    rel_p = normalize_path(full_p.relative_to(self.repo_root))
                    try:
                        # Read text safely (skip large binary or unreadable files)
                        if full_p.stat().st_size <= 2_000_000:
                            self._content_cache[rel_p] = full_p.read_text(
                                encoding="utf-8", errors="ignore"
                            )
                    except (OSError, UnicodeDecodeError):
                        continue

        self._initialized = True

    def get_referencing_files(self, target_path: str) -> list[str]:
        """Returns all repo-relative file paths that reference target_path."""
        self.build_cache()
        norm_target = normalize_path(target_path)
        target_name = Path(norm_target).name
        target_stem = Path(norm_target).stem

        # Search patterns
        # 1. Exact relative path: e.g. "tests/fixtures/compaction_fixtures.py"
        # 2. File basename: e.g. "compaction_fixtures.py"
        # 3. Python module path: e.g. "compaction_fixtures" (only if length >= 4)
        referencing: list[str] = []

        for rel_p, content in self._content_cache.items():
            # Exclude self-reference
            if rel_p == norm_target:
                continue

            # Exact path match
            if norm_target in content:
                referencing.append(rel_p)
                continue

            # Target filename match
            if target_name in content:
                referencing.append(rel_p)
                continue

            # If it's a python module stem (like 'compaction_fixtures')
            if len(target_stem) >= 6 and target_stem in content:
                referencing.append(rel_p)

        return referencing

    def is_referenced(self, target_path: str) -> bool:
        """Returns True if the target_path is referenced anywhere in the repository."""
        return len(self.get_referencing_files(target_path)) > 0
