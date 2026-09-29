"""Failure-Driven Development (FDD) Loop Package (Stage 31).

Provides the deterministic, evidence-preserving control loop for failure-driven
candidate optimization:
- Normalization of SQLite & JSONL run records
- Deterministic failure clustering
- Lexicographic cluster prioritization
- Single-dimension intervention specification & validation
- Smoke -> validation -> held-out gating over clean-copy evaluator
- Decision evaluation (PROMOTED, REJECTED, INCONCLUSIVE, NO_ACTIONABLE_DATA)
- Reproducible artifact and manifest generation
"""

from __future__ import annotations

from local.fdd.clustering import cluster_failures, generate_cluster_id
from local.fdd.evaluator import FDDEvaluator
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.interventions import (
    create_candidate_from_baseline,
    load_intervention,
    save_intervention,
    validate_intervention,
)
from local.fdd.loop import FDDLoop, InvalidStateTransitionError
from local.fdd.models import (
    FDDExperimentManifest,
    FDDRunDelta,
    FDDState,
    FailureCluster,
    FailureRecord,
    Intervention,
    InterventionScope,
    PromotionDecision,
)
from local.fdd.normalization import (
    is_infrastructure_failure,
    normalize_failure_record,
    normalize_failures_from_jsonl,
    normalize_failures_from_summaries,
)
from local.fdd.prioritization import select_highest_value_cluster
from local.fdd.reporting import generate_fdd_report, save_fdd_experiment_artifacts

__all__ = [
    "FDDState",
    "InterventionScope",
    "PromotionDecision",
    "FailureRecord",
    "FailureCluster",
    "Intervention",
    "FDDRunDelta",
    "FDDExperimentManifest",
    "normalize_failure_record",
    "normalize_failures_from_summaries",
    "normalize_failures_from_jsonl",
    "is_infrastructure_failure",
    "cluster_failures",
    "generate_cluster_id",
    "select_highest_value_cluster",
    "validate_intervention",
    "save_intervention",
    "load_intervention",
    "create_candidate_from_baseline",
    "compute_run_delta",
    "evaluate_promotion_gate",
    "FDDEvaluator",
    "FDDLoop",
    "InvalidStateTransitionError",
    "generate_fdd_report",
    "save_fdd_experiment_artifacts",
]
