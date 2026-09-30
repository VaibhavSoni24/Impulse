"""Full-Suite Execution Feasibility Evaluator (Stage 34 Section 25).

Determines deterministically whether executing the repository full test suite is
FEASIBLE, NOT_FEASIBLE, or UNKNOWN based on explicit budget and environment bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from local.testing_opt.models import FullSuiteFeasibility, TestPolicy


@dataclass(frozen=True)
class FeasibilityEvaluationResult:
    feasibility: FullSuiteFeasibility
    rationale: str


def evaluate_full_suite_feasibility(
    policy: TestPolicy,
    estimated_runtime_seconds: Optional[float] = None,
    suite_test_count: Optional[int] = None,
    remaining_budget_seconds: Optional[float] = None,
    is_environment_stable: Optional[bool] = None,
) -> FeasibilityEvaluationResult:
    """Convenience helper to evaluate full suite feasibility."""
    evaluator = FullSuiteFeasibilityEvaluator(policy)
    status, rationale = evaluator.evaluate(
        estimated_runtime_seconds=estimated_runtime_seconds,
        suite_test_count=suite_test_count,
        remaining_budget_seconds=remaining_budget_seconds,
        is_environment_stable=is_environment_stable,
    )
    return FeasibilityEvaluationResult(feasibility=status, rationale=rationale)


class FullSuiteFeasibilityEvaluator:
    """Evaluates whether running the full test suite is feasible under current policy constraints."""

    def __init__(self, policy: TestPolicy) -> None:
        self.policy = policy
        self.rules = policy.full_suite_feasibility_rules

    def evaluate(
        self,
        estimated_runtime_seconds: Optional[float] = None,
        suite_test_count: Optional[int] = None,
        remaining_budget_seconds: Optional[float] = None,
        is_environment_stable: Optional[bool] = None,
    ) -> tuple[FullSuiteFeasibility, str]:
        """Evaluates feasibility against explicit policy rules.

        Returns:
            (feasibility_status, rationale)
        """
        # If full suite is not enabled by policy at all
        if not self.policy.full_suite_enabled:
            return (
                FullSuiteFeasibility.NOT_FEASIBLE,
                "Full-suite execution disabled by testing strategy policy.",
            )

        # Environment stability check
        require_stable = self.rules.get("require_stable_env", True)
        if require_stable and is_environment_stable is False:
            return (
                FullSuiteFeasibility.NOT_FEASIBLE,
                "Environment unstable; full suite execution aborted for isolation safety.",
            )

        # Check remaining budget
        if remaining_budget_seconds is not None and remaining_budget_seconds <= 0:
            return (
                FullSuiteFeasibility.NOT_FEASIBLE,
                f"Remaining runtime budget ({remaining_budget_seconds:.1f}s) exhausted.",
            )

        # Check estimated runtime
        max_rt = self.rules.get("max_estimated_runtime_seconds", 120.0)
        if estimated_runtime_seconds is not None:
            if estimated_runtime_seconds > max_rt:
                return (
                    FullSuiteFeasibility.NOT_FEASIBLE,
                    f"Estimated runtime ({estimated_runtime_seconds:.1f}s) exceeds policy ceiling ({max_rt:.1f}s).",
                )
            if remaining_budget_seconds is not None and estimated_runtime_seconds > remaining_budget_seconds:
                return (
                    FullSuiteFeasibility.NOT_FEASIBLE,
                    f"Estimated runtime ({estimated_runtime_seconds:.1f}s) exceeds remaining budget ({remaining_budget_seconds:.1f}s).",
                )

        # Check test count
        max_cases = self.rules.get("max_suite_test_count", 200)
        if suite_test_count is not None and suite_test_count > max_cases:
            return (
                FullSuiteFeasibility.NOT_FEASIBLE,
                f"Suite size ({suite_test_count} tests) exceeds policy threshold ({max_cases} tests).",
            )

        # If critical information is completely unknown, return UNKNOWN (never assume feasible)
        if estimated_runtime_seconds is None and suite_test_count is None and remaining_budget_seconds is None:
            return (
                FullSuiteFeasibility.UNKNOWN,
                "Insufficient historical runtime or suite metrics; feasibility cannot be verified.",
            )

        return (
            FullSuiteFeasibility.FEASIBLE,
            "Full suite runtime and size within configured safety limits.",
        )
