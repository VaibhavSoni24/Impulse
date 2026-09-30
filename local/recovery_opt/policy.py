"""Canonical Recovery Policy Definitions (Stage 35 Sections 14, 20, 21, 38).

Defines canonical configurations for:
- REC0: Baseline matching Stage 20 canonical recovery paths
- REC1: Proactive early detection & rapid fallback
- REC2: Alternate path routing on repeated failure
- REC3: Adaptive loop guard & bounded retries
"""

from __future__ import annotations

from typing import Union

from local.recovery_opt.models import RecoveryPolicy, RecoveryVariant, RetryBudgetConfig


def build_rec0_baseline_policy() -> RecoveryPolicy:
    """Builds canonical REC0 Baseline policy matching Stage 20 canonical recovery paths."""
    return RecoveryPolicy(
        variant=RecoveryVariant.REC0.value,
        candidate_id="REC0",
        retry_budgets=RetryBudgetConfig(
            max_same_action_retries=2,
            max_total_recovery_attempts=4,
            max_alternate_paths=1,
            max_recovery_runtime_seconds=120.0,
            max_recovery_tool_calls=8,
        ),
        early_detection_enabled=False,
        loop_guard_enabled=False,
        alternate_path_routing_enabled=False,
        no_progress_threshold_turns=3,
        triggers={
            "budget_pressure_remaining_tools": 10,
            "budget_pressure_remaining_seconds": 300.0,
            "test_failure_escalate_attempts": 2,
            "bad_edit_max_attempts": 2,
            "search_fallback_max_attempts": 5,
        },
        actions={
            "bad_edit_safe_ownership_only": True,
            "allow_revert": True,
            "allow_alternate_tool": True,
            "allow_stack_inspection": True,
        },
        fallback_rules={
            "on_tool_failure": "RETRY_THEN_ALTERNATE",
            "on_test_failure": "CLASSIFY_THEN_INSPECT",
            "on_bad_edit": "REPAIR_OR_REVERT",
            "on_search_exhaustion": "EXACT_THEN_TREE_THEN_GRAPH",
            "on_budget_pressure": "TARGETED_VALIDATION_THEN_REVIEW",
        },
        stop_conditions=[
            "budget_exhausted",
            "loop_detected",
            "path_exhausted",
            "target_state_recovered",
        ],
        prompt_instruction=None,
    )


def build_rec1_early_detection_policy() -> RecoveryPolicy:
    """Builds canonical REC1 policy: proactive early detection & rapid fallback."""
    return RecoveryPolicy(
        variant=RecoveryVariant.REC1.value,
        candidate_id="REC1",
        retry_budgets=RetryBudgetConfig(
            max_same_action_retries=1,
            max_total_recovery_attempts=4,
            max_alternate_paths=2,
            max_recovery_runtime_seconds=120.0,
            max_recovery_tool_calls=8,
        ),
        early_detection_enabled=True,
        loop_guard_enabled=False,
        alternate_path_routing_enabled=False,
        no_progress_threshold_turns=1,
        triggers={
            "budget_pressure_remaining_tools": 10,
            "budget_pressure_remaining_seconds": 300.0,
            "test_failure_escalate_attempts": 1,
            "bad_edit_max_attempts": 1,
            "search_fallback_max_attempts": 3,
            "early_detection_on_first_error": True,
        },
        actions={
            "bad_edit_safe_ownership_only": True,
            "allow_revert": True,
            "allow_alternate_tool": True,
            "allow_stack_inspection": True,
            "early_diff_inspection": True,
        },
        fallback_rules={
            "on_tool_failure": "IMMEDIATE_FALLBACK_ALTERNATE",
            "on_test_failure": "FAST_INSPECT_STACK",
            "on_bad_edit": "IMMEDIATE_REVERT",
            "on_search_exhaustion": "EXACT_THEN_TREE",
            "on_budget_pressure": "TARGETED_VALIDATION_THEN_REVIEW",
        },
        stop_conditions=[
            "budget_exhausted",
            "early_detection_exhausted",
            "loop_detected",
            "path_exhausted",
            "target_state_recovered",
        ],
        prompt_instruction=None,
    )


def build_rec2_alternate_path_policy() -> RecoveryPolicy:
    """Builds canonical REC2 policy: alternate path routing on repeated failure."""
    return RecoveryPolicy(
        variant=RecoveryVariant.REC2.value,
        candidate_id="REC2",
        retry_budgets=RetryBudgetConfig(
            max_same_action_retries=1,
            max_total_recovery_attempts=4,
            max_alternate_paths=3,
            max_recovery_runtime_seconds=120.0,
            max_recovery_tool_calls=8,
        ),
        early_detection_enabled=True,
        loop_guard_enabled=False,
        alternate_path_routing_enabled=True,
        no_progress_threshold_turns=1,
        triggers={
            "budget_pressure_remaining_tools": 10,
            "budget_pressure_remaining_seconds": 300.0,
            "test_failure_escalate_attempts": 1,
            "bad_edit_max_attempts": 1,
            "search_fallback_max_attempts": 3,
            "alternate_path_on_failure": True,
        },
        actions={
            "bad_edit_safe_ownership_only": True,
            "allow_revert": True,
            "allow_alternate_tool": True,
            "allow_stack_inspection": True,
            "route_alternate_investigation": True,
        },
        fallback_rules={
            "on_tool_failure": "ALTERNATE_TOOL_ROUTE",
            "on_test_failure": "REVISE_HYPOTHESIS_ALTERNATE_PATH",
            "on_bad_edit": "REVERT_AND_ALTERNATE_APPROACH",
            "on_search_exhaustion": "TREE_THEN_GRAPH_ROUTE",
            "on_budget_pressure": "TARGETED_VALIDATION_THEN_REVIEW",
        },
        stop_conditions=[
            "budget_exhausted",
            "loop_detected",
            "no_alternate_path_available",
            "path_exhausted",
            "target_state_recovered",
        ],
        prompt_instruction=None,
    )


def build_rec3_adaptive_loop_guard_policy() -> RecoveryPolicy:
    """Builds canonical REC3 policy: adaptive loop guard & bounded retries."""
    return RecoveryPolicy(
        variant=RecoveryVariant.REC3.value,
        candidate_id="REC3",
        retry_budgets=RetryBudgetConfig(
            max_same_action_retries=1,
            max_total_recovery_attempts=3,
            max_alternate_paths=2,
            max_recovery_runtime_seconds=100.0,
            max_recovery_tool_calls=6,
        ),
        early_detection_enabled=True,
        loop_guard_enabled=True,
        alternate_path_routing_enabled=True,
        no_progress_threshold_turns=1,
        triggers={
            "budget_pressure_remaining_tools": 8,
            "budget_pressure_remaining_seconds": 250.0,
            "test_failure_escalate_attempts": 1,
            "bad_edit_max_attempts": 1,
            "search_fallback_max_attempts": 2,
            "loop_guard_signature_check": True,
        },
        actions={
            "bad_edit_safe_ownership_only": True,
            "allow_revert": True,
            "allow_alternate_tool": True,
            "allow_stack_inspection": True,
            "suppress_oscillation": True,
            "state_fingerprint_guard": True,
        },
        fallback_rules={
            "on_tool_failure": "ALTERNATE_TOOL_WITH_LOOP_GUARD",
            "on_test_failure": "SAFE_REVISE_OR_TERMINATE",
            "on_bad_edit": "SAFE_REVERT_GUARD",
            "on_search_exhaustion": "BOUNDED_TREE_THEN_STOP",
            "on_budget_pressure": "TARGETED_VALIDATION_THEN_REVIEW",
        },
        stop_conditions=[
            "budget_exhausted",
            "loop_detected",
            "oscillation_detected",
            "path_exhausted",
            "state_unchanged_after_recovery",
            "target_state_recovered",
        ],
        prompt_instruction=None,
    )


def get_canonical_recovery_policy(variant: Union[RecoveryVariant, str]) -> RecoveryPolicy:
    """Retrieves the canonical recovery policy instance for a given variant name or enum."""
    val = variant.value if isinstance(variant, RecoveryVariant) else str(variant).upper()
    if val == RecoveryVariant.REC0.value:
        return build_rec0_baseline_policy()
    elif val == RecoveryVariant.REC1.value:
        return build_rec1_early_detection_policy()
    elif val == RecoveryVariant.REC2.value:
        return build_rec2_alternate_path_policy()
    elif val == RecoveryVariant.REC3.value:
        return build_rec3_adaptive_loop_guard_policy()
    raise ValueError(f"Unknown recovery policy variant: {variant}")
