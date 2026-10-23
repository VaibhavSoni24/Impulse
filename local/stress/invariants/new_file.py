"""Stress Invariant Checker: STRESS 8 — Required New File.

Verifies that when a bug fix requires creating a brand new untracked file,
PatchExtractor captures it cleanly via 'git add -N .', path boundaries are preserved,
and FreshPatchApplier reconstructs the new file in a clean validation copy.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

from local.clean_copy.models import PatchBundle, WorkspaceCreationMethod
from local.clean_copy.patch_applier import FreshPatchApplier
from local.clean_copy.patch_extractor import PatchExtractor
from local.clean_copy.snapshot import CleanRepositorySnapshot
from local.stress.fixtures import create_required_new_file_fixture


def check_new_file_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates patch capture and application when a fix introduces a new file.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_agent = Path(tempfile.mkdtemp(prefix="impulse_stress_newfile_agent_"))
    tmp_clean = Path(tempfile.mkdtemp(prefix="impulse_stress_newfile_clean_"))

    try:
        create_required_new_file_fixture(tmp_agent)
        create_required_new_file_fixture(tmp_clean)

        # 1. In agent workspace, create the new file (untracked in git)
        new_file = tmp_agent / "serializer.py"
        new_file_content = (
            '"""Serializer module created to fix pipeline contract."""\n\n'
            "def sanitize_string(val: str) -> str:\n"
            "    return val.strip()\n"
        )
        new_file.write_text(new_file_content, encoding="utf-8")

        # 2. Update existing main.py to use the new serializer
        main_file = tmp_agent / "main.py"
        main_file.write_text(
            "from serializer import sanitize_string\n\n"
            "def run_pipeline(data: str) -> str:\n"
            "    return sanitize_string(data)\n",
            encoding="utf-8",
        )

        # 3. Extract patch using PatchExtractor
        agent_snapshot = CleanRepositorySnapshot(
            workspace_dir=tmp_agent,
            baseline_commit="HEAD",
            task_id="stress_task_newfile",
            run_id="stress_run_newfile",
            role="agent",
            creation_method=WorkspaceCreationMethod.CLONE,
            source_repo=tmp_agent,
        )
        extractor = PatchExtractor()
        bundle = extractor.extract_patch(
            workspace=agent_snapshot,
            run_id="stress_run_newfile",
            task_id="stress_task_newfile",
            candidate_id="M0",
        )

        # Invariant 1: New file is detected in new_files
        if "serializer.py" not in bundle.new_files:
            return (
                False,
                f"New file 'serializer.py' was not captured in bundle.new_files: {bundle.new_files}",
                {"new_files": bundle.new_files},
            )

        # Invariant 2: Modified file main.py is detected
        if "main.py" not in bundle.modified_files:
            return (
                False,
                f"Existing modified file 'main.py' missing from bundle.modified_files: {bundle.modified_files}",
                {"modified_files": bundle.modified_files},
            )

        # Invariant 3: Diff representation includes the new file creation from /dev/null
        if "diff --git a/serializer.py b/serializer.py" not in bundle.tracked_diff:
            return (
                False,
                "Unified diff did not contain git header for serializer.py",
                {"diff": bundle.tracked_diff},
            )

        # 4. Apply patch to fresh clean workspace
        clean_snapshot = CleanRepositorySnapshot(
            workspace_dir=tmp_clean,
            baseline_commit="HEAD",
            task_id="stress_task_newfile",
            run_id="stress_run_newfile",
            role="validation",
            creation_method=WorkspaceCreationMethod.CLONE,
            source_repo=tmp_clean,
        )
        applier = FreshPatchApplier()
        applied, status_msg, _ = applier.apply_patch(clean_snapshot, bundle)

        if not applied or status_msg != "APPLIED":
            return (
                False,
                f"Patch application failed on clean copy: {status_msg}",
                {"status_msg": status_msg},
            )

        # Invariant 4: New file was actually created on disk in clean workspace
        clean_new_file = tmp_clean / "serializer.py"
        if not clean_new_file.exists():
            return (
                False,
                "New file 'serializer.py' does not exist in clean workspace after patch application",
                {},
            )

        # Invariant 5: Test passes in clean workspace
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "test_main.py"],
            cwd=str(tmp_clean),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return (
                False,
                f"Test execution failed in clean workspace: {proc.stderr}",
                {"output": proc.stderr},
            )

        details = {
            "new_files": bundle.new_files,
            "modified_files": bundle.modified_files,
            "new_file_reconstructed": True,
            "test_passed": True,
        }

        return (
            True,
            "Required new file 'serializer.py' cleanly detected via 'git add -N .', incorporated into patch, reconstructed on fresh copy, and verified by tests.",
            details,
        )

    finally:
        for p in [tmp_agent, tmp_clean]:
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
