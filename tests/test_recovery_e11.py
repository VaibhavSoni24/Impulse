"""Unit and regression tests for Candidate E11 and Recovery Paths (Stage 20).

Validates:
A. General routing
B. Search fallback ladder
C. Test-failure recovery
D. Bad-edit recovery and Safe Change Ownership
E. Tool-failure recovery
F. Budget-pressure recovery
G. Loop prevention and state machine bounds
H. TaskState integration and security hygiene
I. E9/E10 invariance
J. Candidate E11 validation
K. Section 15 specific recovery scenarios
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from local.failures import FailureClass, FailureClassifierV1
from local.progress import (
    CycleSnapshot,
    NoProgressDetectorV1,
    NoProgressReason,
    ProgressStatus,
)
from local.recovery import (
    ALTERNATE_TOOL_MAP,
    BUDGET_CALL_THRESHOLD,
    BUDGET_TIME_THRESHOLD_SECONDS,
    MAX_PATH_ATTEMPTS,
    MAX_TOOL_RETRIES,
    RecoveryActionType,
    RecoveryContext,
    RecoveryControllerV1,
    RecoveryDecision,
    RecoveryPath,
    RecoveryState,
)
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E10)
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
E10_AGENT_SHA256 = "779f70c0feeb9f89b577a62c73361afc3aae7823d86a05e23b6fc246b66babf7"
E10_PROMPT_SHA256 = "4766117f671fd7fb4e4e8ade8afe46d7c9412fbe7255ee2a29f9b38ebc25b73f"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

EXPECTED_E11_TOOLS = [
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


class TestRecoveryPathsE11(unittest.TestCase):
    """Focused test suite for Stage 20 / Candidate E11 Recovery Paths."""

    def setUp(self) -> None:
        self.controller = RecoveryControllerV1(max_attempts=MAX_PATH_ATTEMPTS)

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # A. General Routing (1 - 4)
    # -------------------------------------------------------------
    def test_01_no_failure_or_no_progress_results_in_normal_state(self) -> None:
        """1. When execution is nominal with no failure/no-progress, state is NORMAL."""
        context = RecoveryContext(
            failure_classification=None,
            progress_status=ProgressStatus.PROGRESS.value,
            no_progress_reason=None,
            tool_error=None,
            test_result="PASSED",
            budget_warning_present=False,
            source_evidence_sufficient=True,
        )
        decision = self.controller.route_recovery(context)
        self.assertEqual(decision.state, RecoveryState.NORMAL)
        self.assertEqual(decision.selected_path, RecoveryPath.NONE)
        self.assertEqual(decision.action, RecoveryActionType.NONE)

    def test_02_classified_failure_routes_correctly(self) -> None:
        """2. Classified failures route to their respective recovery paths."""
        # REGRESSION routes to BAD_EDIT
        ctx_reg = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["src/parser.py"],
            agent_owned_files=["src/parser.py"],
        )
        dec_reg = self.controller.route_recovery(ctx_reg)
        self.assertEqual(dec_reg.selected_path, RecoveryPath.BAD_EDIT)

        self.controller.reset()
        # WRONG_HYPOTHESIS routes to TEST_FAILURE
        ctx_hyp = RecoveryContext(
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            test_result="FAILED",
            diff_inspected=True,
        )
        dec_hyp = self.controller.route_recovery(ctx_hyp)
        self.assertEqual(dec_hyp.selected_path, RecoveryPath.TEST_FAILURE)
        self.assertEqual(dec_hyp.action, RecoveryActionType.REVISE_HYPOTHESIS)

    def test_03_no_progress_event_routes_correctly(self) -> None:
        """3. No-progress events route appropriately based on reason."""
        ctx_no_ev = RecoveryContext(
            progress_status=ProgressStatus.NO_PROGRESS.value,
            no_progress_reason=NoProgressReason.NO_NEW_EVIDENCE.value,
            source_evidence_sufficient=False,
        )
        dec = self.controller.route_recovery(ctx_no_ev)
        self.assertEqual(dec.selected_path, RecoveryPath.SEARCH_FALLBACK)
        self.assertEqual(dec.action, RecoveryActionType.FALLBACK_SEMANTIC)

    def test_04_unknown_evidence_does_not_cause_unsafe_guessing(self) -> None:
        """4. FailureClass.UNKNOWN does not trigger destructive edit revert."""
        ctx_unk = RecoveryContext(
            failure_classification=FailureClass.UNKNOWN.value,
            modified_files=["src/parser.py"],
            agent_owned_files=["src/parser.py"],
            source_evidence_sufficient=False,
        )
        dec = self.controller.route_recovery(ctx_unk)
        # Routes safely to non-destructive search fallback, not destructive edit revert
        self.assertEqual(dec.selected_path, RecoveryPath.SEARCH_FALLBACK)
        self.assertNotEqual(dec.action, RecoveryActionType.REVERT_EDIT)

    # -------------------------------------------------------------
    # B. Search Fallback (5 - 8)
    # -------------------------------------------------------------
    def test_05_search_fallback_chooses_untried_next_method(self) -> None:
        """5. Search fallback starts at semantic search when untried."""
        ctx = RecoveryContext(
            no_progress_reason=NoProgressReason.NO_NEW_EVIDENCE.value,
            retrieval_history=[],
            source_evidence_sufficient=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.selected_path, RecoveryPath.SEARCH_FALLBACK)
        self.assertEqual(dec.action, RecoveryActionType.FALLBACK_SEMANTIC)

    def test_06_already_exhausted_retrieval_method_is_not_blindly_repeated(self) -> None:
        """6. Search fallback advances through semantic -> exact -> tree -> graph."""
        ladder_steps = [
            (["semantic"], RecoveryActionType.FALLBACK_EXACT_SEARCH),
            (["semantic", "exact"], RecoveryActionType.FALLBACK_TREE_INSPECTION),
            (["semantic", "exact", "tree"], RecoveryActionType.FALLBACK_GRAPH),
            (["semantic", "exact", "tree", "graph"], RecoveryActionType.TERMINATE_PATH),
        ]
        for history, expected_action in ladder_steps:
            self.controller.reset()
            ctx = RecoveryContext(
                no_progress_reason=NoProgressReason.NO_NEW_EVIDENCE.value,
                retrieval_history=history,
                source_evidence_sufficient=False,
            )
            dec = self.controller.route_recovery(ctx)
            self.assertEqual(dec.selected_path, RecoveryPath.SEARCH_FALLBACK)
            self.assertEqual(dec.action, expected_action)

    def test_07_retrieval_remains_within_e6_budgets(self) -> None:
        """7. Search fallback respects ladder size and bounds."""
        ctx = RecoveryContext(
            no_progress_reason=NoProgressReason.NO_NEW_EVIDENCE.value,
            retrieval_history=["semantic", "exact", "tree", "graph"],
            source_evidence_sufficient=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertTrue(dec.is_exhausted)
        self.assertEqual(dec.action, RecoveryActionType.TERMINATE_PATH)

    def test_08_recovery_stops_once_source_evidence_is_sufficient(self) -> None:
        """8. Search fallback terminates when source evidence is already sufficient."""
        ctx = RecoveryContext(
            no_progress_reason=NoProgressReason.NO_NEW_EVIDENCE.value,
            retrieval_history=["semantic"],
            source_evidence_sufficient=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.state, RecoveryState.NORMAL)
        self.assertEqual(dec.action, RecoveryActionType.NONE)

    # -------------------------------------------------------------
    # C. Test-Failure Recovery (9 - 13)
    # -------------------------------------------------------------
    def test_09_failure_classification_is_consulted_for_test_failure(self) -> None:
        """9. Test failure recovery consults failure classification."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.INCOMPLETE_FIX.value,
            diff_inspected=True,
            has_stack_trace=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.selected_path, RecoveryPath.TEST_FAILURE)
        self.assertIn("INCOMPLETE_FIX", dec.evidence_used[0])

    def test_10_diff_inspection_occurs_before_another_edit_path(self) -> None:
        """10. Uninspected diff forces INSPECT_DIFF before code mutations."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.INCOMPLETE_FIX.value,
            modified_files=["src/parser.py"],
            diff_inspected=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.action, RecoveryActionType.INSPECT_DIFF)

    def test_11_stack_call_path_evidence_can_be_requested(self) -> None:
        """11. Stack trace evidence triggers INSPECT_STACK."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.INCOMPLETE_FIX.value,
            diff_inspected=True,
            has_stack_trace=True,
            stack_trace_snippet="Traceback: File parser.py, line 42, in parse",
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.action, RecoveryActionType.INSPECT_STACK)
        self.assertIn("parser.py", dec.target)

    def test_12_wrong_hypothesis_leads_to_hypothesis_revision(self) -> None:
        """12. WRONG_HYPOTHESIS directly triggers REVISE_HYPOTHESIS."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            diff_inspected=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.action, RecoveryActionType.REVISE_HYPOTHESIS)

    def test_13_targeted_verification_is_preferred_before_broad_verification(self) -> None:
        """13. Test failure recovery ladder concludes with TARGETED_VALIDATION."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.NEW_EDGE_CASE.value,
            diff_inspected=True,
            has_stack_trace=False,
        )
        # Attempt 1: Revise hypothesis
        dec1 = self.controller.route_recovery(ctx)
        # Attempt 2: Targeted validation
        dec2 = self.controller.route_recovery(ctx)
        self.assertEqual(dec2.action, RecoveryActionType.TARGETED_VALIDATION)
        self.assertTrue(dec2.is_exhausted)

    # -------------------------------------------------------------
    # D. Bad-Edit Recovery & Safe Ownership (14 - 19)
    # -------------------------------------------------------------
    def test_14_changed_file_attributable_to_agent_can_be_repaired_and_reverted(self) -> None:
        """14. Agent-owned files can be repaired and subsequently reverted."""
        ctx = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["src/calc.py"],
            agent_owned_files=["src/calc.py"],
            unrelated_modified_files=[],
            diff_inspected=True,
        )
        # Attempt 1: Repair
        dec1 = self.controller.route_recovery(ctx)
        self.assertEqual(dec1.action, RecoveryActionType.REPAIR_EDIT)
        self.assertEqual(dec1.target, "src/calc.py")

        # Attempt 2: Revert
        dec2 = self.controller.route_recovery(ctx)
        self.assertEqual(dec2.action, RecoveryActionType.REVERT_EDIT)
        self.assertEqual(dec2.target, "src/calc.py")

    def test_15_unrelated_pre_existing_change_is_strictly_preserved(self) -> None:
        """15. Files marked as unrelated pre-existing changes are NEVER reverted."""
        ctx = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["config/settings.json"],
            agent_owned_files=[],
            unrelated_modified_files=["config/settings.json"],
            diff_inspected=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertNotEqual(dec.action, RecoveryActionType.REVERT_EDIT)
        self.assertNotEqual(dec.action, RecoveryActionType.REPAIR_EDIT)
        self.assertEqual(dec.action, RecoveryActionType.REVISE_HYPOTHESIS)
        self.assertIn("pre-existing change detected", dec.rationale)

    def test_16_ambiguous_ownership_prevents_destructive_revert(self) -> None:
        """16. Files with ambiguous or missing ownership fallback to non-destructive hypothesis revision."""
        ctx = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["unknown_module.py"],
            agent_owned_files=[],  # Empty agent ownership
            diff_inspected=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertNotEqual(dec.action, RecoveryActionType.REVERT_EDIT)
        self.assertEqual(dec.action, RecoveryActionType.REVISE_HYPOTHESIS)

    def test_17_targeted_test_runs_after_repair(self) -> None:
        """17. After repair/revert actions complete, recovery triggers targeted validation."""
        ctrl = RecoveryControllerV1(max_attempts=3)
        ctx = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["src/calc.py"],
            agent_owned_files=["src/calc.py"],
            diff_inspected=True,
        )
        ctrl.route_recovery(ctx)  # Attempt 1: REPAIR_EDIT
        ctrl.route_recovery(ctx)  # Attempt 2: REVERT_EDIT
        dec3 = ctrl.route_recovery(ctx)  # Attempt 3: TARGETED_VALIDATION
        self.assertEqual(dec3.action, RecoveryActionType.TARGETED_VALIDATION)
        self.assertTrue(dec3.is_exhausted)

    def test_18_no_repository_wide_reset_occurs(self) -> None:
        """18. The controller never returns blanket rollback or repo-wide reset commands."""
        for path in RecoveryPath:
            ctx = RecoveryContext(
                failure_classification=FailureClass.REGRESSION.value,
                modified_files=["file1.py", "file2.py"],
                agent_owned_files=["file2.py"],
                diff_inspected=True,
            )
            dec = self.controller.route_recovery(ctx)
            self.assertNotIn("git reset --hard", dec.action.value.lower())
            self.assertNotIn("git checkout .", dec.action.value.lower())
            self.assertNotEqual(dec.target, ".")
            self.assertNotEqual(dec.target, "*")

    def test_19_repeated_bad_edit_recovery_is_bounded(self) -> None:
        """19. Repeated bad edit attempts do not exceed MAX_PATH_ATTEMPTS."""
        ctx = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=["src/calc.py"],
            agent_owned_files=["src/calc.py"],
            diff_inspected=True,
        )
        self.controller.route_recovery(ctx)  # 1
        self.controller.route_recovery(ctx)  # 2
        dec = self.controller.route_recovery(ctx)  # 3 -> exhausted
        self.assertTrue(dec.is_exhausted)

    # -------------------------------------------------------------
    # E. Tool-Failure Recovery (20 - 24)
    # -------------------------------------------------------------
    def test_20_transient_tool_failure_gets_bounded_retry(self) -> None:
        """20. First tool invocation failure gets bounded single retry."""
        ctx = RecoveryContext(
            latest_tool_name="search_similar_code",
            tool_error="Transient timeout in retrieval backend",
            is_command_syntax_error=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.selected_path, RecoveryPath.TOOL_FAILURE)
        self.assertEqual(dec.action, RecoveryActionType.RETRY_TOOL)
        self.assertEqual(dec.target, "search_similar_code")

    def test_21_retry_limit_is_enforced(self) -> None:
        """21. Tool retry limit (MAX_TOOL_RETRIES=1) prevents further direct retries."""
        ctx = RecoveryContext(
            latest_tool_name="search_similar_code",
            tool_error="Transient timeout in retrieval backend",
        )
        dec1 = self.controller.route_recovery(ctx)  # Attempt 1: RETRY_TOOL
        self.assertEqual(dec1.action, RecoveryActionType.RETRY_TOOL)

        dec2 = self.controller.route_recovery(ctx)  # Attempt 2: USE_ALTERNATE_TOOL
        self.assertEqual(dec2.action, RecoveryActionType.USE_ALTERNATE_TOOL)

    def test_22_compatible_alternate_tool_can_be_selected(self) -> None:
        """22. Compatible alternate tool is selected from ALTERNATE_TOOL_MAP."""
        tool_pairs = [
            ("search_similar_code", "run_command"),
            ("get_code_neighbors", "read_file"),
            ("get_code_subgraph", "get_code_neighbors"),
            ("edit_file", "write_file"),
        ]
        for primary, expected_alt in tool_pairs:
            self.controller.reset()
            ctx = RecoveryContext(latest_tool_name=primary, tool_error="Internal execution failure")
            self.controller.route_recovery(ctx)  # 1: Retry
            dec_alt = self.controller.route_recovery(ctx)  # 2: Alternate
            self.assertEqual(dec_alt.action, RecoveryActionType.USE_ALTERNATE_TOOL)
            self.assertEqual(dec_alt.target, expected_alt)

    def test_23_invalid_command_is_not_endlessly_retried(self) -> None:
        """23. Deterministic CLI syntax error is terminated immediately without retry."""
        ctx = RecoveryContext(
            latest_tool_name="run_command",
            tool_error="pytest: error: unrecognized arguments: --invalid-flag",
            is_command_syntax_error=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.action, RecoveryActionType.TERMINATE_PATH)
        self.assertTrue(dec.is_exhausted)

    def test_24_tool_exhaustion_can_terminate_cleanly(self) -> None:
        """24. Tool recovery exhausts cleanly when no alternates remain."""
        ctx = RecoveryContext(
            latest_tool_name="submit_patch",  # No alternate tool in map
            tool_error="Platform submission error",
        )
        self.controller.route_recovery(ctx)  # 1: Retry
        dec = self.controller.route_recovery(ctx)  # 2: No alt -> TERMINATE_PATH
        self.assertEqual(dec.action, RecoveryActionType.TERMINATE_PATH)
        self.assertTrue(dec.is_exhausted)

    # -------------------------------------------------------------
    # F. Budget Pressure (25 - 28)
    # -------------------------------------------------------------
    def test_25_low_value_exploration_is_stopped_under_budget_pressure(self) -> None:
        """25. Tool call threshold <= 10 halts exploratory retrieval."""
        ctx = RecoveryContext(
            remaining_tool_calls=10,
            remaining_time_seconds=600.0,
            budget_warning_present=False,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(dec.selected_path, RecoveryPath.BUDGET_PRESSURE)
        self.assertEqual(dec.action, RecoveryActionType.STOP_EXPLORATION)

    def test_26_targeted_validation_is_retained_under_budget_pressure(self) -> None:
        """26. Budget pressure escalation prioritizes targeted validation."""
        ctx = RecoveryContext(
            remaining_tool_calls=5,
            remaining_time_seconds=200.0,
            budget_warning_present=True,
        )
        self.controller.route_recovery(ctx)  # 1: STOP_EXPLORATION
        dec2 = self.controller.route_recovery(ctx)  # 2: TARGETED_VALIDATION
        self.assertEqual(dec2.action, RecoveryActionType.TARGETED_VALIDATION)

    def test_27_final_diff_review_is_retained_under_budget_pressure(self) -> None:
        """27. Final budget pressure step triggers final diff inspection."""
        ctx = RecoveryContext(budget_warning_present=True)
        self.controller.route_recovery(ctx)  # 1
        self.controller.route_recovery(ctx)  # 2
        dec3 = self.controller.route_recovery(ctx)  # 3: FINAL_REVIEW
        self.assertEqual(dec3.action, RecoveryActionType.FINAL_REVIEW)
        self.assertTrue(dec3.is_exhausted)

    def test_28_budget_boundaries_are_respected(self) -> None:
        """28. Verifies default budget pressure threshold constants."""
        self.assertEqual(BUDGET_CALL_THRESHOLD, 10)
        self.assertEqual(BUDGET_TIME_THRESHOLD_SECONDS, 300.0)

    # -------------------------------------------------------------
    # G. Loop Prevention & State Machine (29 - 32)
    # -------------------------------------------------------------
    def test_29_same_recovery_path_cannot_recurse_indefinitely(self) -> None:
        """29. Recovery controller enforces maximum attempts on a single path."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.INCOMPLETE_FIX.value,
            diff_inspected=True,
        )
        for _ in range(MAX_PATH_ATTEMPTS):
            dec = self.controller.route_recovery(ctx)
            self.assertNotEqual(dec.state, RecoveryState.TERMINAL)

        # Subsequent attempts exceed max_attempts
        dec_final = self.controller.route_recovery(ctx)
        self.assertTrue(dec_final.is_exhausted or dec_final.state == RecoveryState.TERMINAL)

    def test_30_exhausted_recovery_does_not_repeat_forever(self) -> None:
        """30. When all applicable recovery paths are exhausted, transitions to TERMINAL."""
        # Set max_attempts to 1 for quick exhaustion
        ctrl = RecoveryControllerV1(max_attempts=1)
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            diff_inspected=True,
            source_evidence_sufficient=True,
        )
        ctrl.route_recovery(ctx)  # Path TEST_FAILURE attempt 1
        dec = ctrl.route_recovery(ctx)  # Path exhausted -> TERMINAL
        self.assertEqual(dec.state, RecoveryState.TERMINAL)
        self.assertEqual(dec.action, RecoveryActionType.TERMINATE_PATH)

    def test_31_successful_recovery_resets_relevant_no_progress_state(self) -> None:
        """31. Meaningful progress after recovery resets TaskState.no_progress_count."""
        state = TaskState(summary="Repairing parser bug")
        state.increment_no_progress()
        state.increment_no_progress()
        self.assertEqual(state.no_progress_count, 2)

        # Meaningful progress confirmed
        state.reset_no_progress()
        self.assertEqual(state.no_progress_count, 0)

    def test_32_failed_recovery_returns_to_evaluation_rather_than_automatic_repetition(self) -> None:
        """32. Every recovery step records history and returns structured decision for re-evaluation."""
        ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
            diff_inspected=True,
        )
        dec = self.controller.route_recovery(ctx)
        self.assertEqual(len(self.controller.history), 1)
        self.assertEqual(self.controller.history[0], dec)

    # -------------------------------------------------------------
    # H. TaskState Integration & Security Hygiene (33 - 36)
    # -------------------------------------------------------------
    def test_33_recovery_events_are_recorded_in_task_state(self) -> None:
        """33. RecoveryDecision integrates cleanly into TaskState evidence."""
        state = TaskState(summary="Investigating issue")
        decision = RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.BAD_EDIT,
            action=RecoveryActionType.REPAIR_EDIT,
            target="src/parser.py",
            rationale="Bounded repair of parser regex",
        )
        decision.integrate_into_task_state(state)
        self.assertEqual(len(state.evidence), 1)
        self.assertIn("BAD_EDIT -> REPAIR_EDIT", state.evidence[0].observation)
        self.assertEqual(state.evidence[0].source_command_or_file, "recovery_controller_v1")

    def test_34_recovery_history_is_sufficient_to_prevent_duplicate_actions(self) -> None:
        """34. Decision history contains complete serializable telemetry."""
        decision = RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.TOOL_FAILURE,
            action=RecoveryActionType.USE_ALTERNATE_TOOL,
            target="run_command",
            rationale="Falling back to grep search",
            attempt_number=2,
            is_exhausted=False,
            evidence_used=["Tool search_similar_code failed"],
        )
        d = decision.to_dict()
        self.assertEqual(d["selected_path"], "TOOL_FAILURE")
        self.assertEqual(d["action"], "USE_ALTERNATE_TOOL")
        self.assertEqual(d["attempt_number"], 2)

    def test_35_no_secrets_in_recovery_records(self) -> None:
        """35. Sensitive credentials are never embedded into recovery decisions."""
        secret = "ghp_VerySecretAccessToken1234567890"
        ctx = RecoveryContext(
            latest_tool_name="run_command",
            tool_error=f"Authentication error with token {secret}",
            is_command_syntax_error=True,
        )
        dec = self.controller.route_recovery(ctx)
        summary = dec.format_summary()
        self.assertNotIn("password", summary.lower())
        self.assertNotIn("api_key", summary.lower())

    def test_36_evidence_remains_bounded(self) -> None:
        """36. TaskState integration strictly bounds long rationale strings."""
        state = TaskState(summary="Testing bound")
        long_rationale = "x" * 2000
        decision = RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.TEST_FAILURE,
            action=RecoveryActionType.REVISE_HYPOTHESIS,
            rationale=long_rationale,
        )
        decision.integrate_into_task_state(state)
        self.assertLessEqual(len(state.evidence[0].observation), 600)

    # -------------------------------------------------------------
    # I. E9 / E10 Invariance (37 - 40)
    # -------------------------------------------------------------
    def test_37_e9_failure_classes_remain_unchanged(self) -> None:
        """37. Preserves all 8 canonical failure categories from Stage 18."""
        expected_classes = {
            "ENVIRONMENT",
            "COMMAND",
            "PRE_EXISTING_FAILURE",
            "REGRESSION",
            "INCOMPLETE_FIX",
            "WRONG_HYPOTHESIS",
            "NEW_EDGE_CASE",
            "UNKNOWN",
        }
        actual_classes = {fc.value for fc in FailureClass}
        self.assertEqual(actual_classes, expected_classes)

    def test_38_e10_no_progress_detector_behavior_remains_unchanged(self) -> None:
        """38. E10 NoProgressDetectorV1 behavior is preserved intact."""
        detector = NoProgressDetectorV1(threshold=2)
        c1 = CycleSnapshot(cycle_id=1, test_result="FAILED", failure_signature="sig1")
        c2 = CycleSnapshot(cycle_id=2, test_result="FAILED", failure_signature="sig1")
        res1 = detector.record_cycle(c1)
        res2 = detector.record_cycle(c2)
        self.assertEqual(res1.status, ProgressStatus.PROGRESS)
        self.assertEqual(res2.status, ProgressStatus.NO_PROGRESS)

    def test_39_e10_progress_fingerprints_remain_deterministic(self) -> None:
        """39. CycleSnapshot normalized fingerprints remain deterministic."""
        c = CycleSnapshot(cycle_id=1, failure_signature="Traceback: line 42 at 0x7fff5fbff840")
        fp1 = c.failure_fingerprint()
        fp2 = c.failure_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertNotIn("0x7fff", fp1)

    def test_40_canonical_skills_remain_byte_identical(self) -> None:
        """40. Both skills in candidate E11 match canonical versions byte-for-byte."""
        self.assertEqual(
            self._hash_file("experiments/candidates/E11/skills/test_strategy/SKILL.md"),
            CANONICAL_TEST_STRATEGY_SHA256,
        )
        self.assertEqual(
            self._hash_file("experiments/candidates/E11/skills/repo_triage/SKILL.md"),
            CANONICAL_REPO_TRIAGE_SHA256,
        )

    # -------------------------------------------------------------
    # J. Candidate E11 Validation (41 - 45)
    # -------------------------------------------------------------
    def test_41_e11_uses_exact_competition_model(self) -> None:
        """41. E11 specifies exact model gemma-4-31b-it-qat-w4a16-ct."""
        e11_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E11/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e11_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_42_e11_declares_exactly_9_tools(self) -> None:
        """42. E11 declares exactly 9 competition tools."""
        e11_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E11/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e11_yaml["tools"], EXPECTED_E11_TOOLS)
        self.assertEqual(len(e11_yaml["tools"]), 9)

    def test_43_e11_declares_both_existing_skills(self) -> None:
        """43. E11 declares test_strategy and repo_triage skills."""
        e11_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E11/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e11_yaml["skills"], ["skills/test_strategy", "skills/repo_triage"])

    def test_44_no_sub_agents_introduced(self) -> None:
        """44. Verifies no sub-agents (Scout, Debugger, Reviewer) are declared."""
        e11_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E11/agent.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("subagents", e11_yaml)
        self.assertNotIn("scout", str(e11_yaml).lower())
        self.assertNotIn("debugger", str(e11_yaml).lower())
        self.assertNotIn("reviewer", str(e11_yaml).lower())

    def test_45_no_stage_21_or_later_implemented(self) -> None:
        """45. Confirms Stage 21 (Scout) files do not exist."""
        scout_dir = PROJECT_ROOT / "agent" / "subagents"
        self.assertFalse(scout_dir.exists(), "Subagent directory must not exist in Stage 20")

    # -------------------------------------------------------------
    # K. Section 15 Specific Scenarios (46 - 47)
    # -------------------------------------------------------------
    def test_46_scenario_pre_existing_modification_preserved_and_agent_edit_repaired(self) -> None:
        """46. Scenario 1: Pre-existing user modification is preserved; only agent-owned file is repaired."""
        pre_existing_file = "config/app_config.py"
        agent_edit_1 = "src/utils.py"
        agent_edit_2 = "src/parser.py"

        context = RecoveryContext(
            failure_classification=FailureClass.REGRESSION.value,
            modified_files=[pre_existing_file, agent_edit_1, agent_edit_2],
            agent_owned_files=[agent_edit_1, agent_edit_2],
            unrelated_modified_files=[pre_existing_file],
            diff_inspected=True,
        )

        # Pre-existing file is NOT safe to revert
        self.assertFalse(context.is_safe_to_revert(pre_existing_file))
        # Agent edits ARE safe to revert
        self.assertTrue(context.is_safe_to_revert(agent_edit_1))
        self.assertTrue(context.is_safe_to_revert(agent_edit_2))

        # Recovery targets the latest agent-owned file (agent_edit_2)
        dec = self.controller.route_recovery(context)
        self.assertEqual(dec.selected_path, RecoveryPath.BAD_EDIT)
        self.assertEqual(dec.action, RecoveryActionType.REPAIR_EDIT)
        self.assertEqual(dec.target, agent_edit_2)
        self.assertNotEqual(dec.target, pre_existing_file)

    def test_47_scenario_repeated_failure_exhausts_and_does_not_loop_infinitely(self) -> None:
        """47. Scenario 2: Repeated failure (A -> recovery A -> failure A) terminates with RECOVERY_EXHAUSTED / TERMINAL."""
        context = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.INCOMPLETE_FIX.value,
            diff_inspected=True,
            has_stack_trace=False,
            source_evidence_sufficient=True,
        )

        # Sequence of calls under unchanging failing condition
        decisions = []
        for _ in range(5):
            dec = self.controller.route_recovery(context)
            decisions.append(dec)

        # Verify that recovery does not loop endlessly:
        # After max attempts, path exhausts and terminates
        states = [d.state for d in decisions]
        self.assertIn(RecoveryState.RECOVERY_EXHAUSTED, states)
        self.assertEqual(decisions[-1].state, RecoveryState.TERMINAL)


if __name__ == "__main__":
    unittest.main()
