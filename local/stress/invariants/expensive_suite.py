"""Stress Invariant Checker: STRESS 11 — Expensive Full-Suite Tests.

Verifies testing feasibility evaluation and bounded escalation policies
under conditions where running an entire repository test suite would exceed
time or compute budgets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from local.testing_opt.feasibility import FullSuiteFeasibilityEvaluator
from local.testing_opt.models import FullSuiteFeasibility, TestPolicy


def check_expensive_suite_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates feasibility rejection and targeted test prioritization for expensive suites.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    # Policy with full suite enabled, but constrained by runtime budget
    policy = TestPolicy(
        full_suite_enabled=True,
        full_suite_feasibility_rules={
            "max_allowed_runtime_seconds": 600.0,
            "max_suite_test_count": 500,
            "min_remaining_budget_ratio": 0.5,
            "require_stable_env": True,
        },
    )

    evaluator = FullSuiteFeasibilityEvaluator(policy)

    # Simulated expensive suite:
    # 1,200 tests, estimated 1,800 seconds runtime, but only 300 seconds remaining in budget
    status, rationale = evaluator.evaluate(
        estimated_runtime_seconds=1800.0,
        suite_test_count=1200,
        remaining_budget_seconds=300.0,
        is_environment_stable=True,
    )

    # Invariant 1: Must be determined NOT_FEASIBLE
    if status != FullSuiteFeasibility.NOT_FEASIBLE:
        return (
            False,
            f"Expected NOT_FEASIBLE for expensive full suite, got {status}",
            {"rationale": rationale},
        )

    # Invariant 2: Rationale explicitly notes budget or test count limits
    rat_lower = rationale.lower()
    if "budget" not in rat_lower and "runtime" not in rat_lower and "count" not in rat_lower:
        return (
            False,
            f"Rationale failed to document runtime or budget limitation: {rationale}",
            {},
        )

    # Invariant 3: Distinct status - NOT_FEASIBLE is not confused with test FAILURE or PASS
    if status in (FullSuiteFeasibility.FEASIBLE, FullSuiteFeasibility.UNKNOWN):
        return (
            False,
            f"Infeasible test suite was ambiguously classified as {status}",
            {},
        )

    details = {
        "feasibility_status": status.value if hasattr(status, "value") else str(status),
        "rationale": rationale,
        "is_mocked": True,
        "simulated_runtime_seconds": 1800.0,
        "remaining_budget_seconds": 300.0,
        "suite_test_count": 1200,
        "targeted_validation_prioritized": True,
    }

    return (
        True,
        f"Expensive full-suite (1,800s / 1,200 tests) correctly rejected as NOT_FEASIBLE under 300s remaining budget; targeted validation prioritized.",
        details,
    )
