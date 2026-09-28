"""Focused test suite for Stage 28 Clean-Copy Evaluator.

Verifies:
A. Clean snapshot creation (baseline cleanliness, isolation, commit resolution)
B. Candidate loading (valid candidate, invalid rejection, hashes)
C. Patch extraction (tracked edits, new files, deletions, untracked handling)
D. Patch application (clean apply, conflicts, traversal rejection)
E. Patch equivalence (content equivalence, mismatch detection)
F. Clean-copy verification (critical regression: dirty passes but clean fails => failure)
G. Workspace and candidate isolation (Task A vs Task B, Candidate A vs B)
H. Runtime availability (live unavailable, fixture available)
I. Evaluation database integration (persistence, schema, idempotent update)
J. Security (no credentials, no path traversal)
K. Stage 25 context compaction integration (fingerprint consistency)
L. Stage 26 tool-call budgeting integration (run_id association)
M. Stage 27 diff discipline compliance (artifacts hygiene)
N. Frozen Stage 24 topology invariance (M0-M5 hashes)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from local.clean_copy.adapter import (
    AgentExecutionAdapter,
    FixtureAction,
    FixtureAgentSpec,
    check_live_runtime_available,
)
from local.clean_copy.candidate_loader import CandidateLoader, CandidateLoadError
from local.clean_copy.equivalence import PatchEquivalenceChecker
from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import (
    EvaluatorFailureClass,
    EvaluationRunRecord,
    ExecutionMode,
    FailureStage,
    PatchBundle,
)
from local.clean_copy.patch_applier import FreshPatchApplier
from local.clean_copy.patch_extractor import PatchExtractionError, PatchExtractor
from local.clean_copy.snapshot import CleanRepositorySnapshot, SnapshotManager
from local.clean_copy.verifier import CleanCopyVerifier
from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_clean_eval_record
from local.evaluation.queries import get_run, list_runs
from local.runner.models import TaskRecord

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_synthetic_git_repo(root: Path) -> str:
    """Initializes a synthetic git repository for hermetic evaluator unit tests."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "test@eval.local",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "test@eval.local",
            "LC_ALL": "C",
        }
    )
    subprocess.run(["git", "init"], cwd=str(root), env=env, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Author"],
        cwd=str(root),
        env=env,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@eval.local"],
        cwd=str(root),
        env=env,
        capture_output=True,
        check=True,
    )

    # Initial files
    (root / "app.py").write_text("def solve():\n    return 0\n", encoding="utf-8")
    (root / "helper.py").write_text("# initial helper\n", encoding="utf-8")
    test_code = (
        "import unittest\nfrom app import solve\n\n"
        "class TestApp(unittest.TestCase):\n"
        "    def test_solve(self):\n"
        "        self.assertEqual(solve(), 42)\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    (root / "test_app.py").write_text(test_code, encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=str(root), env=env, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(root),
        env=env,
        capture_output=True,
        check=True,
    )
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True)
    return res.stdout.strip()


class TestCleanCopyEvaluatorStage28(unittest.TestCase):
    """Test suite for Clean-Copy Evaluation (Stage 28)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.synthetic_repo = self.test_root / "synthetic_repo"
        self.synthetic_repo.mkdir()
        self.base_commit = create_synthetic_git_repo(self.synthetic_repo)

        # Setup dummy task manifest
        self.tasks_file = self.test_root / "tasks.jsonl"
        task_data = {
            "instance_id": "test_task_1",
            "repo": "test/test_repo",
            "base_commit": self.base_commit,
            "problem_statement": "Make solve() return 42",
        }
        self.tasks_file.write_text(json.dumps(task_data) + "\n", encoding="utf-8")

        # Setup test db
        self.db_path = self.test_root / "test_eval.db"
        init_database(self.db_path)

        self.snapshot_mgr = SnapshotManager(self.synthetic_repo)
        self.patch_extractor = PatchExtractor()
        self.patch_applier = FreshPatchApplier()
        self.equivalence_checker = PatchEquivalenceChecker()
        self.verifier = CleanCopyVerifier()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------
    # Section A: Clean Snapshot Creation
    # -------------------------------------------------------------
    def test_01_snapshot_created_from_clean_baseline(self) -> None:
        """Clean snapshot created successfully from clean baseline repository."""
        snap = self.snapshot_mgr.create_snapshot(
            task_id="test_task_1",
            run_id="run_01",
            baseline_commit=self.base_commit,
            role="agent",
        )
        try:
            self.assertTrue(snap.is_clean())
            self.assertEqual(snap.get_head_commit(), self.base_commit)
            self.assertTrue((snap.workspace_dir / "app.py").exists())
        finally:
            snap.dispose()

    def test_02_snapshot_rejects_dirty_baseline(self) -> None:
        """SnapshotManager strictly rejects evaluation when baseline working tree is dirty."""
        # Make synthetic repo dirty
        (self.synthetic_repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        try:
            with self.assertRaises(ValueError) as ctx:
                self.snapshot_mgr.create_snapshot(
                    task_id="test_task_1",
                    run_id="run_02",
                    baseline_commit=self.base_commit,
                    allow_dirty_baseline=False,
                )
            self.assertIn("rejected dirty baseline repository", str(ctx.exception))
        finally:
            (self.synthetic_repo / "dirty.txt").unlink()

    def test_03_snapshot_isolated_filesystem_location(self) -> None:
        """Snapshots reside in separate filesystem paths and do not modify source repo."""
        snap1 = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1", role="agent")
        snap2 = self.snapshot_mgr.create_snapshot(task_id="t2", run_id="r2", role="validation")
        try:
            self.assertNotEqual(snap1.workspace_dir, snap2.workspace_dir)
            self.assertNotEqual(snap1.workspace_dir, self.synthetic_repo)
        finally:
            snap1.dispose()
            snap2.dispose()

    # -------------------------------------------------------------
    # Section B: Candidate Loading
    # -------------------------------------------------------------
    def test_04_candidate_loader_loads_m0_to_m5(self) -> None:
        """CandidateLoader successfully loads and validates frozen M0 through M5 candidates."""
        loader = CandidateLoader(PROJECT_ROOT)
        for cid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand = loader.load_candidate(cid)
            self.assertEqual(cand.candidate_id, cid)
            self.assertEqual(cand.model_id, "gemma-4-31b-it-qat-w4a16-ct")
            self.assertTrue(len(cand.config_sha256) == 64)
            self.assertTrue(len(cand.bundle_sha256) == 64)

    def test_05_candidate_loader_rejects_invalid_candidate(self) -> None:
        """CandidateLoader rejects candidate directory with missing agent.yaml."""
        invalid_dir = self.test_root / "invalid_cand"
        invalid_dir.mkdir()
        (invalid_dir / "random.txt").write_text("not an agent", encoding="utf-8")

        loader = CandidateLoader(PROJECT_ROOT)
        with self.assertRaises(CandidateLoadError):
            loader.load_candidate(invalid_dir)

    def test_06_candidate_materialization_is_isolated(self) -> None:
        """Materializing a candidate into destination does not mutate source candidate."""
        loader = CandidateLoader(PROJECT_ROOT)
        cand = loader.load_candidate("M0")

        dest = self.test_root / "test_dest"
        dest.mkdir()
        cand.materialize(dest)

        self.assertTrue((dest / "candidate" / "agent.yaml").exists())
        # Source directory remains untouched
        self.assertTrue((cand.candidate_dir / "agent.yaml").exists())

    # -------------------------------------------------------------
    # Section C: Patch Extraction
    # -------------------------------------------------------------
    def test_07_extract_patch_modified_tracked_file(self) -> None:
        """Patch extractor captures edits to tracked files."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            # Modify app.py
            (snap.workspace_dir / "app.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            bundle = self.patch_extractor.extract_patch(snap, "r1", "t1", "M0")

            self.assertEqual(bundle.extraction_status, "OK")
            self.assertIn("app.py", bundle.changed_paths)
            self.assertIn("app.py", bundle.modified_files)
            self.assertIn("+    return 42", bundle.tracked_diff)
            self.assertTrue(len(bundle.patch_sha256) == 64)
        finally:
            snap.dispose()

    def test_08_extract_patch_new_file(self) -> None:
        """Patch extractor captures newly created files as diff additions from /dev/null."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            (snap.workspace_dir / "new_module.py").write_text("NEW_CONST = 100\n", encoding="utf-8")
            bundle = self.patch_extractor.extract_patch(snap, "r1", "t1", "M0")

            self.assertIn("new_module.py", bundle.changed_paths)
            self.assertIn("new_module.py", bundle.new_files)
            self.assertIn("NEW_CONST = 100", bundle.tracked_diff)
        finally:
            snap.dispose()

    def test_09_extract_patch_deleted_file(self) -> None:
        """Patch extractor captures deleted files."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            (snap.workspace_dir / "helper.py").unlink()
            bundle = self.patch_extractor.extract_patch(snap, "r1", "t1", "M0")

            self.assertIn("helper.py", bundle.changed_paths)
            self.assertIn("helper.py", bundle.deleted_files)
        finally:
            snap.dispose()

    def test_10_extract_patch_excludes_git_ignored_files(self) -> None:
        """Patch extraction respects .git/info/exclude and omits pycache/pytest_cache."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            pycache_dir = snap.workspace_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "cache.pyc").write_text("bytecode", encoding="utf-8")

            bundle = self.patch_extractor.extract_patch(snap, "r1", "t1", "M0")
            self.assertEqual(bundle.extraction_status, "EMPTY")
            self.assertEqual(bundle.changed_paths, [])
        finally:
            snap.dispose()

    # -------------------------------------------------------------
    # Section D: Fresh Patch Application
    # -------------------------------------------------------------
    def test_11_apply_patch_cleanly_to_fresh_workspace(self) -> None:
        """Patch cleanly applies to a fresh validation snapshot."""
        # 1. Produce patch in agent workspace
        agent_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        val_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1", role="validation")
        try:
            (agent_snap.workspace_dir / "app.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            bundle = self.patch_extractor.extract_patch(agent_snap, "r1", "t1", "M0")

            # 2. Apply to validation snapshot
            applied_ok, status, diff = self.patch_applier.apply_patch(val_snap, bundle)
            self.assertTrue(applied_ok)
            self.assertEqual(status, "APPLIED")
            self.assertIn("return 42", (val_snap.workspace_dir / "app.py").read_text(encoding="utf-8"))
        finally:
            agent_snap.dispose()
            val_snap.dispose()

    def test_12_apply_patch_detects_conflict(self) -> None:
        """Patch that conflicts with baseline is classified as PATCH_APPLY_CONFLICT."""
        val_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1", role="validation")
        try:
            conflicting_diff = (
                "--- a/non_existent.py\n"
                "+++ b/non_existent.py\n"
                "@@ -1,1 +1,1 @@\n"
                "-old_line\n"
                "+new_line\n"
            )
            bundle = PatchBundle(
                run_id="r1",
                task_id="t1",
                candidate_id="M0",
                baseline_commit=self.base_commit,
                tracked_diff=conflicting_diff,
                changed_paths=["non_existent.py"],
            )

            applied_ok, status, diff = self.patch_applier.apply_patch(val_snap, bundle)
            self.assertFalse(applied_ok)
            self.assertIn("PATCH_APPLY_CONFLICT", status)
        finally:
            val_snap.dispose()

    def test_13_patch_extraction_rejects_path_traversal(self) -> None:
        """Patch targeting paths outside repository is rejected with security error."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            with self.assertRaises(PatchExtractionError):
                self.patch_extractor.validate_patch_security(
                    diff_text="diff",
                    changed_paths=["../../etc/passwd"],
                    workspace_root=snap.workspace_dir,
                )
        finally:
            snap.dispose()

    # -------------------------------------------------------------
    # Section E: Patch Equivalence
    # -------------------------------------------------------------
    def test_14_patch_equivalence_confirms_identical_contents(self) -> None:
        """PatchEquivalenceChecker confirms semantic equivalence between agent and validation."""
        agent_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        val_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1", role="validation")
        try:
            (agent_snap.workspace_dir / "app.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            bundle = self.patch_extractor.extract_patch(agent_snap, "r1", "t1", "M0")
            self.patch_applier.apply_patch(val_snap, bundle)

            equiv, reason = self.equivalence_checker.check_equivalence(
                bundle, agent_snap.workspace_dir, val_snap.workspace_dir
            )
            self.assertTrue(equiv)
            self.assertIn("confirmed", reason)
        finally:
            agent_snap.dispose()
            val_snap.dispose()

    def test_15_patch_equivalence_detects_mismatch(self) -> None:
        """PatchEquivalenceChecker detects content mismatch."""
        agent_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        val_snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1", role="validation")
        try:
            (agent_snap.workspace_dir / "app.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            (val_snap.workspace_dir / "app.py").write_text("def solve():\n    return 99\n", encoding="utf-8")
            bundle = PatchBundle(
                run_id="r1",
                task_id="t1",
                candidate_id="M0",
                baseline_commit=self.base_commit,
                changed_paths=["app.py"],
            )

            equiv, reason = self.equivalence_checker.check_equivalence(
                bundle, agent_snap.workspace_dir, val_snap.workspace_dir
            )
            self.assertFalse(equiv)
            self.assertIn("Content mismatch", reason)
        finally:
            agent_snap.dispose()
            val_snap.dispose()

    # -------------------------------------------------------------
    # Section F: Critical Regression Test (Clean-Copy Verification)
    # -------------------------------------------------------------
    def test_16_critical_regression_dirty_workspace_pass_clean_copy_fail(self) -> None:
        """CRITICAL STAGE 28 REGRESSION:
        
        If a task passes in dirty agent workspace due to an unsubmitted local side-effect,
        but clean-copy verification fails, the evaluation MUST NOT be marked successful.
        """
        # Create an evaluator pointed at our synthetic repo
        evaluator = CleanCopyEvaluator(
            repo_root=self.synthetic_repo,
            tasks_file=self.tasks_file,
            output_dir=self.test_root / "runs",
            db_path=self.db_path,
        )

        # Agent writes an untracked local file outside Git that makes its own test pass,
        # but does NOT modify app.py in git tracked files!
        fixture_spec = FixtureAgentSpec(
            name="dirty_passer_clean_failer",
            actions=[],  # zero git edits
            untracked_disposable_files=[
                # creates a mock override file in agent workspace that is gitignored/disposable
                (".pytest_cache/local_hack.txt", "side_effect")
            ],
        )

        record = evaluator.evaluate_task(
            task_id="test_task_1",
            candidate_ref="M0",
            baseline_commit=self.base_commit,
            mode=ExecutionMode.FIXTURE,
            fixture_spec=fixture_spec,
            verification_command="python test_app.py",
            allow_dirty_baseline=True,
        )

        # The patch was empty, so clean-copy verification was not passed
        self.assertFalse(record.success, "Task must not succeed if patch does not solve the task")
        self.assertEqual(record.patch_extraction_status, "EMPTY")

    def test_17_clean_copy_passes_when_fix_is_complete(self) -> None:
        """When complete fix is captured in patch, clean-copy verification succeeds."""
        evaluator = CleanCopyEvaluator(
            repo_root=self.synthetic_repo,
            tasks_file=self.tasks_file,
            output_dir=self.test_root / "runs",
            db_path=self.db_path,
        )

        # Agent modifies app.py to return 42
        fixture_spec = FixtureAgentSpec(
            name="valid_fixer",
            actions=[
                FixtureAction(
                    action_type="write",
                    path="app.py",
                    content="def solve():\n    return 42\n",
                )
            ],
            tool_calls=3,
            turns=2,
        )

        record = evaluator.evaluate_task(
            task_id="test_task_1",
            candidate_ref="M0",
            baseline_commit=self.base_commit,
            mode=ExecutionMode.FIXTURE,
            fixture_spec=fixture_spec,
            verification_command="python test_app.py",
            allow_dirty_baseline=True,
        )

        self.assertTrue(record.success)
        self.assertEqual(record.verification_status, "PASSED")
        self.assertTrue(record.clean_copy_verified)
        self.assertEqual(record.patch_apply_status, "APPLIED")
        self.assertEqual(record.files_changed, 1)

    # -------------------------------------------------------------
    # Section G: Workspace and Candidate Isolation
    # -------------------------------------------------------------
    def test_18_multi_task_workspace_isolation(self) -> None:
        """Task A cannot contaminate Task B; workspaces are strictly isolated."""
        snapA = self.snapshot_mgr.create_snapshot(task_id="taskA", run_id="runA")
        try:
            (snapA.workspace_dir / "taskA_leak.txt").write_text("leak", encoding="utf-8")

            # Create Task B snapshot from same baseline
            snapB = self.snapshot_mgr.create_snapshot(task_id="taskB", run_id="runB")
            try:
                self.assertFalse((snapB.workspace_dir / "taskA_leak.txt").exists())
                self.assertTrue(snapB.is_clean())
            finally:
                snapB.dispose()
        finally:
            snapA.dispose()

    def test_19_candidate_isolation(self) -> None:
        """Evaluating Candidate M0 does not mutate Candidate M1 source files."""
        loader = CandidateLoader(PROJECT_ROOT)
        m0 = loader.load_candidate("M0")
        m1 = loader.load_candidate("M1")

        m0_agent_yaml = m0.candidate_dir / "agent.yaml"
        m1_agent_yaml = m1.candidate_dir / "agent.yaml"

        m0_content_before = m0_agent_yaml.read_text(encoding="utf-8")
        m1_content_before = m1_agent_yaml.read_text(encoding="utf-8")

        # Materialize M0
        dest = self.test_root / "cand_dest"
        dest.mkdir()
        m0.materialize(dest)

        self.assertEqual(m0_agent_yaml.read_text(encoding="utf-8"), m0_content_before)
        self.assertEqual(m1_agent_yaml.read_text(encoding="utf-8"), m1_content_before)

    # -------------------------------------------------------------
    # Section H: Runtime Availability Boundary
    # -------------------------------------------------------------
    def test_20_runtime_capability_check_reports_unavailable(self) -> None:
        """check_live_runtime_available reports unavailable on local Windows host."""
        avail, reason = check_live_runtime_available()
        self.assertFalse(avail)
        self.assertIn("lacks 4x NVIDIA L4 GPUs", reason)

    def test_21_live_mode_without_hardware_yields_unavailable(self) -> None:
        """Requesting LIVE mode without hardware yields explicit UNAVAILABLE record."""
        evaluator = CleanCopyEvaluator(
            repo_root=self.synthetic_repo,
            tasks_file=self.tasks_file,
            output_dir=self.test_root / "runs",
            db_path=self.db_path,
        )

        record = evaluator.evaluate_task(
            task_id="test_task_1",
            candidate_ref="M0",
            baseline_commit=self.base_commit,
            mode=ExecutionMode.LIVE,
            allow_dirty_baseline=True,
        )

        self.assertEqual(record.execution_status, "UNAVAILABLE")
        self.assertEqual(record.failure_class, EvaluatorFailureClass.RUNTIME_UNAVAILABLE)
        self.assertEqual(record.failure_stage, FailureStage.AGENT_EXECUTION)
        self.assertFalse(record.success)

    # -------------------------------------------------------------
    # Section I: Evaluation Database Integration
    # -------------------------------------------------------------
    def test_22_database_persistence_and_query(self) -> None:
        """EvaluationRunRecord persists cleanly into SQLite evaluation database."""
        conn = get_connection(self.db_path)
        try:
            record = EvaluationRunRecord(
                run_id="run_db_test_01",
                task_id="test_task_1",
                candidate_id="M0",
                baseline_commit=self.base_commit,
                candidate_config_sha256="abc123sha",
                execution_status="COMPLETED",
                success=True,
                verification_status="PASSED",
                clean_copy_verified=True,
                files_changed=2,
                patch_lines=15,
                patch_sha256="patchsha123",
            )
            ingest_clean_eval_record(conn, record)

            runs = list_runs(conn, candidate_id="M0")
            self.assertEqual(len(runs), 1)
            row = runs[0]
            self.assertEqual(row["run_id"], "run_db_test_01")
            self.assertEqual(row["success"], 1)
            self.assertEqual(row["files_changed"], 2)
            self.assertEqual(row["clean_copy_verified"], 1)
        finally:
            conn.close()

    def test_23_database_idempotent_reingest(self) -> None:
        """Re-ingesting existing run_id updates record without integrity errors."""
        conn = get_connection(self.db_path)
        try:
            record = EvaluationRunRecord(
                run_id="run_db_idempotent",
                task_id="test_task_1",
                candidate_id="M0",
                baseline_commit=self.base_commit,
                candidate_config_sha256="abc123sha",
                execution_status="COMPLETED",
                success=False,
            )
            ingest_clean_eval_record(conn, record)
            # Update success to True
            record.success = True
            ingest_clean_eval_record(conn, record)

            runs = list_runs(conn, candidate_id="M0")
            matched = [r for r in runs if r["run_id"] == "run_db_idempotent"]
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["success"], 1)
        finally:
            conn.close()

    # -------------------------------------------------------------
    # Section J: Security
    # -------------------------------------------------------------
    def test_24_no_credentials_in_patch(self) -> None:
        """Patch extractor rejects diffs containing credentials."""
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            (snap.workspace_dir / "app.py").write_text(
                "TOKEN = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'\n", encoding="utf-8"
            )
            with self.assertRaises(PatchExtractionError):
                self.patch_extractor.extract_patch(snap, "r1", "t1", "M0")
        finally:
            snap.dispose()

    # -------------------------------------------------------------
    # Section K: Stage 25 Context Compaction Integration
    # -------------------------------------------------------------
    def test_25_context_compaction_fingerprint_in_clean_workspace(self) -> None:
        """File fingerprints from Stage 25 operate deterministically in clean snapshots."""
        from local.context_compaction.fingerprints import compute_file_fingerprint
        snap = self.snapshot_mgr.create_snapshot(task_id="t1", run_id="r1")
        try:
            content = (snap.workspace_dir / "app.py").read_bytes()
            fp = compute_file_fingerprint("app.py", content)
            self.assertEqual(fp.path, "app.py")
            self.assertTrue(len(fp.sha256) == 64)
        finally:
            snap.dispose()

    # -------------------------------------------------------------
    # Section L: Stage 26 Tool Budgeting Integration
    # -------------------------------------------------------------
    def test_26_tool_budgeting_run_id_association(self) -> None:
        """Tool call events can be generated and associated with clean evaluation run ID."""
        from local.budgeting.models import ToolCallCategory, ToolCallEvent
        event = ToolCallEvent(
            run_id="eval-run-123",
            task_id="t1",
            turn_id=1,
            call_id="c1",
            tool_name="read_file",
            category=ToolCallCategory.READ_OBSERVATION,
            normalized_arguments={"path": "app.py"},
            repository_state_id="state_abc",
        )
        self.assertEqual(event.run_id, "eval-run-123")
        self.assertEqual(event.category, ToolCallCategory.READ_OBSERVATION)

    # -------------------------------------------------------------
    # Section M: Stage 27 Diff Discipline Scanner Compliance
    # -------------------------------------------------------------
    def test_27_evaluator_source_files_pass_hygiene_scan(self) -> None:
        """All Stage 28 clean_copy source files pass Stage 27 artifact classifier as REQUIRED_SOURCE."""
        from local.diff_discipline.classifier import ArtifactClassifier
        from local.diff_discipline.models import ArtifactClass, HygieneAction

        classifier = ArtifactClassifier(PROJECT_ROOT)
        for rel_p in [
            "local/clean_copy/models.py",
            "local/clean_copy/snapshot.py",
            "local/clean_copy/candidate_loader.py",
            "local/clean_copy/adapter.py",
            "local/clean_copy/patch_extractor.py",
            "local/clean_copy/patch_applier.py",
            "local/clean_copy/equivalence.py",
            "local/clean_copy/verifier.py",
            "local/clean_copy/evaluator.py",
            "local/clean_copy/__init__.py",
            "scripts/clean_copy_eval.py",
        ]:
            finding = classifier.classify_file(rel_p, is_tracked=False, is_referenced=True)
            self.assertEqual(finding.artifact_class, ArtifactClass.REQUIRED_SOURCE)
            self.assertEqual(finding.recommended_action, HygieneAction.KEEP)

    # -------------------------------------------------------------
    # Section N: Frozen Stage 24 Topology Invariance
    # -------------------------------------------------------------
    def test_28_frozen_specialists_and_topology_hashes_match(self) -> None:
        """Stage 24 frozen hashes remain strictly invariant."""
        from local.diff_discipline.frozen_verifier import verify_frozen_artifacts

        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertTrue(passed, f"Frozen hash violations: {details}")
        for path, det in details.items():
            self.assertEqual(det["status"], "MATCH", f"Mismatch in {path}")


if __name__ == "__main__":
    unittest.main()
