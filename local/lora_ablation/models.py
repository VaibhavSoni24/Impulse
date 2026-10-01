"""Data models, enums, condition configs, and manifest schemas for Stage 40 LoRA Ablation.

Implements the A/B/C/D controlled ablation framework:
- Condition A: BASELINE_NO_ADAPTER (Frozen Stage 39 baseline control)
- Condition B: L1_ADAPTER (Primary causal comparison: Baseline + L1 adapter)
- Condition C: L1_ADAPTER_PROMPT_VARIANT (Secondary ablation: L1 adapter + prompt variant)
- Condition D: L1_ADAPTER_RETRIEVAL_VARIANT (Secondary ablation: L1 adapter + retrieval variant)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConditionType(str, Enum):
    """The 4 planned controlled ablation conditions (Section 3)."""
    BASELINE_NO_ADAPTER = "BASELINE_NO_ADAPTER"  # Condition A: Frozen baseline control
    L1_ADAPTER = "L1_ADAPTER"                    # Condition B: Baseline + L1 adapter
    L1_ADAPTER_PROMPT_VARIANT = "L1_ADAPTER_PROMPT_VARIANT"        # Condition C: Prompt variant
    L1_ADAPTER_RETRIEVAL_VARIANT = "L1_ADAPTER_RETRIEVAL_VARIANT"  # Condition D: Retrieval variant


class ConditionStatus(str, Enum):
    """Execution readiness status for an ablation condition."""
    READY_FOR_ABLATION = "READY_FOR_ABLATION"
    MISSING_ADAPTER_ARTIFACT = "MISSING_ADAPTER_ARTIFACT"
    BLOCKED_BY_MISSING_ADAPTER = "BLOCKED_BY_MISSING_ADAPTER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AdapterGateStatus(str, Enum):
    """Classification returned by the Hard Adapter Gate (Section 4)."""
    READY = "READY"
    MISSING_ADAPTER_ARTIFACT = "MISSING_ADAPTER_ARTIFACT"
    MISSING_ADAPTER_FILES = "MISSING_ADAPTER_FILES"
    INVALID_ADAPTER_CONFIG = "INVALID_ADAPTER_CONFIG"
    INCOMPATIBLE_BASE_MODEL = "INCOMPATIBLE_BASE_MODEL"
    INCOMPATIBLE_DATASET = "INCOMPATIBLE_DATASET"
    WRONG_OBJECTIVE = "WRONG_OBJECTIVE"
    FIXTURE_ADAPTER_REJECTED = "FIXTURE_ADAPTER_REJECTED"
    TRAINING_STATUS_BLOCKED = "TRAINING_STATUS_BLOCKED"
    HASH_MISMATCH = "HASH_MISMATCH"
    PROVENANCE_INVALID = "PROVENANCE_INVALID"


class TaskPairTransition(str, Enum):
    """Classification of paired task outcome transitions between A and B (Section 11)."""
    A_PASS_B_PASS = "A_PASS_B_PASS"
    A_PASS_B_FAIL = "A_PASS_B_FAIL"
    A_FAIL_B_PASS = "A_FAIL_B_PASS"
    A_FAIL_B_FAIL = "A_FAIL_B_FAIL"


class TargetFailureTransition(str, Enum):
    """Specific transition for the targeted failure class (OBJ-TOOL-DISCIPLINE) (Section 11)."""
    TARGET_FAILURE_RESOLVED = "TARGET_FAILURE_RESOLVED"
    TARGET_FAILURE_REMAINS = "TARGET_FAILURE_REMAINS"
    NEW_TARGET_FAILURE = "NEW_TARGET_FAILURE"
    OTHER_FAILURE_CHANGED = "OTHER_FAILURE_CHANGED"
    NO_TARGET_FAILURE = "NO_TARGET_FAILURE"


class CollateralStatus(str, Enum):
    """Assessment of collateral regression or gain (Section 12)."""
    TARGET_GAIN = "TARGET_GAIN"
    COLLATERAL_REGRESSION = "COLLATERAL_REGRESSION"
    UNCHANGED = "UNCHANGED"
    UNKNOWN = "UNKNOWN"


class PromotionGateDecision(str, Enum):
    """Decision of candidate promotion gate (Section 14)."""
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    HOLD = "HOLD"
    BLOCKED_BY_MISSING_ADAPTER = "BLOCKED_BY_MISSING_ADAPTER"


class Stage40Decision(str, Enum):
    """Authoritative Stage 40 completion statuses (Section 33)."""
    STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER = (
        "STAGE 40 COMPLETE, ABLATION FRAMEWORK VERIFIED, EXECUTION BLOCKED BY MISSING ADAPTER"
    )
    STAGE_40_COMPLETE_AB_EXECUTED_AND_VERIFIED = (
        "STAGE 40 COMPLETE, A/B ABLATION EXECUTED AND VERIFIED"
    )
    STAGE_40_BLOCKED_EVIDENCE_RECORDED = (
        "STAGE 40 BLOCKED, EVIDENCE RECORDED"
    )


# Authoritative frozen dimensions established in Stage 37-39
FROZEN_BASELINE_DIMENSIONS = {
    "base_model": "gemma-4-31b-it-qat-w4a16-ct",
    "prompt_hash": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "retrieval_version": "R0",
    "testing_version": "T0",
    "recovery_version": "REC0",
    "topology": "root_only",
    "objective_id": "OBJ-TOOL-DISCIPLINE",
}

FROZEN_TOOL_CONTRACT_HASHES = {
    "run_command": "d48386318ec0eee1fa585ca53d1d3a8cc04ec06cc9acb851229aa9258cb95d8a",
    "submit_patch": "7ad08c240566f903e9fbcc217fd1af8dbf4796019812be1857b4bba6c9cb9490",
    "get_status": "59d2bdd46f070c357aeba14267cad7f67a394758908eb2c41b6ed140dda0bfe1",
    "read_file": "7c1fc9cd8769c270c8a7895f4322304c09c0212bc515ff24c75e1a39e241cfdc",
    "edit_file": "700f0f4920bd2095d9179a5a743d6dee0ce6997258c7c2dbbb6916645fd7eb50",
    "write_file": "b27c17afe3d7d7ed78cdeebcfca97fe02d866bf885dd088fb760a6ec8daa5183",
    "get_code_neighbors": "ff0902e2aa436c0f62607e95f7e02c9b56f57dfed11579feb81714be2b24b865",
    "search_similar_code": "3e378d8d83a59d3e736b3113db12ddf8ba52d5df929bd16851be4146348e55d7",
    "get_code_subgraph": "48fae3adc006e8e811c1b7dff61e5fe10a83dabbc80ddfc3681d098431b6f784",
}


@dataclass
class AdapterArtifactMetadata:
    """Metadata describing a validated LoRA adapter artifact (Section 4, 19)."""
    adapter_dir: str
    adapter_config_path: str
    adapter_weights_path: str
    manifest_path: str
    adapter_sha256: str
    base_model: str
    dataset_id: str
    dataset_version: str
    dataset_sha256: str
    objective_id: str
    training_run_status: str
    evidence_mode: str = "REAL"
    rank: Optional[int] = None
    alpha: Optional[int] = None
    dropout: Optional[float] = None
    file_hashes: Dict[str, str] = field(default_factory=dict)
    total_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AblationConditionConfig:
    """Configuration defining one controlled ablation condition (Section 3)."""
    condition_type: ConditionType
    condition_label: str
    candidate_id: str
    base_model: str = "gemma-4-31b-it-qat-w4a16-ct"
    adapter_enabled: bool = False
    adapter_path: Optional[str] = None
    adapter_sha256: Optional[str] = None
    prompt_hash: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    prompt_variant_reason: Optional[str] = None
    prompt_diff: Optional[str] = None
    tool_contract_hashes: Dict[str, str] = field(default_factory=lambda: dict(FROZEN_TOOL_CONTRACT_HASHES))
    retrieval_version: str = "R0"
    retrieval_variant_reason: Optional[str] = None
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    benchmark_split: str = "dev"
    benchmark_manifest_hash: str = "1b95c9fcfad8478fb4839cf9e3557e5e3d7a8e7e137a1f592d3f74151a6671fe"
    sampling_settings: Dict[str, Any] = field(default_factory=lambda: {
        "temperature": 0.2,
        "top_p": 0.95,
        "max_output_tokens": 16384,
    })
    status: ConditionStatus = ConditionStatus.READY_FOR_ABLATION
    status_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["condition_type"] = self.condition_type.value
        data["status"] = self.status.value
        return data


@dataclass
class TaskEvaluationRecord:
    """Execution telemetry and metrics for a single task under one condition (Section 8, 10)."""
    task_id: str
    condition: ConditionType
    result: str
    success: bool
    target_failure_status: str
    tool_calls: int = 0
    turns: int = 0
    runtime_ms: float = 0.0
    repeated_command_count: int = 0
    repeated_failing_command_count: int = 0
    tool_invocation_error_count: int = 0
    recovery_events: int = 0
    termination_reason: str = "COMPLETED"
    failure_class: Optional[str] = None
    cost_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["condition"] = self.condition.value
        return data


@dataclass
class PairedTaskComparison:
    """Paired comparison of identical task under Condition A vs Condition B (Section 11)."""
    task_id: str
    task_transition: TaskPairTransition
    target_transition: TargetFailureTransition
    collateral_status: CollateralStatus
    a_record: TaskEvaluationRecord
    b_record: TaskEvaluationRecord
    repeated_failing_delta: int
    tool_invocation_error_delta: int
    runtime_delta_ms: float
    tool_call_delta: int

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["task_transition"] = self.task_transition.value
        data["target_transition"] = self.target_transition.value
        data["collateral_status"] = self.collateral_status.value
        data["a_record"] = self.a_record.to_dict()
        data["b_record"] = self.b_record.to_dict()
        return data


@dataclass
class AblationAggregateMetrics:
    """Aggregate metrics for a condition or comparison (Section 10, 13)."""
    condition: ConditionType
    task_count: int = 0
    success_count: int = 0
    pass_rate: float = 0.0
    total_repeated_commands: int = 0
    repeated_command_rate: float = 0.0
    total_repeated_failing_commands: int = 0
    repeated_failing_command_rate: float = 0.0
    total_tool_invocation_errors: int = 0
    tool_invocation_error_rate: float = 0.0
    avg_tool_calls: float = 0.0
    avg_turns: float = 0.0
    avg_runtime_ms: float = 0.0
    failure_class_distribution: Dict[str, int] = field(default_factory=dict)
    cost_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["condition"] = self.condition.value
        return data


@dataclass
class AblationRunManifest:
    """Full reproducibility manifest for an ablation experiment run (Section 15, 18)."""
    run_id: str
    candidate_id: str
    condition: ConditionType
    parent_commit: str
    model_identifier: str = "gemma-4-31b-it-qat-w4a16-ct"
    adapter_identifier: Optional[str] = None
    adapter_sha256: Optional[str] = None
    prompt_hash: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    skill_hashes: Dict[str, str] = field(default_factory=dict)
    tool_contract_hashes: Dict[str, str] = field(default_factory=lambda: dict(FROZEN_TOOL_CONTRACT_HASHES))
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    benchmark_hashes: Dict[str, str] = field(default_factory=dict)
    runtime_settings: Dict[str, Any] = field(default_factory=dict)
    sampling_settings: Dict[str, Any] = field(default_factory=dict)
    hardware: Dict[str, Any] = field(default_factory=dict)
    software_versions: Dict[str, str] = field(default_factory=dict)
    start_time: str = ""
    end_time: str = ""
    status: ConditionStatus = ConditionStatus.READY_FOR_ABLATION
    evidence_mode: str = "REAL"
    manifest_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["condition"] = self.condition.value
        data["status"] = self.status.value
        return data


@dataclass
class AblationComparisonReport:
    """Comprehensive comparison report between conditions (Section 11, 26)."""
    report_id: str
    parent_commit: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    primary_comparison: str = "A_VS_B"
    a_condition: Optional[AblationConditionConfig] = None
    b_condition: Optional[AblationConditionConfig] = None
    c_condition: Optional[AblationConditionConfig] = None
    d_condition: Optional[AblationConditionConfig] = None
    adapter_gate_status: AdapterGateStatus = AdapterGateStatus.MISSING_ADAPTER_ARTIFACT
    adapter_metadata: Optional[AdapterArtifactMetadata] = None
    paired_comparisons: List[PairedTaskComparison] = field(default_factory=list)
    a_metrics: Optional[AblationAggregateMetrics] = None
    b_metrics: Optional[AblationAggregateMetrics] = None
    collateral_assessment: CollateralStatus = CollateralStatus.UNKNOWN
    promotion_decision: PromotionGateDecision = PromotionGateDecision.BLOCKED_BY_MISSING_ADAPTER
    decision_reason: str = ""
    overall_status: Stage40Decision = Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "report_id": self.report_id,
            "parent_commit": self.parent_commit,
            "created_at": self.created_at,
            "primary_comparison": self.primary_comparison,
            "adapter_gate_status": self.adapter_gate_status.value,
            "collateral_assessment": self.collateral_assessment.value,
            "promotion_decision": self.promotion_decision.value,
            "decision_reason": self.decision_reason,
            "overall_status": self.overall_status.value,
            "a_condition": self.a_condition.to_dict() if self.a_condition else None,
            "b_condition": self.b_condition.to_dict() if self.b_condition else None,
            "c_condition": self.c_condition.to_dict() if self.c_condition else None,
            "d_condition": self.d_condition.to_dict() if self.d_condition else None,
            "adapter_metadata": self.adapter_metadata.to_dict() if self.adapter_metadata else None,
            "paired_comparisons": [p.to_dict() for p in self.paired_comparisons],
            "a_metrics": self.a_metrics.to_dict() if self.a_metrics else None,
            "b_metrics": self.b_metrics.to_dict() if self.b_metrics else None,
        }
        return data
