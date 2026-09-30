"""Recovery Optimization Loop Package (IMPULSE Stage 35).

Exports:
- Models: RecoveryPatternType, RecoveryOutcome, RecoveryInterventionType,
  RecoveryStateMachineState, RecoveryVariant, RecoverySelectionStatus,
  TaskRecoveryTransition, RecoveryFailureRecord, RecoveryCluster,
  RetryBudgetConfig, RecoveryPolicy, RecoveryExecutionEvent,
  RecoveryCostMetrics, RecoveryQualityMetrics, RecoveryDiagnostics,
  RecoveryHypothesis, RecoveryTaskPairOutcome, RecoveryCandidateManifest
- Policies: build_rec0_baseline_policy, build_rec1_early_detection_policy,
  build_rec2_alternate_path_policy, build_rec3_adaptive_loop_guard_policy,
  get_canonical_recovery_policy
- Diff: diff_recovery_policies, format_recovery_policy_diff_md
- Mining: RecoveryTraceMiner, normalize_command_str, extract_failure_signature
- Clustering: cluster_recovery_failures, select_highest_value_recovery_cluster
- Earliest Detection: analyze_early_detection, EarlyDetectionReport
- Loop Detector: RecoveryLoopDetector, LoopDetectionResult, is_loop_regression
- Metrics: compute_recovery_cost_metrics, compute_recovery_quality_metrics
- Trace: RecoveryTraceCollector
- Paired: compute_paired_recovery_comparisons, save_paired_results
- Validator: validate_recovery_candidate_integrity, validate_recovery_hypothesis,
  check_candidate_loop_safety, RecoveryValidationError
- Reporting: generate_candidate_report_md, generate_pareto_frontier_md
- Manager: RecoveryExperimentManager
- CLI: run_recovery_cli
"""

from __future__ import annotations

from local.recovery_opt.cli import run_recovery_cli
from local.recovery_opt.clustering import cluster_recovery_failures, select_highest_value_recovery_cluster
from local.recovery_opt.diff import diff_recovery_policies, format_recovery_policy_diff_md
from local.recovery_opt.earliest_detection import EarlyDetectionReport, analyze_early_detection
from local.recovery_opt.experiment import RecoveryExperimentManager
from local.recovery_opt.loop_detector import LoopDetectionResult, RecoveryLoopDetector, is_loop_regression
from local.recovery_opt.metrics import compute_recovery_cost_metrics, compute_recovery_quality_metrics
from local.recovery_opt.mining import RecoveryTraceMiner, extract_failure_signature, normalize_command_str
from local.recovery_opt.models import (
    RecoveryCandidateManifest,
    RecoveryCluster,
    RecoveryCostMetrics,
    RecoveryDiagnostics,
    RecoveryExecutionEvent,
    RecoveryFailureRecord,
    RecoveryHypothesis,
    RecoveryInterventionType,
    RecoveryOutcome,
    RecoveryPatternType,
    RecoveryPolicy,
    RecoveryQualityMetrics,
    RecoverySelectionStatus,
    RecoveryStateMachineState,
    RecoveryTaskPairOutcome,
    RecoveryVariant,
    RetryBudgetConfig,
    TaskRecoveryTransition,
)
from local.recovery_opt.paired import compute_paired_recovery_comparisons, save_paired_results
from local.recovery_opt.policy import (
    build_rec0_baseline_policy,
    build_rec1_early_detection_policy,
    build_rec2_alternate_path_policy,
    build_rec3_adaptive_loop_guard_policy,
    get_canonical_recovery_policy,
)
from local.recovery_opt.reporting import generate_candidate_report_md, generate_pareto_frontier_md
from local.recovery_opt.trace import RecoveryTraceCollector
from local.recovery_opt.validator import (
    RecoveryValidationError,
    check_candidate_loop_safety,
    validate_recovery_candidate_integrity,
    validate_recovery_hypothesis,
)

__all__ = [
    "RecoveryPatternType",
    "RecoveryOutcome",
    "RecoveryInterventionType",
    "RecoveryStateMachineState",
    "RecoveryVariant",
    "RecoverySelectionStatus",
    "TaskRecoveryTransition",
    "RecoveryFailureRecord",
    "RecoveryCluster",
    "RetryBudgetConfig",
    "RecoveryPolicy",
    "RecoveryExecutionEvent",
    "RecoveryCostMetrics",
    "RecoveryQualityMetrics",
    "RecoveryDiagnostics",
    "RecoveryHypothesis",
    "RecoveryTaskPairOutcome",
    "RecoveryCandidateManifest",
    "build_rec0_baseline_policy",
    "build_rec1_early_detection_policy",
    "build_rec2_alternate_path_policy",
    "build_rec3_adaptive_loop_guard_policy",
    "get_canonical_recovery_policy",
    "diff_recovery_policies",
    "format_recovery_policy_diff_md",
    "RecoveryTraceMiner",
    "normalize_command_str",
    "extract_failure_signature",
    "cluster_recovery_failures",
    "select_highest_value_recovery_cluster",
    "analyze_early_detection",
    "EarlyDetectionReport",
    "RecoveryLoopDetector",
    "LoopDetectionResult",
    "is_loop_regression",
    "compute_recovery_cost_metrics",
    "compute_recovery_quality_metrics",
    "RecoveryTraceCollector",
    "compute_paired_recovery_comparisons",
    "save_paired_results",
    "validate_recovery_candidate_integrity",
    "validate_recovery_hypothesis",
    "check_candidate_loop_safety",
    "RecoveryValidationError",
    "generate_candidate_report_md",
    "generate_pareto_frontier_md",
    "RecoveryExperimentManager",
    "run_recovery_cli",
]
