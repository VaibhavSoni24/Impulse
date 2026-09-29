"""Data models and enums for the Failure-Driven Development (FDD) Loop (Stage 31).

Defines:
- FDDState: Finite state machine lifecycle
- FailureRecord: Normalized internal failure representation
- FailureCluster: Deterministic grouping of failure modes
- InterventionScope: Constrained intervention dimension
- Intervention: Single hypothesis-driven change record
- PromotionDecision: Outcome of evaluation gating
- FDDRunDelta: Targeted vs collateral delta analysis
- FDDExperimentManifest: Complete reproducibility manifest
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FDDState(str, Enum):
    """Finite state machine states for the FDD loop (Section 10)."""

    IDLE = "IDLE"
    BENCHMARK_COLLECTED = "BENCHMARK_COLLECTED"
    FAILURES_NORMALIZED = "FAILURES_NORMALIZED"
    FAILURES_CLUSTERED = "FAILURES_CLUSTERED"
    CLUSTER_SELECTED = "CLUSTER_SELECTED"
    INTERVENTION_FORMED = "INTERVENTION_FORMED"
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    SMOKE_TESTED = "SMOKE_TESTED"
    VALIDATED = "VALIDATED"
    HELD_OUT_CHECKED = "HELD_OUT_CHECKED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    NO_ACTIONABLE_FAILURES = "NO_ACTIONABLE_FAILURES"
    INFRASTRUCTURE_BLOCKED = "INFRASTRUCTURE_BLOCKED"
    EVALUATION_ERROR = "EVALUATION_ERROR"


class InterventionScope(str, Enum):
    """Single major dimension allowed for one intervention (Section 7)."""

    PROMPT = "PROMPT"
    RETRIEVAL = "RETRIEVAL"
    TESTING = "TESTING"
    RECOVERY = "RECOVERY"
    TOPOLOGY = "TOPOLOGY"
    SKILL = "SKILL"


class PromotionDecision(str, Enum):
    """Authoritative outcome of the promotion gate (Section 12)."""

    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED_INFRASTRUCTURE = "BLOCKED_INFRASTRUCTURE"
    NO_ACTIONABLE_DATA = "NO_ACTIONABLE_DATA"


@dataclass
class FailureRecord:
    """Normalized internal representation for failure-driven analysis (Section 4).

    Preserves raw evidence pointers and maintains distinction between cognitive
    and infrastructure-unavailable runs.
    """

    run_id: str
    candidate_id: str
    task_id: str
    split: str = "dev"
    repository: str = ""
    evidence_mode: str = "UNAVAILABLE"
    run_status: str = "UNKNOWN"
    success: Optional[bool] = None  # None indicates unexecuted or unavailable
    failure_category: str = "UNKNOWN"
    failure_stage: str = "UNKNOWN"
    termination_reason: str = ""
    runtime_seconds: Optional[float] = None
    tool_calls: Optional[int] = None
    turns: Optional[int] = None
    files_changed: Optional[int] = None
    diff_lines: Optional[int] = None
    recovery_triggered: Optional[bool] = None
    recovery_success: Optional[bool] = None
    evaluator_stage: Optional[str] = None
    source_record_reference: str = ""
    is_actionable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureCluster:
    """Deterministic cluster of failure modes with evidence references (Section 5)."""

    cluster_id: str
    signature: str
    failure_category: str
    failure_stage: str
    termination_reason_sample: str
    affected_runs_count: int
    unique_tasks_count: int
    eligible_completed_run_count: int
    evidence_modes: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    splits: list[str] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    representative_failure: Optional[dict[str, Any]] = None
    is_actionable: bool = False
    actionability_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Intervention:
    """Typed specification for exactly ONE causal intervention (Section 7)."""

    intervention_id: str
    source_cluster_id: Optional[str]
    target_failure_mode: str
    hypothesis: str
    expected_behavior_change: str
    intervention_scope: str
    changed_dimensions: list[str]
    affected_files: list[str]
    baseline_candidate: str
    candidate_id: str
    smoke_tasks: list[str] = field(default_factory=list)
    validation_split: str = "validation"
    held_out_policy: str = "WHEN_PROMISING"
    success_metric: str = "target_failure_reduction"
    rejection_condition: str = "collateral_regression_or_target_failure_increase"
    status: str = "PROPOSED"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FDDRunDelta:
    """Targeted failure reduction vs. collateral effects comparison (Section 13 & 14)."""

    target_failure_mode: str
    baseline_failure_count: Optional[int] = None
    candidate_failure_count: Optional[int] = None
    targeted_reduction: Optional[int] = None
    baseline_pass_rate: Optional[float] = None
    candidate_pass_rate: Optional[float] = None
    pass_rate_delta: Optional[float] = None
    baseline_runtime_mean: Optional[float] = None
    candidate_runtime_mean: Optional[float] = None
    baseline_tool_calls_mean: Optional[float] = None
    candidate_tool_calls_mean: Optional[float] = None
    collateral_regressions: dict[str, int] = field(default_factory=dict)
    collateral_improvements: dict[str, int] = field(default_factory=dict)
    held_out_pass_rate_baseline: Optional[float] = None
    held_out_pass_rate_candidate: Optional[float] = None
    held_out_regression: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FDDExperimentManifest:
    """Complete reproducibility manifest for an FDD loop iteration (Section 15)."""

    experiment_id: str
    intervention_id: str
    baseline_candidate: str
    candidate_id: str
    target_failure_mode: str
    state: FDDState = FDDState.IDLE
    decision: PromotionDecision = PromotionDecision.NO_ACTIONABLE_DATA
    decision_rationale: str = ""
    evidence_mode: str = "UNAVAILABLE"
    cluster_id: Optional[str] = None
    split_manifest_sha256: str = ""
    held_out_lock_sha256: str = ""
    git_commit: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    smoke_passed: Optional[bool] = None
    validation_passed: Optional[bool] = None
    held_out_passed: Optional[bool] = None
    run_delta: Optional[FDDRunDelta] = None
    artifact_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value if isinstance(self.state, FDDState) else str(self.state)
        res["decision"] = self.decision.value if isinstance(self.decision, PromotionDecision) else str(self.decision)
        return res
