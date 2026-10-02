"""Invariant checker for CALLER_INSPECTION / GRAPH regressions (Stage 45 Phase 5).

Covers:
- REG-GRAPH-001: Caller and relational inspection discipline under contract changes.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.graph.controller import NeighborPolicyV1
from local.graph.models import NeighborReconContext


def check_caller_inspection_discipline() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-GRAPH-001: Policy enforces disciplined caller/callee relationship exploration."""
    policy = NeighborPolicyV1()

    # Invariant 1: Approves exploration when symbol is promising and relationships are unresolved
    ctx_needs_caller = NeighborReconContext(
        target_symbol="process_payment_v2",
        is_promising_candidate=True,
        needs_relationship_exploration=True,
        direct_source_sufficient=False,
        phase="localization",
    )
    should_ret, rationale = policy.should_retrieve(ctx_needs_caller)
    if not should_ret:
        raise RegressionExecutionError(
            f"REG-GRAPH-001 violation: Failed to approve relational caller exploration: {rationale}"
        )

    # Invariant 2: Blocks exploration if direct source inspection already explains the defect
    ctx_sufficient = NeighborReconContext(
        target_symbol="process_payment_v2",
        is_promising_candidate=True,
        needs_relationship_exploration=True,
        direct_source_sufficient=True,  # Direct source already sufficient
        phase="localization",
    )
    should_ret_suff, rationale_suff = policy.should_retrieve(ctx_sufficient)
    if should_ret_suff:
        raise RegressionExecutionError(
            "REG-GRAPH-001 violation: Allowed unneeded graph exploration when direct source was sufficient"
        )

    # Invariant 3: Blocks consecutive neighbor calls without intermediate inspection
    ctx_consecutive = NeighborReconContext(
        target_symbol="validate_token",
        is_promising_candidate=True,
        needs_relationship_exploration=True,
        direct_source_sufficient=False,
        last_tool_was_neighbor=True,  # Consecutive call
        phase="localization",
    )
    should_ret_consec, rationale_consec = policy.should_retrieve(ctx_consecutive)
    if should_ret_consec:
        raise RegressionExecutionError(
            "REG-GRAPH-001 violation: Allowed consecutive neighbor calls without intermediate source inspection"
        )

    # Invariant 4: Blocks graph exploration during editing phase
    ctx_edit_phase = NeighborReconContext(
        target_symbol="process_payment_v2",
        is_promising_candidate=True,
        needs_relationship_exploration=True,
        phase="edit",
    )
    should_ret_edit, rationale_edit = policy.should_retrieve(ctx_edit_phase)
    if should_ret_edit:
        raise RegressionExecutionError(
            "REG-GRAPH-001 violation: Allowed graph neighbor exploration outside localization phase"
        )

    return True, "Disciplined caller and relationship exploration enforced without unconstrained expansion", {
        "approved_rationale": rationale,
        "blocked_sufficient_rationale": rationale_suff,
        "blocked_consecutive_rationale": rationale_consec,
        "blocked_edit_phase_rationale": rationale_edit,
    }
