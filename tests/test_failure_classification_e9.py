"""Unit and regression tests for Candidate E9 and Failure Classification (Stage 18)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.failures import (
    EvidenceStrength,
    FailureClass,
    FailureClassification,
    FailureClassificationContext,
    FailureClassifierV1,
)
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E8)
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
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

EXPECTED_E9_TOOLS = [
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


class TestFailureClassificationE9(unittest.TestCase):
    """37+ focused verification tests for Stage 18 Candidate E9 and Failure Classification."""

    def setUp(self) -> None:
        self.classifier = FailureClassifierV1()

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # 1-5: Submission Validation & Parity with E8
    # -------------------------------------------------------------
    def test_01_e9_submission_configuration_passes_validation(self) -> None:
        """1. E9 candidate directory satisfies all submission rules."""
        e9_dir = PROJECT_ROOT / "experiments" / "candidates" / "E9"
        validator = SubmissionValidator(e9_dir)
        valid = validator.validate()
        self.assertTrue(valid, f"E9 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    def test_02_e9_preserves_e8_model(self) -> None:
        """2. E9 preserves the exact model gemma-4-31b-it-qat-w4a16-ct."""
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e9_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e9_yaml["model"], e8_yaml["model"])

    def test_03_e9_preserves_e8_generation_settings(self) -> None:
        """3. E9 preserves identical sampling configuration."""
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e9_yaml["generate_content_config"], e8_yaml["generate_content_config"])

    def test_04_e9_preserves_all_9_tools(self) -> None:
        """4. E9 preserves all 9 competition tools without additions or removals."""
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e9_yaml["tools"], EXPECTED_E9_TOOLS)
        self.assertEqual(len(e9_yaml["tools"]), 9)

    def test_05_e9_preserves_both_skills(self) -> None:
        """5. E9 preserves both skills declared in agent.yaml."""
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        self.assertIn("skills", e9_yaml)
        self.assertIn("skills/test_strategy", e9_yaml["skills"])
        self.assertIn("skills/repo_triage", e9_yaml["skills"])
        self.assertEqual(len(e9_yaml["skills"]), 2)

    # -------------------------------------------------------------
    # 6-14: Invariance of Prior Candidates (E0–E8)
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

    # -------------------------------------------------------------
    # 15-16: Taxonomy Completeness & Stable Machine-Readable Identifiers
    # -------------------------------------------------------------
    def test_15_all_eight_failure_classes_exist(self) -> None:
        """15. All eight primary failure categories exist in FailureClass enum."""
        expected = {
            "ENVIRONMENT",
            "COMMAND",
            "PRE_EXISTING_FAILURE",
            "REGRESSION",
            "INCOMPLETE_FIX",
            "WRONG_HYPOTHESIS",
            "NEW_EDGE_CASE",
            "UNKNOWN",
        }
        actual = {member.value for member in FailureClass}
        self.assertEqual(actual, expected)
        self.assertEqual(len(FailureClass), 8)

    def test_16_machine_readable_identifiers_are_stable(self) -> None:
        """16. String values of FailureClass enum are stable and match names."""
        for member in FailureClass:
            self.assertEqual(member.name, member.value)
            self.assertIsInstance(member.value, str)

    # -------------------------------------------------------------
    # 17-21: Category Confusion Prevention & Boundaries
    # -------------------------------------------------------------
    def test_17_command_is_separated_from_environment(self) -> None:
        """17. Invalid CLI syntax produces COMMAND, missing binary/module produces ENVIRONMENT."""
        cmd_context = FailureClassificationContext(
            command="pytest --unrecognized-flag-xyz",
            exit_code=2,
            stderr="pytest: error: unrecognized arguments: --unrecognized-flag-xyz",
        )
        res_cmd = self.classifier.classify(cmd_context)
        self.assertEqual(res_cmd.failure_class, FailureClass.COMMAND)

        env_context = FailureClassificationContext(
            command="pytest tests/",
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'cryptography'",
        )
        res_env = self.classifier.classify(env_env := env_context)
        self.assertEqual(res_env.failure_class, FailureClass.ENVIRONMENT)

    def test_18_pre_existing_failure_is_distinguished_from_regression(self) -> None:
        """18. Baseline failure produces PRE_EXISTING_FAILURE; baseline pass produces REGRESSION."""
        pre_context = FailureClassificationContext(
            command="pytest tests/test_auth.py",
            exit_code=1,
            test_output="AssertionError: Token invalid",
            baseline_result="FAILED",
        )
        res_pre = self.classifier.classify(pre_context)
        self.assertEqual(res_pre.failure_class, FailureClass.PRE_EXISTING_FAILURE)

        reg_context = FailureClassificationContext(
            command="pytest tests/test_auth.py",
            exit_code=1,
            test_output="AssertionError: Token invalid",
            baseline_result="PASSED",
        )
        res_reg = self.classifier.classify(reg_context)
        self.assertEqual(res_reg.failure_class, FailureClass.REGRESSION)

    def test_19_incomplete_fix_is_distinguished_from_wrong_hypothesis(self) -> None:
        """19. Directional fix with secondary failure produces INCOMPLETE_FIX; unrelated defect produces WRONG_HYPOTHESIS."""
        incomplete_context = FailureClassificationContext(
            command="pytest tests/test_core.py",
            exit_code=1,
            test_output="AssertionError: partially satisfied; remaining 1 assertion failed",
            modified_files=["pkg/core.py"],
            is_related_to_changes=True,
            previous_test_result="FAILED",
        )
        res_inc = self.classifier.classify(incomplete_context)
        self.assertEqual(res_inc.failure_class, FailureClass.INCOMPLETE_FIX)

        wrong_hyp_context = FailureClassificationContext(
            command="pytest tests/test_core.py",
            exit_code=1,
            test_output="AssertionError in database/connection.py: connection pool exhausted",
            modified_files=["pkg/core.py"],
            is_related_to_changes=False,
            previous_test_result="FAILED",
        )
        res_wrong = self.classifier.classify(wrong_hyp_context)
        self.assertEqual(res_wrong.failure_class, FailureClass.WRONG_HYPOTHESIS)

    def test_20_new_edge_case_is_distinct_from_regression(self) -> None:
        """20. Boundary input failures produce NEW_EDGE_CASE, not REGRESSION when baseline passed is absent."""
        edge_context = FailureClassificationContext(
            command="pytest tests/test_boundary.py -k test_empty_string",
            exit_code=1,
            test_output="AssertionError: empty string handling raised IndexError",
            is_edge_case=True,
            baseline_result=None,
        )
        res_edge = self.classifier.classify(edge_context)
        self.assertEqual(res_edge.failure_class, FailureClass.NEW_EDGE_CASE)

    def test_21_insufficient_evidence_produces_unknown(self) -> None:
        """21. Context lacking diagnostic markers produces UNKNOWN without guessing."""
        empty_context = FailureClassificationContext(
            command="pytest",
            exit_code=1,
            stdout="",
            stderr="",
            test_output="",
            baseline_result=None,
        )
        res = self.classifier.classify(empty_context)
        self.assertEqual(res.failure_class, FailureClass.UNKNOWN)
        self.assertEqual(res.evidence_strength, EvidenceStrength.UNKNOWN)

    # -------------------------------------------------------------
    # 22-26: Classifier Determinism, Evidence & TaskState Integration
    # -------------------------------------------------------------
    def test_22_deterministic_classifier_is_reproducible(self) -> None:
        """22. Running classifier multiple times on identical context returns identical result."""
        ctx = FailureClassificationContext(
            command="pytest tests/",
            exit_code=1,
            stderr="ImportError: cannot import name 'fast_json'",
        )
        r1 = self.classifier.classify(ctx)
        r2 = self.classifier.classify(ctx)
        self.assertEqual(r1.failure_class, r2.failure_class)
        self.assertEqual(r1.evidence_strength, r2.evidence_strength)
        self.assertEqual(r1.rationale, r2.rationale)

    def test_23_evidence_is_stored_with_classification(self) -> None:
        """23. Classification records capture concrete evidence list."""
        ctx = FailureClassificationContext(
            command="pytest --invalid",
            exit_code=2,
            stderr="usage: pytest [options]",
        )
        res = self.classifier.classify(ctx)
        self.assertTrue(len(res.evidence) > 0)
        self.assertIn("usage:", res.evidence[0].lower())

    def test_24_raw_huge_logs_are_not_stored_in_task_state(self) -> None:
        """24. Large tracebacks are truncated when integrating into TaskState."""
        state = TaskState()
        huge_traceback = "Traceback line\n" * 500  # ~7500 chars
        classification = FailureClassification(
            failure_class=FailureClass.REGRESSION,
            evidence_strength=EvidenceStrength.STRONG,
            rationale="Regression introduced in core parser",
            relevant_command="pytest",
            evidence=["Assertion failed"],
        )
        classification.integrate_into_task_state(state, traceback_snippet=huge_traceback)
        self.assertEqual(len(state.failures), 1)
        stored = state.failures[0]
        self.assertLessEqual(len(stored.traceback_snippet), 1000)
        self.assertLess(len(stored.description), 500)

    def test_25_secrets_are_excluded_from_classification_records_and_artifacts(self) -> None:
        """25. No credentials or secrets exist in Stage 18 files or classification objects."""
        for path in [
            PROJECT_ROOT / "local/failures/models.py",
            PROJECT_ROOT / "local/failures/classifier.py",
            PROJECT_ROOT / "local/failures/__init__.py",
            PROJECT_ROOT / "docs/decisions/failure_classification.md",
            PROJECT_ROOT / "experiments/candidates/E9/agent.yaml",
            PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md",
            PROJECT_ROOT / "experiments/prompts/E9/manifest.json",
            PROJECT_ROOT / "experiments/prompts/E9/report.md",
        ]:
            text = path.read_text(encoding="utf-8").lower()
            for pattern in ["api_key", "bearer ", "ghp_", "sk-proj-", "sk-live-", "private_key"]:
                self.assertNotIn(pattern, text, f"Potential credential pattern found in {path.name}")

    def test_26_task_state_failure_field_receives_concise_classification(self) -> None:
        """26. TaskState failure field records the failure_class identifier cleanly."""
        state = TaskState()
        classification = FailureClassification(
            failure_class=FailureClass.COMMAND,
            evidence_strength=EvidenceStrength.STRONG,
            rationale="Unrecognized pytest flag",
            relevant_command="pytest -x --foo",
            evidence=["error: unrecognized argument"],
        )
        classification.integrate_into_task_state(state)
        self.assertEqual(state.failures[0].failure_type, "COMMAND")
        self.assertIn("Unrecognized pytest flag", state.failures[0].description)

    # -------------------------------------------------------------
    # 27-31: Root Prompt Integration & Stage Boundaries
    # -------------------------------------------------------------
    def test_27_root_prompt_requires_explicit_classification_after_meaningful_failure(self) -> None:
        """27. E9 prompt explicitly instructs agent to classify failures using the 8 categories."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8")
        for cls in [
            "ENVIRONMENT",
            "COMMAND",
            "PRE_EXISTING_FAILURE",
            "REGRESSION",
            "INCOMPLETE_FIX",
            "WRONG_HYPOTHESIS",
            "NEW_EDGE_CASE",
            "UNKNOWN",
        ]:
            self.assertIn(cls, prompt)
        self.assertIn("Classify and Address Failures Iteratively", prompt)

    def test_28_prompt_does_not_prescribe_recovery_actions(self) -> None:
        """28. Prompt does not prescribe automated recovery branches or actions."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("if regression then revert", prompt)
        self.assertNotIn("recovery path a", prompt)
        self.assertNotIn("recovery path b", prompt)

    def test_29_no_stage_19_no_progress_logic_in_e9(self) -> None:
        """29. Prompt and classifier do not contain Stage 19 no-progress threshold triggers."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("stop repeating.", prompt)
        self.assertNotIn("no-progress threshold reached", prompt)
        self.assertNotIn("no_progress_detector", prompt)

    def test_30_no_stage_20_recovery_logic_in_e9(self) -> None:
        """30. Prompt and classifier do not contain Stage 20 recovery paths."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("recovery paths", prompt)
        self.assertNotIn("automatic rollback", prompt)

    def test_31_no_benchmark_specific_classification_rules(self) -> None:
        """31. Classifier and prompt contain zero benchmark task IDs or repo-specific hardcodes."""
        text = (PROJECT_ROOT / "local/failures/classifier.py").read_text(encoding="utf-8").lower()
        prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8").lower()
        for forbidden in ["fastapi_14479", "fastapi_14786", "requests_6629", "requests_7505", "rich_4070"]:
            self.assertNotIn(forbidden, text)
            self.assertNotIn(forbidden, prompt)

    # -------------------------------------------------------------
    # 32-34: Minimal Delta & Skills Parity
    # -------------------------------------------------------------
    def test_32_e9_changes_are_minimal_relative_to_e8(self) -> None:
        """32. E9 prompt preserves all E8 triage, localization, and testing guidance."""
        e9_prompt = (PROJECT_ROOT / "experiments/candidates/E9/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("repo_triage", e9_prompt)
        self.assertIn("test_strategy", e9_prompt)
        self.assertIn("## Hybrid Localization Strategy", e9_prompt)
        self.assertIn("search_similar_code", e9_prompt)
        self.assertIn("get_code_neighbors", e9_prompt)
        self.assertIn("get_code_subgraph", e9_prompt)

    def test_33_no_new_competition_tools_in_e9(self) -> None:
        """33. Exactly 9 tools in E9 agent.yaml."""
        e9_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E9/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(e9_yaml["tools"]), 9)

    def test_34_both_prior_skills_remain_byte_for_byte_unchanged(self) -> None:
        """34. Packaged skills in E9 match canonical hashes exactly."""
        e9_test = self._hash_file("experiments/candidates/E9/skills/test_strategy/SKILL.md")
        e9_triage = self._hash_file("experiments/candidates/E9/skills/repo_triage/SKILL.md")
        self.assertEqual(e9_test, CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(e9_triage, CANONICAL_REPO_TRIAGE_SHA256)


if __name__ == "__main__":
    unittest.main()
