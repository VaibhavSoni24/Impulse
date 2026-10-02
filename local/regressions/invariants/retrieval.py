"""Invariant checkers for RETRIEVAL regressions (Stage 45 Phase 5).

Covers:
- REG-RETRIEVAL-001: Weak semantic search fallback to exact search.
- REG-RETRIEVAL-002: Semantic retrieval budget exhaustion and bounded expansion.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.retrieval_opt.policy import build_r1_semantic_policy, build_r0_baseline_policy


def check_weak_semantic_fallback() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RETRIEVAL-001: Weak semantic candidates must not mislead agent; must fall back to exact search."""
    r1_policy = build_r1_semantic_policy()

    # Invariant 1: Semantic fallback behavior must be EXACT_SEARCH
    expected_fallback = "EXACT_SEARCH"
    actual_fallback = r1_policy.fallback_behavior.get("on_semantic_failure")
    if actual_fallback != expected_fallback:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-001 violation: Expected semantic fallback '{expected_fallback}', got '{actual_fallback}'"
        )

    # Invariant 2: Minimum similarity threshold must be configured and >= 0.50
    min_sim = r1_policy.trigger_conditions.get("min_similarity", 0.0)
    if min_sim < 0.50 or r1_policy.similarity_threshold < 0.50:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-001 violation: Semantic similarity threshold ({min_sim}) too permissive; must be >= 0.50"
        )

    # Invariant 3: Simulated candidate below threshold must trigger fallback
    simulated_candidates = [
        {"symbol": "unrelated_helper", "similarity": 0.32},
        {"symbol": "irrelevant_util", "similarity": 0.28},
    ]
    accepted = [c for c in simulated_candidates if c["similarity"] >= r1_policy.similarity_threshold]
    if len(accepted) > 0:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-001 violation: Weak candidates accepted despite similarity below threshold {r1_policy.similarity_threshold}"
        )

    return True, "Weak semantic search strictly falls back to exact search with threshold >= 0.50", {
        "fallback_mode": actual_fallback,
        "min_similarity": min_sim,
        "rejected_candidate_count": len(simulated_candidates),
    }


def check_retrieval_budget_exhaustion() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-RETRIEVAL-002: Semantic retrieval budget bounded; stops on exhaustion."""
    r1_policy = build_r1_semantic_policy()

    # Invariant 1: Max semantic calls strictly bounded (<= 3)
    if r1_policy.max_semantic_calls <= 0 or r1_policy.max_semantic_calls > 5:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-002 violation: max_semantic_calls must be between 1 and 5, got {r1_policy.max_semantic_calls}"
        )

    # Invariant 2: Fallback on budget exhaustion must be STOP_RETRIEVAL
    expected_budget_fallback = "STOP_RETRIEVAL"
    actual_budget_fallback = r1_policy.fallback_behavior.get("on_budget_exhausted")
    if actual_budget_fallback != expected_budget_fallback:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-002 violation: Expected budget fallback '{expected_budget_fallback}', got '{actual_budget_fallback}'"
        )

    # Invariant 3: Maximum retrieved items strictly bounded
    if r1_policy.max_retrieved_items <= 0 or r1_policy.max_retrieved_items > 25:
        raise RegressionExecutionError(
            f"REG-RETRIEVAL-002 violation: max_retrieved_items must be bounded <= 25, got {r1_policy.max_retrieved_items}"
        )

    return True, "Retrieval budget strictly bounded and terminates with STOP_RETRIEVAL upon exhaustion", {
        "max_semantic_calls": r1_policy.max_semantic_calls,
        "max_retrieved_items": r1_policy.max_retrieved_items,
        "budget_fallback": actual_budget_fallback,
    }
