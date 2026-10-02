"""Invariant checker for HYGIENE regressions (Stage 45 Phase 5).

Covers:
- REG-HYGIENE-001: Temporary files left behind detected and removed by diff hygiene discipline.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.diff_discipline.cleaner import SafeCleaner
from local.diff_discipline.detectors import detect_log_file, detect_scratch_file
from local.diff_discipline.models import ArtifactClass, HygieneAction


def check_temporary_file_hygiene() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-HYGIENE-001: Temporary scratch files and logs are detected and slated for removal."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create simulated scratch files and debug logs
        scratch_file = tmp_path / "scratch_work.py"
        scratch_file.write_text("print('temporary debug')\n", encoding="utf-8")

        temp_patch = tmp_path / "temp.patch"
        temp_patch.write_text("--- a/foo\n+++ b/foo\n", encoding="utf-8")

        debug_log = tmp_path / "test_execution.log"
        debug_log.write_text("DEBUG: test failure stack trace\n", encoding="utf-8")

        # 2. Test detectors
        f_scratch = detect_scratch_file(str(scratch_file), is_tracked=False, is_referenced=False)
        if not f_scratch or f_scratch.recommended_action != HygieneAction.REMOVE:
            raise RegressionExecutionError(
                f"REG-HYGIENE-001 violation: Scratch file not flagged for REMOVE: {f_scratch}"
            )
        if f_scratch.artifact_class != ArtifactClass.SCRATCH_ARTIFACT:
            raise RegressionExecutionError(
                f"REG-HYGIENE-001 violation: Expected SCRATCH_ARTIFACT, got {f_scratch.artifact_class}"
            )

        f_patch = detect_scratch_file(str(temp_patch), is_tracked=False, is_referenced=False)
        if not f_patch or f_patch.recommended_action != HygieneAction.REMOVE:
            raise RegressionExecutionError(
                f"REG-HYGIENE-001 violation: Temp patch not flagged for REMOVE: {f_patch}"
            )

        f_log = detect_log_file(str(debug_log), is_tracked=False)
        if not f_log or f_log.recommended_action != HygieneAction.REMOVE:
            raise RegressionExecutionError(
                f"REG-HYGIENE-001 violation: Debug log not flagged for REMOVE: {f_log}"
            )

        # 3. Test SafeCleaner approval
        cleaner = SafeCleaner(repo_root=tmp_path)
        safe_scratch, msg_scratch = cleaner.is_safe_to_remove(f_scratch)
        if not safe_scratch:
            raise RegressionExecutionError(
                f"REG-HYGIENE-001 violation: SafeCleaner rejected removal of scratch file: {msg_scratch}"
            )

        # Conservative safety check: Tracked files must NEVER be auto-removed without manual review
        f_tracked_scratch = detect_scratch_file(str(scratch_file), is_tracked=True, is_referenced=False)
        safe_tracked, msg_tracked = cleaner.is_safe_to_remove(f_tracked_scratch)
        if safe_tracked:
            raise RegressionExecutionError(
                "REG-HYGIENE-001 violation: SafeCleaner dangerously allowed automatic removal of tracked file"
            )

        return True, "Scratch files, temporary patches, and debug logs are strictly detected and safely cleaned", {
            "scratch_action": f_scratch.recommended_action.value,
            "patch_action": f_patch.recommended_action.value,
            "log_action": f_log.recommended_action.value,
            "tracked_protection_active": not safe_tracked,
        }
