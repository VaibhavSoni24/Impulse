"""Stress Invariant Checker: STRESS 4 — Multi-File Fix.

Verifies that multi-file changes across caller, service, and test contracts
are accurately captured by PatchExtractor without dropping hunks, that unrelated
files remain untainted, and that FreshPatchApplier cleanly reproduces the fix.
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
from local.stress.fixtures import create_multifile_repo_fixture


def check_multifile_fix_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates patch extraction and clean-copy application for a multi-file fix.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_agent = Path(tempfile.mkdtemp(prefix="impulse_stress_multifile_agent_"))
    tmp_clean = Path(tempfile.mkdtemp(prefix="impulse_stress_multifile_clean_"))

    try:
        # 1. Initialize agent workspace and clean reference workspace
        create_multifile_repo_fixture(tmp_agent)
        create_multifile_repo_fixture(tmp_clean)

        # Baseline: client_run(5) = (5 + 10) * 2 = 30.
        # Defect requirement: Change service return from `val + 10` to `val + 20`.
        # This requires updating `service.py` AND `test_pipeline.py` (which expects 50 instead of 30).
        # Notice `client.py` is an UNMODIFIED intermediary file.

        service_path = tmp_agent / "service.py"
        service_path.write_text(
            '"""Core service module."""\n\n'
            "def execute_task(val: int) -> int:\n"
            "    return val + 20\n",
            encoding="utf-8",
        )

        test_path = tmp_agent / "test_pipeline.py"
        test_path.write_text(
            "import unittest\n"
            "from client import client_run\n\n"
            "class TestPipeline(unittest.TestCase):\n"
            "    def test_run(self):\n"
            "        self.assertEqual(client_run(5), 50)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )

        # 2. Extract patch using PatchExtractor
        agent_snapshot = CleanRepositorySnapshot(
            workspace_dir=tmp_agent,
            baseline_commit="HEAD",
            task_id="stress_task_multi",
            run_id="stress_run_multi",
            role="agent",
            creation_method=WorkspaceCreationMethod.CLONE,
            source_repo=tmp_agent,
        )
        extractor = PatchExtractor()
        bundle = extractor.extract_patch(
            workspace=agent_snapshot,
            run_id="stress_run_multi",
            task_id="stress_task_multi",
            candidate_id="M0",
        )

        # Invariant 1: Modified files list contains exactly service.py and test_pipeline.py
        expected_modified = {"service.py", "test_pipeline.py"}
        actual_modified = set(bundle.modified_files)
        if actual_modified != expected_modified:
            return (
                False,
                f"Multi-file modified set mismatch: expected {expected_modified}, got {actual_modified}",
                {"bundle_modified": bundle.modified_files},
            )

        # Invariant 2: Intermediary client.py must NOT be touched
        if "client.py" in actual_modified or "client.py" in bundle.tracked_diff:
            return (
                False,
                "Diff discipline violation: client.py was unintentionally modified or included in patch",
                {},
            )

        # Invariant 3: Diff contains hunks for both files
        if "service.py" not in bundle.tracked_diff or "test_pipeline.py" not in bundle.tracked_diff:
            return (
                False,
                "Diff does not contain both target files in its unified representation",
                {"diff": bundle.tracked_diff},
            )

        # 4. Apply to fresh clean validation workspace
        clean_snapshot = CleanRepositorySnapshot(
            workspace_dir=tmp_clean,
            baseline_commit="HEAD",
            task_id="stress_task_multi",
            run_id="stress_run_multi",
            role="validation",
            creation_method=WorkspaceCreationMethod.CLONE,
            source_repo=tmp_clean,
        )
        applier = FreshPatchApplier()
        applied, status_msg, _ = applier.apply_patch(clean_snapshot, bundle)

        if not applied or status_msg != "APPLIED":
            return (
                False,
                f"Patch application failed on clean copy: status={status_msg}",
                {"status_msg": status_msg},
            )

        # 5. Run test against fresh clean workspace to verify fix validity
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "test_pipeline.py"],
            cwd=str(tmp_clean),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return (
                False,
                f"Test failed in clean workspace after applying multi-file patch: {proc.stderr}",
                {"output": proc.stderr},
            )

        details = {
            "modified_files": bundle.modified_files,
            "diff_byte_size": len(bundle.tracked_diff.encode("utf-8")),
            "clean_copy_applied": True,
            "test_passed": True,
        }

        return (
            True,
            "Multi-file fix spanning service.py and test_pipeline.py cleanly extracted, verified, applied to fresh workspace, and test passed.",
            details,
        )

    finally:
        for p in [tmp_agent, tmp_clean]:
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
