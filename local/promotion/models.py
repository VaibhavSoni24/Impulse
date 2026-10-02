"""Data models, enums, and schemas for Stage 44 Candidate Promotion Gate.

Establishes:
- 5 independent promotion gate dimension results (PASS, FAIL, UNKNOWN, NOT_APPLICABLE)
- Authoritative gate decisions (PROMOTE, REJECT, BLOCKED)
- Primary metric definitions and task-paired validation structures
- Held-out, runtime, configuration, and reproducibility records
- Complete JSON-serializable promotion evaluation records
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GateDimensionStatus(str, Enum):
    """Evaluation status for an individual promotion gate dimension."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GateDecision(str, Enum):
    """Authoritative gate promotion decisions."""
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    BLOCKED = "BLOCKED"


class MetricDirection(str, Enum):
    """Optimization direction for evaluation metrics."""
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class EvidenceMode(str, Enum):
    """Evidence grounding classifications."""
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class TaskPairOutcome:
    """Detailed paired contingency table for benchmark validation tasks."""
    baseline_pass_candidate_pass: int = 0
    baseline_pass_candidate_fail: int = 0
    baseline_fail_candidate_pass: int = 0
    baseline_fail_candidate_fail: int = 0
    validation_tasks_total: int = 0
    validation_tasks_changed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationComparisonResult:
    """Evaluation result for validation improvement dimension."""
    dimension_status: str
    primary_metric_name: str
    direction: str
    baseline_value: Optional[float]
    candidate_value: Optional[float]
    delta: Optional[float]
    task_pairs: Optional[TaskPairOutcome]
    evidence_mode: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.task_pairs:
            res["task_pairs"] = self.task_pairs.to_dict()
        return res


@dataclass
class HeldOutComparisonResult:
    """Evaluation result for held-out regression dimension."""
    dimension_status: str
    baseline_result: Optional[float]
    candidate_result: Optional[float]
    regression_count: int
    changed_tasks: int
    evidence_mode: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeEvaluationResult:
    """Evaluation result for runtime acceptability dimension."""
    dimension_status: str
    avg_runtime_ms: Optional[float]
    median_runtime_ms: Optional[float]
    max_runtime_ms: Optional[float]
    budget_limit_ms: Optional[float]
    tool_call_count: Optional[int]
    budget_violated: bool
    evidence_mode: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfigurationEvaluationResult:
    """Evaluation result for configuration validity dimension."""
    dimension_status: str
    submission_valid: bool
    manifest_valid: bool
    model_permitted: bool
    is_multi_dimension: bool
    multi_dimension_allowed: bool
    secrets_found: bool
    missing_files: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReproducibilityEvaluationResult:
    """Evaluation result for behavior reproducibility dimension."""
    dimension_status: str
    git_commit_verified: bool
    manifest_hash_verified: bool
    benchmark_hashes_present: bool
    sampling_settings_present: bool
    compute_environment_present: bool
    single_run_only: bool
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CurrentBestValidationResult:
    """Validation report on current_best.json consistency."""
    valid: bool
    current_best_candidate_id: str
    candidate_status: str
    manifest_verified: bool
    evidence_mode: str
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionEvaluationRecord:
    """Complete machine-readable promotion decision record."""
    candidate_id: str
    baseline_candidate_id: Optional[str]
    decision: str
    timestamp: str
    gate_version: str
    primary_metric: str
    validation_result: Dict[str, Any]
    held_out_result: Dict[str, Any]
    runtime_result: Dict[str, Any]
    configuration_result: Dict[str, Any]
    reproducibility_result: Dict[str, Any]
    overall_result: str
    evidence_mode: str
    reasons: List[str] = field(default_factory=list)
    source_manifests: Dict[str, str] = field(default_factory=dict)
    source_hashes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
