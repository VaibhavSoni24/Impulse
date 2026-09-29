"""Data models and enums for the IMPULSE Failure Dashboard (Stage 30).

Defines normalized run records, evidence modes, metric statistics,
and dashboard reporting models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EvidenceMode(str, Enum):
    """Execution evidence classification (Phase 3 & 18).

    - LIVE: Actual Gemma 4 31B model inference and competition-compatible evaluation.
    - FIXTURE: Synthetic evaluator/agent execution used for local architecture testing.
    - INFRASTRUCTURE_ONLY: Hardware/runtime execution records without model inference.
    - UNAVAILABLE: Environment unavailable for model inference on local host.
    - MIXED: Aggregated view across multiple distinct execution modes.
    """

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"
    MIXED = "MIXED"


class ReportStatus(str, Enum):
    """Overall status of the generated candidate/split report."""

    PASS = "PASS"
    FAIL = "FAIL"
    NO_LIVE_RESULTS = "NO_LIVE_RESULTS"
    NO_RESULTS = "NO_RESULTS"
    FIXTURE_VERIFIED = "FIXTURE_VERIFIED"
    INFRASTRUCTURE_UNAVAILABLE = "INFRASTRUCTURE_UNAVAILABLE"


@dataclass
class RunSummary:
    """Normalized evaluation run record for dashboard aggregation (Phase 4).

    Preserves explicit nulls when values were unobserved.
    """

    run_id: str
    candidate_id: str
    task_id: str
    split_name: str = ""
    split_version: str = "v1"
    repository: str = ""
    task_type: Optional[str] = None  # None indicates unavailable from source
    execution_mode: str = EvidenceMode.UNAVAILABLE.value
    success: Optional[bool] = None  # True (resolved), False (failed), None (unexecuted)
    execution_status: str = "UNKNOWN"
    termination_reason: Optional[str] = None
    failure_class: Optional[str] = None
    failure_stage: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    tool_calls: Optional[int] = None
    turns: Optional[int] = None
    files_changed: Optional[int] = None
    patch_lines: Optional[int] = None
    recovery_triggered: Optional[bool] = None
    recovery_success: Optional[bool] = None
    final_review_status: Optional[str] = None
    patch_apply_status: Optional[str] = None
    verification_status: Optional[str] = None
    clean_copy_verified: Optional[bool] = None
    created_at: str = ""

    def is_eligible(self, target_evidence_mode: Optional[EvidenceMode] = None) -> bool:
        """Determines if this run is eligible for pass-rate evaluation."""
        if target_evidence_mode == EvidenceMode.LIVE:
            return self.execution_mode == EvidenceMode.LIVE.value and self.success is not None
        if target_evidence_mode == EvidenceMode.FIXTURE:
            return self.execution_mode == EvidenceMode.FIXTURE.value and self.success is not None
        # Default: executed runs with a concrete boolean success value
        return self.success is not None

    def to_dict(self) -> dict[str, Any]:
        """Serializes to a clean dictionary."""
        return asdict(self)


@dataclass
class MetricStats:
    """Statistical summary for continuous metrics (runtime, tool calls, turns)."""

    count: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    p95: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean": self.mean,
            "median": self.median,
            "p95": self.p95,
            "min": self.min_val,
            "max": self.max_val,
        }


@dataclass
class RepositoryMetrics:
    """Per-repository performance breakdown."""

    repository: str
    total_tasks: int = 0
    completed_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    unavailable_runs: int = 0
    pass_rate: Optional[float] = None  # None if completed == 0


@dataclass
class TaskTypeMetrics:
    """Per-task-type performance breakdown (if authoritative data exists)."""

    task_type: str
    total_tasks: int = 0
    completed_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    pass_rate: Optional[float] = None
    status: str = "AVAILABLE"
    reason: str = ""


@dataclass
class FailureCategorySummary:
    """Summary of failure categories."""

    category: str
    count: int = 0
    percentage: float = 0.0
    is_evaluator_stage: bool = False


@dataclass
class DashboardReport:
    """Complete aggregated dashboard report for a candidate and split."""

    candidate_id: str
    split_name: str
    split_version: str = "v1"
    evidence_mode: EvidenceMode = EvidenceMode.UNAVAILABLE
    report_status: ReportStatus = ReportStatus.NO_RESULTS
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    generator_version: str = "1.0.0"
    git_commit: str = ""

    # Dataset totals
    total_tasks_in_split: int = 0
    total_runs_recorded: int = 0
    eligible_run_count: int = 0
    completed_run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    unavailable_count: int = 0
    skipped_count: int = 0
    overall_pass_rate: Optional[float] = None
    overall_failure_rate: Optional[float] = None

    # Breakdowns
    repository_results: list[RepositoryMetrics] = field(default_factory=list)
    task_type_results: list[TaskTypeMetrics] = field(default_factory=list)
    task_type_status: str = "UNAVAILABLE"
    task_type_reason: str = "source dataset does not provide task-type metadata"

    # Failures
    canonical_failures: list[FailureCategorySummary] = field(default_factory=list)
    evaluator_failures: list[FailureCategorySummary] = field(default_factory=list)
    termination_reasons: dict[str, int] = field(default_factory=dict)

    # Statistics
    runtime_stats: MetricStats = field(default_factory=MetricStats)
    tool_call_stats: MetricStats = field(default_factory=MetricStats)
    turn_stats: MetricStats = field(default_factory=MetricStats)
    patch_line_stats: MetricStats = field(default_factory=MetricStats)
    files_changed_stats: MetricStats = field(default_factory=MetricStats)

    # Recovery
    recovery_attempts: int = 0
    recovery_successes: int = 0
    recovery_success_rate: Optional[float] = None

    # Clean copy specifics
    patch_apply_conflicts: int = 0
    verification_failures: int = 0
    clean_copy_verified_count: int = 0

    # Failed run objects for failures.jsonl
    failed_runs: list[dict[str, Any]] = field(default_factory=list)

    # Hash metadata
    split_manifest_sha256: str = ""
    source_db_sha256: str = ""
