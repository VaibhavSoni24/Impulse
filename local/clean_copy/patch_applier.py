"""Fresh patch application subsystem for Clean-Copy Evaluation (Stage 28 Phase 10).

Applies an extracted PatchBundle to a second, fresh CleanRepositorySnapshot.
Guarantees:
- Validation workspace begins from identical clean baseline commit
- Rejects conflicting or corrupt patches (classified as PATCH_APPLY_CONFLICT)
- Verifies post-application file existence and deletions
- Never executes in dirty workspace
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.clean_copy.models import PatchBundle
from local.clean_copy.snapshot import CleanRepositorySnapshot


class PatchApplicationError(Exception):
    """Raised when patch application to clean validation workspace fails."""


class FreshPatchApplier:
    """Applies patch bundles to fresh validation workspaces and verifies integrity."""

    def __init__(self) -> None:
        pass

    def apply_patch(
        self,
        workspace: CleanRepositorySnapshot,
        bundle: PatchBundle,
    ) -> tuple[bool, str, str]:
        """Applies PatchBundle to the validation workspace.
        
        Returns:
            (success: bool, status_message: str, applied_diff: str)
        """
        if not bundle.tracked_diff.strip():
            return True, "NO_CHANGES", ""

        # 1. Verify validation workspace is initially clean
        if not workspace.is_clean():
            raise PatchApplicationError(
                "Validation workspace is not clean prior to patch application."
            )

        # 2. Write patch to a temporary file
        patch_file = workspace.workspace_dir / ".impulse_eval_patch.diff"
        patch_file.write_text(bundle.tracked_diff, encoding="utf-8")

        try:
            # 3. Test apply with --check first
            check_res = workspace.run_git(
                ["apply", "--whitespace=nowarn", "--check", str(patch_file.name)],
                check=False,
            )
            if check_res.returncode != 0:
                err_msg = check_res.stderr.strip() or check_res.stdout.strip()
                return False, f"PATCH_APPLY_CONFLICT: {err_msg}", ""

            # 4. Perform actual apply
            apply_res = workspace.run_git(
                ["apply", "--whitespace=nowarn", str(patch_file.name)],
                check=False,
            )
            if apply_res.returncode != 0:
                err_msg = apply_res.stderr.strip() or apply_res.stdout.strip()
                return False, f"PATCH_APPLY_CONFLICT: {err_msg}", ""

        finally:
            # Clean up the temporary patch file so it doesn't pollute the diff
            if patch_file.exists():
                patch_file.unlink()

        # 5. Capture resulting diff in validation workspace (including new files via add -N)
        workspace.run_git(["add", "-N", "."], check=True)
        res_diff = workspace.run_git(["diff", "HEAD"], check=True)
        applied_diff = res_diff.stdout.replace("\r\n", "\n")

        # 6. Verify expected files and deletions
        root = workspace.workspace_dir
        for new_f in bundle.new_files:
            if not (root / new_f).exists():
                return False, f"Expected new file '{new_f}' was not created by patch application.", ""

        for del_f in bundle.deleted_files:
            if (root / del_f).exists():
                return False, f"Expected deleted file '{del_f}' still exists after patch application.", ""

        return True, "APPLIED", applied_diff
