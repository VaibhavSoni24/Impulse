"""Invariant checker for TESTING regressions (Stage 45 Phase 5).

Covers:
- REG-TESTING-001: Stopping prematurely after first red test without escalation or recovery.
- REG-TESTING-002: Unconstrained whole-repository test sweeps on localized changes.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.testing_opt.feasibility import FullSuiteFeasibilityEvaluator
from local.testing_opt.models import FullSuiteFeasibility
from local.testing_opt.policy import (
    build_t0_targeted_policy,
    build_t1_adjacent_policy,
    build_t2_subsystem_full_policy,
)


def check_stop_after_first_red_test() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-TESTING-001: Policy forbids premature stopping on first red test; mandates escalation."""
    t1_policy = build_t1_adjacent_policy()

    # Invariant 1: Escalation rule must require escalation on targeted test failure
    escalate_on_fail = t1_policy.escalation_rules.get("escalate_on_targeted_failure", False)
    if not escalate_on_fail:
        raise RegressionExecutionError(
            "REG-TESTING-001 violation: T1 policy must have escalate_on_targeted_failure=True"
        )

    # Invariant 2: Stop rules must not allow stopping on failed test as success
    for stop_rule, val in t1_policy.stop_rules.items():
        if "fail" in stop_rule.lower() and val:
            raise RegressionExecutionError(
                f"REG-TESTING-001 violation: Invalid stop rule allowing stop on failure: {stop_rule}"
            )

    # Invariant 3: T2 policy also enforces escalation on high risk and regressions
    t2_policy = build_t2_subsystem_full_policy()
    if not t2_policy.escalation_rules.get("escalate_on_adjacent_regression", False):
        raise RegressionExecutionError(
            "REG-TESTING-001 violation: T2 policy must escalate on adjacent regression"
        )

    return True, "Policy strictly enforces escalation on test failure; prevents premature stopping on red test", {
        "t1_escalate_on_failure": escalate_on_fail,
        "t2_escalate_on_regression": t2_policy.escalation_rules.get("escalate_on_adjacent_regression"),
    }


def check_unconstrained_repo_sweep() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-TESTING-002: Bounded testing limits prevent unconstrained repository-wide sweeps."""
    t0_policy = build_t0_targeted_policy()

    # Invariant 1: T0 baseline disables full suite execution
    if t0_policy.full_suite_enabled:
        raise RegressionExecutionError("REG-TESTING-002 violation: Full suite must be disabled in T0 baseline")

    # Invariant 2: Execution bounds strictly enforced
    if t0_policy.max_test_commands > 3 or t0_policy.max_test_cases > 30:
        raise RegressionExecutionError(
            f"REG-TESTING-002 violation: T0 execution limits too loose: commands={t0_policy.max_test_commands}, cases={t0_policy.max_test_cases}"
        )

    # Invariant 3: Feasibility evaluator strictly evaluates full suite as NOT_FEASIBLE under T0
    evaluator = FullSuiteFeasibilityEvaluator(t0_policy)
    status, rationale = evaluator.evaluate(estimated_runtime_seconds=60.0, suite_test_count=50)
    if status != FullSuiteFeasibility.NOT_FEASIBLE:
        raise RegressionExecutionError(
            f"REG-TESTING-002 violation: Feasibility evaluator allowed full suite under T0: {status}"
        )

    return True, "Unconstrained repository test sweeps strictly prevented by bounded policy and feasibility rules", {
        "t0_full_suite_enabled": t0_policy.full_suite_enabled,
        "max_test_commands": t0_policy.max_test_commands,
        "max_test_cases": t0_policy.max_test_cases,
        "feasibility_status": status.value,
    }
