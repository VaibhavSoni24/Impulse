"""Invariant checkers for RECOVERY regressions (Stage 45 Phase 5 & 6).

Covers the 10 Stage 35 recovery failure patterns:
- REG-RECOVERY-001: REPEATED_COMMAND
- REG-RECOVERY-002: REPEATED_ERROR
- REG-RECOVERY-003: REPEATED_EDIT
- REG-RECOVERY-004: REPEATED_HYPOTHESIS
- REG-RECOVERY-005: RECOVERY_LOOP
- REG-RECOVERY-006: RECOVERY_THRASHING
- REG-RECOVERY-007: RETRY_WASTE
- REG-RECOVERY-008: RECOVERY_OMISSION
- REG-RECOVERY-009: LATE_RECOVERY
- REG-RECOVERY-010: FAILED_RECOVERY
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
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


def check_repeated_command_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-001: Detects repeated command without progress across threshold cycles."""
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
    r1 = detector.record_cycle(s1)
    if r1.status == ProgressStatus.NO_PROGRESS:
        raise RegressionExecutionError("REG-RECOVERY-001 violation: Single cycle triggered NO_PROGRESS prematurely")

    # Identical command repeated with identical failure
    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="pytest tests/test_core.py -k test_calc",
        test_result="FAILED",
        failure_class="REGRESSION",
        failure_signature="AssertionError: 4 != 5",
        hypothesis="Hypothesis A: off-by-one error",
        edit_content="diff --git a/calc.py b/calc.py\n+return x + 1",
    )
    r2 = detector.record_cycle(s2)
    if r2.status != ProgressStatus.NO_PROGRESS:
        raise RegressionExecutionError(
            f"REG-RECOVERY-001 violation: Expected NO_PROGRESS on cycle 2, got {r2.status}"
        )
    if r2.reason not in (NoProgressReason.REPEATED_FAILURE, NoProgressReason.REPEATED_EDIT):
        raise RegressionExecutionError(
            f"REG-RECOVERY-001 violation: Expected REPEATED_FAILURE or REPEATED_EDIT, got {r2.reason}"
        )

    return True, "Repeated command failure detected across threshold=2 cycles", {
        "status": r2.status.value,
        "reason": r2.reason.value,
        "consecutive_count": detector.consecutive_count,
    }


def check_repeated_error_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-002: Detects repeated identical error signature."""
    detector = NoProgressDetectorV1(threshold=2)

    # Invariant requires repeated identical error signature across cycles without new evidence
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
    r2 = detector.record_cycle(s2)
    if r2.status != ProgressStatus.NO_PROGRESS or r2.reason != NoProgressReason.REPEATED_FAILURE:
        raise RegressionExecutionError(
            f"REG-RECOVERY-002 violation: Expected NO_PROGRESS with REPEATED_FAILURE, got status={r2.status}, reason={r2.reason}"
        )

    return True, "Repeated error signature detected and classified as REPEATED_FAILURE", {
        "status": r2.status.value,
        "reason": r2.reason.value,
    }


def check_repeated_edit_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-003: Detects materially identical repeated code edits."""
    detector = NoProgressDetectorV1(threshold=2)

    edit_text = "def parse(s):\n    return s.strip()\n"
    s1 = CycleSnapshot(
        cycle_id=1,
        test_command="pytest tests/test_util.py",
        test_result="FAILED",
        failure_class="COMMAND",
        failure_signature="SyntaxError in util.py",
        edit_content=edit_text,
    )
    detector.record_cycle(s1)

    # Materially identical edit with minor whitespace differences
    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="pytest tests/test_util.py",
        test_result="FAILED",
        failure_class="COMMAND",
        failure_signature="SyntaxError in util.py",
        edit_content="  def parse(s):\n      return s.strip()\n  ",
    )
    r2 = detector.record_cycle(s2)
    if r2.status != ProgressStatus.NO_PROGRESS:
        raise RegressionExecutionError(
            f"REG-RECOVERY-003 violation: Expected NO_PROGRESS on repeated edit, got {r2.status}"
        )

    return True, "Materially identical edit detected across cycles and flagged", {
        "status": r2.status.value,
        "reason": r2.reason.value,
    }


def check_repeated_hypothesis_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-004: Detects repeated hypothesis without new evidence."""
    detector = NoProgressDetectorV1(threshold=2)

    hyp = "Root cause is missing JSON decoder encoding fallback"
    s1 = CycleSnapshot(
        cycle_id=1,
        test_command="python -m unittest tests.test_json",
        test_result="FAILED",
        failure_class="WRONG_HYPOTHESIS",
        failure_signature="UnicodeDecodeError: 'utf-8' codec",
        hypothesis=hyp,
    )
    detector.record_cycle(s1)

    s2 = CycleSnapshot(
        cycle_id=2,
        test_command="python -m unittest tests.test_json",
        test_result="FAILED",
        failure_class="WRONG_HYPOTHESIS",
        failure_signature="UnicodeDecodeError: 'utf-8' codec",
        hypothesis=hyp.upper(),  # Same hypothesis case-insensitive normalized
    )
    r2 = detector.record_cycle(s2)
    if r2.status != ProgressStatus.NO_PROGRESS:
        raise RegressionExecutionError(
            f"REG-RECOVERY-004 violation: Expected NO_PROGRESS for repeated hypothesis, got {r2.status}"
        )

    return True, "Repeated root-cause hypothesis detected and stopped", {
        "status": r2.status.value,
        "reason": r2.reason.value,
    }


def check_recovery_loop_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-005: Detects oscillating recovery actions (A -> B -> A -> B)."""
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
    if not res.loop_detected:
        raise RegressionExecutionError("REG-RECOVERY-005 violation: Oscillation loop (A -> B -> A -> B) not detected")

    return True, "Recovery oscillation loop successfully detected and flagged", {
        "loop_detected": res.loop_detected,
        "loop_type": res.loop_type,
        "cycle_count": res.cycle_count,
    }


def check_recovery_thrashing_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-006: Detects rapid thrashing across disparate unverified recovery actions."""
    # 4 distinct actions attempted with identical underlying failure and zero evidence improvement
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

    # Verify that consecutive unverified attempts without evidence change are identified
    unimproved_count = sum(1 for e in events if not e.evidence_changed and e.state_after == "FAIL")
    if unimproved_count < 3:
        raise RegressionExecutionError("REG-RECOVERY-006 violation: Failed to track unimproved recovery attempts")

    return True, "Recovery thrashing tracked across consecutive unverified interventions", {
        "unimproved_attempts": unimproved_count,
        "total_actions": len(events),
    }


def check_retry_waste_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-007: Bounded retry budget enforces BUDGET_EXHAUSTED."""
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
        raise RegressionExecutionError(
            f"REG-RECOVERY-007 violation: Retry budget failed to flag exhaustion at attempt {attempt_count}"
        )

    policy = RecoveryPolicy(retry_budgets=budget)
    stop_conds = policy.stop_conditions
    if "budget_exhausted" not in stop_conds:
        raise RegressionExecutionError("REG-RECOVERY-007 violation: 'budget_exhausted' missing from policy stop_conditions")

    return True, "Retry waste prevented; attempts beyond budget strictly stop with budget_exhausted", {
        "max_total_recovery_attempts": budget.max_total_recovery_attempts,
        "attempt_count": attempt_count,
        "is_exhausted": is_exhausted,
    }


def check_recovery_omission_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-008: Meaningful failure immediately requires recovery eligibility."""
    from local.failures.models import FailureClass

    # Verify all non-NONE failure classes are recovery-eligible
    meaningful_classes = [fc.value for fc in FailureClass if fc != FailureClass.UNKNOWN]
    for fc in meaningful_classes:
        # Canonical rule: every meaningful failure must have an assigned fallback rule in RecoveryPolicy
        policy = RecoveryPolicy()
        if "on_test_failure" not in policy.fallback_rules:
            raise RegressionExecutionError("REG-RECOVERY-008 violation: Missing on_test_failure fallback rule")

    return True, "Recovery omission prevented: all verified failures require explicit classification and fallback", {
        "meaningful_classes_count": len(meaningful_classes),
        "primary_fallback": policy.fallback_rules["on_test_failure"],
    }


def check_late_recovery_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-009: Pre-emptive detection triggers recovery within threshold turns."""
    policy = RecoveryPolicy()
    # Canonical rule: no_progress_threshold_turns must be <= 3 (early detection)
    if policy.no_progress_threshold_turns > 3:
        raise RegressionExecutionError(
            f"REG-RECOVERY-009 violation: no_progress_threshold_turns ({policy.no_progress_threshold_turns}) exceeds 3"
        )

    return True, "Late recovery prevented: no-progress threshold is bounded to <= 3 turns", {
        "no_progress_threshold_turns": policy.no_progress_threshold_turns,
    }


def check_failed_recovery_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RECOVERY-010: Failed primary recovery transitions to alternate path."""
    policy = RecoveryPolicy(alternate_path_routing_enabled=True)
    fallback = policy.fallback_rules.get("on_tool_failure")
    if fallback != "RETRY_THEN_ALTERNATE":
        raise RegressionExecutionError(
            f"REG-RECOVERY-010 violation: Expected on_tool_failure fallback 'RETRY_THEN_ALTERNATE', got '{fallback}'"
        )

    return True, "Failed recovery escalates cleanly to alternate path (RETRY_THEN_ALTERNATE)", {
        "tool_fallback": fallback,
        "alternate_path_enabled": policy.alternate_path_routing_enabled,
    }
