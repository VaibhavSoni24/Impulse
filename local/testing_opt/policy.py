"""Canonical Testing Strategy Policy Definitions (Stage 34 Sections 4, 5-8, 10).

Defines canonical configurations for:
- T0: Minimal Targeted Test (baseline)
- T1: Targeted + Adjacent Tests
- T2: Targeted + Subsystem + Full when Feasible
- T3: Adaptive Escalation based on Failure Risk
"""

from __future__ import annotations

from typing import Union

from local.testing_opt.models import TestPolicy, TestingStrategyVariant


def build_t0_targeted_policy() -> TestPolicy:
    """Builds canonical T0 Baseline policy: minimal targeted test execution only."""
    return TestPolicy(
        variant=TestingStrategyVariant.T0.value,
        candidate_id="T0",
        targeted_enabled=True,
        adjacent_enabled=False,
        subsystem_enabled=False,
        full_suite_enabled=False,
        adaptive_enabled=False,
        max_test_commands=2,
        max_test_cases=20,
        runtime_budget_seconds=120.0,
        full_suite_feasibility_rules={
            "max_estimated_runtime_seconds": 120.0,
            "max_suite_test_count": 200,
            "require_stable_env": True,
        },
        escalation_rules={
            "escalate_on_targeted_failure": False,
            "escalate_on_high_risk": False,
            "escalate_on_adjacent_regression": False,
        },
        stop_rules={
            "stop_on_targeted_pass_if_low_risk": True,
            "stop_on_adjacent_pass_if_no_regressions": True,
            "stop_on_budget_exhaustion": True,
        },
        fallback_rules={
            "on_targeted_not_found": "BROADER_DISCOVERY",
            "on_command_launch_error": "FALLBACK_RUNNER",
            "on_full_suite_infeasible": "STOP_AT_SUBSYSTEM",
            "on_framework_unavailable": "CLASSIFY_INFRASTRUCTURE",
        },
    )


def build_t1_adjacent_policy() -> TestPolicy:
    """Builds canonical T1 policy: targeted + adjacent test execution."""
    return TestPolicy(
        variant=TestingStrategyVariant.T1.value,
        candidate_id="T1",
        targeted_enabled=True,
        adjacent_enabled=True,
        subsystem_enabled=False,
        full_suite_enabled=False,
        adaptive_enabled=False,
        max_test_commands=4,
        max_test_cases=40,
        runtime_budget_seconds=180.0,
        full_suite_feasibility_rules={
            "max_estimated_runtime_seconds": 120.0,
            "max_suite_test_count": 200,
            "require_stable_env": True,
        },
        escalation_rules={
            "escalate_on_targeted_failure": True,
            "escalate_on_high_risk": False,
            "escalate_on_adjacent_regression": False,
        },
        stop_rules={
            "stop_on_targeted_pass_if_low_risk": False,
            "stop_on_adjacent_pass_if_no_regressions": True,
            "stop_on_budget_exhaustion": True,
        },
        fallback_rules={
            "on_targeted_not_found": "BROADER_DISCOVERY",
            "on_command_launch_error": "FALLBACK_RUNNER",
            "on_full_suite_infeasible": "STOP_AT_SUBSYSTEM",
            "on_framework_unavailable": "CLASSIFY_INFRASTRUCTURE",
        },
    )


def build_t2_subsystem_full_policy(
    max_full_suite_runtime_sec: Optional[float] = None,
) -> TestPolicy:
    """Builds canonical T2 policy: targeted + subsystem + full suite when feasible."""
    max_rt = max_full_suite_runtime_sec if max_full_suite_runtime_sec is not None else 120.0
    return TestPolicy(
        variant=TestingStrategyVariant.T2.value,
        candidate_id="T2",
        targeted_enabled=True,
        adjacent_enabled=True,
        subsystem_enabled=True,
        full_suite_enabled=True,
        adaptive_enabled=False,
        max_test_commands=6,
        max_test_cases=80,
        runtime_budget_seconds=300.0,
        full_suite_feasibility_rules={
            "max_estimated_runtime_seconds": max_rt,
            "max_suite_test_count": 200,
            "require_stable_env": True,
        },
        escalation_rules={
            "escalate_on_targeted_failure": True,
            "escalate_on_high_risk": True,
            "escalate_on_adjacent_regression": True,
        },
        stop_rules={
            "stop_on_targeted_pass_if_low_risk": False,
            "stop_on_adjacent_pass_if_no_regressions": False,
            "stop_on_budget_exhaustion": True,
        },
        fallback_rules={
            "on_targeted_not_found": "BROADER_DISCOVERY",
            "on_command_launch_error": "FALLBACK_RUNNER",
            "on_full_suite_infeasible": "STOP_AT_SUBSYSTEM",
            "on_framework_unavailable": "CLASSIFY_INFRASTRUCTURE",
        },
    )


def build_t3_adaptive_policy() -> TestPolicy:
    """Builds canonical T3 policy: dynamic adaptive escalation based on failure risk."""
    return TestPolicy(
        variant=TestingStrategyVariant.T3.value,
        candidate_id="T3",
        targeted_enabled=True,
        adjacent_enabled=True,
        subsystem_enabled=True,
        full_suite_enabled=True,
        adaptive_enabled=True,
        max_test_commands=6,
        max_test_cases=80,
        runtime_budget_seconds=300.0,
        full_suite_feasibility_rules={
            "max_estimated_runtime_seconds": 120.0,
            "max_suite_test_count": 200,
            "require_stable_env": True,
        },
        escalation_rules={
            "escalate_on_targeted_failure": True,
            "escalate_on_high_risk": True,
            "escalate_on_adjacent_regression": True,
            "escalate_on_incomplete_fix": True,
        },
        stop_rules={
            "stop_on_targeted_pass_if_low_risk": True,
            "stop_on_adjacent_pass_if_no_regressions": True,
            "stop_on_budget_exhaustion": True,
        },
        fallback_rules={
            "on_targeted_not_found": "BROADER_DISCOVERY",
            "on_command_launch_error": "FALLBACK_RUNNER",
            "on_full_suite_infeasible": "STOP_AT_SUBSYSTEM",
            "on_framework_unavailable": "CLASSIFY_INFRASTRUCTURE",
        },
    )


def get_canonical_testing_policy(variant: Union[TestingStrategyVariant, str]) -> TestPolicy:
    """Retrieves the canonical policy instance for a given variant name or enum."""
    val = variant.value if isinstance(variant, TestingStrategyVariant) else str(variant).upper()
    if val == TestingStrategyVariant.T0.value:
        return build_t0_targeted_policy()
    elif val == TestingStrategyVariant.T1.value:
        return build_t1_adjacent_policy()
    elif val == TestingStrategyVariant.T2.value:
        return build_t2_subsystem_full_policy()
    elif val == TestingStrategyVariant.T3.value:
        return build_t3_adaptive_policy()
    raise ValueError(f"Unknown testing strategy variant: {variant}")
