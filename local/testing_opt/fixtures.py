"""Deterministic Testing Strategy Experiment Fixtures A through Y (Stage 34 Section 31).

Provides clean, reproducible synthetic data for verifying testing strategy optimization
without fabricating live Gemma 4 model inference:
A. T0 targeted test passes
B. T0 targeted test fails
C. T1 adjacent test discovers hidden regression
D. T1 adds only redundant tests
E. T2 subsystem test discovers regression
F. T2 full suite infeasible
G. T2 full suite feasible
H. T3 low-risk task stops early
I. T3 high-risk task escalates
J. T3 discovers regression at later stage
K. duplicate test execution
L. repeated full suite
M. test discovery failure
N. test command failure with fallback
O. pre-existing test failure
P. infrastructure-only execution
Q. target failure improves
R. target failure unchanged
S. collateral regression
T. held-out regression
U. paired comparison
V. deterministic policy diff
W. manifest mismatch
X. frozen skill hash mismatch
Y. no actionable live data

All fixtures explicitly enforce evidence_mode = "FIXTURE" (except P and Y which test special evidence modes).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from local.fdd.models import FailureRecord
from local.testing_opt.diff import compute_test_policy_diff
from local.testing_opt.models import (
    FullSuiteFeasibility,
    RiskSignal,
    RiskSignalType,
    TestCandidateManifest,
    TestExecutionEvent,
    TestHypothesis,
    TestLevel,
    TestPolicy,
    TestingStrategyVariant,
)
from local.testing_opt.policy import (
    build_t0_targeted_policy,
    build_t1_adjacent_policy,
    build_t2_subsystem_full_policy,
    build_t3_adaptive_policy,
)
from local.testing_opt.validator import (
    EXPECTED_FROZEN_TEST_SKILL_SHA256,
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
    EXPECTED_TOPOLOGY_ID,
)


def get_fixture_a_t0_targeted_pass() -> Tuple[TestPolicy, List[FailureRecord], List[TestExecutionEvent]]:
    """Fixture A: T0 targeted test passes."""
    policy = build_t0_targeted_policy()
    records = [
        FailureRecord(
            run_id="run-t0-pass",
            candidate_id="T0",
            task_id="astropy__astropy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t0-pass",
            task_id="astropy__astropy-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command="pytest astropy/io/fits/tests/test_header.py -k test_card_key",
            selected_tests=["astropy.io.fits.tests.test_header.test_card_key"],
            selection_reason="Targeted test directly covers changed function parse_card()",
            start_time="2026-09-30T10:00:00Z",
            duration_ms=450.0,
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            output_size_bytes=1024,
            stop_decision="TARGETED_PASSED",
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_b_t0_targeted_fail() -> Tuple[TestPolicy, List[FailureRecord], List[TestExecutionEvent]]:
    """Fixture B: T0 targeted test fails."""
    policy = build_t0_targeted_policy()
    records = [
        FailureRecord(
            run_id="run-t0-fail",
            candidate_id="T0",
            task_id="astropy__astropy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="TEST_FAILURE",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t0-fail",
            task_id="astropy__astropy-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command="pytest astropy/io/fits/tests/test_header.py -k test_card_key",
            selected_tests=["astropy.io.fits.tests.test_header.test_card_key"],
            selection_reason="Targeted test directly covers changed function parse_card()",
            start_time="2026-09-30T10:00:00Z",
            duration_ms=480.0,
            result="FAILED",
            tests_executed=1,
            failures_detected=1,
            output_size_bytes=2048,
            stop_decision="TARGETED_FAILED_STOP",
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_c_t1_adjacent_discovers_regression() -> Tuple[TestPolicy, List[FailureRecord], List[TestExecutionEvent]]:
    """Fixture C: T1 adjacent test discovers hidden regression."""
    policy = build_t1_adjacent_policy()
    records = [
        FailureRecord(
            run_id="run-t1-adjacent-reg",
            candidate_id="T1",
            task_id="astropy__astropy-2",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t1-adjacent-reg",
            task_id="astropy__astropy-2",
            candidate_id="T1",
            strategy_id="T1",
            test_level=TestLevel.TARGETED.value,
            command="pytest astropy/time/tests/test_formats.py -k test_iso",
            selected_tests=["astropy.time.tests.test_formats.test_iso"],
            selection_reason="Targeted test for TimeISO formatting",
            duration_ms=300.0,
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            escalation_decision="ESCALATE_TO_ADJACENT",
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t1-adjacent-reg",
            task_id="astropy__astropy-2",
            candidate_id="T1",
            strategy_id="T1",
            test_level=TestLevel.ADJACENT.value,
            command="pytest astropy/time/tests/test_formats.py",
            selected_tests=["astropy.time.tests.test_formats.test_ymdhms"],
            selection_reason="Neighboring test class in same module",
            duration_ms=650.0,
            result="FAILED",
            tests_executed=4,
            failures_detected=1,
            stop_decision="ADJACENT_FOUND_REGRESSION",
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, records, events


def get_fixture_d_t1_redundant_tests() -> Tuple[TestPolicy, List[FailureRecord], List[TestExecutionEvent]]:
    """Fixture D: T1 adds only redundant tests with no new failure discoveries."""
    policy = build_t1_adjacent_policy()
    records = [
        FailureRecord(
            run_id="run-t1-redundant",
            candidate_id="T1",
            task_id="astropy__astropy-3",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t1-redundant",
            task_id="astropy__astropy-3",
            candidate_id="T1",
            strategy_id="T1",
            test_level=TestLevel.TARGETED.value,
            command="pytest astropy/utils/tests/test_misc.py -k test_isiterable",
            selected_tests=["test_isiterable"],
            selection_reason="Targeted utility test",
            duration_ms=200.0,
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            escalation_decision="ESCALATE_TO_ADJACENT",
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t1-redundant",
            task_id="astropy__astropy-3",
            candidate_id="T1",
            strategy_id="T1",
            test_level=TestLevel.ADJACENT.value,
            command="pytest astropy/utils/tests/test_misc.py",
            selected_tests=["test_isiterable", "test_silence", "test_format_value"],
            selection_reason="Same module sibling tests",
            duration_ms=500.0,
            result="PASSED",
            tests_executed=3,
            failures_detected=0,
            stop_decision="ADJACENT_PASSED_NO_NEW_FAILURES",
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, records, events


def get_fixture_e_t2_subsystem_discovers_regression() -> Tuple[TestPolicy, List[FailureRecord], List[TestExecutionEvent]]:
    """Fixture E: T2 subsystem test discovers regression that targeted & adjacent missed."""
    policy = build_t2_subsystem_full_policy()
    records = [
        FailureRecord(
            run_id="run-t2-subsystem-reg",
            candidate_id="T2",
            task_id="sympy__sympy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t2-subsystem-reg",
            task_id="sympy__sympy-1",
            candidate_id="T2",
            strategy_id="T2",
            test_level=TestLevel.TARGETED.value,
            command="pytest sympy/core/tests/test_expr.py -k test_as_coeff_Add",
            selected_tests=["test_as_coeff_Add"],
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            duration_ms=400.0,
            escalation_decision="ESCALATE_TO_ADJACENT",
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t2-subsystem-reg",
            task_id="sympy__sympy-1",
            candidate_id="T2",
            strategy_id="T2",
            test_level=TestLevel.ADJACENT.value,
            command="pytest sympy/core/tests/test_expr.py",
            selected_tests=["sympy/core/tests/test_expr.py"],
            result="PASSED",
            tests_executed=15,
            failures_detected=0,
            duration_ms=1200.0,
            escalation_decision="ESCALATE_TO_SUBSYSTEM",
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t2-subsystem-reg",
            task_id="sympy__sympy-1",
            candidate_id="T2",
            strategy_id="T2",
            test_level=TestLevel.SUBSYSTEM.value,
            command="pytest sympy/simplify/tests/test_simplify.py",
            selected_tests=["sympy/simplify/tests/test_simplify.py"],
            result="FAILED",
            tests_executed=30,
            failures_detected=2,
            duration_ms=3500.0,
            stop_decision="SUBSYSTEM_DETECTED_REGRESSION",
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, records, events


def get_fixture_f_t2_full_suite_infeasible() -> Tuple[TestPolicy, Dict[str, Any]]:
    """Fixture F: T2 full suite feasibility evaluates to NOT_FEASIBLE."""
    policy = build_t2_subsystem_full_policy(max_full_suite_runtime_sec=60.0)
    context = {
        "historical_runtime_sec": 300.0,
        "remaining_budget_sec": 45.0,
        "total_test_count": 2500,
        "environment_stable": True,
        "known_incompatible_suite": False,
    }
    return policy, context


def get_fixture_g_t2_full_suite_feasible() -> Tuple[TestPolicy, Dict[str, Any]]:
    """Fixture G: T2 full suite feasibility evaluates to FEASIBLE."""
    policy = build_t2_subsystem_full_policy(max_full_suite_runtime_sec=120.0)
    context = {
        "historical_runtime_sec": 40.0,
        "remaining_budget_sec": 180.0,
        "total_test_count": 120,
        "environment_stable": True,
        "known_incompatible_suite": False,
    }
    return policy, context


def get_fixture_h_t3_low_risk_stops_early() -> Tuple[TestPolicy, List[RiskSignal], List[TestExecutionEvent]]:
    """Fixture H: T3 low-risk task stops early after targeted test passes."""
    policy = build_t3_adaptive_policy()
    signals = [
        RiskSignal(
            signal_type=RiskSignalType.LARGE_DIFF_SIZE.value,
            observed=False,
            source="git_diff",
            severity="LOW",
            rationale="Diff is under 15 lines",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t3-low-risk",
            task_id="django__django-10",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.TARGETED.value,
            command="pytest tests/forms_tests/field_tests/test_charfield.py",
            selected_tests=["test_charfield"],
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            duration_ms=250.0,
            stop_decision="LOW_RISK_TARGETED_PASS_STOP",
            risk_signals=["LOW_DIFF"],
            evidence_mode="FIXTURE",
        )
    ]
    return policy, signals, events


def get_fixture_i_t3_high_risk_escalates() -> Tuple[TestPolicy, List[RiskSignal], List[TestExecutionEvent]]:
    """Fixture I: T3 high-risk task escalates from targeted to adjacent to subsystem."""
    policy = build_t3_adaptive_policy()
    signals = [
        RiskSignal(
            signal_type=RiskSignalType.MULTIPLE_CHANGED_FILES.value,
            observed=True,
            source="git_diff",
            severity="HIGH",
            rationale="4 files modified across 2 packages",
        ),
        RiskSignal(
            signal_type=RiskSignalType.CHANGED_SHARED_UTILITY.value,
            observed=True,
            source="diff_analysis",
            severity="HIGH",
            rationale="Modified core utility helper django/utils/functional.py",
        ),
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t3-high-risk",
            task_id="django__django-20",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.TARGETED.value,
            command="pytest tests/utils_tests/test_functional.py -k test_lazy",
            selected_tests=["test_lazy"],
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            duration_ms=300.0,
            escalation_decision="ESCALATE_HIGH_RISK_MULTIPLE_CHANGED_FILES",
            risk_signals=["MULTIPLE_CHANGED_FILES", "CHANGED_SHARED_UTILITY"],
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t3-high-risk",
            task_id="django__django-20",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.ADJACENT.value,
            command="pytest tests/utils_tests/test_functional.py",
            selected_tests=["tests/utils_tests/test_functional.py"],
            result="PASSED",
            tests_executed=10,
            failures_detected=0,
            duration_ms=800.0,
            escalation_decision="ESCALATE_HIGH_RISK_SHARED_UTILITY",
            risk_signals=["CHANGED_SHARED_UTILITY"],
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t3-high-risk",
            task_id="django__django-20",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.SUBSYSTEM.value,
            command="pytest tests/model_fields/ tests/forms_tests/",
            selected_tests=["tests/model_fields/", "tests/forms_tests/"],
            result="PASSED",
            tests_executed=50,
            failures_detected=0,
            duration_ms=4200.0,
            stop_decision="SUBSYSTEM_PASSED_HIGH_CONFIDENCE",
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, signals, events


def get_fixture_j_t3_discovers_regression_at_later_stage() -> Tuple[TestPolicy, List[RiskSignal], List[TestExecutionEvent]]:
    """Fixture J: T3 escalates due to risk and discovers regression at ADJACENT/SUBSYSTEM level."""
    policy = build_t3_adaptive_policy()
    signals = [
        RiskSignal(
            signal_type=RiskSignalType.CHANGED_PUBLIC_API.value,
            observed=True,
            source="ast_diff",
            severity="HIGH",
            rationale="Modified signature of public function",
        )
    ]
    events = [
        TestExecutionEvent(
            run_id="run-t3-later-reg",
            task_id="requests__requests-1",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.TARGETED.value,
            command="pytest tests/test_requests.py -k test_entry_point",
            selected_tests=["test_entry_point"],
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            duration_ms=200.0,
            escalation_decision="ESCALATE_PUBLIC_API_CHANGED",
            risk_signals=["CHANGED_PUBLIC_API"],
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-t3-later-reg",
            task_id="requests__requests-1",
            candidate_id="T3",
            strategy_id="T3",
            test_level=TestLevel.ADJACENT.value,
            command="pytest tests/test_requests.py -k test_params",
            selected_tests=["test_params"],
            result="FAILED",
            tests_executed=3,
            failures_detected=1,
            duration_ms=600.0,
            stop_decision="ADJACENT_DISCOVERED_REGRESSION",
            risk_signals=["CHANGED_PUBLIC_API"],
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, signals, events


def get_fixture_k_duplicate_test_execution() -> List[TestExecutionEvent]:
    """Fixture K: Duplicate test commands/cases executed unnecessarily."""
    cmd = "pytest tests/test_core.py -k test_foo"
    return [
        TestExecutionEvent(
            run_id="run-dup",
            task_id="task-dup-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command=cmd,
            selected_tests=["test_foo"],
            duration_ms=100.0,
            result="PASSED",
            tests_executed=1,
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-dup",
            task_id="task-dup-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command=cmd,
            selected_tests=["test_foo"],
            duration_ms=100.0,
            result="PASSED",
            tests_executed=1,
            evidence_mode="FIXTURE",
        ),
    ]


def get_fixture_l_repeated_full_suite() -> List[TestExecutionEvent]:
    """Fixture L: Repeated full suite executions detected."""
    cmd = "pytest tests/"
    return [
        TestExecutionEvent(
            run_id="run-rep-full",
            task_id="task-full-1",
            candidate_id="T2",
            strategy_id="T2",
            test_level=TestLevel.FULL.value,
            command=cmd,
            duration_ms=30000.0,
            result="PASSED",
            tests_executed=500,
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-rep-full",
            task_id="task-full-1",
            candidate_id="T2",
            strategy_id="T2",
            test_level=TestLevel.FULL.value,
            command=cmd,
            duration_ms=31000.0,
            result="PASSED",
            tests_executed=500,
            evidence_mode="FIXTURE",
        ),
    ]


def get_fixture_m_test_discovery_failure() -> Tuple[TestPolicy, TestExecutionEvent]:
    """Fixture M: Test discovery fails to locate relevant targeted test."""
    policy = build_t0_targeted_policy()
    event = TestExecutionEvent(
        run_id="run-disc-fail",
        task_id="task-disc-1",
        candidate_id="T0",
        strategy_id="T0",
        test_level=TestLevel.TARGETED.value,
        command="",
        selected_tests=[],
        selection_reason="Discovery failed: no test framework or matching test file located",
        result="SKIPPED",
        tests_executed=0,
        failures_detected=0,
        stop_decision="DISCOVERY_FAILED_FALLBACK_NEEDED",
        metadata={"discovery_error": "No matching test files found for repo root"},
        evidence_mode="FIXTURE",
    )
    return policy, event


def get_fixture_n_test_command_failure_fallback() -> Tuple[TestPolicy, List[TestExecutionEvent]]:
    """Fixture N: Test command failure triggers fallback mechanism."""
    policy = build_t0_targeted_policy()
    events = [
        TestExecutionEvent(
            run_id="run-cmd-fail",
            task_id="task-cmd-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command="pytest -k invalid_selector_syntax(((",
            selected_tests=[],
            result="ERROR",
            tests_executed=0,
            failures_detected=1,
            escalation_decision="FALLBACK_BROADER_COMMAND",
            evidence_mode="FIXTURE",
        ),
        TestExecutionEvent(
            run_id="run-cmd-fail",
            task_id="task-cmd-1",
            candidate_id="T0",
            strategy_id="T0",
            test_level=TestLevel.TARGETED.value,
            command="pytest tests/test_basic.py",
            selected_tests=["test_basic"],
            result="PASSED",
            tests_executed=1,
            failures_detected=0,
            stop_decision="FALLBACK_COMMAND_SUCCEEDED",
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, events


def get_fixture_o_pre_existing_test_failure() -> Tuple[FailureRecord, TestExecutionEvent]:
    """Fixture O: Pre-existing failure present before candidate changes."""
    record = FailureRecord(
        run_id="run-pre-exist",
        candidate_id="T0",
        task_id="task-pre-1",
        run_status="COMPLETED",
        is_actionable=True,
        success=False,
        failure_category="PRE_EXISTING_FAILURE",
        evidence_mode="FIXTURE",
        failure_subreason="Failed on clean baseline snapshot before patch",
    )
    event = TestExecutionEvent(
        run_id="run-pre-exist",
        task_id="task-pre-1",
        candidate_id="T0",
        strategy_id="T0",
        test_level=TestLevel.TARGETED.value,
        command="pytest tests/test_legacy.py",
        result="FAILED",
        tests_executed=1,
        failures_detected=1,
        metadata={"pre_existing": True},
        evidence_mode="FIXTURE",
    )
    return record, event


def get_fixture_p_infrastructure_only_execution() -> Tuple[FailureRecord, TestExecutionEvent]:
    """Fixture P: Infrastructure-only execution (tool unavailable / timeout)."""
    record = FailureRecord(
        run_id="run-infra-only",
        candidate_id="T0",
        task_id="task-infra-1",
        run_status="UNKNOWN",
        is_actionable=False,
        success=False,
        failure_category="INFRASTRUCTURE_UNAVAILABLE",
        evidence_mode="INFRASTRUCTURE_ONLY",
    )
    event = TestExecutionEvent(
        run_id="run-infra-only",
        task_id="task-infra-1",
        candidate_id="T0",
        strategy_id="T0",
        test_level=TestLevel.TARGETED.value,
        command="docker run ...",
        result="ERROR",
        tests_executed=0,
        failures_detected=0,
        evidence_mode="INFRASTRUCTURE_ONLY",
        metadata={"infra_error": "Docker socket not responsive"},
    )
    return record, event


def get_fixture_q_target_failure_improves() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture Q: Target failure mode count improves from baseline to candidate (4 -> 1)."""
    baseline = [
        FailureRecord(
            run_id="run-base",
            candidate_id="T0",
            task_id=f"target-task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    candidate = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="T1",
            task_id="target-task-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
    ] + [
        FailureRecord(
            run_id="run-cand",
            candidate_id="T1",
            task_id=f"target-task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(2, 5)
    ]
    return baseline, candidate


def get_fixture_r_target_failure_unchanged() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture R: Target failure mode unchanged (4 -> 4)."""
    baseline = [
        FailureRecord(
            run_id="run-base",
            candidate_id="T0",
            task_id=f"target-task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    candidate = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="T1",
            task_id=f"target-task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    return baseline, candidate


def get_fixture_s_collateral_regression() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture S: Target failure improves, but collateral regression occurs on unrelated tasks."""
    baseline = [
        FailureRecord(
            run_id="run-base",
            candidate_id="T0",
            task_id=f"target-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ] + [
        FailureRecord(
            run_id="run-base",
            candidate_id="T0",
            task_id=f"other-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    candidate = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="T1",
            task_id=f"target-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ] + [
        FailureRecord(
            run_id="run-cand",
            candidate_id="T1",
            task_id=f"other-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="TEST_TIMEOUT",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    return baseline, candidate


def get_fixture_t_held_out_regression() -> Tuple[List[FailureRecord], List[FailureRecord], List[FailureRecord], List[FailureRecord]]:
    """Fixture T: Validation split passes, but held-out split shows regression."""
    val_base = [
        FailureRecord(
            run_id="val-base",
            candidate_id="T0",
            task_id=f"val-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    val_cand = [
        FailureRecord(
            run_id="val-cand",
            candidate_id="T1",
            task_id=f"val-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    held_base = [
        FailureRecord(
            run_id="held-base",
            candidate_id="T0",
            task_id=f"held-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    held_cand = [
        FailureRecord(
            run_id="held-cand",
            candidate_id="T1",
            task_id=f"held-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="INCOMPLETE_FIX",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    return val_base, val_cand, held_base, held_cand


def get_fixture_u_paired_comparison() -> Tuple[List[FailureRecord], List[FailureRecord], List[TestExecutionEvent], List[TestExecutionEvent]]:
    """Fixture U: Paired task comparison between T0 baseline and T1 candidate."""
    tasks = ["task-1", "task-2", "task-3", "task-4"]
    t0_records = [
        FailureRecord(run_id="run-t0", candidate_id="T0", task_id="task-1", run_status="COMPLETED", is_actionable=True, success=True, evidence_mode="FIXTURE"),
        FailureRecord(run_id="run-t0", candidate_id="T0", task_id="task-2", run_status="COMPLETED", is_actionable=True, success=True, evidence_mode="FIXTURE"),  # False confidence
        FailureRecord(run_id="run-t0", candidate_id="T0", task_id="task-3", run_status="COMPLETED", is_actionable=True, success=False, failure_category="TEST_FAILURE", evidence_mode="FIXTURE"),
        FailureRecord(run_id="run-t0", candidate_id="T0", task_id="task-4", run_status="COMPLETED", is_actionable=True, success=False, failure_category="TEST_FAILURE", evidence_mode="FIXTURE"),
    ]
    t1_records = [
        FailureRecord(run_id="run-t1", candidate_id="T1", task_id="task-1", run_status="COMPLETED", is_actionable=True, success=True, evidence_mode="FIXTURE"),
        FailureRecord(run_id="run-t1", candidate_id="T1", task_id="task-2", run_status="COMPLETED", is_actionable=True, success=False, failure_category="INCOMPLETE_FIX", evidence_mode="FIXTURE"),  # Discovered regression
        FailureRecord(run_id="run-t1", candidate_id="T1", task_id="task-3", run_status="COMPLETED", is_actionable=True, success=False, failure_category="TEST_FAILURE", evidence_mode="FIXTURE"),
        FailureRecord(run_id="run-t1", candidate_id="T1", task_id="task-4", run_status="COMPLETED", is_actionable=True, success=True, evidence_mode="FIXTURE"),  # Fixed
    ]
    t0_events = [
        TestExecutionEvent(run_id="run-t0", task_id=t, candidate_id="T0", strategy_id="T0", test_level=TestLevel.TARGETED.value, command=f"pytest tests/test_{t}.py", duration_ms=200.0, result="PASSED" if t in ("task-1", "task-2") else "FAILED", tests_executed=1, failures_detected=0 if t in ("task-1", "task-2") else 1, evidence_mode="FIXTURE")
        for t in tasks
    ]
    t1_events = [
        TestExecutionEvent(run_id="run-t1", task_id=t, candidate_id="T1", strategy_id="T1", test_level=TestLevel.TARGETED.value, command=f"pytest tests/test_{t}.py", duration_ms=200.0, result="PASSED" if t != "task-3" else "FAILED", tests_executed=1, failures_detected=0 if t != "task-3" else 1, evidence_mode="FIXTURE")
        for t in tasks
    ] + [
        TestExecutionEvent(run_id="run-t1", task_id="task-2", candidate_id="T1", strategy_id="T1", test_level=TestLevel.ADJACENT.value, command="pytest tests/test_task-2_adjacent.py", duration_ms=500.0, result="FAILED", tests_executed=4, failures_detected=1, evidence_mode="FIXTURE")
    ]
    return t0_records, t1_records, t0_events, t1_events


def get_fixture_v_deterministic_policy_diff() -> Tuple[TestPolicy, TestPolicy]:
    """Fixture V: Deterministic policy diff between T0 and T1."""
    p0 = build_t0_targeted_policy()
    p1 = build_t1_adjacent_policy()
    return p0, p1


def get_fixture_w_manifest_mismatch() -> Tuple[TestCandidateManifest, TestPolicy]:
    """Fixture W: Manifest records tampered or mismatched policy hash."""
    policy = build_t1_adjacent_policy()
    manifest = TestCandidateManifest(
        candidate_id="T1",
        parent_candidate_id="T0",
        strategy_variant=TestingStrategyVariant.T1.value,
        test_policy_hash="0000000000000000000000000000000000000000000000000000000000000000",
        hypothesis=TestHypothesis(
            target_failure="INCOMPLETE_FIX",
            observation="Adjacent tests detect hidden regressions",
            hypothesis="T1 adjacent testing catches edge cases",
            testing_change="Enable adjacent test level",
            expected_signal="Reduction in incomplete fix failures",
            rejection_condition="Zero new failures discovered or excessive runtime",
        ),
        evidence_mode="FIXTURE",
    )
    return manifest, policy


def get_fixture_x_frozen_skill_hash_mismatch() -> str:
    """Fixture X: Tampered test strategy skill hash."""
    return "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"


def get_fixture_y_no_actionable_live_data() -> List[FailureRecord]:
    """Fixture Y: Current real local baseline state where all runs are infrastructure/unavailable."""
    return [
        FailureRecord(
            run_id="run-unavail-local",
            candidate_id="T0",
            task_id=f"task-local-{i}",
            run_status="UNKNOWN",
            is_actionable=False,
            success=False,
            failure_category="INFRASTRUCTURE_UNAVAILABLE",
            evidence_mode="UNAVAILABLE",
        )
        for i in range(1, 5)
    ]
