"""Data models and representations for Recovery Optimization Loop (Stage 35).

Defines:
- RecoveryPatternType: Canonical mined failure patterns (REPEATED_COMMAND, REPEATED_ERROR, etc.)
- RecoveryOutcome: Bounded recovery outcomes (RECOVERED, LOOP_DETECTED, etc.)
- RecoveryInterventionType: Vocabulary for single-change interventions
- RecoveryStateMachineState: Lifecycle states of recovery execution
- RecoveryVariant: Canonical recovery policy variants (REC0, REC1, REC2, REC3)
- RecoverySelectionStatus: Selection statuses for failure clusters
- TaskRecoveryTransition: Paired comparison transitions (FAIL_TO_RECOVERED, etc.)
- RecoveryFailureRecord: Normalized recovery record preserving provenance
- RecoveryCluster: Deterministic cluster of recovery failures
- RetryBudgetConfig: Explicit bounded retry parameters
- RecoveryPolicy: Typed configuration for recovery strategy
- RecoveryExecutionEvent: Structured telemetry event for recovery trace
- RecoveryCostMetrics: Resource and cost metrics for recovery
- RecoveryQualityMetrics: Recovery effectiveness, latency, and success metrics
- RecoveryDiagnostics: Deterministic diagnostic flags
- RecoveryHypothesis: Structured hypothesis specification
- RecoveryTaskPairOutcome: Paired per-task outcome on the same failure set
- RecoveryCandidateManifest: Reproducibility manifest with invariance hashes
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class RecoveryPatternType(str, Enum):
    """Canonical recovery-relevant failure patterns (Stage 35 Section 7)."""

    REPEATED_COMMAND = "REPEATED_COMMAND"
    REPEATED_ERROR = "REPEATED_ERROR"
    REPEATED_EDIT = "REPEATED_EDIT"
    REPEATED_HYPOTHESIS = "REPEATED_HYPOTHESIS"
    RECOVERY_THRASHING = "RECOVERY_THRASHING"
    RECOVERY_OMISSION = "RECOVERY_OMISSION"
    LATE_RECOVERY = "LATE_RECOVERY"
    FAILED_RECOVERY = "FAILED_RECOVERY"
    RECOVERY_LOOP = "RECOVERY_LOOP"
    RETRY_WASTE = "RETRY_WASTE"


class RecoveryOutcome(str, Enum):
    """Explicit observable recovery outcomes (Stage 35 Section 15)."""

    RECOVERED = "RECOVERED"
    RECOVERED_AFTER_RETRY = "RECOVERED_AFTER_RETRY"
    RECOVERED_AFTER_ALTERNATE_PATH = "RECOVERED_AFTER_ALTERNATE_PATH"
    NOT_RECOVERED = "NOT_RECOVERED"
    LOOP_DETECTED = "LOOP_DETECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    INFRASTRUCTURE_BLOCKED = "INFRASTRUCTURE_BLOCKED"
    NO_ACTIONABLE_DATA = "NO_ACTIONABLE_DATA"
    INCONCLUSIVE = "INCONCLUSIVE"


class RecoveryInterventionType(str, Enum):
    """Controlled vocabulary for recovery interventions (Stage 35 Section 12)."""

    ADD_RECOVERY_RULE = "ADD_RECOVERY_RULE"
    MODIFY_RECOVERY_TRIGGER = "MODIFY_RECOVERY_TRIGGER"
    MODIFY_RECOVERY_ACTION = "MODIFY_RECOVERY_ACTION"
    MODIFY_RETRY_BOUND = "MODIFY_RETRY_BOUND"
    ADD_ALTERNATE_PATH = "ADD_ALTERNATE_PATH"
    MODIFY_NO_PROGRESS_RESPONSE = "MODIFY_NO_PROGRESS_RESPONSE"
    MODIFY_TOOL_FAILURE_FALLBACK = "MODIFY_TOOL_FAILURE_FALLBACK"
    MODIFY_TEST_FAILURE_RECOVERY = "MODIFY_TEST_FAILURE_RECOVERY"
    MODIFY_BAD_EDIT_RECOVERY = "MODIFY_BAD_EDIT_RECOVERY"
    MODIFY_BUDGET_RECOVERY = "MODIFY_BUDGET_RECOVERY"
    MODIFY_RECOVERY_STOP_CONDITION = "MODIFY_RECOVERY_STOP_CONDITION"
    ADD_RECOVERY_GUARD = "ADD_RECOVERY_GUARD"


class RecoveryStateMachineState(str, Enum):
    """Lifecycle states of the recovery state machine (Stage 35 Section 19)."""

    FAILURE_DETECTED = "FAILURE_DETECTED"
    RECOVERY_ELIGIBLE = "RECOVERY_ELIGIBLE"
    RECOVERY_SELECTED = "RECOVERY_SELECTED"
    RECOVERY_EXECUTED = "RECOVERY_EXECUTED"
    RESULT_OBSERVED = "RESULT_OBSERVED"
    RECOVERED = "RECOVERED"
    RETRY_ELIGIBLE = "RETRY_ELIGIBLE"
    ALTERNATE_PATH = "ALTERNATE_PATH"
    STOP_RECOVERY = "STOP_RECOVERY"
    LOOP_DETECTED = "LOOP_DETECTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class RecoveryVariant(str, Enum):
    """Canonical recovery policy variants (Stage 35 Section 38)."""

    REC0 = "REC0"  # Baseline: Stage 20 canonical recovery paths
    REC1 = "REC1"  # Candidate 1: Proactive early detection & rapid fallback
    REC2 = "REC2"  # Candidate 2: Alternate path routing on repeated failure
    REC3 = "REC3"  # Candidate 3: Adaptive loop guard & bounded retries


class RecoverySelectionStatus(str, Enum):
    """Selection outcome for recovery pattern clusters (Stage 35 Section 9)."""

    ACTIONABLE_RECOVERY_SELECTED = "ACTIONABLE_RECOVERY_SELECTED"
    NO_ACTIONABLE_LIVE_RECOVERY = "NO_ACTIONABLE_LIVE_RECOVERY"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    NO_PATTERNS_FOUND = "NO_PATTERNS_FOUND"


class TaskRecoveryTransition(str, Enum):
    """Categorized behavioral shift on an individual task (Stage 35 Section 31)."""

    FAIL_TO_RECOVERED = "FAIL_TO_RECOVERED"
    FAIL_TO_STILL_FAILING = "FAIL_TO_STILL_FAILING"
    FAIL_TO_DIFFERENT_FAIL = "FAIL_TO_DIFFERENT_FAIL"
    FAIL_TO_LOOP = "FAIL_TO_LOOP"
    FAIL_TO_BUDGET_EXHAUSTED = "FAIL_TO_BUDGET_EXHAUSTED"
    PASS_UNCHANGED = "PASS_UNCHANGED"
    UNPAIRED = "UNPAIRED"


@dataclass
class RetryBudgetConfig:
    """Explicit bounded retry parameters for recovery (Stage 35 Section 21)."""

    max_same_action_retries: int = 2
    max_total_recovery_attempts: int = 4
    max_alternate_paths: int = 2
    max_recovery_runtime_seconds: float = 120.0
    max_recovery_tool_calls: int = 8

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetryBudgetConfig:
        return cls(**data)


@dataclass
class RecoveryFailureRecord:
    """Normalized internal representation for recovery-specific failure analysis (Stage 35 Section 6).

    Preserves exact provenance to source runs and telemetry events.
    """

    run_id: str
    task_id: str
    candidate_id: str
    split: str = "dev"
    evidence_mode: str = "UNAVAILABLE"
    failure_id: str = ""
    failure_class: str = "UNKNOWN"  # Authoritative Stage 18 FailureClass
    failure_stage: str = "UNKNOWN"
    failure_signature: str = ""
    recovery_trigger: str = ""
    recovery_action: str = ""
    recovery_attempt_number: int = 1
    recovery_success: Optional[bool] = None
    recovery_outcome: str = RecoveryOutcome.INCONCLUSIVE.value
    repeated_pattern: Optional[str] = None
    loop_detected: bool = False
    loop_length: int = 0
    first_failure_event: Optional[int] = None
    first_recovery_opportunity: Optional[int] = None
    actual_recovery_trigger: Optional[int] = None
    terminal_outcome: str = ""
    runtime: Optional[float] = None
    tool_calls: Optional[int] = None
    turns: Optional[int] = None
    source_event_ids: list[str] = field(default_factory=list)
    is_actionable: bool = False
    repository: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryFailureRecord:
        return cls(**data)


@dataclass
class RecoveryCluster:
    """Deterministic cluster of recovery failure patterns (Stage 35 Section 8)."""

    cluster_id: str
    pattern_type: str
    canonical_signature: str
    affected_runs: list[str] = field(default_factory=list)
    affected_unique_tasks: list[str] = field(default_factory=list)
    evidence_modes: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    splits: list[str] = field(default_factory=list)
    recurrence_count: int = 0
    successful_recovery_count: int = 0
    failed_recovery_count: int = 0
    loop_count: int = 0
    earliest_detection_opportunity: Optional[int] = None
    representative_trace_references: list[str] = field(default_factory=list)
    actionable_status: bool = False
    actionability_reason: str = ""
    representative_failure: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryCluster:
        return cls(**data)


@dataclass
class RecoveryPolicy:
    """Typed recovery policy configuration (Stage 35 Section 14, 20, 21)."""

    variant: str = RecoveryVariant.REC0.value
    candidate_id: str = "REC0"
    retry_budgets: RetryBudgetConfig = field(default_factory=RetryBudgetConfig)
    early_detection_enabled: bool = False
    loop_guard_enabled: bool = False
    alternate_path_routing_enabled: bool = False
    no_progress_threshold_turns: int = 3
    triggers: dict[str, Any] = field(
        default_factory=lambda: {
            "budget_pressure_remaining_tools": 10,
            "budget_pressure_remaining_seconds": 300.0,
            "test_failure_escalate_attempts": 2,
            "bad_edit_max_attempts": 2,
            "search_fallback_max_attempts": 5,
        }
    )
    actions: dict[str, Any] = field(
        default_factory=lambda: {
            "bad_edit_safe_ownership_only": True,
            "allow_revert": True,
            "allow_alternate_tool": True,
            "allow_stack_inspection": True,
        }
    )
    fallback_rules: dict[str, str] = field(
        default_factory=lambda: {
            "on_tool_failure": "RETRY_THEN_ALTERNATE",
            "on_test_failure": "CLASSIFY_THEN_INSPECT",
            "on_bad_edit": "REPAIR_OR_REVERT",
            "on_search_exhaustion": "EXACT_THEN_TREE_THEN_GRAPH",
            "on_budget_pressure": "TARGETED_VALIDATION_THEN_REVIEW",
        }
    )
    stop_conditions: list[str] = field(
        default_factory=lambda: [
            "target_state_recovered",
            "budget_exhausted",
            "path_exhausted",
            "loop_detected",
        ]
    )
    prompt_instruction: Optional[str] = None  # Narrowly scoped recovery instruction if applicable

    @property
    def strategy_id(self) -> str:
        return self.variant

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def compute_policy_hash(self) -> str:
        """Computes deterministic SHA-256 hash of canonical policy parameters."""
        data = {
            "variant": self.variant,
            "retry_budgets": self.retry_budgets.to_dict() if isinstance(self.retry_budgets, RetryBudgetConfig) else self.retry_budgets,
            "early_detection_enabled": self.early_detection_enabled,
            "loop_guard_enabled": self.loop_guard_enabled,
            "alternate_path_routing_enabled": self.alternate_path_routing_enabled,
            "no_progress_threshold_turns": self.no_progress_threshold_turns,
            "triggers": self.triggers,
            "actions": self.actions,
            "fallback_rules": self.fallback_rules,
            "stop_conditions": sorted(self.stop_conditions),
            "prompt_instruction": self.prompt_instruction,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryPolicy:
        d = dict(data)
        if "retry_budgets" in d and isinstance(d["retry_budgets"], dict):
            d["retry_budgets"] = RetryBudgetConfig.from_dict(d["retry_budgets"])
        return cls(**d)


@dataclass
class RecoveryExecutionEvent:
    """Structured telemetry event for an individual recovery execution (Stage 35 Section 40)."""

    run_id: str
    task_id: str
    candidate_id: str
    event_index: int
    failure_signature: str
    failure_class: str
    recovery_eligible: bool
    trigger: str
    action: str
    attempt_number: int
    state_before: str
    state_after: str
    evidence_changed: bool
    recovery_outcome: str
    loop_detected: bool
    stop_reason: str
    duration_ms: float = 0.0
    tool_calls_added: int = 0
    turn: int = 1
    evidence_mode: str = "FIXTURE"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryExecutionEvent:
        return cls(**data)


@dataclass
class RecoveryCostMetrics:
    """Quantitative resource and cost metrics for recovery (Stage 35 Section 17)."""

    recovery_tool_calls: int = 0
    recovery_turns: int = 0
    retry_count: int = 0
    recovery_runtime_ms: float = 0.0
    additional_tests_caused: int = 0
    additional_retrieval_calls: int = 0
    additional_context_growth_bytes: int = 0
    repeated_failed_interventions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryCostMetrics:
        return cls(**data)


@dataclass
class RecoveryQualityMetrics:
    """Quantitative recovery quality and effectiveness metrics (Stage 35 Section 16, 32)."""

    targeted_recovery_success_rate: float = 0.0
    targeted_failure_reduction: int = 0
    recovery_loop_count: int = 0
    detection_latency_events: float = 0.0
    detection_latency_turns: float = 0.0
    average_recovery_attempts: float = 0.0
    mean_recovery_runtime_ms: float = 0.0
    tasks_recovered_after_failure: int = 0
    tasks_abandoned_after_failure: int = 0
    alternate_path_success_rate: float = 0.0
    first_attempt_recovery_success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryQualityMetrics:
        return cls(**data)


@dataclass
class RecoveryDiagnostics:
    """Deterministic diagnostic flags for recovery behavior (Stage 35 Section 41)."""

    late_recovery: bool = False
    repeated_identical_recovery: bool = False
    recovery_oscillation: bool = False
    retry_waste: bool = False
    recovery_without_state_change: bool = False
    missed_recovery_opportunity: bool = False
    failed_recovery: bool = False
    recovery_causing_unrelated_regression: bool = False
    recovery_causing_excessive_testing: bool = False
    recovery_causing_excessive_retrieval: bool = False
    recovery_budget_exhaustion: bool = False
    recovery_success_after_unnecessary_repetitions: bool = False
    diagnostic_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryDiagnostics:
        return cls(**data)


@dataclass
class RecoveryHypothesis:
    """Structured causal hypothesis for a recovery intervention (Stage 35 Section 11)."""

    target_failure: str
    observation: str
    hypothesis: str
    recovery_change: str
    expected_behavior: str
    expected_metric_signal: str
    rejection_condition: str
    intervention_type: str = RecoveryInterventionType.MODIFY_RECOVERY_TRIGGER.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryHypothesis:
        return cls(**data)


@dataclass
class RecoveryTaskPairOutcome:
    """Paired per-task outcome comparing baseline vs candidate on the SAME failure set (Stage 35 Section 30, 31)."""

    task_id: str
    baseline_failure_pattern: Optional[str] = None
    candidate_failure_pattern: Optional[str] = None
    baseline_recovery_triggered: bool = False
    candidate_recovery_triggered: bool = False
    baseline_recovery_action: str = ""
    candidate_recovery_action: str = ""
    baseline_recovery_outcome: str = RecoveryOutcome.INCONCLUSIVE.value
    candidate_recovery_outcome: str = RecoveryOutcome.INCONCLUSIVE.value
    baseline_detection_latency: Optional[int] = None
    candidate_detection_latency: Optional[int] = None
    baseline_attempts: int = 0
    candidate_attempts: int = 0
    baseline_loops: int = 0
    candidate_loops: int = 0
    baseline_task_result: str = "FAIL"
    candidate_task_result: str = "FAIL"
    transition: str = TaskRecoveryTransition.FAIL_TO_STILL_FAILING.value
    diff_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryTaskPairOutcome:
        return cls(**data)


@dataclass
class RecoveryCandidateManifest:
    """Complete candidate manifest guaranteeing full reproducibility and provenance (Stage 35 Section 38)."""

    candidate_id: str
    parent_candidate: str
    policy_hash: str
    intervention_id: str
    root_prompt_hash: str
    retrieval_policy_hash: str
    testing_policy_hash: str
    topology_hash: str
    model_id: str
    test_strategy_skill_hash: str
    repo_triage_skill_hash: str
    evidence_mode: str = "UNAVAILABLE"
    benchmark_split: str = "dev"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryCandidateManifest:
        return cls(**data)
