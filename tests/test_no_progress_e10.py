"""Unit and regression tests for Candidate E10 and No-Progress Detection (Stage 19)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.failures import FailureClass
from local.progress import (
    CycleSnapshot,
    NoProgressDetectorV1,
    NoProgressReason,
    ProgressAssessment,
    ProgressStatus,
)
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E9)
E0_AGENT_SHA256 = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
E0_PROMPT_SHA256 = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"
E1_AGENT_SHA256 = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
E1_PROMPT_SHA256 = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"
E2_AGENT_SHA256 = "cefb9297917626ba10f07b39a2769a668246b6a3d13f4f6e1ffde08f0c62df04"
E2_PROMPT_SHA256 = "f8358618a67353d0a456ece8dc037bbdaefe108d99fa4f997e5daf4fb354fd4e"
E3_AGENT_SHA256 = "2cf03011fc03c37292a1b0cdd74ae9d512f97bd8f1a5148939410e96c5e6b783"
E3_PROMPT_SHA256 = "6925be383fbbdd0f58a885a82c02b5e9fefe434d8cb7f91d6b5107ada9e120cf"
E4_AGENT_SHA256 = "ec3cddcf88d5e04a2415dac7a59aed6464ce0e379f301ae4df24e507368953ca"
E4_PROMPT_SHA256 = "4a7eefeb785bf1334e2f6f85a2f6b9ebeb5349f42b0acb3327d19bbd9ad7008d"
E5_AGENT_SHA256 = "137e26ebcd7018bdad4b488f71d1221b06f979f2b3f5d8ac9179f89c95f6cf28"
E5_PROMPT_SHA256 = "d4128a6dc3d016422370cb6354a355971408463399196dcaf97e7ce04ec83756"
E6_AGENT_SHA256 = "c2dec89c9df91bc9c0324ab43c379f7ef9fc6a79ae35af3bdd09e13e0d093724"
E6_PROMPT_SHA256 = "fe9805fc39ef2e4861aa4ea9b0956985080012acef70397b3f485f083733278e"
E7_AGENT_SHA256 = "92021a5379f36c7eeacca0962f666494efe028c973148f8e0f412812479692a0"
E7_PROMPT_SHA256 = "d1195b317a475a2411b99b49d701d16e71bedd9b3c6c035d800970e15914950d"
E8_AGENT_SHA256 = "c7c7f49faae94b904357583b2fc0e46ce9be0999688641f5d18e8a1e0e905f15"
E8_PROMPT_SHA256 = "d607c494fc32f3132df3301bccc693adf8ba4074bdbc190860b1df65b6f78220"
E9_AGENT_SHA256 = "eba7d0f032fa169918e2e3e1a1606ead98d1d825688db2817625922dd5ecc977"
E9_PROMPT_SHA256 = "a03fba7410c03d0929d95653ad892c42f802d2a0a017eab92a2e2168bee2fc48"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

EXPECTED_E10_TOOLS = [
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
]


class TestNoProgressE10(unittest.TestCase):
    """37+ focused verification tests for Stage 19 Candidate E10 and No-Progress Detection."""

    def setUp(self) -> None:
        self.detector = NoProgressDetectorV1(threshold=2)

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # 1-5: Submission Validation & Parity with E9
    # -------------------------------------------------------------
    def test_01_e10_submission_configuration_passes_validation(self) -> None:
        """1. E10 candidate directory satisfies all submission rules."""
        e10_dir = PROJECT_ROOT / "experiments" / "candidates" / "E10"
        validator = SubmissionValidator(e10_dir)
        valid = validator.validate()
        self.assertTrue(valid, f"E10 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    def test_02_e10_preserves_e9_model(self) -> None:
        """2. E10 preserves the exact model gemma-4-31b-it-qat-w4a16-ct."""
        e10_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E10/agent.yaml").read_text(encoding="utf-8"))
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e10_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e10_yaml["model"], e9_yaml["model"])

    def test_03_e10_preserves_e9_generation_settings(self) -> None:
        """3. E10 preserves identical sampling configuration."""
        e10_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E10/agent.yaml").read_text(encoding="utf-8"))
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e10_yaml["generate_content_config"], e9_yaml["generate_content_config"])

    def test_04_e10_preserves_all_9_tools(self) -> None:
        """4. E10 preserves all 9 competition tools without additions or removals."""
        e10_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E10/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e10_yaml["tools"], EXPECTED_E10_TOOLS)
        self.assertEqual(len(e10_yaml["tools"]), 9)

    def test_05_e10_preserves_both_skills(self) -> None:
        """5. E10 preserves both skills declared in agent.yaml."""
        e10_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E10/agent.yaml").read_text(encoding="utf-8"))
        self.assertIn("skills", e10_yaml)
        self.assertIn("skills/test_strategy", e10_yaml["skills"])
        self.assertIn("skills/repo_triage", e10_yaml["skills"])
        self.assertEqual(len(e10_yaml["skills"]), 2)

    # -------------------------------------------------------------
    # 6-15: Invariance of Prior Candidates (E0–E9)
    # -------------------------------------------------------------
    def test_06_e0_remains_unchanged(self) -> None:
        """6. E0 files remain strictly invariant."""
        self.assertEqual(self._hash_file("agent/agent.yaml"), E0_AGENT_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/root.md"), E0_PROMPT_SHA256)

    def test_07_e1_remains_unchanged(self) -> None:
        """7. E1 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E1/agent.yaml"), E1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E1/prompts/root.md"), E1_PROMPT_SHA256)

    def test_08_e2_remains_unchanged(self) -> None:
        """8. E2 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E2/agent.yaml"), E2_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E2/prompts/root.md"), E2_PROMPT_SHA256)

    def test_09_e3_remains_unchanged(self) -> None:
        """9. E3 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E3/agent.yaml"), E3_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E3/prompts/root.md"), E3_PROMPT_SHA256)

    def test_10_e4_remains_unchanged(self) -> None:
        """10. E4 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E4/agent.yaml"), E4_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E4/prompts/root.md"), E4_PROMPT_SHA256)

    def test_11_e5_remains_unchanged(self) -> None:
        """11. E5 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E5/agent.yaml"), E5_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E5/prompts/root.md"), E5_PROMPT_SHA256)

    def test_12_e6_remains_unchanged(self) -> None:
        """12. E6 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E6/agent.yaml"), E6_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E6/prompts/root.md"), E6_PROMPT_SHA256)

    def test_13_e7_remains_unchanged(self) -> None:
        """13. E7 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E7/agent.yaml"), E7_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E7/prompts/root.md"), E7_PROMPT_SHA256)

    def test_14_e8_remains_unchanged(self) -> None:
        """14. E8 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E8/agent.yaml"), E8_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E8/prompts/root.md"), E8_PROMPT_SHA256)

    def test_15_e9_remains_unchanged(self) -> None:
        """15. E9 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E9/agent.yaml"), E9_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E9/prompts/root.md"), E9_PROMPT_SHA256)

    # -------------------------------------------------------------
    # 16-24: Core Detection Rules & State Transitions
    # -------------------------------------------------------------
    def test_16_one_failure_is_not_no_progress(self) -> None:
        """16. A single failure baseline cycle never triggers NO_PROGRESS."""
        cycle1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            failure_signature="test_parser: AssertionError: expected 42 got 0",
            hypothesis="Parser omits integer token conversion",
        )
        res = self.detector.record_cycle(cycle1)
        self.assertNotEqual(res.status, ProgressStatus.NO_PROGRESS)
        self.assertEqual(res.status, ProgressStatus.PROGRESS)
        self.assertEqual(res.consecutive_no_progress_count, 1)

    def test_17_repeated_identical_failure_triggers_no_progress(self) -> None:
        """17. Repeated identical failure reaching threshold=2 triggers NO_PROGRESS."""
        cycle1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            failure_signature="test_parser: AssertionError: expected 42 got 0",
            hypothesis="Parser omits integer token conversion",
            edit_content="diff --git a/core.py b/core.py\n+ int(val)",
        )
        cycle2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            failure_signature="test_parser: AssertionError: expected 42 got 0",
            hypothesis="Parser omits integer token conversion",
            edit_content="diff --git a/core.py b/core.py\n+ int(val)",
        )
        self.detector.record_cycle(cycle1)
        res2 = self.detector.record_cycle(cycle2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)
        self.assertIn(res2.reason, [NoProgressReason.REPEATED_FAILURE, NoProgressReason.REPEATED_EDIT, NoProgressReason.REPEATED_HYPOTHESIS])
        self.assertEqual(res2.consecutive_no_progress_count, 2)

    def test_18_repeated_failure_with_new_evidence_is_progress(self) -> None:
        """18. Same test failing but new diagnostic evidence recorded counts as PROGRESS."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            failure_signature="test_parser: AssertionError",
            evidence_items=["Error in parse_int"],
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            failure_signature="test_parser: AssertionError",
            evidence_items=["Error in parse_int", "Discovered unhandled float token at index 5"],
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.PROGRESS)
        self.assertEqual(res2.reason, NoProgressReason.NONE)

    def test_19_repeated_hypothesis_triggers_no_progress(self) -> None:
        """19. Repeated hypothesis across unsuccessful cycles triggers NO_PROGRESS."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            hypothesis="Memory leak in connection pool",
            failure_signature="ConnectionError: pool exhausted",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            hypothesis="Memory leak in connection pool",
            failure_signature="ConnectionError: pool exhausted",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)

    def test_20_changed_hypothesis_counts_as_progress(self) -> None:
        """20. Revising the hypothesis counts as PROGRESS and resets streak."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            hypothesis="Memory leak in connection pool",
            failure_signature="ConnectionError: pool exhausted",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest tests/test_core.py",
            test_result="FAILED",
            hypothesis="Timeout setting is configured in seconds instead of milliseconds",
            failure_signature="ConnectionError: pool exhausted",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.PROGRESS)
        self.assertEqual(res2.reason, NoProgressReason.NONE)

    def test_21_repeated_equivalent_edit_triggers_no_progress(self) -> None:
        """21. Attempting materially identical code edits triggers REPEATED_EDIT."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest",
            test_result="FAILED",
            edit_content="x = 10\ny = 20\n",
            failure_signature="test_err",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest",
            test_result="FAILED",
            edit_content="x = 10\ny = 20\n",
            failure_signature="test_err",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)
        self.assertEqual(res2.reason, NoProgressReason.REPEATED_EDIT)

    def test_22_changed_relevant_source_state_counts_as_progress(self) -> None:
        """22. Modifying a different relevant source file counts as PROGRESS."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_command="pytest",
            test_result="FAILED",
            modified_files=["pkg/auth.py"],
            relevant_source_files=["pkg/auth.py", "pkg/client.py"],
            failure_signature="err",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_command="pytest",
            test_result="FAILED",
            modified_files=["pkg/client.py"],
            relevant_source_files=["pkg/auth.py", "pkg/client.py"],
            failure_signature="err",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.PROGRESS)

    def test_23_successful_verification_resets_streak(self) -> None:
        """23. A PASSED test result immediately resets the no-progress streak."""
        c1 = CycleSnapshot(cycle_id=1, test_result="FAILED", failure_signature="err")
        c2 = CycleSnapshot(cycle_id=2, test_result="FAILED", failure_signature="err")
        self.detector.record_cycle(c1)
        res_fail = self.detector.record_cycle(c2)
        self.assertEqual(res_fail.status, ProgressStatus.NO_PROGRESS)

        c3 = CycleSnapshot(cycle_id=3, test_result="PASSED")
        res_pass = self.detector.record_cycle(c3)
        self.assertEqual(res_pass.status, ProgressStatus.PROGRESS)
        self.assertEqual(res_pass.consecutive_no_progress_count, 0)

    def test_24_changed_failure_signature_counts_as_progress(self) -> None:
        """24. Execution advancing to a different failing assertion resets streak."""
        c1 = CycleSnapshot(cycle_id=1, test_result="FAILED", failure_signature="test_step1: AssertionError")
        c2 = CycleSnapshot(cycle_id=2, test_result="FAILED", failure_signature="test_step2: IndexError")
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.PROGRESS)

    # -------------------------------------------------------------
    # 25-28: Normalization, Noise & Insufficient Evidence
    # -------------------------------------------------------------
    def test_25_unrelated_file_changes_do_not_falsely_count_as_progress(self) -> None:
        """25. Modifying docs or scratch files while relevant source files unchanged does not grant progress."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_result="FAILED",
            modified_files=["pkg/core.py"],
            relevant_source_files=["pkg/core.py"],
            failure_signature="same_error",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_result="FAILED",
            modified_files=["pkg/core.py", "docs/notes.md"],
            relevant_source_files=["pkg/core.py"],
            failure_signature="same_error",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)

    def test_26_whitespace_only_edits_do_not_count_as_meaningful_progress(self) -> None:
        """26. Edits differing only by whitespace/formatting do not grant progress."""
        c1 = CycleSnapshot(
            cycle_id=1,
            test_result="FAILED",
            edit_content="def func():\n    return 42\n",
            failure_signature="test_fail",
        )
        c2 = CycleSnapshot(
            cycle_id=2,
            test_result="FAILED",
            edit_content="def func():   \n\n    return 42  \n",
            failure_signature="test_fail",
        )
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)
        self.assertEqual(res2.reason, NoProgressReason.REPEATED_EDIT)

    def test_27_repeated_command_execution_with_same_outcome_does_not_count_as_progress(self) -> None:
        """27. Invoking the exact same command with identical outcome triggers NO_PROGRESS."""
        c1 = CycleSnapshot(cycle_id=1, test_command="pytest -k test_auth", test_result="FAILED", failure_signature="401")
        c2 = CycleSnapshot(cycle_id=2, test_command="pytest -k test_auth", test_result="FAILED", failure_signature="401")
        self.detector.record_cycle(c1)
        res2 = self.detector.record_cycle(c2)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)

    def test_28_insufficient_evidence_produces_insufficient_evidence_status(self) -> None:
        """28. Empty snapshot triggers INSUFFICIENT_EVIDENCE."""
        empty_cycle = CycleSnapshot()
        res = self.detector.record_cycle(empty_cycle)
        self.assertEqual(res.status, ProgressStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(res.reason, NoProgressReason.UNKNOWN)

    # -------------------------------------------------------------
    # 29-32: Configurable Threshold, Determinism & TaskState
    # -------------------------------------------------------------
    def test_29_configurable_threshold_works(self) -> None:
        """29. Custom threshold (e.g. 3) requires 3 consecutive cycles before NO_PROGRESS."""
        detector3 = NoProgressDetectorV1(threshold=3)
        c1 = CycleSnapshot(cycle_id=1, test_result="FAILED", failure_signature="err")
        c2 = CycleSnapshot(cycle_id=2, test_result="FAILED", failure_signature="err")
        c3 = CycleSnapshot(cycle_id=3, test_result="FAILED", failure_signature="err")

        detector3.record_cycle(c1)
        r2 = detector3.record_cycle(c2)
        self.assertEqual(r2.status, ProgressStatus.PROGRESS)  # Streak 2 < 3
        r3 = detector3.record_cycle(c3)
        self.assertEqual(r3.status, ProgressStatus.NO_PROGRESS)  # Streak 3 >= 3
        self.assertEqual(r3.consecutive_no_progress_count, 3)

    def test_30_detector_is_reproducible_across_identical_inputs(self) -> None:
        """30. Multiple runs on identical sequences yield identical ProgressAssessment objects."""
        c1 = CycleSnapshot(cycle_id=1, test_result="FAILED", failure_signature="err")
        c2 = CycleSnapshot(cycle_id=2, test_result="FAILED", failure_signature="err")

        d1 = NoProgressDetectorV1(threshold=2)
        d2 = NoProgressDetectorV1(threshold=2)

        d1.record_cycle(c1)
        res1 = d1.record_cycle(c2)

        d2.record_cycle(c1)
        res2 = d2.record_cycle(c2)

        self.assertEqual(res1.status, res2.status)
        self.assertEqual(res1.reason, res2.reason)
        self.assertEqual(res1.consecutive_no_progress_count, res2.consecutive_no_progress_count)

    def test_31_task_state_integration_updates_counters_and_evidence(self) -> None:
        """31. ProgressAssessment integrates cleanly into TaskState without bloat."""
        state = TaskState()
        self.assertEqual(state.no_progress_count, 0)

        assessment = ProgressAssessment(
            status=ProgressStatus.NO_PROGRESS,
            reason=NoProgressReason.REPEATED_FAILURE,
            consecutive_no_progress_count=2,
            threshold=2,
            rationale="Repeated failure on test_auth across 2 cycles",
            signals=["Same error trace"],
        )
        assessment.integrate_into_task_state(state)
        self.assertEqual(state.no_progress_count, 1)
        self.assertTrue(any("No-progress detected" in e.observation for e in state.evidence))

        pass_assessment = ProgressAssessment(
            status=ProgressStatus.PROGRESS,
            reason=NoProgressReason.NONE,
            consecutive_no_progress_count=0,
            threshold=2,
            rationale="Verification passed",
        )
        pass_assessment.integrate_into_task_state(state)
        self.assertEqual(state.no_progress_count, 0)

    def test_32_no_secrets_and_bounded_logs_in_stage_19_artifacts(self) -> None:
        """32. No credentials, tokens, or unbounded logs in Stage 19 files."""
        for path in [
            PROJECT_ROOT / "local/progress/models.py",
            PROJECT_ROOT / "local/progress/detector.py",
            PROJECT_ROOT / "local/progress/__init__.py",
            PROJECT_ROOT / "docs/decisions/no_progress_detection.md",
            PROJECT_ROOT / "experiments/candidates/E10/agent.yaml",
            PROJECT_ROOT / "experiments/candidates/E10/prompts/root.md",
            PROJECT_ROOT / "experiments/prompts/E10/manifest.json",
            PROJECT_ROOT / "experiments/prompts/E10/report.md",
        ]:
            text = path.read_text(encoding="utf-8").lower()
            for pattern in ["api_key", "bearer ", "ghp_", "sk-proj-", "sk-live-", "private_key"]:
                self.assertNotIn(pattern, text, f"Potential credential pattern found in {path.name}")

    # -------------------------------------------------------------
    # 33-37: Prompt, Skills & Stage 20 Exclusion
    # -------------------------------------------------------------
    def test_33_e10_prompt_integrates_progress_monitoring(self) -> None:
        """33. E10 prompt contains explicit instructions to monitor progress and record NO_PROGRESS."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E10/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("REPEATED_FAILURE", prompt)
        self.assertIn("REPEATED_HYPOTHESIS", prompt)
        self.assertIn("REPEATED_EDIT", prompt)
        self.assertIn("NO_NEW_EVIDENCE", prompt)
        self.assertIn("Classify Failures and Monitor Progress Iteratively", prompt)

    def test_34_prompt_contains_no_stage_20_recovery_instructions(self) -> None:
        """34. Prompt strictly excludes Stage 20 recovery paths and rollback commands."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E10/prompts/root.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("recovery path a", prompt)
        self.assertNotIn("recovery path b", prompt)
        self.assertNotIn("automatic rollback", prompt)
        self.assertNotIn("rollback to base", prompt)
        self.assertNotIn("scout agent", prompt)
        self.assertNotIn("debugger agent", prompt)

    def test_35_packaged_skills_match_canonical_hashes_exactly(self) -> None:
        """35. Packaged skills in E10 match canonical versions byte-for-byte."""
        e10_test = self._hash_file("experiments/candidates/E10/skills/test_strategy/SKILL.md")
        e10_triage = self._hash_file("experiments/candidates/E10/skills/repo_triage/SKILL.md")
        self.assertEqual(e10_test, CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(e10_triage, CANONICAL_REPO_TRIAGE_SHA256)

    def test_36_failure_classification_remains_unchanged(self) -> None:
        """36. E9 failure classification taxonomy and models are preserved unchanged."""
        from local.failures.models import FailureClass as E9FailureClass
        self.assertEqual(len(E9FailureClass), 8)
        self.assertEqual(E9FailureClass.REGRESSION.value, "REGRESSION")

    def test_37_no_benchmark_specific_hardcoding(self) -> None:
        """37. Prompt and detector contain zero benchmark task IDs or repo-specific hardcodes."""
        text = (PROJECT_ROOT / "local/progress/detector.py").read_text(encoding="utf-8").lower()
        prompt = (PROJECT_ROOT / "experiments/candidates/E10/prompts/root.md").read_text(encoding="utf-8").lower()
        for forbidden in ["fastapi_14479", "fastapi_14786", "requests_6629", "requests_7505", "rich_4070"]:
            self.assertNotIn(forbidden, text)
            self.assertNotIn(forbidden, prompt)


if __name__ == "__main__":
    unittest.main()
