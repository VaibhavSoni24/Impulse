"""Unit and regression tests for Candidate V0/V1 and Reviewer Agent (Stage 23).

Validates:
A. Configuration (1-5)
B. Read-only enforcement (6-10)
C. Input contract & normalization (11-16)
D. Output contract & bounded serialization (17-26)
E. Review logic (27-33)
F. Trigger determinism (34-37)
G. Loop prevention (38-41)
H. Candidate isolation V0 vs V1 (42-50)
I. Prior-stage invariance (51-56)
J. Submission validation & anti-overfitting (57-61)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.failures import FailureClass
from local.progress import NoProgressReason, ProgressStatus
from local.recovery import RecoveryControllerV1, RecoveryPath
from local.reviewer import (
    ReviewerControllerV1,
    ReviewerInput,
    ReviewerPolicy,
    ReviewerResult,
    ReviewerStatus,
    ReviewerTriggerContext,
    evaluate_review_findings,
    evaluate_reviewer_trigger,
    is_review_ready,
)
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Canonical hashes for Stage 21, Stage 22, and Skills
CANONICAL_SCOUT_YAML_SHA256 = "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877"
CANONICAL_SCOUT_MD_SHA256 = "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805"
CANONICAL_DEBUGGER_YAML_SHA256 = "07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199"
CANONICAL_DEBUGGER_MD_SHA256 = "a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

EXPECTED_ROOT_TOOLS = [
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

EXPECTED_READONLY_TOOLS = [
    "read_file",
    "get_status",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
]


class TestReviewerStage23(unittest.TestCase):
    """61 verification tests for Stage 23 Candidates V0 / V1 and the Reviewer agent."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # A. Configuration (1 - 5)
    # -------------------------------------------------------------
    def test_01_reviewer_config_parses_under_harness_schema(self) -> None:
        """1. Reviewer YAML configuration parses into a valid mapping."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/reviewer.yaml"
        self.assertTrue(cfg_path.exists())
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("name"), "reviewer")

    def test_02_reviewer_uses_exact_competition_model(self) -> None:
        """2. Reviewer declares the exact model gemma-4-31b-it-qat-w4a16-ct."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/reviewer.yaml"
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.get("model"), "gemma-4-31b-it-qat-w4a16-ct")

    def test_03_reviewer_valid_sub_agent_declaration(self) -> None:
        """3. Candidate V1 declares reviewer under sub_agents."""
        yaml_path = PROJECT_ROOT / "experiments/candidates/V1/agent.yaml"
        parsed = parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
        self.assertIn("sub_agents", parsed)
        sub_agents = parsed["sub_agents"]
        config_paths = [sa["config_path"] for sa in sub_agents if isinstance(sa, dict)]
        self.assertIn("sub_agents/reviewer.yaml", config_paths)

    def test_04_reviewer_included_only_in_v1(self) -> None:
        """4. Candidate V0 does NOT configure Reviewer; V1 does."""
        v0_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V0/agent.yaml").read_text(encoding="utf-8"))
        v0_sub = [sa["config_path"] for sa in v0_cfg.get("sub_agents", [])]
        self.assertNotIn("sub_agents/reviewer.yaml", v0_sub)

        v1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V1/agent.yaml").read_text(encoding="utf-8"))
        v1_sub = [sa["config_path"] for sa in v1_cfg.get("sub_agents", [])]
        self.assertIn("sub_agents/reviewer.yaml", v1_sub)

    def test_05_reviewer_prompt_exists_and_forbids_mutations(self) -> None:
        """5. Reviewer prompt exists and explicitly enforces read-only behavior."""
        prompt_path = PROJECT_ROOT / "agent/prompts/reviewer.md"
        self.assertTrue(prompt_path.exists())
        content = prompt_path.read_text(encoding="utf-8")
        self.assertIn("READ ONLY", content)
        self.assertIn("Do not modify any repository file", content)
        self.assertIn("submit_patch", content)

    # -------------------------------------------------------------
    # B. Read-Only Enforcement (6 - 10)
    # -------------------------------------------------------------
    def test_06_reviewer_has_no_edit_file(self) -> None:
        """6. Reviewer does not expose edit_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("edit_file", cfg.get("tools", []))

    def test_07_reviewer_has_no_write_file(self) -> None:
        """7. Reviewer does not expose write_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("write_file", cfg.get("tools", []))

    def test_08_reviewer_has_no_submit_patch(self) -> None:
        """8. Reviewer does not expose submit_patch."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("submit_patch", cfg.get("tools", []))

    def test_09_reviewer_has_no_destructive_commands(self) -> None:
        """9. Reviewer does not expose run_command (strictly read-only tools)."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("run_command", cfg.get("tools", []))
        self.assertEqual(cfg.get("tools"), EXPECTED_READONLY_TOOLS)

    def test_10_structured_result_cannot_mutate_repository_state(self) -> None:
        """10. ReviewerResult integration mutates only TaskState evidence/review notes, not filesystem."""
        state = TaskState(summary="Initial state before review")
        result = ReviewerResult(
            status=ReviewerStatus.APPROVE,
            summary="Clean patch verified with passing tests.",
            observed_evidence=["test_parser passed"],
        )
        result.integrate_into_task_state(state)
        self.assertTrue(state.final_review.diff_inspected)
        self.assertTrue(state.final_review.intended_files_only)
        self.assertIn("Clean patch verified", state.final_review.notes)
        self.assertEqual(len(state.evidence), 1)

    # -------------------------------------------------------------
    # C. Inputs Contract (11 - 16)
    # -------------------------------------------------------------
    def test_11_issue_is_accepted(self) -> None:
        """11. ReviewerInput correctly accepts and stores the issue statement."""
        inp = ReviewerInput(issue="Fix zero division in math_utils.py")
        self.assertEqual(inp.issue, "Fix zero division in math_utils.py")

    def test_12_diff_summary_is_accepted(self) -> None:
        """12. ReviewerInput correctly accepts and stores the diff summary."""
        inp = ReviewerInput(diff_summary="+ if denom == 0:\n+     return 0")
        self.assertIn("denom == 0", inp.diff_summary)

    def test_13_relevant_tests_are_accepted(self) -> None:
        """13. ReviewerInput correctly accepts and stores the relevant tests list."""
        inp = ReviewerInput(relevant_tests=["tests/test_math.py::test_zero_div"])
        self.assertEqual(len(inp.relevant_tests), 1)
        self.assertIn("test_zero_div", inp.relevant_tests[0])

    def test_14_result_summary_is_accepted(self) -> None:
        """14. ReviewerInput correctly accepts and stores the verification result summary."""
        inp = ReviewerInput(result_summary="1 passed in 0.05s")
        self.assertEqual(inp.result_summary, "1 passed in 0.05s")

    def test_15_bounded_input_normalization(self) -> None:
        """15. ReviewerInput.normalize truncates excessively long strings and lists."""
        long_issue = "x" * 5000
        long_diff = "y" * 5000
        huge_tests = [f"test_{i}" for i in range(100)]
        inp = ReviewerInput(issue=long_issue, diff_summary=long_diff, relevant_tests=huge_tests)
        norm = inp.normalize()
        self.assertLessEqual(len(norm.issue), 2000)
        self.assertLessEqual(len(norm.diff_summary), 2000)
        self.assertLessEqual(len(norm.relevant_tests), 20)

    def test_16_missing_evidence_is_represented_safely(self) -> None:
        """16. Empty fields in ReviewerInput do not raise exceptions and trigger missing evidence findings."""
        inp = ReviewerInput()
        res = evaluate_review_findings(inp)
        self.assertIn(res.status, [ReviewerStatus.INSUFFICIENT_EVIDENCE, ReviewerStatus.CHANGES_REQUESTED])
        self.assertTrue(len(res.missing_evidence) > 0)

    # -------------------------------------------------------------
    # D. Output Contract (17 - 26)
    # -------------------------------------------------------------
    def test_17_approve_status(self) -> None:
        """17. ReviewerStatus supports APPROVE and serializes properly."""
        res = ReviewerResult(status=ReviewerStatus.APPROVE)
        self.assertEqual(res.to_dict()["status"], "APPROVE")

    def test_18_changes_requested_status(self) -> None:
        """18. ReviewerStatus supports CHANGES_REQUESTED and serializes properly."""
        res = ReviewerResult(status=ReviewerStatus.CHANGES_REQUESTED)
        self.assertEqual(res.to_dict()["status"], "CHANGES_REQUESTED")

    def test_19_insufficient_evidence_status(self) -> None:
        """19. ReviewerStatus supports INSUFFICIENT_EVIDENCE and serializes properly."""
        res = ReviewerResult(status=ReviewerStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(res.to_dict()["status"], "INSUFFICIENT_EVIDENCE")

    def test_20_blocking_findings_recorded(self) -> None:
        """20. ReviewerResult records and preserves blocking findings."""
        res = ReviewerResult(blocking_findings=["Failing verification test"])
        d = res.to_dict()
        self.assertEqual(d["blocking_findings"], ["Failing verification test"])

    def test_21_nonblocking_findings_recorded(self) -> None:
        """21. ReviewerResult records and preserves nonblocking findings."""
        res = ReviewerResult(nonblocking_findings=["Unused import in test file"])
        d = res.to_dict()
        self.assertEqual(d["nonblocking_findings"], ["Unused import in test file"])

    def test_22_required_followups_recorded(self) -> None:
        """22. ReviewerResult records and preserves required followups."""
        res = ReviewerResult(required_followups=["Remove unused import"])
        d = res.to_dict()
        self.assertEqual(d["required_followups"], ["Remove unused import"])

    def test_23_observed_evidence_separate_from_inferred_risks(self) -> None:
        """23. Output maintains strict distinction between observed evidence and inferred risks."""
        res = ReviewerResult(
            observed_evidence=["Line 42 of parser.py modified"],
            inferred_risks=["Potential boundary mismatch for negative integers"],
        )
        d = res.to_dict()
        self.assertEqual(len(d["observed_evidence"]), 1)
        self.assertEqual(len(d["inferred_risks"]), 1)
        self.assertNotEqual(d["observed_evidence"], d["inferred_risks"])

    def test_24_bounded_output_lengths(self) -> None:
        """24. ReviewerResult.to_dict enforces maximum length on text fields and lists."""
        long_str = "z" * 2000
        huge_list = [f"item_{i}" for i in range(100)]
        res = ReviewerResult(
            issue_alignment=long_str,
            blocking_findings=huge_list,
        )
        d = res.to_dict()
        self.assertLessEqual(len(d["issue_alignment"]), 500)
        self.assertLessEqual(len(d["blocking_findings"]), 20)

    def test_25_no_raw_log_dumping_in_summary(self) -> None:
        """25. ReviewerResult.format_summary does not dump raw test output or unbounded text."""
        res = ReviewerResult(
            status=ReviewerStatus.APPROVE,
            summary="Clean patch with passing test suite.",
            observed_evidence=["Passed test_math.py"],
        )
        formatted = res.format_summary()
        self.assertIn("=== Reviewer Assessment Result ===", formatted)
        self.assertNotIn("Traceback (most recent call last):", formatted)

    def test_26_no_secrets_in_result_contract(self) -> None:
        """26. ReviewerResult does not define secret or credential storage fields."""
        res = ReviewerResult()
        d = res.to_dict()
        for forbidden in ["token", "secret", "password", "api_key", "credentials"]:
            self.assertNotIn(forbidden, d)

    # -------------------------------------------------------------
    # E. Review Logic (27 - 33)
    # -------------------------------------------------------------
    def test_27_issue_alignment_finding(self) -> None:
        """27. Detects missing issue statement as an alignment evidence deficiency."""
        inp = ReviewerInput(
            diff_summary="+ fix code",
            relevant_tests=["test_a"],
            verification_status="PASSED",
        )
        res = evaluate_review_findings(inp)
        self.assertTrue(any("Issue statement" in m for m in res.missing_evidence))

    def test_28_unrelated_diff_finding(self) -> None:
        """28. Flags modifications to unrelated infrastructure (e.g. .github/ workflows) as blocking."""
        inp = ReviewerInput(
            issue="Fix bug",
            diff_summary="+ update ci",
            relevant_tests=["test_a"],
            verification_status="PASSED",
            modified_files=[".github/workflows/ci.yml"],
        )
        res = evaluate_review_findings(inp)
        self.assertEqual(res.status, ReviewerStatus.CHANGES_REQUESTED)
        self.assertTrue(any("infrastructure files modified" in b for b in res.blocking_findings))

    def test_29_test_insufficiency_finding(self) -> None:
        """29. Flags missing test execution as missing evidence."""
        inp = ReviewerInput(
            issue="Fix bug",
            diff_summary="+ some code",
            relevant_tests=[],
            verification_status="",
        )
        res = evaluate_review_findings(inp)
        self.assertTrue(any("No relevant tests" in m for m in res.missing_evidence))

    def test_30_regression_risk_finding(self) -> None:
        """30. Flags failed verification outcome as a blocking finding with elevated regression risk."""
        inp = ReviewerInput(
            issue="Fix bug",
            diff_summary="+ some code",
            relevant_tests=["test_a"],
            verification_status="FAILED",
            result_summary="AssertionError: expected 1 got 2",
        )
        res = evaluate_review_findings(inp)
        self.assertEqual(res.status, ReviewerStatus.CHANGES_REQUESTED)
        self.assertTrue(any("reported FAILED" in b for b in res.blocking_findings))

    def test_31_scope_finding(self) -> None:
        """31. Appropriately reports modified file count in diff scope."""
        inp = ReviewerInput(
            issue="Fix bug",
            diff_summary="+ some code",
            relevant_tests=["test_a"],
            verification_status="PASSED",
            modified_files=["src/core.py", "tests/test_core.py"],
        )
        res = evaluate_review_findings(inp)
        self.assertIn("2 file(s)", res.diff_scope)

    def test_32_security_hygiene_finding(self) -> None:
        """32. Flags accidental inclusion of GitHub tokens (ghp_*) as blocking."""
        inp = ReviewerInput(
            issue="Fix bug",
            diff_summary="+ token = 'ghp_123456789012345678901234567890123456'",
            relevant_tests=["test_a"],
            verification_status="PASSED",
            modified_files=["src/auth.py"],
        )
        res = evaluate_review_findings(inp)
        self.assertEqual(res.status, ReviewerStatus.CHANGES_REQUESTED)
        self.assertTrue(any("GitHub Personal Access Token" in b for b in res.blocking_findings))

    def test_33_no_finding_when_evidence_supports_clean_review(self) -> None:
        """33. Returns APPROVE when clean code, relevant tests, and passing verification are supplied."""
        inp = ReviewerInput(
            issue="Fix IndexError in parser",
            diff_summary="+ if idx < len(tokens):\n+     return tokens[idx]",
            relevant_tests=["tests/test_parser.py::test_bounds"],
            verification_status="PASSED",
            result_summary="1 passed in 0.02s",
            modified_files=["src/parser.py"],
        )
        res = evaluate_review_findings(inp)
        self.assertEqual(res.status, ReviewerStatus.APPROVE)
        self.assertEqual(len(res.blocking_findings), 0)

    # -------------------------------------------------------------
    # F. Trigger Evaluation (34 - 37)
    # -------------------------------------------------------------
    def test_34_completed_patch_and_verification_can_trigger_review(self) -> None:
        """34. REVIEWER_TRIGGER fires when candidate diff and verification evidence exist."""
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            is_final_review_point=True,
        )
        ready, reason = is_review_ready(ctx)
        self.assertTrue(ready)
        self.assertIn("ready for final review", reason)

    def test_35_empty_diff_does_not_trigger_review(self) -> None:
        """35. Empty candidate diff does NOT trigger review."""
        ctx = ReviewerTriggerContext(
            has_candidate_diff=False,
            verification_attempted=True,
            has_result_summary=True,
        )
        ready, reason = is_review_ready(ctx)
        self.assertFalse(ready)
        self.assertIn("Candidate diff is empty", reason)

    def test_36_no_verification_result_does_not_falsely_appear_review_ready(self) -> None:
        """36. Omitted verification result summary does not trigger review."""
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=False,
        )
        ready, reason = is_review_ready(ctx)
        self.assertFalse(ready)
        self.assertIn("Result summary is missing", reason)

    def test_37_trigger_deterministic_for_identical_state(self) -> None:
        """37. Evaluating the trigger context twice produces identical decisions."""
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            is_final_review_point=True,
        )
        r1, m1 = is_review_ready(ctx)
        r2, m2 = is_review_ready(ctx)
        self.assertEqual(r1, r2)
        self.assertEqual(m1, m2)

    # -------------------------------------------------------------
    # G. Loop Prevention (38 - 41)
    # -------------------------------------------------------------
    def test_38_one_review_per_unchanged_patch_episode(self) -> None:
        """38. Controller permits first review and blocks second review on unchanged patch."""
        ctrl = ReviewerControllerV1(policy=ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW)
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            patch_state_version=1,
            current_patch_hash="abc123hash",
        )
        can_run_1, _ = ctrl.should_invoke(ctx)
        self.assertTrue(can_run_1)

        ctrl.record_result(ctx, ReviewerResult(status=ReviewerStatus.APPROVE))

        # Second check on same patch state
        can_run_2, reason_2 = ctrl.should_invoke(ctx)
        self.assertFalse(can_run_2)
        self.assertIn("loop prevention", reason_2)

    def test_39_changes_requested_does_not_cause_automatic_repeated_review(self) -> None:
        """39. CHANGES_REQUESTED outcome does not re-trigger review without material patch change."""
        ctrl = ReviewerControllerV1(policy=ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW)
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            patch_state_version=1,
            current_patch_hash="patch_hash_x",
        )
        ctrl.record_result(ctx, ReviewerResult(status=ReviewerStatus.CHANGES_REQUESTED))

        can_run, reason = ctrl.should_invoke(ctx)
        self.assertFalse(can_run)
        self.assertIn("loop prevention", reason)

    def test_40_insufficient_evidence_does_not_cause_automatic_repeated_review(self) -> None:
        """40. INSUFFICIENT_EVIDENCE outcome does not re-trigger review on unchanged state."""
        ctrl = ReviewerControllerV1(policy=ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW)
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            patch_state_version=1,
            current_patch_hash="patch_hash_y",
        )
        ctrl.record_result(ctx, ReviewerResult(status=ReviewerStatus.INSUFFICIENT_EVIDENCE))

        can_run, reason = ctrl.should_invoke(ctx)
        self.assertFalse(can_run)
        self.assertIn("loop prevention", reason)

    def test_41_new_patch_state_can_create_new_review_episode(self) -> None:
        """41. Advancing the patch version and hash enables a new review episode."""
        ctrl = ReviewerControllerV1(policy=ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW)
        ctx = ReviewerTriggerContext(
            has_candidate_diff=True,
            verification_attempted=True,
            has_result_summary=True,
            patch_state_version=1,
            current_patch_hash="hash_v1",
        )
        ctrl.record_result(ctx, ReviewerResult(status=ReviewerStatus.CHANGES_REQUESTED))

        # Root modifies patch -> patch version 2, new hash
        ctx.patch_state_version = 2
        ctx.current_patch_hash = "hash_v2"
        can_run, _ = ctrl.should_invoke(ctx)
        self.assertTrue(can_run)

    # -------------------------------------------------------------
    # H. Candidate Isolation V0 vs V1 (42 - 50)
    # -------------------------------------------------------------
    def test_42_v0_has_no_reviewer(self) -> None:
        """42. Candidate V0 agent.yaml does NOT configure Reviewer specialist."""
        v0_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V0/agent.yaml").read_text(encoding="utf-8"))
        sub_paths = [sa["config_path"] for sa in v0_cfg["sub_agents"]]
        self.assertNotIn("sub_agents/reviewer.yaml", sub_paths)

    def test_43_v1_has_reviewer(self) -> None:
        """43. Candidate V1 agent.yaml configures Reviewer specialist."""
        v1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V1/agent.yaml").read_text(encoding="utf-8"))
        sub_paths = [sa["config_path"] for sa in v1_cfg["sub_agents"]]
        self.assertIn("sub_agents/reviewer.yaml", sub_paths)

    def test_44_same_root_model(self) -> None:
        """44. Both V0 and V1 declare the exact competition model gemma-4-31b-it-qat-w4a16-ct."""
        for cand in ["V0", "V1"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_45_same_root_tools(self) -> None:
        """45. Both V0 and V1 provide the exact 9 competition tools to the Root agent."""
        for cand in ["V0", "V1"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["tools"], EXPECTED_ROOT_TOOLS)

    def test_46_same_scout(self) -> None:
        """46. Scout configuration and prompt in V0 and V1 match canonical Scout exactly."""
        for cand in ["V0", "V1"]:
            scout_yaml_hash = self._hash_file(f"experiments/candidates/{cand}/sub_agents/scout.yaml")
            scout_md_hash = self._hash_file(f"experiments/candidates/{cand}/prompts/scout.md")
            self.assertEqual(scout_yaml_hash, CANONICAL_SCOUT_YAML_SHA256)
            self.assertEqual(scout_md_hash, CANONICAL_SCOUT_MD_SHA256)

    def test_47_same_debugger(self) -> None:
        """47. Debugger configuration and prompt in V0 and V1 match canonical Debugger exactly."""
        for cand in ["V0", "V1"]:
            debugger_yaml_hash = self._hash_file(f"experiments/candidates/{cand}/sub_agents/debugger.yaml")
            debugger_md_hash = self._hash_file(f"experiments/candidates/{cand}/prompts/debugger.md")
            self.assertEqual(debugger_yaml_hash, CANONICAL_DEBUGGER_YAML_SHA256)
            self.assertEqual(debugger_md_hash, CANONICAL_DEBUGGER_MD_SHA256)

    def test_48_same_skills(self) -> None:
        """48. Both V0 and V1 package identical canonical test_strategy and repo_triage skills."""
        for cand in ["V0", "V1"]:
            ts_hash = self._hash_file(f"experiments/candidates/{cand}/skills/test_strategy/SKILL.md")
            rt_hash = self._hash_file(f"experiments/candidates/{cand}/skills/repo_triage/SKILL.md")
            self.assertEqual(ts_hash, CANONICAL_TEST_STRATEGY_SHA256)
            self.assertEqual(rt_hash, CANONICAL_REPO_TRIAGE_SHA256)

    def test_49_same_generation_settings(self) -> None:
        """49. Both candidates preserve identical root generation settings."""
        v0_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V0/agent.yaml").read_text(encoding="utf-8"))
        v1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V1/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(v0_cfg["generate_content_config"], v1_cfg["generate_content_config"])

    def test_50_only_reviewer_availability_differs(self) -> None:
        """50. V0 declares scout and debugger; V1 declares scout, debugger, and reviewer."""
        v0_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V0/agent.yaml").read_text(encoding="utf-8"))
        v1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V1/agent.yaml").read_text(encoding="utf-8"))
        v0_subs = [sa["config_path"] for sa in v0_cfg["sub_agents"]]
        v1_subs = [sa["config_path"] for sa in v1_cfg["sub_agents"]]
        self.assertEqual(v0_subs, ["sub_agents/scout.yaml", "sub_agents/debugger.yaml"])
        self.assertEqual(v1_subs, ["sub_agents/scout.yaml", "sub_agents/debugger.yaml", "sub_agents/reviewer.yaml"])

    # -------------------------------------------------------------
    # I. Prior-Stage Invariance (51 - 56)
    # -------------------------------------------------------------
    def test_51_scout_unchanged(self) -> None:
        """51. Canonical Scout artifacts in agent/ match Stage 21 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/scout.yaml"), CANONICAL_SCOUT_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/scout.md"), CANONICAL_SCOUT_MD_SHA256)

    def test_52_debugger_unchanged(self) -> None:
        """52. Canonical Debugger artifacts in agent/ match Stage 22 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/debugger.yaml"), CANONICAL_DEBUGGER_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/debugger.md"), CANONICAL_DEBUGGER_MD_SHA256)

    def test_53_e9_taxonomy_unchanged(self) -> None:
        """53. FailureClass canonical 8-category taxonomy remains intact."""
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
        self.assertEqual({fc.value for fc in FailureClass}, expected)

    def test_54_e10_progress_behavior_unchanged(self) -> None:
        """54. ProgressStatus and NoProgressReason remain intact."""
        self.assertIn("PROGRESS", [ps.value for ps in ProgressStatus])
        self.assertIn("NO_PROGRESS", [ps.value for ps in ProgressStatus])
        self.assertIn("REPEATED_FAILURE", [nr.value for nr in NoProgressReason])

    def test_55_e11_recovery_unchanged(self) -> None:
        """55. RecoveryControllerV1 and RecoveryPath remain intact."""
        ctrl = RecoveryControllerV1()
        self.assertIsInstance(ctrl, RecoveryControllerV1)
        self.assertIn(RecoveryPath.TEST_FAILURE, list(RecoveryPath))

    def test_56_canonical_skills_unchanged(self) -> None:
        """56. Canonical skill artifacts in agent/skills/ match frozen hashes."""
        self.assertEqual(self._hash_file("agent/skills/test_strategy/SKILL.md"), CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(self._hash_file("agent/skills/repo_triage/SKILL.md"), CANONICAL_REPO_TRIAGE_SHA256)

    # -------------------------------------------------------------
    # J. Validation & Anti-Overfitting (57 - 61)
    # -------------------------------------------------------------
    def test_57_v0_submission_validation_passes(self) -> None:
        """57. Candidate V0 passes submission validation."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/V0")
        valid = validator.validate()
        self.assertTrue(valid, f"V0 validation failed: {validator.errors}")

    def test_58_v1_submission_validation_passes(self) -> None:
        """58. Candidate V1 passes submission validation."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/V1")
        valid = validator.validate()
        self.assertTrue(valid, f"V1 validation failed: {validator.errors}")

    def test_59_v1_contains_exactly_one_additional_specialist(self) -> None:
        """59. V1 sub_agents contains exactly scout, debugger, and reviewer."""
        v1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/V1/agent.yaml").read_text(encoding="utf-8"))
        sub_paths = [sa["config_path"] for sa in v1_cfg["sub_agents"]]
        self.assertEqual(len(sub_paths), 3)
        self.assertIn("sub_agents/scout.yaml", sub_paths)
        self.assertIn("sub_agents/debugger.yaml", sub_paths)
        self.assertIn("sub_agents/reviewer.yaml", sub_paths)

    def test_60_no_stage_24_plus_agents(self) -> None:
        """60. Only allowed sub-agents (scout, debugger, reviewer) are present in V1."""
        subagent_files = list((PROJECT_ROOT / "experiments/candidates/V1/sub_agents").glob("*.yaml"))
        names = sorted(f.stem for f in subagent_files)
        self.assertEqual(names, ["debugger", "reviewer", "scout"])

    def test_61_no_benchmark_specific_hardcoding(self) -> None:
        """61. Reviewer prompt and config contain zero competition task IDs or benchmark solution snippets."""
        reviewer_prompt = (PROJECT_ROOT / "agent/prompts/reviewer.md").read_text(encoding="utf-8")
        reviewer_yaml = (PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").read_text(encoding="utf-8")
        prohibited_terms = [
            "django__django",
            "pytest-dev__pytest",
            "sympy__sympy",
            "matplotlib__matplotlib",
            "scikit-learn__scikit-learn",
            "astropy__astropy",
            "sphinx-doc__sphinx",
            "requests__requests",
            "flask__flask",
        ]
        for term in prohibited_terms:
            self.assertNotIn(term, reviewer_prompt)
            self.assertNotIn(term, reviewer_yaml)


if __name__ == "__main__":
    unittest.main()
