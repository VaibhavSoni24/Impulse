"""Tests for Git-level patch capture semantics (Stage 7).

NOTE ON BOUNDARY AND SCOPE:
This module verifies the documented Git-level patch-extraction behavior defined in
HARNESS_README.md Section 8.1 ('git add -N .' followed by 'git diff HEAD').

The official competition 'submit_patch()' tool executes inside a proprietary remote
evaluation container and is NOT locally available on this workstation.
These tests provide LOCAL REPRODUCTION / CONTRACT VERIFICATION of the documented
Git mechanics in isolated temporary repositories. They do NOT execute or fake the
official proprietary harness tool.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def run_git(args: list[str], repo_dir: Path) -> subprocess.CompletedProcess[str]:
    """Runs a git command in an isolated repository with throwaway identity."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Runner",
            "GIT_AUTHOR_EMAIL": "test@eval.local",
            "GIT_COMMITTER_NAME": "Test Runner",
            "GIT_COMMITTER_EMAIL": "test@eval.local",
            "LC_ALL": "C",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_dir),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def stage_untracked_intents(repo_dir: Path) -> subprocess.CompletedProcess[str]:
    """Stages intent-to-add for untracked files, reproducing documented harness behavior.

    Corresponds to: 'cd /workspace && git add -N .'
    """
    return run_git(["add", "-N", "."], repo_dir)


def get_reproduced_patch(repo_dir: Path) -> str:
    """Captures unified diff from HEAD, reproducing documented harness extraction.

    Corresponds to: 'cd /workspace && git diff HEAD'
    """
    proc = run_git(["diff", "HEAD"], repo_dir)
    # Normalize CRLF to LF for cross-platform assertion reliability
    return proc.stdout.replace("\r\n", "\n")


def capture_patch_reproduction(repo_dir: Path) -> tuple[str, int, int]:
    """Executes the full documented patch capture sequence.

    1. Stages untracked file intents via 'git add -N .'
    2. Extracts diff via 'git diff HEAD'
    3. Calculates patch size in bytes and number of changed files.

    Returns:
        tuple of (patch_content, patch_size_bytes, files_changed_count)
    """
    stage_untracked_intents(repo_dir)
    patch = get_reproduced_patch(repo_dir)
    patch_size = len(patch.encode("utf-8"))

    # Count distinct files modified in the diff
    files_changed = sum(1 for line in patch.splitlines() if line.startswith("diff --git "))
    return patch, patch_size, files_changed


def setup_reproduction_repository(repo_dir: Path) -> None:
    """Initializes a clean isolated Git repository with a baseline commit."""
    run_git(["init"], repo_dir)
    run_git(["config", "--local", "user.name", "Test Runner"], repo_dir)
    run_git(["config", "--local", "user.email", "test@eval.local"], repo_dir)

    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    initial_file = src_dir / "app.py"
    initial_file.write_text(
        "def calculate_sum(a, b):\n"
        "    return a + b\n\n"
        "def main():\n"
        "    print(calculate_sum(1, 2))\n",
        encoding="utf-8",
    )

    run_git(["add", "-A"], repo_dir)
    run_git(["commit", "-m", "baseline", "--allow-empty"], repo_dir)


def configure_git_excludes(repo_dir: Path, patterns: list[str]) -> None:
    """Appends ignore patterns to .git/info/exclude, mirroring harness setup_git_exclude."""
    exclude_path = repo_dir / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    with open(exclude_path, "a", encoding="utf-8") as f:
        for pattern in patterns:
            f.write(f"{pattern}\n")


class TestPatchCaptureReproduction(unittest.TestCase):
    """Test suite validating patch capture semantics in isolated Git repositories."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.temp_dir.name)
        setup_reproduction_repository(self.repo_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_scenario_a_tracked_file_modification(self) -> None:
        """Scenario A: Verify modification to an existing tracked file is accurately captured."""
        # 1. Verify initially clean baseline
        clean_patch = get_reproduced_patch(self.repo_dir)
        self.assertEqual(clean_patch, "")

        # 2. Modify tracked file
        app_file = self.repo_dir / "src" / "app.py"
        app_file.write_text(
            "def calculate_sum(a: int, b: int) -> int:\n"
            "    # Type annotated implementation\n"
            "    return a + b\n\n"
            "def main():\n"
            "    print(calculate_sum(1, 2))\n",
            encoding="utf-8",
        )

        # 3. Capture patch representation
        patch, patch_size, files_changed = capture_patch_reproduction(self.repo_dir)

        # 4. Assert content, metrics, and diff headers
        self.assertEqual(files_changed, 1)
        self.assertGreater(patch_size, 0)
        self.assertIn("diff --git a/src/app.py b/src/app.py", patch)
        self.assertIn("-def calculate_sum(a, b):", patch)
        self.assertIn("+def calculate_sum(a: int, b: int) -> int:", patch)
        self.assertIn("+    # Type annotated implementation", patch)
        self.assertIn(" def main():", patch)

    def test_scenario_b_untracked_file_intent_staging(self) -> None:
        """Scenario B: Verify untracked files require 'git add -N .' to be captured in git diff HEAD."""
        # 1. Create a brand new untracked file
        new_file = self.repo_dir / "src" / "helper.py"
        new_file.write_text(
            "def format_output(value: int) -> str:\n"
            "    return f'Result: {value}'\n",
            encoding="utf-8",
        )

        # 2. Before intent-to-add: standard git diff HEAD MUST NOT include the untracked file
        raw_diff_before = get_reproduced_patch(self.repo_dir)
        self.assertEqual(
            raw_diff_before,
            "",
            "Untracked file must not appear in git diff HEAD prior to staging intent",
        )

        # 3. Apply intent-to-add staging and capture patch
        patch, patch_size, files_changed = capture_patch_reproduction(self.repo_dir)

        # 4. Assert untracked file is now represented as a full addition
        self.assertEqual(files_changed, 1)
        self.assertGreater(patch_size, 0)
        self.assertIn("diff --git a/src/helper.py b/src/helper.py", patch)
        self.assertIn("new file mode", patch)
        self.assertIn("--- /dev/null", patch)
        self.assertIn("+++ b/src/helper.py", patch)
        self.assertIn("+def format_output(value: int) -> str:", patch)
        self.assertIn("+    return f'Result: {value}'", patch)

    def test_scenario_c_accidental_scratch_file_contamination(self) -> None:
        """Scenario C: Verify accidental scratch files contaminate the patch unless cleaned or excluded."""
        # 1. Modify tracked source code (intended change)
        app_file = self.repo_dir / "src" / "app.py"
        app_file.write_text(
            "def calculate_sum(a, b):\n"
            "    return int(a) + int(b)\n",
            encoding="utf-8",
        )

        # 2. Create unintended reproduction / debug scratch file in workspace root
        scratch_file = self.repo_dir / "repro.py"
        scratch_file.write_text(
            "import src.app\n"
            "print('Testing local reproduction')\n",
            encoding="utf-8",
        )

        # 3. Capture patch with scratch file present
        patch_contaminated, size_contaminated, count_contaminated = capture_patch_reproduction(
            self.repo_dir
        )

        # 4. Confirm the accidental hazard: repro.py IS captured into the patch
        self.assertEqual(count_contaminated, 2)
        self.assertIn("diff --git a/repro.py b/repro.py", patch_contaminated)
        self.assertIn("+print('Testing local reproduction')", patch_contaminated)

        # 5. Remediation Demonstration 1: Deleting scratch file clears contamination
        scratch_file.unlink()
        run_git(["reset", "HEAD", "repro.py"], self.repo_dir)  # remove intent entry from index
        patch_cleaned, size_cleaned, count_cleaned = capture_patch_reproduction(self.repo_dir)

        self.assertEqual(count_cleaned, 1)
        self.assertNotIn("repro.py", patch_cleaned)
        self.assertIn("src/app.py", patch_cleaned)

        # 6. Remediation Demonstration 2: Files in external directory (/tmp) never contaminate
        with tempfile.TemporaryDirectory() as external_temp_dir:
            ext_script = Path(external_temp_dir) / "external_repro.py"
            ext_script.write_text("print('external')", encoding="utf-8")
            patch_ext, _, count_ext = capture_patch_reproduction(self.repo_dir)
            self.assertEqual(count_ext, 1)
            self.assertNotIn("external_repro.py", patch_ext)

    def test_scenario_d_multiple_mixed_changes_with_harness_excludes(self) -> None:
        """Scenario D: Verify mixed changes correctly include intended files and ignore excluded patterns."""
        # 1. Configure standard harness patterns in .git/info/exclude
        harness_excludes = [
            "__pycache__/",
            "*.pyc",
            ".pytest_cache/",
            "*.egg-info/",
            "build/",
            "dist/",
            ".coverage",
        ]
        configure_git_excludes(self.repo_dir, harness_excludes)

        # 2. Deliberate modification to existing file
        app_file = self.repo_dir / "src" / "app.py"
        app_file.write_text(
            "def calculate_sum(a, b):\n"
            "    return a + b + 0\n",
            encoding="utf-8",
        )

        # 3. Deliberate creation of new module
        models_file = self.repo_dir / "src" / "models.py"
        models_file.write_text(
            "class CalculationResult:\n"
            "    def __init__(self, val: int):\n"
            "        self.val = val\n",
            encoding="utf-8",
        )

        # 4. Create excluded build, bytecode, and cache artifacts
        pycache_dir = self.repo_dir / "src" / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "app.cpython-313.pyc").write_bytes(b"\x00\x00\x00\x00bytecode")

        pytest_dir = self.repo_dir / ".pytest_cache" / "v" / "cache"
        pytest_dir.mkdir(parents=True, exist_ok=True)
        (pytest_dir / "nodeids").write_text("test_node_id\n", encoding="utf-8")

        build_dir = self.repo_dir / "build" / "lib"
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "app.py").write_text("build copy\n", encoding="utf-8")

        (self.repo_dir / ".coverage").write_text("!coverage data!", encoding="utf-8")

        # 5. Capture patch
        patch, patch_size, files_changed = capture_patch_reproduction(self.repo_dir)

        # 6. Verify: Exactly 2 files changed (app.py and models.py)
        self.assertEqual(files_changed, 2)
        self.assertGreater(patch_size, 0)

        # Verify intended changes are present
        self.assertIn("diff --git a/src/app.py b/src/app.py", patch)
        self.assertIn("+    return a + b + 0", patch)
        self.assertIn("diff --git a/src/models.py b/src/models.py", patch)
        self.assertIn("+class CalculationResult:", patch)

        # Verify excluded artifacts are strictly ABSENT from the patch
        self.assertNotIn("__pycache__", patch)
        self.assertNotIn(".pyc", patch)
        self.assertNotIn(".pytest_cache", patch)
        self.assertNotIn("build/", patch)
        self.assertNotIn(".coverage", patch)


if __name__ == "__main__":
    unittest.main()
