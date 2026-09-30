"""Data models and representations for Testing Strategy Optimization Loop (Stage 34).

Defines:
- TestingStrategyVariant: Canonical testing variants (T0, T1, T2, T3)
- TestLevel: Structured hierarchy of test escalation (TARGETED, ADJACENT, SUBSYSTEM, FULL)
- RiskSignalType & RiskSignal: Structured, observable risk signals for adaptive decisions
- FullSuiteFeasibility: Feasibility evaluation outcomes (FEASIBLE, NOT_FEASIBLE, UNKNOWN)
- TestPolicy: Typed testing strategy configuration
- TestExecutionEvent: Telemetry event for individual test executions
- AdaptiveEscalationTrace: Trace of dynamic escalation and stopping decisions for T3
- TestCostMetrics: Quantitative resource and cost metrics
- TestEvidenceMetrics: Quantitative validation quality and evidence yield metrics
- TestDiagnostics: Auditable diagnostic flags (redundancy, duplicate tests, etc.)
- TestHypothesis: Structured causal hypothesis specification
- TestTaskPairOutcome: Paired per-task outcome comparison with testing diff
- TestCandidateManifest: Reproducibility manifest for testing experiments
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class TestingStrategyVariant(str, Enum):
    """Canonical testing strategy variants defined by PLAN.md Stage 34 Section 4."""

    T0 = "T0"  # Baseline: Minimal targeted test
    T1 = "T1"  # Targeted + adjacent tests
    T2 = "T2"  # Targeted + subsystem + full when feasible
    T3 = "T3"  # Adaptive escalation based on failure risk


class TestLevel(str, Enum):
    """Ordered escalation levels for test execution (Stage 34 Section 12)."""

    TARGETED = "TARGETED"
    ADJACENT = "ADJACENT"
    SUBSYSTEM = "SUBSYSTEM"
    FULL = "FULL"


class RiskSignalType(str, Enum):
    """Observable risk signal types driving T3 adaptive escalation (Stage 34 Section 9)."""

    TARGETED_TEST_FAILED = "TARGETED_TEST_FAILED"
    MULTIPLE_FILES_CHANGED = "MULTIPLE_FILES_CHANGED"
    PUBLIC_API_CHANGED = "PUBLIC_API_CHANGED"
    CHANGED_PUBLIC_API = "PUBLIC_API_CHANGED"
    SHARED_UTILITY_CHANGED = "SHARED_UTILITY_CHANGED"
    CHANGED_SHARED_UTILITY = "SHARED_UTILITY_CHANGED"
    TEST_INFRASTRUCTURE_CHANGED = "TEST_INFRASTRUCTURE_CHANGED"
    DEPENDENCY_CONFIG_CHANGED = "DEPENDENCY_CONFIG_CHANGED"
    MULTI_PACKAGE_CHANGED = "MULTI_PACKAGE_CHANGED"
    MULTIPLE_CHANGED_FILES = "MULTIPLE_FILES_CHANGED"
    ADJACENT_TEST_REGRESSION = "ADJACENT_TEST_REGRESSION"
    INCOMPLETE_FIX_CLASSIFICATION = "INCOMPLETE_FIX_CLASSIFICATION"
    PRE_EXISTING_FAILURE_INVOLVEMENT = "PRE_EXISTING_FAILURE_INVOLVEMENT"
    LARGE_DIFF_SIZE = "LARGE_DIFF_SIZE"
    NO_TARGETED_TEST_FOUND = "NO_TARGETED_TEST_FOUND"
    CRITICAL_PATH_NEW_FILE = "CRITICAL_PATH_NEW_FILE"


class FullSuiteFeasibility(str, Enum):
    """Feasibility outcome for full-suite test execution (Stage 34 Section 25)."""

    FEASIBLE = "FEASIBLE"
    NOT_FEASIBLE = "NOT_FEASIBLE"
    UNKNOWN = "UNKNOWN"


class TaskTransition(str, Enum):
    """Categorized behavioral shift on an individual task."""

    FAIL_TO_PASS = "FAIL_TO_PASS"
    PASS_TO_FAIL = "PASS_TO_FAIL"
    FAIL_TO_OTHER_FAIL = "FAIL_TO_OTHER_FAIL"
    FAIL_UNCHANGED = "FAIL_UNCHANGED"
    PASS_UNCHANGED = "PASS_UNCHANGED"
    UNPAIRED = "UNPAIRED"


@dataclass
class RiskSignal:
    """Explicit, observable risk signal record for adaptive escalation decisions."""

    signal_type: str
    observed: bool = True
    severity: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    rationale: str = ""
    evidence_reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskSignal:
        return cls(**data)


@dataclass
class TestHypothesis:
    """Structured causal hypothesis for a testing strategy intervention (Stage 34 Section 18)."""

    target_failure: str
    observation: str
    hypothesis: str
    testing_change: str
    expected_signal: str
    rejection_condition: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestHypothesis:
        return cls(**data)


@dataclass
class TestPolicy:
    """Typed representation of a testing strategy policy configuration (Stage 34 Section 10)."""

    variant: str = TestingStrategyVariant.T0.value
    candidate_id: str = "T0"
    targeted_enabled: bool = True
    adjacent_enabled: bool = False
    subsystem_enabled: bool = False
    full_suite_enabled: bool = False
    adaptive_enabled: bool = False

    @property
    def strategy_id(self) -> str:
        return self.variant

    max_test_commands: int = 4
    max_test_cases: int = 50
    runtime_budget_seconds: float = 300.0

    full_suite_feasibility_rules: dict[str, Any] = field(
        default_factory=lambda: {
            "max_estimated_runtime_seconds": 120.0,
            "max_suite_test_count": 200,
            "require_stable_env": True,
        }
    )

    escalation_rules: dict[str, Any] = field(
        default_factory=lambda: {
            "escalate_on_targeted_failure": True,
            "escalate_on_high_risk": True,
            "escalate_on_adjacent_regression": True,
        }
    )

    stop_rules: dict[str, Any] = field(
        default_factory=lambda: {
            "stop_on_targeted_pass_if_low_risk": True,
            "stop_on_adjacent_pass_if_no_regressions": True,
            "stop_on_budget_exhaustion": True,
        }
    )

    fallback_rules: dict[str, str] = field(
        default_factory=lambda: {
            "on_targeted_not_found": "BROADER_DISCOVERY",
            "on_command_launch_error": "FALLBACK_RUNNER",
            "on_full_suite_infeasible": "STOP_AT_SUBSYSTEM",
            "on_framework_unavailable": "CLASSIFY_INFRASTRUCTURE",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_policy_hash(self) -> str:
        """Computes deterministic SHA-256 hash of canonical policy parameters."""
        data = {
            "variant": self.variant,
            "targeted_enabled": self.targeted_enabled,
            "adjacent_enabled": self.adjacent_enabled,
            "subsystem_enabled": self.subsystem_enabled,
            "full_suite_enabled": self.full_suite_enabled,
            "adaptive_enabled": self.adaptive_enabled,
            "max_test_commands": self.max_test_commands,
            "max_test_cases": self.max_test_cases,
            "runtime_budget_seconds": self.runtime_budget_seconds,
            "full_suite_feasibility_rules": self.full_suite_feasibility_rules,
            "escalation_rules": self.escalation_rules,
            "stop_rules": self.stop_rules,
            "fallback_rules": self.fallback_rules,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestPolicy:
        return cls(**data)


@dataclass
class TestExecutionEvent:
    """Structured telemetry event for an individual test command execution (Stage 34 Section 11)."""

    run_id: str
    task_id: str
    candidate_id: str
    strategy_id: str
    test_level: str
    command: str
    selected_tests: list[str] = field(default_factory=list)
    selection_reason: str = ""
    risk_signals: list[str] = field(default_factory=list)
    start_time: str = ""
    duration_ms: float = 0.0
    result: str = "PASS"  # "PASS", "FAIL", "ERROR", "TIMEOUT", "SKIPPED"
    tests_executed: int = 0
    failures_detected: int = 0
    output_size_bytes: int = 0
    compacted_output_size_bytes: Optional[int] = None
    escalation_decision: str = "STOP"
    stop_decision: bool = True
    evidence_mode: str = "FIXTURE"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestExecutionEvent:
        return cls(**data)


@dataclass
class AdaptiveEscalationTrace:
    """Structured telemetry for an individual round of T3 adaptive escalation (Stage 34 Section 8)."""

    round_index: int
    current_level: str
    test_result: str
    observed_risk_signals: list[str]
    decision: str  # "STOP" | "ESCALATE"
    target_level: Optional[str]
    decision_rationale: str
    budget_remaining_commands: int
    budget_remaining_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptiveEscalationTrace:
        return cls(**data)


@dataclass
class TestCostMetrics:
    """Quantitative cost metrics for a testing strategy candidate (Stage 34 Section 13)."""

    total_test_commands: int = 0
    targeted_commands: int = 0
    adjacent_commands: int = 0
    subsystem_commands: int = 0
    full_suite_commands: int = 0
    total_tests_executed: int = 0
    total_test_runtime_ms: float = 0.0
    mean_test_duration_ms: Optional[float] = None
    median_test_duration_ms: Optional[float] = None
    p95_test_duration_ms: Optional[float] = None
    total_output_bytes: int = 0
    repeated_command_count: int = 0
    duplicate_test_case_count: int = 0
    total_agent_runtime_ms: Optional[float] = None
    testing_tool_call_share: Optional[float] = None
    total_test_duration_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if self.total_test_duration_ms is not None and self.total_test_runtime_ms == 0.0:
            self.total_test_runtime_ms = self.total_test_duration_ms
        elif self.total_test_runtime_ms != 0.0 and self.total_test_duration_ms is None:
            self.total_test_duration_ms = self.total_test_runtime_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestCostMetrics:
        return cls(**data)


@dataclass
class TestEvidenceMetrics:
    """Quantitative validation quality and evidence yield metrics (Stage 34 Section 14)."""

    pass_rate: float
    failure_rate: float
    targeted_failure_mode: str
    targeted_failure_count: int
    targeted_failure_rate: float
    regressions_detected: int = 0
    incomplete_fixes_detected: int = 0
    targeted_behavior_confirmed: int = 0
    adjacent_failures_discovered: int = 0
    subsystem_failures_discovered: int = 0
    full_suite_failures_discovered: int = 0
    false_confidence_count: int = 0
    early_detection_level: str = "NONE"  # "TARGETED", "ADJACENT", "SUBSYSTEM", "FULL", "NONE"
    clean_copy_verification_success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestEvidenceMetrics:
        return cls(**data)


@dataclass
class TestDiagnostics:
    """Auditable diagnostic flags for test execution pathology detection (Stage 34 Section 16)."""

    duplicate_command_count: int = 0
    duplicate_case_count: int = 0
    rerun_unchanged_code_count: int = 0
    unnecessary_full_suite_count: int = 0
    zero_new_evidence_adjacent_count: int = 0
    zero_new_evidence_subsystem_count: int = 0
    repeated_failure_count: int = 0
    diagnostic_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestDiagnostics:
        return cls(**data)


@dataclass
class TestTaskPairOutcome:
    """Task-level paired outcome comparison between baseline and candidate testing strategies (Stage 34 Section 28)."""

    task_id: str
    baseline_success: Optional[bool]
    candidate_success: Optional[bool]
    baseline_failure_category: str
    candidate_failure_category: str
    transition: TaskTransition
    baseline_test_commands: int = 0
    candidate_test_commands: int = 0
    test_command_delta: int = 0
    baseline_test_level_reached: str = TestLevel.TARGETED.value
    candidate_test_level_reached: str = TestLevel.TARGETED.value
    testing_behavior_diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["transition"] = (
            self.transition.value
            if isinstance(self.transition, TaskTransition)
            else str(self.transition)
        )
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestTaskPairOutcome:
        d = dict(data)
        if "transition" in d and isinstance(d["transition"], str):
            d["transition"] = TaskTransition(d["transition"])
        return cls(**d)


@dataclass
class TestCandidateManifest:
    """Reproducibility manifest for a testing strategy candidate (Stage 34 Section 10)."""

    candidate_id: str
    parent_candidate_id: Optional[str]
    testing_variant: str = ""
    testing_policy_hash: str = ""
    source_failure_cluster_id: Optional[str] = None
    target_failure_mode: str = "UNKNOWN"
    hypothesis: Optional[TestHypothesis] = None
    benchmark_split: str = "validation"
    benchmark_manifest_hash: str = ""
    held_out_lock_hash: str = ""
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    topology_id: str = "root_only"
    prompt_id: str = "P0"
    prompt_sha256: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    retrieval_candidate_id: str = "R0"
    retrieval_policy_hash: str = "3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7"
    test_strategy_skill_sha256: str = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
    tool_budget_id: str = "standard_stage26"
    evidence_mode: str = "UNAVAILABLE"
    created_from_commit: str = ""
    experiment_id: str = ""
    decision: str = "INCONCLUSIVE"
    decision_rationale: str = ""
    strategy_variant: Optional[str] = None
    test_policy_hash: Optional[str] = None
    retrieval_id: Optional[str] = None
    frozen_test_skill_sha256: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    artifact_hashes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.strategy_variant and not self.testing_variant:
            self.testing_variant = self.strategy_variant
        elif self.testing_variant and not self.strategy_variant:
            self.strategy_variant = self.testing_variant

        if self.test_policy_hash and not self.testing_policy_hash:
            self.testing_policy_hash = self.test_policy_hash
        elif self.testing_policy_hash and not self.test_policy_hash:
            self.test_policy_hash = self.testing_policy_hash

        if self.retrieval_id and not self.retrieval_candidate_id:
            self.retrieval_candidate_id = self.retrieval_id

        if self.frozen_test_skill_sha256 and not self.test_strategy_skill_sha256:
            self.test_strategy_skill_sha256 = self.frozen_test_skill_sha256

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.hypothesis:
            res["hypothesis"] = self.hypothesis.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestCandidateManifest:
        d = dict(data)
        if d.get("hypothesis") and isinstance(d["hypothesis"], dict):
            d["hypothesis"] = TestHypothesis.from_dict(d["hypothesis"])
        return cls(**d)
