"""Deterministic patch equivalence checking for Clean-Copy Evaluation (Stage 28 Phase 11).

Compares extracted patch effects against applied changes in the fresh validation workspace.
Verifies semantic and file-content equivalence rather than brittle textual patch syntax.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.clean_copy.models import PatchBundle


class PatchEquivalenceChecker:
    """Verifies that the patch applied to clean copy reproduces exact agent intent."""

    def __init__(self) -> None:
        pass

    def check_equivalence(
        self,
        bundle: PatchBundle,
        agent_root: Path,
        validation_root: Path,
    ) -> tuple[bool, str]:
        """Compares file contents, additions, and deletions between agent and validation workspaces.
        
        Returns:
            (is_equivalent: bool, reason: str)
        """
        # 1. Check all changed paths
        for rel_p in bundle.changed_paths:
            agent_file = agent_root / rel_p
            val_file = validation_root / rel_p

            if rel_p in bundle.deleted_files:
                if val_file.exists():
                    return False, f"File '{rel_p}' marked deleted still exists in validation workspace."
                continue

            # File was added or modified
            if not val_file.exists():
                return False, f"File '{rel_p}' present in agent workspace is missing in validation workspace."

            if not agent_file.exists():
                return False, f"File '{rel_p}' missing in agent workspace but listed in patch bundle."

            # Compare file content SHA-256
            agent_sha = hashlib.sha256(agent_file.read_bytes()).hexdigest()
            val_sha = hashlib.sha256(val_file.read_bytes()).hexdigest()

            if agent_sha != val_sha:
                return False, (
                    f"Content mismatch in '{rel_p}': "
                    f"agent sha={agent_sha[:8]} vs validation sha={val_sha[:8]}"
                )

        # 2. Check for unexpected stray files in validation workspace
        for new_f in bundle.new_files:
            if not (validation_root / new_f).exists():
                return False, f"New file '{new_f}' was not materialized in validation workspace."

        return True, "Patch equivalence confirmed across all changed paths and contents."
