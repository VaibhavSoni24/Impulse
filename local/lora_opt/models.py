"""Data models and representations for LoRA Feasibility / Readiness Study (Stage 37).

Defines:
- L0Decision: Readiness decision gate (READY_FOR_STAGE_38, CONDITIONALLY_READY_FOR_STAGE_38, NOT_READY, BLOCKED_BY_INFRASTRUCTURE)
- ReadinessDimensionStatus: Stability status per dimension (STABLE, CHANGED, UNKNOWN, UNAVAILABLE)
- BenchmarkStabilityStatus: Benchmark stability states (BENCHMARK_STABLE, BENCHMARK_CHANGED, BENCHMARK_UNAVAILABLE)
- InfrastructureClassification: Hardware classification (LOCAL_FEASIBLE, LOCAL_NOT_FEASIBLE, EXTERNAL_GPU_REQUIRED, INFRASTRUCTURE_UNKNOWN)
- ObjectiveStatus: Candidate training objective status (PRIMARY_SELECTED, SECONDARY_CANDIDATE, REJECTED_TOO_BROAD, INSUFFICIENT_EVIDENCE)
- BaselineSnapshot: Cryptographic snapshot of all fixed system dimensions
- ArchitectureStabilityReport: Multi-dimensional stability analysis
- BenchmarkStabilityReport: Benchmark split verification audit
- FailureCategoryAudit: Audit of canonical failure taxonomy readiness
- ToolContractRecord: Predefined tool contract specifications
- HardwareAuditReport: Comprehensive local runtime environment audit
- CandidateObjective: Structured candidate LoRA objective definition
- ControlledLoRAExperimentContract: Formal contract for future Stage 39 execution
- L0Manifest: Complete reproducibility manifest
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class L0Decision(str, Enum):
    """Authoritative Stage 37 L0 decision gate (Stage 37 Section 26)."""

    READY_FOR_STAGE_38 = "READY_FOR_STAGE_38"
    CONDITIONALLY_READY_FOR_STAGE_38 = "CONDITIONALLY_READY_FOR_STAGE_38"
    NOT_READY = "NOT_READY"
    BLOCKED_BY_INFRASTRUCTURE = "BLOCKED_BY_INFRASTRUCTURE"


class ReadinessDimensionStatus(str, Enum):
    """Stability status per system dimension (Stage 37 Section 5)."""

    STABLE = "STABLE"
    CHANGED = "CHANGED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class BenchmarkStabilityStatus(str, Enum):
    """Benchmark stability states (Stage 37 Section 6)."""

    BENCHMARK_STABLE = "BENCHMARK_STABLE"
    BENCHMARK_CHANGED = "BENCHMARK_CHANGED"
    BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"


class InfrastructureClassification(str, Enum):
    """Hardware capability classification (Stage 37 Section 12)."""

    LOCAL_FEASIBLE = "LOCAL_FEASIBLE"
    LOCAL_NOT_FEASIBLE = "LOCAL_NOT_FEASIBLE"
    EXTERNAL_GPU_REQUIRED = "EXTERNAL_GPU_REQUIRED"
    INFRASTRUCTURE_UNKNOWN = "INFRASTRUCTURE_UNKNOWN"


class ObjectiveStatus(str, Enum):
    """Candidate training objective status (Stage 37 Section 8, 9)."""

    PRIMARY_SELECTED = "PRIMARY_SELECTED"
    SECONDARY_CANDIDATE = "SECONDARY_CANDIDATE"
    REJECTED_TOO_BROAD = "REJECTED_TOO_BROAD"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ToolContractStatus(str, Enum):
    """Tool contract status (Stage 37 Section 11)."""

    STABLE = "STABLE"
    CHANGED = "CHANGED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ToolContractRecord:
    """Audit record for a competition-exposed tool contract (Stage 37 Section 11)."""

    tool_name: str
    signature: str
    contract_hash: str
    source_location: str
    status: str = ToolContractStatus.STABLE.value
    reason: str = "Standard pre-defined competition tool schema verified."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolContractRecord:
        return cls(**data)


@dataclass
class CandidateObjective:
    """Structured candidate LoRA training objective (Stage 37 Section 8)."""

    objective_id: str
    name: str
    problem_definition: str
    target_failure_classes: list[str]
    observable_input: str
    desired_behavior: str
    undesired_behavior: str
    training_signal: str
    evaluation_metric: str
    primary_benchmark_split: str
    negative_behavior: str
    possible_confounders: list[str]
    minimum_evidence_required: str
    status: str = ObjectiveStatus.PRIMARY_SELECTED.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateObjective:
        return cls(**data)


@dataclass
class HardwareAuditReport:
    """Environment and hardware capability audit (Stage 37 Section 12)."""

    os_name: str
    os_release: str
    python_version: str
    cuda_available: bool
    gpu_model: Optional[str]
    gpu_count: int
    per_gpu_vram_gb: Optional[float]
    total_ram_gb: float
    free_disk_gb: float
    transformers_version: Optional[str]
    peft_version: Optional[str]
    torch_version: Optional[str]
    classification: str = InfrastructureClassification.EXTERNAL_GPU_REQUIRED.value
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HardwareAuditReport:
        return cls(**data)


@dataclass
class ArchitectureStabilityReport:
    """Multi-dimensional stability verification report (Stage 37 Section 5)."""

    root_prompt_status: str = ReadinessDimensionStatus.STABLE.value
    topology_status: str = ReadinessDimensionStatus.STABLE.value
    retrieval_status: str = ReadinessDimensionStatus.STABLE.value
    testing_status: str = ReadinessDimensionStatus.STABLE.value
    recovery_status: str = ReadinessDimensionStatus.STABLE.value
    tools_status: str = ReadinessDimensionStatus.STABLE.value
    skills_status: str = ReadinessDimensionStatus.STABLE.value
    benchmark_status: str = ReadinessDimensionStatus.STABLE.value
    overall_status: str = ReadinessDimensionStatus.STABLE.value
    dimension_hashes: dict[str, str] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureStabilityReport:
        return cls(**data)


@dataclass
class PromptStabilityReport:
    """Root prompt stability audit report (Stage 37 Section 10)."""

    status: str
    prompt_hash: str
    expected_hash: str
    is_frozen: bool
    commits_count: int
    history: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptStabilityReport:
        return cls(**data)


@dataclass
class BenchmarkStabilityReport:
    """Benchmark split reproducibility verification report (Stage 37 Section 6)."""

    source_sha256: str
    manifest_sha256: str
    dev_file_sha256: str
    validation_file_sha256: str
    held_out_file_sha256: str
    held_out_lock_sha256: str
    total_tasks_count: int
    status: str = BenchmarkStabilityStatus.BENCHMARK_STABLE.value
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkStabilityReport:
        return cls(**data)


@dataclass
class FailureCategoryAudit:
    """Audit of an individual failure category's LoRA readiness (Stage 37 Section 7)."""

    category_name: str
    definition: str
    observable_evidence: str
    reliably_distinguishable: bool
    live_observations_count: int
    fixture_observations_count: int
    learnable_by_lora: bool
    too_broad: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureCategoryAudit:
        return cls(**data)


@dataclass
class ControlledLoRAExperimentContract:
    """Machine-readable experiment contract for Stage 39 (Stage 37 Section 14, 15)."""

    baseline_candidate: str = "M0"
    candidate_id_placeholder: str = "L1"
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    adapter_role: str = "ROOT_AGENT_ADAPTER"
    primary_objective: str = ""
    training_data_source_placeholder: str = "STAGE_38_TRAJECTORY_DATASET"
    training_data_hash_placeholder: str = "PENDING_STAGE_38"
    train_split_placeholder: str = "dev"
    validation_split_placeholder: str = "validation"
    held_out_split: str = "held_out"
    prompt_hash: str = ""
    skill_hashes: dict[str, str] = field(default_factory=dict)
    tool_contract_hashes: dict[str, str] = field(default_factory=dict)
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    sampling_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 16384,
            "thinking_config": {
                "thinking_level": "high",
                "thinking_budget": 4096,
                "include_thoughts": True,
            },
        }
    )
    evaluation_protocol: str = "CLEAN_COPY_EVALUATOR_PAIRED_COMPARISON"
    primary_metric: str = "command_redundancy_count"
    secondary_metrics: list[str] = field(
        default_factory=lambda: [
            "task_success_rate",
            "target_failure_rate",
            "tool_call_count",
            "turn_count",
            "runtime_ms",
        ]
    )
    cost_metrics: list[str] = field(
        default_factory=lambda: [
            "adapter_size_bytes",
            "training_hours_l4",
            "inference_latency_delta_ms",
        ]
    )
    promotion_gate: str = "VALIDATION_IMPROVEMENT_AND_NO_HELD_OUT_REGRESSION"
    stop_conditions: list[str] = field(
        default_factory=lambda: [
            "HELD_OUT_REGRESSION",
            "TOOL_SCHEMA_VIOLATION",
            "NON_TARGET_BEHAVIOR_COLLATERAL_DROP",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlledLoRAExperimentContract:
        return cls(**data)


@dataclass
class BaselineSnapshot:
    """Machine-readable immutable baseline snapshot for L0 (Stage 37 Section 4)."""

    git_commit: str
    model_id: str
    prompt_hash: str
    topology_identity: str
    retrieval_policy_hash: str
    testing_policy_hash: str
    recovery_policy_hash: str
    skill_hashes: dict[str, str]
    benchmark_source_hash: str
    dev_manifest_hash: str
    validation_manifest_hash: str
    held_out_manifest_hash: str
    held_out_lock_hash: str
    evaluator_version: str
    tool_contract_hashes: dict[str, str]
    python_version: str
    package_versions: dict[str, Optional[str]]
    operating_system: str
    gpu_info: str
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineSnapshot:
        return cls(**data)


@dataclass
class L0Manifest:
    """Authoritative reproducibility manifest for L0 (Stage 37 Section 18)."""

    stage: str = "Stage 37"
    candidate_id: str = "L0"
    git_commit: str = ""
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    prompt_hash: str = ""
    skill_hashes: dict[str, str] = field(default_factory=dict)
    benchmark_hashes: dict[str, str] = field(default_factory=dict)
    tool_contract_hashes: dict[str, str] = field(default_factory=dict)
    retrieval_policy_hash: str = ""
    testing_policy_hash: str = ""
    recovery_policy_hash: str = ""
    topology: str = "root_only"
    hardware: dict[str, Any] = field(default_factory=dict)
    software_versions: dict[str, Any] = field(default_factory=dict)
    objective_id: str = "NONE"
    evidence_mode: str = "FIXTURE"
    decision: str = L0Decision.NOT_READY.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> L0Manifest:
        return cls(**data)
