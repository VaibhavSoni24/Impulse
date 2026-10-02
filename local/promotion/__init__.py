"""Stage 44 Candidate Promotion Gate Subsystem.

Provides:
- 5-dimensional deterministic promotion evaluation gate
- Non-collapsing gate decisions (PROMOTE, REJECT, BLOCKED)
- Fail-closed promotion action with zero bypass tolerance
- Machine-readable decision records and audit logging
"""

from __future__ import annotations

from typing import Optional

from local.promotion.errors import (
    BaselineNotFoundError,
    CandidateNotFoundError,
    ForbiddenBypassError,
    InvalidCurrentBestError,
    MultiDimensionConfoundingError,
    PromotionError,
    PromotionGateFailureError,
    UnverifiedCandidateError,
)
from local.promotion.comparison import (
    compare_held_out,
    compare_validation,
    resolve_primary_metric,
)
from local.promotion.config import evaluate_configuration
from local.promotion.gate import PROMOTION_GATE_VERSION, PromotionGate
from local.promotion.models import (
    ConfigurationEvaluationResult,
    CurrentBestValidationResult,
    EvidenceMode,
    GateDecision,
    GateDimensionStatus,
    HeldOutComparisonResult,
    MetricDirection,
    PromotionEvaluationRecord,
    ReproducibilityEvaluationResult,
    RuntimeEvaluationResult,
    TaskPairOutcome,
    ValidationComparisonResult,
)
from local.promotion.reproducibility import evaluate_reproducibility
from local.promotion.runtime import evaluate_runtime


def evaluate_promotion(
    candidate_id: str,
    baseline_id: Optional[str] = None,
) -> PromotionEvaluationRecord:
    """Convenience functional wrapper to evaluate promotion for a candidate."""
    gate = PromotionGate()
    return gate.evaluate(candidate_id=candidate_id, baseline_id=baseline_id)


def promote_candidate(
    candidate_id: str,
    baseline_id: Optional[str] = None,
    actor: str = "IMPULSE-Gate",
    notes: str = "",
) -> PromotionEvaluationRecord:
    """Convenience functional wrapper to promote a candidate fail-closed."""
    gate = PromotionGate()
    return gate.promote_candidate(candidate_id=candidate_id, baseline_id=baseline_id, actor=actor, notes=notes)


def reject_candidate(
    candidate_id: str,
    baseline_id: Optional[str] = None,
    actor: str = "IMPULSE-Gate",
    reason: str = "",
) -> PromotionEvaluationRecord:
    """Convenience functional wrapper to reject a candidate."""
    gate = PromotionGate()
    return gate.reject_candidate(candidate_id=candidate_id, baseline_id=baseline_id, actor=actor, reason=reason)


def explain_promotion(candidate_id: str) -> str:
    """Convenience functional wrapper to explain promotion decision."""
    gate = PromotionGate()
    return gate.explain_promotion(candidate_id=candidate_id)


__all__ = [
    "PROMOTION_GATE_VERSION",
    "PromotionGate",
    "GateDimensionStatus",
    "GateDecision",
    "MetricDirection",
    "EvidenceMode",
    "PromotionEvaluationRecord",
    "ValidationComparisonResult",
    "HeldOutComparisonResult",
    "RuntimeEvaluationResult",
    "ConfigurationEvaluationResult",
    "ReproducibilityEvaluationResult",
    "CurrentBestValidationResult",
    "TaskPairOutcome",
    "PromotionError",
    "CandidateNotFoundError",
    "BaselineNotFoundError",
    "PromotionGateFailureError",
    "InvalidCurrentBestError",
    "ForbiddenBypassError",
    "MultiDimensionConfoundingError",
    "UnverifiedCandidateError",
    "evaluate_promotion",
    "promote_candidate",
    "reject_candidate",
    "explain_promotion",
    "compare_validation",
    "compare_held_out",
    "evaluate_runtime",
    "evaluate_configuration",
    "evaluate_reproducibility",
    "resolve_primary_metric",
]
