"""Conservative and safe cleanup mechanism for Stage 27.

Enforces strict cleanup criteria:
1. Target must have recommended_action == HygieneAction.REMOVE
2. Target confidence >= 0.90
3. Target must NOT be in protected paths
4. Target must NOT be tracked in Git (prevent accidental tree mutation)
5. Target must NOT be referenced anywhere in the repository
6. Target must NOT be a frozen artifact or candidate package
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.diff_discipline.classifier import PROTECTED_PREFIXES
from local.diff_discipline.models import ArtifactFinding, HygieneAction


class SafeCleaner:
    """Safely and conservatively cleans removable development scratch artifacts."""

    def __init__(self, repo_root: Optional[str | Path] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    def is_safe_to_remove(self, finding: ArtifactFinding) -> tuple[bool, str]:
        """Validates whether a finding strictly meets all conservative safety criteria for removal."""
        norm_path = normalize_path(finding.path)

        # 1. Action check
        if finding.recommended_action != HygieneAction.REMOVE:
            return False, f"Action is {finding.recommended_action.value}, not REMOVE"

        # 2. Confidence check
        if finding.confidence < 0.90:
            return False, f"Confidence {finding.confidence:.2f} is below 0.90 threshold"

        # 3. Tracked check - never automatically remove tracked files!
        if finding.is_tracked:
            return False, "Tracked file cannot be automatically removed; requires manual git review"

        # 4. Reference check
        if finding.is_referenced:
            return False, "File is referenced within the codebase"

        # 5. Protected path check
        for prefix in PROTECTED_PREFIXES:
            if norm_path.startswith(prefix):
                return False, f"Path is under protected prefix '{prefix}'"

        # 6. Check root protected files
        if norm_path in ("AGENTS.md", "IMPULSE.md", "PLAN.md", "README.md", "pyproject.toml", ".gitignore"):
            return False, "Path is a root governance/configuration file"

        # All checks passed
        return True, "Safe to remove"

    def execute_cleanup(
        self,
        findings: list[ArtifactFinding],
        dry_run: bool = True,
    ) -> tuple[list[str], list[str]]:
        """Executes cleanup on qualifying findings.
        
        Returns:
            (removed_paths, skipped_paths)
        """
        removed: list[str] = []
        skipped: list[str] = []

        for finding in findings:
            safe, reason = self.is_safe_to_remove(finding)
            if not safe:
                skipped.append(f"{finding.path} ({reason})")
                continue

            full_path = self.repo_root / finding.path
            if not full_path.exists():
                skipped.append(f"{finding.path} (does not exist)")
                continue

            if dry_run:
                removed.append(f"[DRY RUN] {finding.path}")
            else:
                try:
                    if full_path.is_file() or full_path.is_symlink():
                        full_path.unlink()
                    elif full_path.is_dir():
                        full_path.rmdir()
                    removed.append(finding.path)
                except OSError as e:
                    skipped.append(f"{finding.path} (deletion error: {e})")

        return removed, skipped
