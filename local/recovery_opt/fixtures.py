"""Deterministic Test Fixtures for Recovery Optimization Loop (Stage 35 Section 36).

Provides deterministic fixtures covering all 31 mandatory scenarios A through AE:
A. repeated identical command
B. repeated identical error
C. repeated file edit
D. no-progress trigger
E. recovery succeeds immediately
F. recovery succeeds after alternate path
G. recovery fails
H. recovery loops
I. alternating recovery loop
J. retry budget exhausted
K. recovery triggered too late
L. correct recovery opportunity missed
M. failed tool -> alternate tool succeeds
N. test failure -> revised investigation succeeds
O. bad edit -> repair succeeds
P. search fallback -> useful path
Q. budget pressure -> bounded recovery
R. collateral regression
S. targeted failure reduction
T. unchanged target failure
U. detection latency improvement
V. detection latency regression
W. Stage 34 testing policy fixed
X. Stage 33 retrieval policy fixed
Y. prompt invariant
Z. skill invariant
AA. no actionable LIVE recovery data
AB. infrastructure-only data
AC. held-out regression
AD. manifest/hash mismatch
AE. duplicate candidate rejection

All fixtures have evidence_mode = FIXTURE.
"""

from __future__ import annotations

from typing import Any, Dict, List

from local.failures.models import FailureClass
from local.recovery_opt.models import (
    RecoveryCandidateManifest,
    RecoveryExecutionEvent,
    RecoveryFailureRecord,
    RecoveryHypothesis,
    RecoveryOutcome,
    RecoveryPatternType,
    RecoveryPolicy,
    RecoveryVariant,
)
from local.recovery_opt.policy import build_rec0_baseline_policy, build_rec1_early_detection_policy
from local.recovery_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
)


def fixture_a_repeated_command() -> List[RecoveryExecutionEvent]:
    """Fixture A: repeated identical shell command failing consecutively."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_a",
            task_id="task_cmd_repeat",
            candidate_id="REC0",
            event_index=1,
            failure_signature="pytest -k test_auth exit code 1",
            failure_class=FailureClass.COMMAND.value,
            recovery_eligible=True,
            trigger="TEST_COMMAND_FAILURE",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="UNVERIFIED",
            state_after="UNVERIFIED",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=150.0,
            tool_calls_added=1,
            turn=1,
            evidence_mode="FIXTURE",
            metadata={"command": "pytest -k test_auth", "result": "FAIL"},
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_a",
            task_id="task_cmd_repeat",
            candidate_id="REC0",
            event_index=2,
            failure_signature="pytest -k test_auth exit code 1",
            failure_class=FailureClass.COMMAND.value,
            recovery_eligible=True,
            trigger="TEST_COMMAND_FAILURE",
            action="RETRY_TOOL",
            attempt_number=2,
            state_before="UNVERIFIED",
            state_after="UNVERIFIED",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=150.0,
            tool_calls_added=1,
            turn=2,
            evidence_mode="FIXTURE",
            metadata={"command": "pytest -k test_auth", "result": "FAIL"},
        ),
    ]


def fixture_b_repeated_error() -> List[RecoveryExecutionEvent]:
    """Fixture B: repeated identical error signature without evidence change."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_b",
            task_id="task_err_repeat",
            candidate_id="REC0",
            event_index=1,
            failure_signature="ImportError: cannot import name 'get_settings'",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=True,
            trigger="IMPORT_ERROR",
            action="INSPECT_DIFF",
            attempt_number=1,
            state_before="ERROR",
            state_after="ERROR",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=200.0,
            tool_calls_added=1,
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_b",
            task_id="task_err_repeat",
            candidate_id="REC0",
            event_index=2,
            failure_signature="ImportError: cannot import name 'get_settings'",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=True,
            trigger="IMPORT_ERROR",
            action="INSPECT_DIFF",
            attempt_number=2,
            state_before="ERROR",
            state_after="ERROR",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=200.0,
            tool_calls_added=1,
            turn=2,
            evidence_mode="FIXTURE",
        ),
    ]


def fixture_c_repeated_edit() -> List[RecoveryExecutionEvent]:
    """Fixture C: repeated edits to the same file region without progress."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_c",
            task_id="task_edit_repeat",
            candidate_id="REC0",
            event_index=1,
            failure_signature="AssertionError: expected 200 got 500",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="TEST_FAIL_AFTER_EDIT",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="EDITED",
            state_after="EDITED",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=300.0,
            tool_calls_added=1,
            turn=1,
            evidence_mode="FIXTURE",
            metadata={"target_file": "app/main.py", "result": "FAIL"},
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_c",
            task_id="task_edit_repeat",
            candidate_id="REC0",
            event_index=2,
            failure_signature="AssertionError: expected 200 got 500",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="TEST_FAIL_AFTER_EDIT",
            action="REPAIR_EDIT",
            attempt_number=2,
            state_before="EDITED",
            state_after="EDITED",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            duration_ms=300.0,
            tool_calls_added=1,
            turn=2,
            evidence_mode="FIXTURE",
            metadata={"target_file": "app/main.py", "result": "FAIL"},
        ),
    ]


def fixture_d_no_progress_trigger() -> List[RecoveryExecutionEvent]:
    """Fixture D: Stage 19 No-progress detector fires after 3 turns of no evidence."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_d",
            task_id="task_no_progress",
            candidate_id="REC0",
            event_index=1,
            failure_signature="FileNotFoundError: config.json",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=False,
            trigger="NO_PROGRESS_DETECTOR",
            action="NONE",
            attempt_number=1,
            state_before="STAGNANT",
            state_after="STAGNANT",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.INCONCLUSIVE.value,
            loop_detected=False,
            stop_reason="",
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_d",
            task_id="task_no_progress",
            candidate_id="REC0",
            event_index=2,
            failure_signature="FileNotFoundError: config.json",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=True,
            trigger="NO_PROGRESS_THRESHOLD_REACHED",
            action="FALLBACK_SEMANTIC",
            attempt_number=1,
            state_before="STAGNANT",
            state_after="RECOVERING",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=3,
            evidence_mode="FIXTURE",
        ),
    ]


def fixture_e_recovery_succeeds_immediately() -> List[RecoveryExecutionEvent]:
    """Fixture E: recovery succeeds on the very first attempt."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_e",
            task_id="task_succ_imm",
            candidate_id="REC1",
            event_index=1,
            failure_signature="SyntaxError: invalid syntax",
            failure_class=FailureClass.COMMAND.value,
            recovery_eligible=True,
            trigger="SYNTAX_ERROR_DETECTED",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="SYNTAX_ERROR",
            state_after="CLEAN_SYNTAX",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            duration_ms=80.0,
            tool_calls_added=1,
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_f_recovery_succeeds_after_alternate_path() -> List[RecoveryExecutionEvent]:
    """Fixture F: primary recovery fails, but alternate path succeeds."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_f",
            task_id="task_alt_succ",
            candidate_id="REC2",
            event_index=1,
            failure_signature="KeyError: 'secret_key'",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="TEST_FAILURE",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAILING",
            state_after="FAILING",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_f",
            task_id="task_alt_succ",
            candidate_id="REC2",
            event_index=2,
            failure_signature="KeyError: 'secret_key'",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="ALTERNATE_PATH_ROUTED",
            action="FALLBACK_TREE_INSPECTION",
            attempt_number=2,
            state_before="FAILING",
            state_after="SUCCESS",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=2,
            evidence_mode="FIXTURE",
        ),
    ]


def fixture_g_recovery_fails() -> List[RecoveryExecutionEvent]:
    """Fixture G: recovery attempted but fails across all attempts."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_g",
            task_id="task_fail_all",
            candidate_id="REC0",
            event_index=1,
            failure_signature="ConnectionRefusedError: port 8000",
            failure_class=FailureClass.ENVIRONMENT.value,
            recovery_eligible=True,
            trigger="CONNECTION_ERROR",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="UNREACHABLE",
            state_after="UNREACHABLE",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="",
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_g",
            task_id="task_fail_all",
            candidate_id="REC0",
            event_index=2,
            failure_signature="ConnectionRefusedError: port 8000",
            failure_class=FailureClass.ENVIRONMENT.value,
            recovery_eligible=True,
            trigger="CONNECTION_ERROR",
            action="USE_ALTERNATE_TOOL",
            attempt_number=2,
            state_before="UNREACHABLE",
            state_after="UNREACHABLE",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="path_exhausted",
            turn=2,
            evidence_mode="FIXTURE",
        ),
    ]


def fixture_h_recovery_loops() -> List[RecoveryExecutionEvent]:
    """Fixture H: direct recovery loop repeating identical action without state change."""
    events: list[RecoveryExecutionEvent] = []
    for i in range(1, 4):
        events.append(
            RecoveryExecutionEvent(
                run_id="run_fx_h",
                task_id="task_direct_loop",
                candidate_id="REC_BAD",
                event_index=i,
                failure_signature="ValueError: invalid format",
                failure_class=FailureClass.COMMAND.value,
                recovery_eligible=True,
                trigger="VALUE_ERROR",
                action="REPAIR_EDIT",
                attempt_number=i,
                state_before="BAD_FORMAT",
                state_after="BAD_FORMAT",
                evidence_changed=False,
                recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                loop_detected=False,
                stop_reason="",
                turn=i,
                evidence_mode="FIXTURE",
            )
        )
    return events


def fixture_i_alternating_recovery_loop() -> List[RecoveryExecutionEvent]:
    """Fixture I: alternating recovery loop (oscillation between action A and action B)."""
    actions = ["INSPECT_DIFF", "REPAIR_EDIT", "INSPECT_DIFF", "REPAIR_EDIT"]
    events: list[RecoveryExecutionEvent] = []
    for i, act in enumerate(actions, start=1):
        events.append(
            RecoveryExecutionEvent(
                run_id="run_fx_i",
                task_id="task_oscillation",
                candidate_id="REC_OSC",
                event_index=i,
                failure_signature="IndexError: list index out of range",
                failure_class=FailureClass.INCOMPLETE_FIX.value,
                recovery_eligible=True,
                trigger="OSCILLATION_TRIGGER",
                action=act,
                attempt_number=i,
                state_before="OSCILLATING",
                state_after="OSCILLATING",
                evidence_changed=False,
                recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                loop_detected=False,
                stop_reason="",
                turn=i,
                evidence_mode="FIXTURE",
            )
        )
    return events


def fixture_j_retry_budget_exhausted() -> List[RecoveryExecutionEvent]:
    """Fixture J: recovery bounded by retry budget and stops gracefully."""
    events: list[RecoveryExecutionEvent] = []
    for i in range(1, 5):
        is_last = (i == 4)
        events.append(
            RecoveryExecutionEvent(
                run_id="run_fx_j",
                task_id="task_budget_exhaust",
                candidate_id="REC0",
                event_index=i,
                failure_signature="TimeoutError: 30s exceeded",
                failure_class=FailureClass.ENVIRONMENT.value,
                recovery_eligible=True,
                trigger="TIMEOUT_ERROR",
                action="RETRY_TOOL",
                attempt_number=i,
                state_before="TIMED_OUT",
                state_after="TIMED_OUT",
                evidence_changed=False,
                recovery_outcome=RecoveryOutcome.BUDGET_EXHAUSTED.value if is_last else RecoveryOutcome.NOT_RECOVERED.value,
                loop_detected=False,
                stop_reason="budget_exhausted" if is_last else "",
                turn=i,
                evidence_mode="FIXTURE",
            )
        )
    return events


def fixture_k_recovery_triggered_too_late() -> List[RecoveryExecutionEvent]:
    """Fixture K: recovery is triggered 4 events after the first observable failure."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_k",
            task_id="task_late_rec",
            candidate_id="REC0",
            event_index=1,
            failure_signature="ZeroDivisionError: division by zero",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="",
            action="NONE",
            attempt_number=0,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.INCONCLUSIVE.value,
            loop_detected=False,
            stop_reason="",
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_fx_k",
            task_id="task_late_rec",
            candidate_id="REC0",
            event_index=5,
            failure_signature="ZeroDivisionError: division by zero",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="LATE_TRIGGER",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAIL",
            state_after="RECOVERED",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=5,
            evidence_mode="FIXTURE",
        ),
    ]


def fixture_l_correct_recovery_opportunity_missed() -> List[RecoveryExecutionEvent]:
    """Fixture L: recovery was eligible but never triggered."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_l",
            task_id="task_missed_opp",
            candidate_id="REC0",
            event_index=1,
            failure_signature="AttributeError: 'NoneType' object has no attribute 'val'",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            recovery_eligible=True,
            trigger="",
            action="NONE",
            attempt_number=0,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="terminated_without_recovery",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_m_failed_tool_alternate_tool_succeeds() -> List[RecoveryExecutionEvent]:
    """Fixture M: tool fails (e.g. bash error), alternate tool (e.g. file edit) succeeds."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_m",
            task_id="task_tool_fail",
            candidate_id="REC2",
            event_index=1,
            failure_signature="ToolError: command execution timed out",
            failure_class=FailureClass.COMMAND.value,
            recovery_eligible=True,
            trigger="TOOL_ERROR",
            action="USE_ALTERNATE_TOOL",
            attempt_number=1,
            state_before="TOOL_ERROR",
            state_after="TOOL_RECOVERED",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_n_test_failure_revised_investigation_succeeds() -> List[RecoveryExecutionEvent]:
    """Fixture N: test failure triggers revised hypothesis and succeeding investigation."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_n",
            task_id="task_test_rev",
            candidate_id="REC1",
            event_index=1,
            failure_signature="AssertionError: 404 != 200",
            failure_class=FailureClass.WRONG_HYPOTHESIS.value,
            recovery_eligible=True,
            trigger="TEST_FAILURE",
            action="REVISE_HYPOTHESIS",
            attempt_number=1,
            state_before="WRONG_PATH",
            state_after="REVISED_PATH",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_o_bad_edit_repair_succeeds() -> List[RecoveryExecutionEvent]:
    """Fixture O: bad edit (regression) detected and repair/revert succeeds."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_o",
            task_id="task_bad_edit",
            candidate_id="REC1",
            event_index=1,
            failure_signature="RegressionError: previously passing test broke",
            failure_class=FailureClass.REGRESSION.value,
            recovery_eligible=True,
            trigger="REGRESSION_DETECTED",
            action="REVERT_EDIT",
            attempt_number=1,
            state_before="REGRESSED",
            state_after="RESTORED",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_p_search_fallback_useful_path() -> List[RecoveryExecutionEvent]:
    """Fixture P: semantic search fails, fallback to exact search produces useful path."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_p",
            task_id="task_search_fb",
            candidate_id="REC0",
            event_index=1,
            failure_signature="SearchEmptyError: 0 symbols found",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=True,
            trigger="SEARCH_EMPTY",
            action="FALLBACK_EXACT_SEARCH",
            attempt_number=1,
            state_before="NO_EVIDENCE",
            state_after="EVIDENCE_FOUND",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_q_budget_pressure_bounded_recovery() -> List[RecoveryExecutionEvent]:
    """Fixture Q: remaining budget drops below threshold, controller forces bounded recovery."""
    return [
        RecoveryExecutionEvent(
            run_id="run_fx_q",
            task_id="task_budget_press",
            candidate_id="REC0",
            event_index=1,
            failure_signature="BudgetPressure: 5 tool calls remaining",
            failure_class=FailureClass.UNKNOWN.value,
            recovery_eligible=True,
            trigger="BUDGET_WARNING",
            action="STOP_EXPLORATION",
            attempt_number=1,
            state_before="EXPLORING",
            state_after="CONSOLIDATED",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="budget_conserved",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]


def fixture_r_collateral_regression() -> tuple[list[RecoveryFailureRecord], list[RecoveryFailureRecord]]:
    """Fixture R: target failure improved, but collateral regressions introduced."""
    baseline = [
        RecoveryFailureRecord(
            run_id="run_b_1",
            task_id="task_1",
            candidate_id="REC0",
            failure_class="WRONG_HYPOTHESIS",
            failure_signature="Wrong hypothesis in auth",
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            is_actionable=True,
            evidence_mode="FIXTURE",
        ),
        RecoveryFailureRecord(
            run_id="run_b_2",
            task_id="task_2",
            candidate_id="REC0",
            failure_class="WRONG_HYPOTHESIS",
            failure_signature="Wrong hypothesis in auth",
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            is_actionable=True,
            evidence_mode="FIXTURE",
        ),
    ]
    candidate = [
        # Target failure fixed on task 1 and 2
        RecoveryFailureRecord(
            run_id="run_c_1",
            task_id="task_1",
            candidate_id="REC1",
            failure_class="WRONG_HYPOTHESIS",
            failure_signature="Wrong hypothesis in auth",
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            is_actionable=True,
            evidence_mode="FIXTURE",
        ),
        RecoveryFailureRecord(
            run_id="run_c_2",
            task_id="task_2",
            candidate_id="REC1",
            failure_class="WRONG_HYPOTHESIS",
            failure_signature="Wrong hypothesis in auth",
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            is_actionable=True,
            evidence_mode="FIXTURE",
        ),
        # But collateral regression introduced on task 3
        RecoveryFailureRecord(
            run_id="run_c_3",
            task_id="task_3",
            candidate_id="REC1",
            failure_class="REGRESSION",
            failure_signature="Collateral regression in database driver",
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            is_actionable=True,
            evidence_mode="FIXTURE",
        ),
    ]
    return baseline, candidate


def fixture_s_targeted_failure_reduction() -> tuple[list[RecoveryExecutionEvent], list[RecoveryExecutionEvent]]:
    """Fixture S: candidate reduces targeted failure from 2 down to 0 without collateral regression."""
    baseline = [
        RecoveryExecutionEvent(
            run_id="run_b_s1",
            task_id="task_s1",
            candidate_id="REC0",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="TEST_FAIL",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="path_exhausted",
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_b_s2",
            task_id="task_s2",
            candidate_id="REC0",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="TEST_FAIL",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="path_exhausted",
            evidence_mode="FIXTURE",
        ),
    ]
    candidate = [
        RecoveryExecutionEvent(
            run_id="run_c_s1",
            task_id="task_s1",
            candidate_id="REC1",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="FAST_TRIGGER",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAIL",
            state_after="PASS",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_c_s2",
            task_id="task_s2",
            candidate_id="REC1",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="FAST_TRIGGER",
            action="REPAIR_EDIT",
            attempt_number=1,
            state_before="FAIL",
            state_after="PASS",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            evidence_mode="FIXTURE",
        ),
    ]
    return baseline, candidate


def fixture_t_unchanged_target_failure() -> tuple[list[RecoveryExecutionEvent], list[RecoveryExecutionEvent]]:
    """Fixture T: candidate leaves target failure count completely unchanged."""
    b, _ = fixture_s_targeted_failure_reduction()
    c = [
        RecoveryExecutionEvent(
            run_id="run_c_t1",
            task_id="task_s1",
            candidate_id="REC1",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="TEST_FAIL",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="path_exhausted",
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_c_t2",
            task_id="task_s2",
            candidate_id="REC1",
            event_index=1,
            failure_signature="Targeted error: auth token expired",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="TEST_FAIL",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="path_exhausted",
            evidence_mode="FIXTURE",
        ),
    ]
    return b, c


def fixture_u_detection_latency_improvement() -> tuple[list[RecoveryExecutionEvent], list[RecoveryExecutionEvent]]:
    """Fixture U: candidate detects failure earlier than baseline (latency improves from 4 to 1 event)."""
    base = [
        RecoveryExecutionEvent(
            run_id="run_b_u",
            task_id="task_lat",
            candidate_id="REC0",
            event_index=1,
            failure_signature="DatabaseLocked",
            failure_class="ENVIRONMENT",
            recovery_eligible=True,
            trigger="",
            action="NONE",
            attempt_number=0,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.INCONCLUSIVE.value,
            loop_detected=False,
            stop_reason="",
            turn=1,
            evidence_mode="FIXTURE",
        ),
        RecoveryExecutionEvent(
            run_id="run_b_u",
            task_id="task_lat",
            candidate_id="REC0",
            event_index=5,
            failure_signature="DatabaseLocked",
            failure_class="ENVIRONMENT",
            recovery_eligible=True,
            trigger="LATE_TRIGGER",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="FAIL",
            state_after="PASS",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=3,
            evidence_mode="FIXTURE",
        ),
    ]
    cand = [
        RecoveryExecutionEvent(
            run_id="run_c_u",
            task_id="task_lat",
            candidate_id="REC1",
            event_index=1,
            failure_signature="DatabaseLocked",
            failure_class="ENVIRONMENT",
            recovery_eligible=True,
            trigger="EARLY_TRIGGER",
            action="RETRY_TOOL",
            attempt_number=1,
            state_before="FAIL",
            state_after="PASS",
            evidence_changed=True,
            recovery_outcome=RecoveryOutcome.RECOVERED.value,
            loop_detected=False,
            stop_reason="target_state_recovered",
            turn=1,
            evidence_mode="FIXTURE",
        )
    ]
    return base, cand


def fixture_v_detection_latency_regression() -> tuple[list[RecoveryExecutionEvent], list[RecoveryExecutionEvent]]:
    """Fixture V: candidate detects failure later than baseline (latency regresses)."""
    cand, base = fixture_u_detection_latency_improvement()
    return base, cand


def fixture_w_testing_policy_invariant_manifest() -> RecoveryCandidateManifest:
    """Fixture W: manifest verifying Stage 34 testing policy hash is fixed to T0."""
    policy = build_rec0_baseline_policy()
    return RecoveryCandidateManifest(
        candidate_id="REC0",
        parent_candidate="REC0",
        policy_hash=policy.compute_policy_hash(),
        intervention_id="int_rec_base",
        root_prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        topology_hash=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        test_strategy_skill_hash=EXPECTED_TEST_STRATEGY_SKILL_SHA256,
        repo_triage_skill_hash=EXPECTED_REPO_TRIAGE_SKILL_SHA256,
        evidence_mode="FIXTURE",
    )


def fixture_x_retrieval_policy_invariant_manifest() -> RecoveryCandidateManifest:
    """Fixture X: manifest verifying Stage 33 retrieval policy hash is fixed to R0."""
    return fixture_w_testing_policy_invariant_manifest()


def fixture_y_prompt_invariant_manifest() -> RecoveryCandidateManifest:
    """Fixture Y: manifest verifying root prompt is fixed to P0."""
    return fixture_w_testing_policy_invariant_manifest()


def fixture_z_skill_invariant_manifest() -> RecoveryCandidateManifest:
    """Fixture Z: manifest verifying skills match frozen Stage 24 hashes."""
    return fixture_w_testing_policy_invariant_manifest()


def fixture_aa_no_actionable_live_recovery() -> List[RecoveryFailureRecord]:
    """Fixture AA: all runs are UNAVAILABLE local execution, resulting in NO_ACTIONABLE_LIVE_RECOVERY."""
    return [
        RecoveryFailureRecord(
            run_id="run_live_unavail_1",
            task_id="fastapi_14786",
            candidate_id="REC0",
            evidence_mode="UNAVAILABLE",
            failure_class="infrastructure_unavailable",
            failure_signature="Local Windows host environment lacks 4x NVIDIA L4 GPUs",
            terminal_outcome="execution_unavailable_local_host",
            is_actionable=False,
        ),
        RecoveryFailureRecord(
            run_id="run_live_unavail_2",
            task_id="rich_4070",
            candidate_id="REC0",
            evidence_mode="UNAVAILABLE",
            failure_class="infrastructure_unavailable",
            failure_signature="Local Windows host environment lacks 4x NVIDIA L4 GPUs",
            terminal_outcome="execution_unavailable_local_host",
            is_actionable=False,
        ),
    ]


def fixture_ab_infrastructure_only_data() -> List[RecoveryFailureRecord]:
    """Fixture AB: infrastructure failure data exclusively."""
    return fixture_aa_no_actionable_live_recovery()


def fixture_ac_held_out_regression() -> dict[str, Any]:
    """Fixture AC: validation passes, but held-out confirmation shows regression."""
    return {
        "validation_passed": True,
        "held_out_baseline_pr": 0.50,
        "held_out_candidate_pr": 0.25,
        "held_out_regression": True,
    }


def fixture_ad_manifest_hash_mismatch() -> tuple[RecoveryCandidateManifest, RecoveryPolicy]:
    """Fixture AD: candidate manifest contains incorrect policy hash."""
    policy = build_rec0_baseline_policy()
    manifest = RecoveryCandidateManifest(
        candidate_id="REC1",
        parent_candidate="REC0",
        policy_hash="0000000000000000000000000000000000000000000000000000000000000000",
        intervention_id="int_bad_hash",
        root_prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        topology_hash=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        test_strategy_skill_hash=EXPECTED_TEST_STRATEGY_SKILL_SHA256,
        repo_triage_skill_hash=EXPECTED_REPO_TRIAGE_SKILL_SHA256,
        evidence_mode="FIXTURE",
    )
    return manifest, policy


def fixture_ae_duplicate_candidate_rejection() -> tuple[RecoveryCandidateManifest, RecoveryPolicy]:
    """Fixture AE: candidate_id equals parent_candidate (in-place mutation forbidden)."""
    policy = build_rec0_baseline_policy()
    manifest = RecoveryCandidateManifest(
        candidate_id="REC1",
        parent_candidate="REC1",
        policy_hash=policy.compute_policy_hash(),
        intervention_id="int_dup_cand",
        root_prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        topology_hash=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        test_strategy_skill_hash=EXPECTED_TEST_STRATEGY_SKILL_SHA256,
        repo_triage_skill_hash=EXPECTED_REPO_TRIAGE_SKILL_SHA256,
        evidence_mode="FIXTURE",
    )
    return manifest, policy
