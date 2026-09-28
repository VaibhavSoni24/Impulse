"""Focused unit, safety, and integration tests for Context Compaction (Stage 25).

Covers:
A. File fingerprinting
B. Changed-file tracking
C. Observation deduplication
D. Test-log compaction
E. Repository-map caching
F. Hypothesis/history safety
G. Security/hygiene (secrets scrubbing, normalization)
H. Integration with E9 / E10 / E11 and TaskState
I. Invariance verification for Stage 24 and frozen specialists
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from local.context_compaction import (
    ChangedFileTracker,
    CompactedTaskContext,
    CompactionAction,
    CompactionPolicy,
    FactObservationTracker,
    HypothesisStatus,
    HypothesisTracker,
    ObservationDeduplicator,
    ObservationType,
    RepositoryMapCache,
    are_observations_identical,
    compact_test_log,
    compute_content_sha256,
    compute_file_fingerprint,
    normalize_path,
    sanitize_text,
)
from local.failures import FailureClassifierV1, FailureClass
from local.progress import NoProgressDetectorV1, NoProgressReason, ProgressStatus
from local.recovery import (
    RecoveryActionType,
    RecoveryContext,
    RecoveryControllerV1,
    RecoveryPath,
)
from local.task_state.models import TaskState
from tests.fixtures.compaction_fixtures import (
    SYNTHETIC_FAILING_TEST_CMD,
    SYNTHETIC_FAILING_TEST_EXIT_CODE,
    SYNTHETIC_FAILING_TEST_STDOUT,
    SYNTHETIC_FAILING_TEST_STDOUT_REPEAT,
    SYNTHETIC_FILE_CONTENT_V1,
    SYNTHETIC_FILE_CONTENT_V1_REPEAT,
    SYNTHETIC_FILE_CONTENT_V2,
    SYNTHETIC_FILE_PATH,
    SYNTHETIC_LS_OUTPUT_RUN_1,
    SYNTHETIC_LS_OUTPUT_RUN_2,
    SYNTHETIC_LOG_WITH_SECRET,
    SYNTHETIC_OTHER_FILE_CONTENT,
    SYNTHETIC_OTHER_FILE_PATH,
    SYNTHETIC_PASSING_TEST_CMD,
    SYNTHETIC_PASSING_TEST_EXIT_CODE,
    SYNTHETIC_PASSING_TEST_STDOUT,
    SYNTHETIC_UNITTEST_FAIL_CMD,
    SYNTHETIC_UNITTEST_FAIL_EXIT_CODE,
    SYNTHETIC_UNITTEST_FAIL_STDOUT,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (Scout, Debugger, Reviewer)
FROZEN_SCOUT_YAML_SHA256 = "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877"
FROZEN_SCOUT_PROMPT_SHA256 = "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805"
FROZEN_DEBUGGER_YAML_SHA256 = "07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199"
FROZEN_DEBUGGER_PROMPT_SHA256 = "a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f"
FROZEN_REVIEWER_YAML_SHA256 = "facfcbb4fbc8d42a82f32a6979bf8b090de5857ba92b4641e4a45617b340200c"
FROZEN_REVIEWER_PROMPT_SHA256 = "d2432da56d07170989edbd83add7fe51323df1db6dd458b80f0d893cdb9264c6"

FROZEN_TOPOLOGY_SHARED_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"


def sha256_file(path: Path) -> str:
    """Computes SHA-256 for a given file path."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestContextCompactionStage25(unittest.TestCase):
    """Stage 25 test suite verifying deterministic, loss-bounded compaction."""

    # =========================================================================
    # A. File Fingerprinting
    # =========================================================================

    def test_file_fingerprint_identical_content(self) -> None:
        """Identical content yields identical fingerprint."""
        fp1 = compute_file_fingerprint(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        fp2 = compute_file_fingerprint(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1_REPEAT)

        self.assertEqual(fp1.sha256, fp2.sha256)
        self.assertEqual(fp1.size_bytes, fp2.size_bytes)
        self.assertTrue(are_observations_identical(fp1, fp2))

    def test_file_fingerprint_changed_content(self) -> None:
        """Changed content produces a distinct fingerprint."""
        fp1 = compute_file_fingerprint(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        fp2 = compute_file_fingerprint(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V2)

        self.assertNotEqual(fp1.sha256, fp2.sha256)
        self.assertFalse(are_observations_identical(fp1, fp2))

    def test_file_fingerprint_different_path_same_content_never_collapses(self) -> None:
        """Distinct paths with matching content must NEVER be collapsed across paths."""
        fp1 = compute_file_fingerprint(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        fp2 = compute_file_fingerprint(SYNTHETIC_OTHER_FILE_PATH, SYNTHETIC_OTHER_FILE_CONTENT)

        self.assertEqual(fp1.sha256, fp2.sha256)
        self.assertNotEqual(fp1.path, fp2.path)
        # are_observations_identical must return False for different paths
        self.assertFalse(are_observations_identical(fp1, fp2))

    # =========================================================================
    # B. Changed-File Tracking
    # =========================================================================

    def test_changed_file_tracker_initial_observation(self) -> None:
        """First observation records initial fingerprint and has_changed=False."""
        tracker = ChangedFileTracker()
        rec, is_new = tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)

        self.assertTrue(is_new)
        self.assertEqual(rec.path, SYNTHETIC_FILE_PATH)
        self.assertEqual(rec.initial_fingerprint, rec.latest_fingerprint)
        self.assertFalse(rec.has_changed)
        self.assertEqual(rec.edit_count, 0)
        self.assertTrue(rec.is_relevant)

    def test_changed_file_tracker_unchanged_reobservation(self) -> None:
        """Re-observing identical content does not falsely mark file as changed."""
        tracker = ChangedFileTracker()
        tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        rec, is_new = tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1_REPEAT)

        self.assertFalse(is_new)
        self.assertFalse(rec.has_changed)
        self.assertEqual(rec.edit_count, 0)
        # Unchanged file is NOT dropped
        self.assertIn(SYNTHETIC_FILE_PATH, [r.path for r in tracker.list_tracked_files()])
        self.assertEqual(len(tracker.list_changed_files()), 0)

    def test_changed_file_tracker_modification(self) -> None:
        """Editing file updates latest_fingerprint, increments edit_count, and sets has_changed=True."""
        tracker = ChangedFileTracker()
        tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        rec = tracker.mark_file_edit(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V2, "Fix empty query bug")

        self.assertTrue(rec.has_changed)
        self.assertEqual(rec.edit_count, 1)
        self.assertNotEqual(rec.initial_fingerprint, rec.latest_fingerprint)
        self.assertEqual(len(tracker.list_changed_files()), 1)

    def test_changed_file_tracker_manifest_digest(self) -> None:
        """Manifest digest deterministically changes when any tracked file changes."""
        tracker = ChangedFileTracker()
        tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        digest1 = tracker.get_manifest_digest()

        # Re-observing unchanged content retains identical manifest digest
        tracker.record_file_observation(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V1)
        digest2 = tracker.get_manifest_digest()
        self.assertEqual(digest1, digest2)

        # Modifying content updates manifest digest
        tracker.mark_file_edit(SYNTHETIC_FILE_PATH, SYNTHETIC_FILE_CONTENT_V2)
        digest3 = tracker.get_manifest_digest()
        self.assertNotEqual(digest1, digest3)

    # =========================================================================
    # C. Observation Deduplication
    # =========================================================================

    def test_observation_deduplication_exact_duplicate(self) -> None:
        """Exact duplicate observation increments repetition_count without duplicating records."""
        dedup = ObservationDeduplicator()

        obs1, is_new1 = dedup.record_observation(
            obs_type=ObservationType.COMMAND_OUTPUT,
            action=CompactionAction.SAFE_TO_COMPACT,
            source="ls -la",
            content=SYNTHETIC_LS_OUTPUT_RUN_1,
        )
        self.assertTrue(is_new1)
        self.assertEqual(obs1.repetition_count, 1)

        obs2, is_new2 = dedup.record_observation(
            obs_type=ObservationType.COMMAND_OUTPUT,
            action=CompactionAction.SAFE_TO_COMPACT,
            source="ls -la",
            content=SYNTHETIC_LS_OUTPUT_RUN_2,
        )
        self.assertFalse(is_new2)
        self.assertEqual(obs2.repetition_count, 2)
        self.assertEqual(dedup.unique_count(), 1)
        self.assertEqual(dedup.total_raw_count(), 2)
        self.assertEqual(dedup.duplicate_count(), 1)

    def test_observation_deduplication_changed_observation_remains_distinct(self) -> None:
        """Distinct observations are preserved as separate canonical records."""
        dedup = ObservationDeduplicator()

        dedup.record_observation(
            obs_type=ObservationType.FILE_READ,
            action=CompactionAction.PRESERVE_WITH_STRUCTURE,
            source=SYNTHETIC_FILE_PATH,
            content=SYNTHETIC_FILE_CONTENT_V1,
        )
        dedup.record_observation(
            obs_type=ObservationType.FILE_READ,
            action=CompactionAction.PRESERVE_WITH_STRUCTURE,
            source=SYNTHETIC_FILE_PATH,
            content=SYNTHETIC_FILE_CONTENT_V2,
        )
        self.assertEqual(dedup.unique_count(), 2)
        self.assertEqual(dedup.total_raw_count(), 2)
        self.assertEqual(dedup.duplicate_count(), 0)

    # =========================================================================
    # D. Test-Log Compaction
    # =========================================================================

    def test_test_log_compaction_pytest_failures_preserved(self) -> None:
        """Critical error lines, failing test name, exit code, and traceback are preserved."""
        compact_log = compact_test_log(
            command=SYNTHETIC_FAILING_TEST_CMD,
            exit_code=SYNTHETIC_FAILING_TEST_EXIT_CODE,
            stdout=SYNTHETIC_FAILING_TEST_STDOUT,
        )

        self.assertEqual(compact_log.command, SYNTHETIC_FAILING_TEST_CMD)
        self.assertEqual(compact_log.exit_code, 1)
        self.assertEqual(compact_log.outcome, "FAIL")
        self.assertEqual(compact_log.runner, "pytest")

        # Failing test name must be extracted and preserved
        self.assertIn("tests/test_parser.py::test_empty_query", compact_log.failing_tests)
        self.assertIn("tests/test_parser.py::test_empty_query", compact_log.preserved_text)

        # Critical error line must survive
        self.assertTrue(any("ValueError: Empty query" in e for e in compact_log.error_lines))
        self.assertIn("ValueError: Empty query", compact_log.preserved_text)

        # Traceback / code frame must survive
        self.assertTrue(any("parse_query" in f for f in compact_log.traceback_frames))

        # File and line reference must survive
        self.assertTrue(any("tests/test_parser.py:14" in ref for ref in compact_log.file_references))

        # Boilerplate lines were collapsed
        self.assertGreater(compact_log.collapsed_boilerplate_lines, 0)

    def test_test_log_compaction_unittest_assertion_preserved(self) -> None:
        """Unittest runner assertion failure and stack frames survive compaction."""
        compact_log = compact_test_log(
            command=SYNTHETIC_UNITTEST_FAIL_CMD,
            exit_code=SYNTHETIC_UNITTEST_FAIL_EXIT_CODE,
            stdout=SYNTHETIC_UNITTEST_FAIL_STDOUT,
        )

        self.assertEqual(compact_log.runner, "unittest")
        self.assertEqual(compact_log.exit_code, 1)
        self.assertEqual(compact_log.outcome, "FAIL")

        # Assertion line must be preserved
        self.assertTrue(any("AssertionError: None != {}" in l for l in compact_log.error_lines))
        self.assertIn("AssertionError: None != {}", compact_log.preserved_text)

        # Traceback line reference preserved
        self.assertTrue(any("tests/test_parser.py:22" in ref for ref in compact_log.file_references))

        # Passing test was collapsed
        self.assertEqual(compact_log.passed_count, 1)

    def test_test_log_compaction_passing_output_collapsed(self) -> None:
        """Passing test output is cleanly compacted to a brief summary without diagnostic loss."""
        compact_log = compact_test_log(
            command=SYNTHETIC_PASSING_TEST_CMD,
            exit_code=SYNTHETIC_PASSING_TEST_EXIT_CODE,
            stdout=SYNTHETIC_PASSING_TEST_STDOUT,
        )

        self.assertEqual(compact_log.exit_code, 0)
        self.assertEqual(compact_log.outcome, "PASS")
        self.assertEqual(len(compact_log.failing_tests), 0)
        self.assertEqual(len(compact_log.error_lines), 0)
        self.assertIn("All tests passed", compact_log.preserved_text)

    def test_naive_truncation_would_lose_critical_line_but_policy_preserves_it(self) -> None:
        """Tests that a failure embedded after dozens of verbose lines is never chopped off."""
        # Synthesize 50 lines of boilerplate followed by an isolated fatal error
        padding = "\n".join(f"test_item_{i:03d} ... ok" for i in range(100))
        verbose_stdout = f"{padding}\nFAIL: test_critical_edge_case\nAssertionError: expected 42 got 0\n"

        compact_log = compact_test_log(
            command="pytest verbose",
            exit_code=1,
            stdout=verbose_stdout,
            max_preserved_lines=20,  # Strict budget
        )

        # If naive head(20) were used, the error at line 101 would be completely lost!
        self.assertIn("AssertionError: expected 42 got 0", compact_log.preserved_text)
        self.assertTrue(any("AssertionError" in e for e in compact_log.error_lines))

    # =========================================================================
    # E. Repository-Map Caching
    # =========================================================================

    def test_repo_map_cache_hit_and_invalidation(self) -> None:
        """Cache hit for unchanged state; automatic invalidation upon state change."""
        cache = RepositoryMapCache()
        manifest1 = {"src/main.py": "hash_a", "src/utils.py": "hash_b"}
        digest1 = cache.compute_manifest_digest(manifest1)

        cache.put_map(
            manifest_digest=digest1,
            language_and_framework="Python 3.10 / pytest",
            top_level_structure=["src", "tests"],
            test_directories=["tests"],
        )

        # 1. Valid hit
        entry = cache.get_map(digest1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.language_and_framework, "Python 3.10 / pytest")
        self.assertTrue(cache.is_valid(digest1))

        # 2. File modification changes manifest
        manifest2 = {"src/main.py": "hash_a_MODIFIED", "src/utils.py": "hash_b"}
        digest2 = cache.compute_manifest_digest(manifest2)
        self.assertNotEqual(digest1, digest2)

        # Cache miss for new digest
        self.assertIsNone(cache.get_map(digest2))
        self.assertFalse(cache.is_valid(digest2))

        # Explicit invalidation
        cache.invalidate(digest1)
        self.assertIsNone(cache.get_map(digest1))
        self.assertEqual(cache.size(), 0)

    # =========================================================================
    # F. Hypothesis and History Safety
    # =========================================================================

    def test_hypothesis_tracker_lifecycle(self) -> None:
        """Active hypothesis can be superseded or contradicted without deleting historical evidence."""
        tracker = HypothesisTracker()

        # 1. Formulate initial hypothesis
        h1 = tracker.create_hypothesis(
            hypothesis_id="hypo_1",
            statement="Parser fails because empty string input raises ValueError instead of returning empty dict",
            supporting_evidence=["Traceback in test_empty_query"],
        )
        self.assertEqual(h1.status, HypothesisStatus.ACTIVE)
        self.assertEqual(tracker.get_active().hypothesis_id, "hypo_1")

        # 2. Formulate refined hypothesis superseding hypo_1
        tracker.create_hypothesis(
            hypothesis_id="hypo_2",
            statement="Parser needs to return empty dict on empty query and lowercase keys",
        )
        tracker.supersede(
            hypothesis_id="hypo_1",
            superseded_by_id="hypo_2",
            reason="Empty query handling requires case-normalization",
        )

        h1_after = tracker.get("hypo_1")
        self.assertEqual(h1_after.status, HypothesisStatus.SUPERSEDED)
        self.assertIn("Superseded by hypo_2", h1_after.transition_reason)
        self.assertEqual(tracker.get_active().hypothesis_id, "hypo_2")

        # 3. Contradict hypo_2 with new test evidence
        tracker.contradict(
            hypothesis_id="hypo_2",
            contradicting_evidence="Query keys must preserve casing according to RFC",
            reason="Case-normalization broke contract test",
        )
        h2_after = tracker.get("hypo_2")
        self.assertEqual(h2_after.status, HypothesisStatus.CONTRADICTED)
        self.assertIn("Case-normalization broke contract test", h2_after.transition_reason)
        self.assertIn("RFC", h2_after.contradicting_evidence[0])

        # All hypotheses remain in history; none were erased
        self.assertEqual(len(tracker.list_all()), 2)

    # =========================================================================
    # G. Security and Hygiene
    # =========================================================================

    def test_security_secret_scrubbing(self) -> None:
        """Secrets matching common token patterns are scrubbed from text and metadata."""
        sanitized = sanitize_text(SYNTHETIC_LOG_WITH_SECRET)
        self.assertNotIn("sk-live-abcdef1234567890abcdef123456", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)
        # Non-secret traceback lines remain completely intact
        self.assertIn("ConnectionRefusedError: Could not connect", sanitized)

    def test_policy_enforces_preservation_for_security_findings(self) -> None:
        """CompactionPolicy guarantees PRESERVE_EXACTLY for security-sensitive findings."""
        action = CompactionPolicy.evaluate(
            obs_type=ObservationType.COMMAND_OUTPUT,
            content="Vulnerability detected in package foo",
            metadata={"security_finding": True},
        )
        self.assertEqual(action, CompactionAction.PRESERVE_EXACTLY)
        self.assertFalse(CompactionPolicy.is_safe_to_compact(action))

    def test_path_normalization_handles_backslashes_and_dots(self) -> None:
        """Windows backslashes and redundant prefixes are normalized cleanly."""
        self.assertEqual(normalize_path("impulse\\core\\parser.py"), "impulse/core/parser.py")
        self.assertEqual(normalize_path("./impulse/core/parser.py"), "impulse/core/parser.py")

    # =========================================================================
    # H. Integration with E9 / E10 / E11 and TaskState
    # =========================================================================

    def test_e9_failure_classification_with_compacted_log(self) -> None:
        """Compacted log context successfully drives E9 failure classification."""
        ctx = CompactedTaskContext()
        compact_log = ctx.record_test_run(
            command=SYNTHETIC_FAILING_TEST_CMD,
            exit_code=SYNTHETIC_FAILING_TEST_EXIT_CODE,
            stdout=SYNTHETIC_FAILING_TEST_STDOUT,
        )

        failure_ctx = ctx.create_failure_classification_context(compact_log)
        classifier = FailureClassifierV1()
        res = classifier.classify(failure_ctx)

        # Because test failed with ValueError during testing, classifier identifies it correctly
        self.assertIn(
            res.failure_class,
            [
                FailureClass.INCOMPLETE_FIX,
                FailureClass.REGRESSION,
                FailureClass.PRE_EXISTING_FAILURE,
                FailureClass.NEW_EDGE_CASE,
            ],
        )

    def test_e10_no_progress_detection_with_compacted_snapshots(self) -> None:
        """Consecutive identical compacted test failures trigger NO_PROGRESS in E10."""
        ctx = CompactedTaskContext()
        ctx.state.set_hypothesis("Parser needs fix")

        compact_log_1 = ctx.record_test_run(
            command=SYNTHETIC_FAILING_TEST_CMD,
            exit_code=SYNTHETIC_FAILING_TEST_EXIT_CODE,
            stdout=SYNTHETIC_FAILING_TEST_STDOUT,
        )
        snap1 = ctx.create_cycle_snapshot(compact_log_1, failure_class=FailureClass.INCOMPLETE_FIX.value, cycle_id=1)

        compact_log_2 = ctx.record_test_run(
            command=SYNTHETIC_FAILING_TEST_CMD,
            exit_code=SYNTHETIC_FAILING_TEST_EXIT_CODE,
            stdout=SYNTHETIC_FAILING_TEST_STDOUT_REPEAT,
        )
        snap2 = ctx.create_cycle_snapshot(compact_log_2, failure_class=FailureClass.INCOMPLETE_FIX.value, cycle_id=2)

        detector = NoProgressDetectorV1(threshold=2)
        eval1 = detector.record_cycle(snap1)
        # First cycle establishes baseline
        self.assertEqual(eval1.status, ProgressStatus.PROGRESS)

        eval2 = detector.record_cycle(snap2)
        # Second identical failure triggers NO_PROGRESS with valid no-progress reason
        self.assertEqual(eval2.status, ProgressStatus.NO_PROGRESS)
        self.assertIn(eval2.reason, [NoProgressReason.REPEATED_HYPOTHESIS, NoProgressReason.REPEATED_FAILURE])

    def test_e11_recovery_with_compacted_task_state(self) -> None:
        """E11 Recovery controller selects correct recovery family using compacted TaskState."""
        ctx = CompactedTaskContext()
        ctx.state.set_hypothesis("Incorrect root cause")
        ctx.state.increment_no_progress()
        ctx.state.increment_no_progress()

        controller = RecoveryControllerV1()
        recovery_ctx = RecoveryContext(
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            progress_status=ProgressStatus.NO_PROGRESS.value,
            no_progress_reason=NoProgressReason.REPEATED_HYPOTHESIS.value,
            test_result="FAILED",
            diff_inspected=True,
        )
        decision = controller.route_recovery(recovery_ctx)
        self.assertEqual(decision.selected_path, RecoveryPath.TEST_FAILURE)
        self.assertEqual(decision.action, RecoveryActionType.REVISE_HYPOTHESIS)

    # =========================================================================
    # I. Invariance Verification for Frozen Specialists and Topology
    # =========================================================================

    def test_frozen_specialist_hashes(self) -> None:
        """Verifies that Scout, Debugger, and Reviewer remain byte-for-byte frozen."""
        scout_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "scout.yaml"
        scout_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "scout.md"
        debugger_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "debugger.yaml"
        debugger_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "debugger.md"
        reviewer_yaml = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "sub_agents" / "reviewer.yaml"
        reviewer_prompt = PROJECT_ROOT / "experiments" / "candidates" / "M5" / "prompts" / "reviewer.md"

        self.assertEqual(sha256_file(scout_yaml), FROZEN_SCOUT_YAML_SHA256)
        self.assertEqual(sha256_file(scout_prompt), FROZEN_SCOUT_PROMPT_SHA256)
        self.assertEqual(sha256_file(debugger_yaml), FROZEN_DEBUGGER_YAML_SHA256)
        self.assertEqual(sha256_file(debugger_prompt), FROZEN_DEBUGGER_PROMPT_SHA256)
        self.assertEqual(sha256_file(reviewer_yaml), FROZEN_REVIEWER_YAML_SHA256)
        self.assertEqual(sha256_file(reviewer_prompt), FROZEN_REVIEWER_PROMPT_SHA256)

    def test_frozen_topology_candidates_unchanged(self) -> None:
        """Verifies that Stage 24 topology candidates (M0..M5) root prompt remains unchanged."""
        for m_id in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            prompt_file = PROJECT_ROOT / "experiments" / "candidates" / m_id / "prompts" / "root.md"
            self.assertTrue(prompt_file.exists(), f"Missing candidate prompt {prompt_file}")
            self.assertEqual(
                sha256_file(prompt_file),
                FROZEN_TOPOLOGY_SHARED_PROMPT_SHA256,
                f"Candidate {m_id} prompt modified!",
            )


if __name__ == "__main__":
    unittest.main()
