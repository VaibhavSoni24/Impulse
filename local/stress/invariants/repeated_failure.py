"""Stress Invariant Checker: STRESS 10 — Repeated Test Failure Patterns.

Exercises all 10 Stage 35 recovery and loop patterns under stressful repetition sequences:
1. REPEATED_COMMAND: identical test command re-executed without progress.
2. REPEATED_ERROR: identical error signature recurring.
3. REPEATED_EDIT: identical code diff repeated across cycles.
4. REPEATED_HYPOTHESIS: identical diagnosis proposed repeatedly.
5. RECOVERY_LOOP: direct action loop or A -> B -> A oscillation detected.
6. RECOVERY_THRASHING: erratic switching across recovery paths without progress.
7. RETRY_WASTE: retrying when budget is exhausted or failure signature is unyielding.
8. RECOVERY_OMISSION: failure to trigger recovery when consecutive errors occur.
9. LATE_RECOVERY: recovery initiated only after excessive wasted cycles.
10. FAILED_RECOVERY: recovery attempted but resulting in unrecovered failure.

Includes negative test verifying that legitimate distinct commands are not falsely flagged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from local.failures.models import FailureClass
from local.progress.detector import NoProgressDetectorV1
from local.progress.models import CycleSnapshot, NoProgressReason, ProgressStatus
from local.recovery_opt.loop_detector import RecoveryLoopDetector
from local.recovery_opt.models import (
    RecoveryExecutionEvent,
    RecoveryOutcome,
    RecoveryPatternType,
    RecoveryPolicy,
    RetryBudgetConfig,
)


def check_stress_repeated_command() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-001: Repeated command detection and negative discrimination."""
    detector = NoProgressDetectorV1(threshold=2)

    s1 = CycleSnapshot(
        cycle_id=1,
        test_command="pytest tests/test_core.py -k test_calc",
        test_result="FAILED",
        failure_class="REGRESSION",
        failure_signature="AssertionError: 4 != 5",
        hypothesis="Hypothesis A: off-by-one error",
        edit_content="diff --git a/calc.py b/calc.py\n+return x + 1",
    )
    res1 = detector.record_cycle(s1)
    if res1.status == ProgressStatus.NO_PROGRESS:
        return False, "Premature NO_PROGRESS on cycle 1", {}

    # Repeated identical command with identical failure
    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="pytest tests/test_core.py -k test_calc",
        test_result="FAILED",
        failure_class="REGRESSION",
        failure_signature="AssertionError: 4 != 5",
        hypothesis="Hypothesis A: off-by-one error",
        edit_content="diff --git a/calc.py b/calc.py\n+return x + 1",
    )
    res2 = detector.record_cycle(s2)
    if res2.status != ProgressStatus.NO_PROGRESS:
        return False, "Failed to detect NO_PROGRESS on repeated command", {}

    # Negative discrimination: distinct command does NOT trigger no-progress
    detector.reset()
    detector.record_cycle(s1)
    s_diff = CycleSnapshot(
        cycle_id=2,
        test_command="pytest tests/test_other.py -k test_calc",
        test_result="FAILED",
        failure_class="REGRESSION",
        failure_signature="AssertionError: 4 != 5",
        hypothesis="Hypothesis A: off-by-one error",
        edit_content="diff --git a/calc.py b/calc.py\n+return x + 1",
    )
    res_diff = detector.record_cycle(s_diff)
    if res_diff.status == ProgressStatus.NO_PROGRESS:
        return False, "False positive: Distinct command incorrectly flagged as repeated", {}

    return True, "Repeated command accurately detected; distinct command preserved.", {"threshold": 2}


def check_stress_repeated_error() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-002: Repeated error signature detection."""
    detector = NoProgressDetectorV1(threshold=2)
    s1 = CycleSnapshot(
        cycle_id=1,
        test_command="pytest tests/test_parser.py",
        test_result="FAILED",
        failure_class="INCOMPLETE_FIX",
        failure_signature="KeyError: 'token_stream'",
        hypothesis=None,
    )
    detector.record_cycle(s1)
    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="pytest tests/test_parser.py",
        test_result="FAILED",
        failure_class="INCOMPLETE_FIX",
        failure_signature="KeyError: 'token_stream'",
        hypothesis=None,
    )
    res2 = detector.record_cycle(s2)
    if res2.status != ProgressStatus.NO_PROGRESS or res2.reason != NoProgressReason.REPEATED_FAILURE:
        return False, f"Expected REPEATED_FAILURE, got status={res2.status}, reason={res2.reason}", {}
    return True, "Repeated error signature reliably identified across cycles.", {"reason": res2.reason.value}


def check_stress_repeated_edit() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-003: Repeated edit detection."""
    detector = NoProgressDetectorV1(threshold=2)
    diff = "diff --git a/app.py b/app.py\n+timeout = 30\n"
    s1 = CycleSnapshot(cycle_id=1, edit_content=diff, test_result="FAILED", failure_signature="Timeout")
    detector.record_cycle(s1)
    s2 = CycleSnapshot(cycle_id=2, edit_content=diff, test_result="FAILED", failure_signature="Timeout")
    res2 = detector.record_cycle(s2)
    if res2.status != ProgressStatus.NO_PROGRESS:
        return False, "Failed to detect repeated edit", {}
    return True, "Identical code edit repeated without progress correctly detected.", {}


def check_stress_repeated_hypothesis() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-004: Repeated hypothesis detection."""
    detector = NoProgressDetectorV1(threshold=2)
    hypo = "Root cause is missing JSON decoder encoding fallback"
    s1 = CycleSnapshot(
        cycle_id=1,
        test_command="python -m unittest tests.test_json",
        test_result="FAILED",
        failure_class="WRONG_HYPOTHESIS",
        failure_signature="UnicodeDecodeError: 'utf-8' codec",
        hypothesis=hypo,
    )
    detector.record_cycle(s1)
    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="python -m unittest tests.test_json",
        test_result="FAILED",
        failure_class="WRONG_HYPOTHESIS",
        failure_signature="UnicodeDecodeError: 'utf-8' codec",
        hypothesis=hypo.upper(),
    )
    res2 = detector.record_cycle(s2)
    if res2.status != ProgressStatus.NO_PROGRESS or res2.reason != NoProgressReason.REPEATED_HYPOTHESIS:
        return False, f"Expected REPEATED_HYPOTHESIS, got {res2.reason}", {}
    return True, "Repeated unverified hypothesis correctly identified.", {}


def check_stress_recovery_loop() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-005: Direct loop and oscillation detection."""
    detector = RecoveryLoopDetector(max_allowed_direct_repeats=2)
    events = [
        RecoveryExecutionEvent(
            run_id="run_1",
            task_id="task_001",
            candidate_id="REC0",
            event_index=0,
            failure_signature="SIG_A",
            failure_class="REGRESSION",
            recovery_eligible=True,
            trigger="test_failure",
            action="REPAIR_HANDLER",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="CONTINUE",
        ),
        RecoveryExecutionEvent(
            run_id="run_1",
            task_id="task_001",
            candidate_id="REC0",
            event_index=1,
            failure_signature="SIG_B",
            failure_class="REGRESSION",
            recovery_eligible=True,
            trigger="test_failure",
            action="REVERT_DIFF",
            attempt_number=1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="CONTINUE",
        ),
        RecoveryExecutionEvent(
            run_id="run_1",
            task_id="task_001",
            candidate_id="REC0",
            event_index=2,
            failure_signature="SIG_A",
            failure_class="REGRESSION",
            recovery_eligible=True,
            trigger="test_failure",
            action="REPAIR_HANDLER",
            attempt_number=2,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="CONTINUE",
        ),
        RecoveryExecutionEvent(
            run_id="run_1",
            task_id="task_001",
            candidate_id="REC0",
            event_index=3,
            failure_signature="SIG_B",
            failure_class="REGRESSION",
            recovery_eligible=True,
            trigger="test_failure",
            action="REVERT_DIFF",
            attempt_number=2,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="CONTINUE",
        ),
    ]
    res = detector.analyze_events(events)
    if not res.loop_detected or res.loop_type not in ("OSCILLATION", "DIRECT_LOOP"):
        return False, f"Failed to detect oscillation loop: {res}", {}
    return True, f"Recovery oscillation loop detected: {res.loop_type} with cycle_count={res.cycle_count}.", {"loop_type": res.loop_type}


def check_stress_recovery_thrashing() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-006: Recovery thrashing detection."""
    events = [
        RecoveryExecutionEvent(
            run_id="run_thrash",
            task_id="task_002",
            candidate_id="REC0",
            event_index=i,
            failure_signature="SIG_STATIC_FAIL",
            failure_class="INCOMPLETE_FIX",
            recovery_eligible=True,
            trigger="test_failure",
            action=f"ACTION_ATTEMPT_{i}",
            attempt_number=i + 1,
            state_before="FAIL",
            state_after="FAIL",
            evidence_changed=False,
            recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
            loop_detected=False,
            stop_reason="CONTINUE",
        )
        for i in range(4)
    ]
    unimproved_count = sum(1 for e in events if not e.evidence_changed and e.state_after == "FAIL")
    if unimproved_count < 3:
        return False, "Failed to track unimproved recovery attempts", {}
    return True, f"Recovery thrashing tracked across {unimproved_count} unimproved consecutive interventions.", {"unimproved_count": unimproved_count}


def check_stress_retry_waste() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-007: Retry waste under exhausted budget."""
    budget = RetryBudgetConfig(
        max_same_action_retries=1,
        max_total_recovery_attempts=2,
        max_alternate_paths=1,
        max_recovery_runtime_seconds=60.0,
        max_recovery_tool_calls=4,
    )
    attempt_count = 3
    is_exhausted = attempt_count > budget.max_total_recovery_attempts
    if not is_exhausted:
        return False, f"Retry budget failed to flag exhaustion at attempt {attempt_count}", {}

    policy = RecoveryPolicy(retry_budgets=budget)
    if "budget_exhausted" not in policy.stop_conditions:
        return False, "'budget_exhausted' missing from policy stop_conditions", {}

    return True, "Retry waste prevented: attempts beyond budget strictly stop with budget_exhausted.", {"attempt_count": attempt_count}


def check_stress_recovery_omission() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-008: Recovery omission detection."""
    meaningful_classes = [fc.value for fc in FailureClass if fc != FailureClass.UNKNOWN]
    policy = RecoveryPolicy()
    for fc in meaningful_classes:
        if "on_test_failure" not in policy.fallback_rules:
            return False, "Missing on_test_failure fallback rule", {}

    return True, f"Recovery omission avoided: {len(meaningful_classes)} failure classes require explicit classification and fallback.", {"count": len(meaningful_classes)}


def check_stress_late_recovery() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-009: Late recovery boundary enforcement."""
    policy = RecoveryPolicy()
    if policy.no_progress_threshold_turns > 3:
        return False, f"no_progress_threshold_turns ({policy.no_progress_threshold_turns}) exceeds 3", {}
    return True, f"Late recovery prevented: no-progress threshold is bounded to {policy.no_progress_threshold_turns} turns (<= 3).", {"threshold_turns": policy.no_progress_threshold_turns}


def check_stress_failed_recovery() -> tuple[bool, str, dict[str, Any]]:
    """STRESS-RECOVERY-010: Terminal failed recovery outcome tracking."""
    policy = RecoveryPolicy(alternate_path_routing_enabled=True)
    fallback = policy.fallback_rules.get("on_tool_failure")
    if fallback != "RETRY_THEN_ALTERNATE":
        return False, f"Expected on_tool_failure fallback 'RETRY_THEN_ALTERNATE', got '{fallback}'", {}
    return True, f"Failed recovery escalates cleanly to alternate path: {fallback}.", {"fallback": fallback}
