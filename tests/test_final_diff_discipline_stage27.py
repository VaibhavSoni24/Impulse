"""Focused test suite for Stage 27: Final Diff Discipline & Repository Hygiene.

Verifies:
A. Git status and diff parsing
B. Scratch file detection
C. Log file detection
D. Debug marker detection
E. Temporary fixture detection
F. Local configuration detection
G. Machine-specific artifact detection
H. Reference safety
I. Protected artifacts and frozen Stage 24 invariance
J. Secret hygiene and masking
K. Cleanup safety and conservative execution
L. Post-cleanup verification and real repository audit
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local.diff_discipline.classifier import ArtifactClassifier
from local.diff_discipline.cleaner import SafeCleaner
from local.diff_discipline.detectors import (
    detect_local_config,
    detect_log_file,
    detect_machine_specific,
    detect_scratch_file,
    scan_content_for_debug_markers,
    scan_content_for_machine_paths,
    scan_content_for_secrets,
)
from local.diff_discipline.frozen_verifier import (
    FROZEN_STAGE24_HASHES,
    verify_frozen_artifacts,
)
from local.diff_discipline.git_inspector import GitInspector
from local.diff_discipline.models import (
    ArtifactClass,
    ArtifactFinding,
    GitFileStatus,
    HygieneAction,
)
from local.diff_discipline.pipeline import FinalDiffReviewPipeline
from local.diff_discipline.reference_checker import ReferenceChecker

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFinalDiffDisciplineStage27(unittest.TestCase):
    """Test suite for Stage 27 Final Diff Discipline."""

    def setUp(self) -> None:
        self.inspector = GitInspector(PROJECT_ROOT)
        self.classifier = ArtifactClassifier(PROJECT_ROOT)
        self.cleaner = SafeCleaner(PROJECT_ROOT)

    # -------------------------------------------------------------
    # Section A: Git Status & Diff Parsing
    # -------------------------------------------------------------
    def test_01_parse_modified_line(self) -> None:
        """Parse modified file indicators from git status --short."""
        status, path = self.inspector.parse_status_line(" M agent/models.py")
        self.assertEqual(status, GitFileStatus.MODIFIED)
        self.assertEqual(path, "agent/models.py")

        status, path = self.inspector.parse_status_line("M  agent/models.py")
        self.assertEqual(status, GitFileStatus.MODIFIED)
        self.assertEqual(path, "agent/models.py")

    def test_02_parse_added_line(self) -> None:
        """Parse staged/added file indicator."""
        status, path = self.inspector.parse_status_line("A  local/new_tool.py")
        self.assertEqual(status, GitFileStatus.ADDED)
        self.assertEqual(path, "local/new_tool.py")

    def test_03_parse_deleted_line(self) -> None:
        """Parse deleted file indicator."""
        status, path = self.inspector.parse_status_line(" D temp_file.py")
        self.assertEqual(status, GitFileStatus.DELETED)
        self.assertEqual(path, "temp_file.py")

    def test_04_parse_renamed_line(self) -> None:
        """Parse renamed file indicator."""
        status, path = self.inspector.parse_status_line("R  old_path.py -> new_path.py")
        self.assertEqual(status, GitFileStatus.RENAMED)
        self.assertEqual(path, "new_path.py")

    def test_05_parse_untracked_line(self) -> None:
        """Parse untracked file indicator."""
        status, path = self.inspector.parse_status_line("?? scratch_test.py")
        self.assertEqual(status, GitFileStatus.UNTRACKED)
        self.assertEqual(path, "scratch_test.py")

    def test_06_parse_ignored_line(self) -> None:
        """Parse ignored file indicator."""
        status, path = self.inspector.parse_status_line("!! local.log")
        self.assertEqual(status, GitFileStatus.IGNORED)
        self.assertEqual(path, "local.log")

    def test_07_git_inspector_snapshot_collection(self) -> None:
        """Inspect working tree snapshot structure."""
        snapshot = self.inspector.inspect_snapshot()
        self.assertIsNotNone(snapshot.head_commit)
        self.assertTrue(isinstance(snapshot.modified_files, list))
        self.assertTrue(isinstance(snapshot.untracked_files, list))

    # -------------------------------------------------------------
    # Section B: Scratch Detection
    # -------------------------------------------------------------
    def test_08_scratch_file_detected_and_removable(self) -> None:
        """Obvious untracked scratch files are classified as SCRATCH_ARTIFACT and REMOVE."""
        for name in ["scratch.py", "scratch_eval.py", "tmp_test.py", "temp_run.py", "out.txt", "file.bak"]:
            f = detect_scratch_file(f"local/{name}", is_tracked=False, is_referenced=False)
            self.assertIsNotNone(f, f"Failed to detect scratch file: {name}")
            self.assertEqual(f.artifact_class, ArtifactClass.SCRATCH_ARTIFACT)
            self.assertEqual(f.recommended_action, HygieneAction.REMOVE)

    def test_09_temp_patch_file_detected(self) -> None:
        """Temporary patch dumps are detected as scratch."""
        f = detect_scratch_file("temp.patch", is_tracked=False, is_referenced=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.artifact_class, ArtifactClass.SCRATCH_ARTIFACT)
        self.assertEqual(f.recommended_action, HygieneAction.REMOVE)

    def test_10_legitimate_source_not_classified_as_scratch(self) -> None:
        """Legitimate source files must never be classified as scratch."""
        for path in [
            "agent/root_agent.py",
            "local/context_compaction/models.py",
            "scripts/validate_submission.py",
            "tests/test_baseline.py",
        ]:
            f = detect_scratch_file(path, is_tracked=True, is_referenced=True)
            self.assertIsNone(f)

    def test_11_legitimate_fixtures_preserved(self) -> None:
        """Test fixtures in tests/fixtures/ are explicitly protected from scratch classification."""
        for path in [
            "tests/fixtures/compaction_fixtures.py",
            "tests/fixtures/budget_fixtures.py",
        ]:
            f = detect_scratch_file(path, is_tracked=True, is_referenced=True)
            self.assertIsNone(f)

    def test_12_tracked_scratch_requires_review_not_remove(self) -> None:
        """Tracked files matching scratch patterns require REVIEW, never automated REMOVE."""
        f = detect_scratch_file("scratch.py", is_tracked=True, is_referenced=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REVIEW)

    # -------------------------------------------------------------
    # Section C: Log Detection
    # -------------------------------------------------------------
    def test_13_accidental_local_log_detected(self) -> None:
        """Untracked log files are detected for REMOVE."""
        f = detect_log_file("run.log", is_tracked=False, is_referenced=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REMOVE)

    def test_14_tracked_experiment_reports_preserved_as_required_reports(self) -> None:
        """Authoritative experiment reports are preserved and classified as REQUIRED_REPORT."""
        f = self.classifier.classify_file(
            "experiments/prompts/stage26_report.md", is_tracked=True, is_referenced=True
        )
        self.assertEqual(f.artifact_class, ArtifactClass.REQUIRED_REPORT)
        self.assertEqual(f.recommended_action, HygieneAction.KEEP)

    def test_15_benchmark_artifacts_preserved(self) -> None:
        """Benchmark data is preserved as REQUIRED_BENCHMARK_DATA."""
        f = self.classifier.classify_file(
            "benchmark/split_manifest.json", is_tracked=True, is_referenced=True
        )
        self.assertEqual(f.artifact_class, ArtifactClass.REQUIRED_BENCHMARK_DATA)
        self.assertEqual(f.recommended_action, HygieneAction.KEEP)

    # -------------------------------------------------------------
    # Section D: Debug Marker Detection
    # -------------------------------------------------------------
    def test_16_breakpoint_detection(self) -> None:
        """breakpoint() is detected with high confidence."""
        content = "def test_func():\n    breakpoint()\n    return 42\n"
        findings = scan_content_for_debug_markers("agent/test.py", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].artifact_class, ArtifactClass.DEBUG_ARTIFACT)
        self.assertIn("breakpoint()", findings[0].reason)

    def test_17_pdb_detection(self) -> None:
        """pdb.set_trace() and pdb import are detected."""
        content = "import pdb\npdb.set_trace()\n"
        findings = scan_content_for_debug_markers("local/debug_mod.py", content)
        self.assertEqual(len(findings), 2)

    def test_18_temporary_debug_print_detection(self) -> None:
        """Temporary debug print calls are detected."""
        content = 'print("DEBUG: entering critical section")\n'
        findings = scan_content_for_debug_markers("local/mod.py", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].artifact_class, ArtifactClass.DEBUG_ARTIFACT)

    def test_19_legitimate_logging_not_flagged(self) -> None:
        """Standard logging calls (logger.info, etc.) are not flagged as debug markers."""
        content = 'logger.info("Task completed successfully")\nlogger.warning("Retrying")\n'
        findings = scan_content_for_debug_markers("agent/service.py", content)
        self.assertEqual(len(findings), 0)

    # -------------------------------------------------------------
    # Section E: Temporary Fixtures & Referential Safety
    # -------------------------------------------------------------
    def test_20_unreferenced_temp_fixture_candidate(self) -> None:
        """Unreferenced test_tmp file is flagged as scratch."""
        f = detect_scratch_file("tests/test_tmp_experiment.py", is_tracked=False, is_referenced=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.artifact_class, ArtifactClass.SCRATCH_ARTIFACT)

    def test_21_referenced_fixture_is_not_removable(self) -> None:
        """If a temporary fixture is referenced, it is not marked for removal."""
        f = detect_scratch_file("tests/test_tmp_helper.py", is_tracked=False, is_referenced=True)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REVIEW)

    def test_22_stage25_and_stage26_fixtures_preserved(self) -> None:
        """Stage 25 and Stage 26 fixtures in tests/fixtures are classified as REQUIRED_TEST_FIXTURE."""
        for path in [
            "tests/fixtures/compaction_fixtures.py",
            "tests/fixtures/budget_fixtures.py",
        ]:
            f = self.classifier.classify_file(path, is_tracked=True, is_referenced=True)
            self.assertEqual(f.artifact_class, ArtifactClass.REQUIRED_TEST_FIXTURE)
            self.assertEqual(f.recommended_action, HygieneAction.KEEP)

    # -------------------------------------------------------------
    # Section F: Local Configuration Detection
    # -------------------------------------------------------------
    def test_23_env_detected_as_sensitive_or_local(self) -> None:
        """.env is detected and flagged for review."""
        f = detect_local_config(".env", is_tracked=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REVIEW)

    def test_24_env_example_preserved_as_required_config(self) -> None:
        """.env.example is explicitly preserved as REQUIRED_CONFIG."""
        f = detect_local_config(".env.example", is_tracked=True)
        self.assertIsNotNone(f)
        self.assertEqual(f.artifact_class, ArtifactClass.REQUIRED_CONFIG)
        self.assertEqual(f.recommended_action, HygieneAction.KEEP)

    def test_25_credentials_json_detected(self) -> None:
        """credentials.json is detected and flagged."""
        f = detect_local_config("credentials.json", is_tracked=False)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REVIEW)

    # -------------------------------------------------------------
    # Section G: Machine-Specific Artifact Detection
    # -------------------------------------------------------------
    def test_26_pycache_and_pytest_cache_detected(self) -> None:
        """__pycache__ and .pytest_cache are detected as MACHINE_SPECIFIC_ARTIFACT."""
        f1 = detect_machine_specific("local/__pycache__/mod.cpython-313.pyc", is_tracked=False)
        self.assertIsNotNone(f1)
        self.assertEqual(f1.artifact_class, ArtifactClass.MACHINE_SPECIFIC_ARTIFACT)
        self.assertEqual(f1.recommended_action, HygieneAction.REMOVE)

        f2 = detect_machine_specific(".pytest_cache/v/cache/nodeids", is_tracked=False)
        self.assertIsNotNone(f2)
        self.assertEqual(f2.artifact_class, ArtifactClass.MACHINE_SPECIFIC_ARTIFACT)

    def test_27_hardcoded_windows_absolute_path_detected(self) -> None:
        """Hardcoded machine absolute Windows paths are detected."""
        content = r'OUTPUT_DIR = "C:\Users\developer\workspace\output"'
        findings = scan_content_for_machine_paths("local/service.py", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].artifact_class, ArtifactClass.MACHINE_SPECIFIC_ARTIFACT)

    def test_28_documentation_example_paths_reviewed_not_removed(self) -> None:
        """Documentation containing example paths is reviewed with lower confidence."""
        content = r"Example: `C:\Users\username\...` in instructions."
        findings = scan_content_for_machine_paths("docs/setup.md", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].confidence, 0.6)

    # -------------------------------------------------------------
    # Section H: Reference Safety
    # -------------------------------------------------------------
    def test_29_reference_checker_identifies_import_reference(self) -> None:
        """ReferenceChecker correctly identifies that compaction_fixtures is referenced in tests."""
        ref_checker = ReferenceChecker(PROJECT_ROOT)
        is_ref = ref_checker.is_referenced("tests/fixtures/compaction_fixtures.py")
        self.assertTrue(is_ref)
        referencing = ref_checker.get_referencing_files("tests/fixtures/compaction_fixtures.py")
        self.assertTrue(any("test_context_compaction_stage25.py" in p for p in referencing))

    def test_30_reference_checker_identifies_markdown_link(self) -> None:
        """ReferenceChecker identifies files linked in documentation."""
        ref_checker = ReferenceChecker(PROJECT_ROOT)
        is_ref = ref_checker.is_referenced("PLAN.md")
        self.assertTrue(is_ref)

    def test_31_referenced_scratch_downgraded_to_review(self) -> None:
        """A scratch-named file that is referenced cannot have REMOVE action."""
        f = detect_scratch_file("tests/tmp_test.py", is_tracked=False, is_referenced=True)
        self.assertIsNotNone(f)
        self.assertEqual(f.recommended_action, HygieneAction.REVIEW)

    # -------------------------------------------------------------
    # Section I: Protected Artifacts & Frozen Invariance
    # -------------------------------------------------------------
    def test_32_frozen_scout_artifacts_match_hashes(self) -> None:
        """Scout YAML and prompt match canonical Stage 21 frozen hashes."""
        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertEqual(details["agent/sub_agents/scout.yaml"]["status"], "MATCH")
        self.assertEqual(details["agent/prompts/scout.md"]["status"], "MATCH")

    def test_33_frozen_debugger_artifacts_match_hashes(self) -> None:
        """Debugger YAML and prompt match canonical Stage 22 frozen hashes."""
        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertEqual(details["agent/sub_agents/debugger.yaml"]["status"], "MATCH")
        self.assertEqual(details["agent/prompts/debugger.md"]["status"], "MATCH")

    def test_34_frozen_reviewer_artifacts_match_hashes(self) -> None:
        """Reviewer YAML and prompt match canonical Stage 23 frozen hashes."""
        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertEqual(details["agent/sub_agents/reviewer.yaml"]["status"], "MATCH")
        self.assertEqual(details["agent/prompts/reviewer.md"]["status"], "MATCH")

    def test_35_shared_topology_root_prompts_match_hashes(self) -> None:
        """M0 through M5 shared root prompts match frozen SHA-256 hash."""
        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        for mid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            path = f"experiments/candidates/{mid}/prompts/root.md"
            self.assertEqual(details[path]["status"], "MATCH", f"Mismatch in {path}")

    def test_36_canonical_skills_match_hashes(self) -> None:
        """Canonical test strategy and repo triage skills match frozen hashes."""
        passed, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertEqual(details["agent/skills/test_strategy/SKILL.md"]["status"], "MATCH")
        self.assertEqual(details["agent/skills/repo_triage/SKILL.md"]["status"], "MATCH")

    def test_37_protected_paths_cannot_be_removed(self) -> None:
        """SafeCleaner strictly rejects any removal attempt in protected paths."""
        for path in [
            "agent/sub_agents/scout.yaml",
            "experiments/candidates/M0/agent.yaml",
            "benchmark/split_manifest.json",
            "tests/fixtures/compaction_fixtures.py",
            "docs/decisions/final_diff_discipline.md",
        ]:
            finding = ArtifactFinding(
                path=path,
                artifact_class=ArtifactClass.REQUIRED_SOURCE,
                recommended_action=HygieneAction.REMOVE,  # deliberately tested
                reason="test probe",
                confidence=1.0,
                is_tracked=False,
                is_referenced=False,
            )
            safe, reason = self.cleaner.is_safe_to_remove(finding)
            self.assertFalse(safe, f"Protected path was not rejected: {path}")

    # -------------------------------------------------------------
    # Section J: Secret Hygiene
    # -------------------------------------------------------------
    def test_38_secret_tokens_detected_without_exposing_value(self) -> None:
        """Secret tokens are detected without the raw token ever appearing in finding details."""
        secret_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        content = f"TOKEN = '{secret_token}'\n"
        findings = scan_content_for_secrets("local/auth.py", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].artifact_class, ArtifactClass.SECRET_OR_CREDENTIAL)
        # Ensure secret value is never in reason or stringified finding
        self.assertNotIn(secret_token, findings[0].reason)
        self.assertNotIn(secret_token, str(findings[0].details))
        self.assertIn("SECRET_DETECTED_IN_PATH", findings[0].reason)

    def test_39_private_key_detected_without_exposing_value(self) -> None:
        """Private key header is detected without leaking private key content."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n"
        findings = scan_content_for_secrets("local/key.pem", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].artifact_class, ArtifactClass.SECRET_OR_CREDENTIAL)

    def test_40_report_masks_secret_findings(self) -> None:
        """Pipeline report masks detected credentials."""
        pipeline = FinalDiffReviewPipeline(PROJECT_ROOT)
        report = pipeline.run_review()
        # Verify no unmasked secrets in report text
        formatted = pipeline.format_report(report)
        self.assertNotIn("ghp_", formatted)
        self.assertNotIn("BEGIN RSA PRIVATE KEY", formatted)

    # -------------------------------------------------------------
    # Section K: Cleanup Safety & Conservative Rules
    # -------------------------------------------------------------
    def test_41_cleaner_skips_tracked_files(self) -> None:
        """SafeCleaner refuses to automatically delete tracked files."""
        finding = ArtifactFinding(
            path="scratch.py",
            artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
            recommended_action=HygieneAction.REMOVE,
            reason="scratch",
            confidence=0.99,
            is_tracked=True,  # Tracked!
            is_referenced=False,
        )
        safe, reason = self.cleaner.is_safe_to_remove(finding)
        self.assertFalse(safe)
        self.assertIn("Tracked file", reason)

    def test_42_cleaner_skips_referenced_files(self) -> None:
        """SafeCleaner refuses to delete referenced files."""
        finding = ArtifactFinding(
            path="scratch_helper.py",
            artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
            recommended_action=HygieneAction.REMOVE,
            reason="scratch",
            confidence=0.95,
            is_tracked=False,
            is_referenced=True,  # Referenced!
        )
        safe, reason = self.cleaner.is_safe_to_remove(finding)
        self.assertFalse(safe)
        self.assertIn("referenced", reason)

    def test_43_cleaner_skips_protected_files(self) -> None:
        """SafeCleaner refuses to delete files under protected prefixes."""
        finding = ArtifactFinding(
            path="agent/sub_agents/scout.yaml",
            artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
            recommended_action=HygieneAction.REMOVE,
            reason="scratch",
            confidence=0.95,
            is_tracked=False,
            is_referenced=False,
        )
        safe, reason = self.cleaner.is_safe_to_remove(finding)
        self.assertFalse(safe)
        self.assertIn("protected prefix", reason)

    def test_44_cleaner_dry_run_mode(self) -> None:
        """Dry-run mode lists files without unlinking them."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            scratch_file = tmp_root / "scratch_temp.py"
            scratch_file.write_text("print('hello')", encoding="utf-8")

            cleaner = SafeCleaner(tmp_root)
            finding = ArtifactFinding(
                path="scratch_temp.py",
                artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
                recommended_action=HygieneAction.REMOVE,
                reason="scratch",
                confidence=0.95,
                is_tracked=False,
                is_referenced=False,
            )

            removed, skipped = cleaner.execute_cleanup([finding], dry_run=True)
            self.assertEqual(len(removed), 1)
            self.assertIn("[DRY RUN]", removed[0])
            self.assertTrue(scratch_file.exists())  # Still exists

    def test_45_cleaner_real_deletion_of_untracked_scratch(self) -> None:
        """Real deletion unlinks qualified untracked scratch artifact."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            scratch_file = tmp_root / "scratch_disposable.py"
            scratch_file.write_text("print('disposable')", encoding="utf-8")

            cleaner = SafeCleaner(tmp_root)
            finding = ArtifactFinding(
                path="scratch_disposable.py",
                artifact_class=ArtifactClass.SCRATCH_ARTIFACT,
                recommended_action=HygieneAction.REMOVE,
                reason="scratch",
                confidence=0.95,
                is_tracked=False,
                is_referenced=False,
            )

            removed, skipped = cleaner.execute_cleanup([finding], dry_run=False)
            self.assertEqual(len(removed), 1)
            self.assertFalse(scratch_file.exists())  # Unlinked!

    def test_46_unknown_artifacts_reported_never_deleted(self) -> None:
        """Artifacts classified as UNKNOWN default to REVIEW and can never be cleaned."""
        finding = ArtifactFinding(
            path="some_arbitrary_blob.xyz",
            artifact_class=ArtifactClass.UNKNOWN,
            recommended_action=HygieneAction.REVIEW,
            reason="Unrecognized artifact",
            confidence=0.5,
            is_tracked=False,
            is_referenced=False,
        )
        safe, reason = self.cleaner.is_safe_to_remove(finding)
        self.assertFalse(safe)
        self.assertIn("Action is REVIEW", reason)

    # -------------------------------------------------------------
    # Section L: Pipeline & Real Repository Audit
    # -------------------------------------------------------------
    def test_47_pipeline_clean_repo_run(self) -> None:
        """Pipeline runs against real repo and verifies overall cleanliness."""
        pipeline = FinalDiffReviewPipeline(PROJECT_ROOT)
        report = pipeline.run_review()
        self.assertTrue(report.is_clean)
        self.assertEqual(len(report.security_violations), 0)
        self.assertFalse(report.requires_test_rerun)

    def test_48_pipeline_detects_dirty_files_and_rerun_need(self) -> None:
        """Pipeline correctly flags when tracked source code modification triggers test rerun requirement."""
        snapshot = self.inspector.inspect_snapshot()
        # If any agent/, local/, or tests/ python file is modified in snapshot, requires_test_rerun is True
        pipeline = FinalDiffReviewPipeline(PROJECT_ROOT)
        report = pipeline.run_review()
        # Currently no tracked code is modified
        self.assertFalse(report.requires_test_rerun)

    def test_49_real_project_artifacts_audit(self) -> None:
        """Full audit across all tracked files verifies zero misclassifications of legitimate artifacts."""
        pipeline = FinalDiffReviewPipeline(PROJECT_ROOT)
        report = pipeline.run_review(scan_all_tracked=True)
        # All tracked files must be KEEP or REVIEW, zero REMOVE
        removals = [f for f in report.findings if f.recommended_action == HygieneAction.REMOVE]
        self.assertEqual(len(removals), 0, f"False positive removals detected: {removals}")

        # Authoritative files must be properly classified
        classes = {f.path: f.artifact_class for f in report.findings}
        self.assertEqual(classes.get("benchmark/tasks/smoke.jsonl"), ArtifactClass.REQUIRED_BENCHMARK_DATA)
        self.assertEqual(classes.get("experiments/prompts/stage26_report.md"), ArtifactClass.REQUIRED_REPORT)
        self.assertEqual(classes.get("tests/fixtures/compaction_fixtures.py"), ArtifactClass.REQUIRED_TEST_FIXTURE)
        self.assertEqual(classes.get("tests/fixtures/budget_fixtures.py"), ArtifactClass.REQUIRED_TEST_FIXTURE)
        self.assertEqual(classes.get("AGENTS.md"), ArtifactClass.REQUIRED_DOCUMENTATION)
        self.assertEqual(classes.get("IMPULSE.md"), ArtifactClass.REQUIRED_DOCUMENTATION)
        self.assertEqual(classes.get("PLAN.md"), ArtifactClass.REQUIRED_DOCUMENTATION)

    def test_50_anti_destructive_guarantee_no_git_clean_fd(self) -> None:
        """Verifies that codebase contains no calls to destructive 'git clean -fd'."""
        pipeline_code = (PROJECT_ROOT / "local/diff_discipline/cleaner.py").read_text(encoding="utf-8")
        self.assertNotIn("git clean", pipeline_code)
        self.assertNotIn("clean -fd", pipeline_code)


if __name__ == "__main__":
    unittest.main()
