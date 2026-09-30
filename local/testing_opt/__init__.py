"""Stage 34: Testing Strategy Optimization Loop for IMPULSE."""

from local.testing_opt.models import (
    AdaptiveEscalationTrace,
    FullSuiteFeasibility,
    RiskSignal,
    RiskSignalType,
    TestCandidateManifest,
    TestCostMetrics,
    TestDiagnostics,
    TestEvidenceMetrics,
    TestExecutionEvent,
    TestHypothesis,
    TestLevel,
    TestPolicy,
    TestTaskPairOutcome,
    TestingStrategyVariant,
)
from local.testing_opt.policy import (
    build_t0_targeted_policy,
    build_t1_adjacent_policy,
    build_t2_subsystem_full_policy,
    build_t3_adaptive_policy,
    get_canonical_testing_policy,
)
from local.testing_opt.diff import (
    TestPolicyDiff,
    compute_test_policy_diff,
    render_test_policy_diff_md,
)
from local.testing_opt.experiment import TestingExperimentManager
from local.testing_opt.trace import TestTraceCollector
from local.testing_opt.metrics import (
    build_test_quality_cost_frontier,
    compute_test_cost_metrics,
    compute_test_evidence_metrics,
    render_test_quality_cost_frontier_md,
)
from local.testing_opt.paired import (
    compute_test_paired_comparison,
    save_test_paired_results_csv,
    save_test_paired_results_jsonl,
    summarize_test_paired_outcomes,
)
from local.testing_opt.validator import (
    EXPECTED_FROZEN_TEST_SKILL_SHA256,
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
    EXPECTED_TOPOLOGY_ID,
    TestingValidationError,
    validate_testing_candidate_integrity,
    validate_testing_hypothesis,
)
from local.testing_opt.feasibility import (
    FeasibilityEvaluationResult,
    FullSuiteFeasibilityEvaluator,
    evaluate_full_suite_feasibility,
)
from local.testing_opt.risk import (
    AdaptiveDecision,
    AdaptiveEscalationController,
    RiskSignalEvaluator,
)

__all__ = [
    "AdaptiveDecision",
    "AdaptiveEscalationController",
    "AdaptiveEscalationTrace",
    "FeasibilityEvaluationResult",
    "FullSuiteFeasibility",
    "FullSuiteFeasibilityEvaluator",
    "RiskSignal",
    "RiskSignalEvaluator",
    "RiskSignalType",
    "TestCandidateManifest",
    "TestCostMetrics",
    "TestDiagnostics",
    "TestEvidenceMetrics",
    "TestExecutionEvent",
    "TestHypothesis",
    "TestLevel",
    "TestPolicy",
    "TestPolicyDiff",
    "TestTaskPairOutcome",
    "TestTraceCollector",
    "TestingExperimentManager",
    "TestingStrategyVariant",
    "TestingValidationError",
    "build_t0_targeted_policy",
    "build_t1_adjacent_policy",
    "build_t2_subsystem_full_policy",
    "build_t3_adaptive_policy",
    "build_test_quality_cost_frontier",
    "compute_test_cost_metrics",
    "compute_test_evidence_metrics",
    "compute_test_paired_comparison",
    "compute_test_policy_diff",
    "evaluate_full_suite_feasibility",
    "get_canonical_testing_policy",
    "render_test_policy_diff_md",
    "render_test_quality_cost_frontier_md",
    "save_test_paired_results_csv",
    "save_test_paired_results_jsonl",
    "summarize_test_paired_outcomes",
    "validate_testing_candidate_integrity",
    "validate_testing_hypothesis",
    "EXPECTED_FROZEN_TEST_SKILL_SHA256",
    "EXPECTED_MODEL_ID",
    "EXPECTED_P0_PROMPT_SHA256",
    "EXPECTED_RETRIEVAL_R0_POLICY_SHA256",
    "EXPECTED_TOPOLOGY_ID",
]
