"""Stage 33: Retrieval Optimization Loop for IMPULSE."""

from local.retrieval_opt.models import (
    DynamicRoundTrace,
    RetrievalCandidateManifest,
    RetrievalCostMetrics,
    RetrievalDiagnostics,
    RetrievalEvent,
    RetrievalHypothesis,
    RetrievalPolicy,
    RetrievalQualityMetrics,
    RetrievalTaskPairOutcome,
    RetrievalType,
    RetrievalVariant,
    TaskTransition,
)
from local.retrieval_opt.policy import (
    build_r0_baseline_policy,
    build_r1_semantic_policy,
    build_r2_neighbors_policy,
    build_r3_subgraph_policy,
    build_r4_dynamic_policy,
    get_canonical_policy,
)
from local.retrieval_opt.diff import (
    RetrievalPolicyDiff,
    compute_retrieval_policy_diff,
    render_retrieval_policy_diff_md,
)
from local.retrieval_opt.experiment import RetrievalExperimentManager
from local.retrieval_opt.trace import RetrievalTraceCollector
from local.retrieval_opt.metrics import (
    build_quality_cost_frontier,
    compute_retrieval_cost_metrics,
    compute_retrieval_quality_metrics,
    render_quality_cost_frontier_md,
)
from local.retrieval_opt.paired import (
    compute_retrieval_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
    summarize_paired_outcomes,
)
from local.retrieval_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_TOPOLOGY_ID,
    RetrievalValidationError,
    validate_retrieval_candidate_integrity,
    validate_retrieval_hypothesis,
)

__all__ = [
    "DynamicRoundTrace",
    "RetrievalCandidateManifest",
    "RetrievalCostMetrics",
    "RetrievalDiagnostics",
    "RetrievalEvent",
    "RetrievalHypothesis",
    "RetrievalPolicy",
    "RetrievalQualityMetrics",
    "RetrievalTaskPairOutcome",
    "RetrievalType",
    "RetrievalVariant",
    "TaskTransition",
    "build_r0_baseline_policy",
    "build_r1_semantic_policy",
    "build_r2_neighbors_policy",
    "build_r3_subgraph_policy",
    "build_r4_dynamic_policy",
    "get_canonical_policy",
    "RetrievalPolicyDiff",
    "compute_retrieval_policy_diff",
    "render_retrieval_policy_diff_md",
    "RetrievalExperimentManager",
    "RetrievalTraceCollector",
    "build_quality_cost_frontier",
    "compute_retrieval_cost_metrics",
    "compute_retrieval_quality_metrics",
    "render_quality_cost_frontier_md",
    "compute_retrieval_paired_comparison",
    "save_paired_results_csv",
    "save_paired_results_jsonl",
    "summarize_paired_outcomes",
    "EXPECTED_MODEL_ID",
    "EXPECTED_P0_PROMPT_SHA256",
    "EXPECTED_TOPOLOGY_ID",
    "RetrievalValidationError",
    "validate_retrieval_candidate_integrity",
    "validate_retrieval_hypothesis",
]
