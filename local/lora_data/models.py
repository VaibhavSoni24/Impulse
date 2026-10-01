"""Data models and schema definitions for LoRA Training Data Curation (Stage 38).

Targeting ONLY:
OBJ-TOOL-DISCIPLINE: Reduce Repeated Failing Commands & Improve Tool Invocation Correctness.

Provides schemas for:
- ToolDisciplineTrainingExample: Single curated training record
- DecisionSignal: Detailed evidence-to-decision action pair
- ToolCallRecord: Normalized tool invocation trace
- ProvenanceRecord: Legal, license, and repository source tracking
- QualityVector: Multi-dimensional quality evaluation vector
- DatasetManifest: Machine-readable dataset metadata and checksums
- Stage39TrainingContract: Formal contract linking Stage 38 data to Stage 39 PEFT execution
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceMode(str, Enum):
    """Evidence mode classification (AGENTS.md and Stage 38 Section 21)."""

    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class SplitType(str, Enum):
    """Dataset partition splits (Stage 38 Section 13, 25)."""

    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    HELD_OUT = "HELD_OUT"


class ContrastiveType(str, Enum):
    """Contrastive pairing status (Stage 38 Section 11)."""

    PAIRED_CONTRASTIVE = "PAIRED_CONTRASTIVE"
    POSITIVE_ONLY = "POSITIVE_ONLY"
    NEGATIVE_ONLY = "NEGATIVE_ONLY"
    UNPAIRED = "UNPAIRED"


class QualityStatus(str, Enum):
    """Quality classification status (Stage 38 Section 18)."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class RejectionReason(str, Enum):
    """Explicit quality and policy rejection categories (Stage 38 Section 18)."""

    REJECT_NO_DECISION_SIGNAL = "REJECT_NO_DECISION_SIGNAL"
    REJECT_NO_PROVENANCE = "REJECT_NO_PROVENANCE"
    REJECT_LEAKAGE = "REJECT_LEAKAGE"
    REJECT_SECRET = "REJECT_SECRET"
    REJECT_INFRASTRUCTURE_ONLY = "REJECT_INFRASTRUCTURE_ONLY"
    REJECT_AMBIGUOUS = "REJECT_AMBIGUOUS"
    REJECT_DUPLICATE = "REJECT_DUPLICATE"
    REJECT_UNSAFE = "REJECT_UNSAFE"
    REJECT_NOT_PERMITTED = "REJECT_NOT_PERMITTED"
    REJECT_FIXTURE_ISOLATION = "REJECT_FIXTURE_ISOLATION"
    REJECT_OBJECTIVE_MISMATCH = "REJECT_OBJECTIVE_MISMATCH"


class LicenseStatus(str, Enum):
    """Source licensing and permission classification (Stage 38 Section 16)."""

    PERMITTED = "PERMITTED"
    PERMITTED_WITH_ATTRIBUTION = "PERMITTED_WITH_ATTRIBUTION"
    UNKNOWN = "UNKNOWN"
    NOT_PERMITTED = "NOT_PERMITTED"


class DatasetStatus(str, Enum):
    """Authoritative Stage 38 dataset status gate (Stage 38 Section 22, 36)."""

    DATASET_READY = "DATASET_READY"
    BLOCKED_BY_DATA = "BLOCKED_BY_DATA"
    NO_ELIGIBLE_TRAINING_DATA = "NO_ELIGIBLE_TRAINING_DATA"


@dataclass
class ToolCallRecord:
    """Audit of an individual tool call within a training trajectory."""

    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    exit_code: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallRecord:
        return cls(**data)


@dataclass
class ProvenanceRecord:
    """Provenance and licensing metadata for a training trajectory (Stage 38 Section 16)."""

    source_name: str
    source_location: str
    source_type: str  # e.g. "evaluation_trace", "curated_demonstration", "fixture"
    license: str
    license_evidence: str
    allowed_for_training: bool
    attribution_required: bool
    redistribution_allowed: bool
    license_status: str = LicenseStatus.PERMITTED.value
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceRecord:
        return cls(**data)


@dataclass
class QualityVector:
    """Multi-dimensional quality evaluation vector (Stage 38 Section 19)."""

    evidence_completeness: float = 1.0  # 0.0 to 1.0
    objective_alignment: float = 1.0  # 1.0 if strictly targeting OBJ-TOOL-DISCIPLINE
    trajectory_completeness: float = 1.0
    tool_specificity: float = 1.0
    outcome_verifiability: float = 1.0
    provenance_completeness: float = 1.0
    safety_status: str = "SAFE"  # "SAFE", "UNSAFE"

    def is_eligible(self) -> bool:
        """Determines if the quality vector satisfies strict inclusion criteria."""
        return (
            self.evidence_completeness >= 0.8
            and self.objective_alignment >= 0.95
            and self.trajectory_completeness >= 0.8
            and self.outcome_verifiability >= 0.8
            and self.provenance_completeness >= 0.9
            and self.safety_status == "SAFE"
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityVector:
        return cls(**data)


@dataclass
class ToolDisciplineTrainingExample:
    """Strict machine-readable training record (Stage 38 Section 7, 8, 24)."""

    example_id: str
    dataset_id: str = "L0-TOOL-DISCIPLINE-DATA-v1"
    split: str = SplitType.TRAIN.value
    task_id: str = ""
    repo: str = ""
    base_commit: str = ""
    objective_id: str = "OBJ-TOOL-DISCIPLINE"
    failure_class: str = "COMMAND"
    trajectory_status: str = "RECOVERED"
    situation: str = ""
    evidence: list[str] = field(default_factory=list)
    tool_sequence: list[dict[str, Any]] = field(default_factory=list)
    preferred_behavior: dict[str, Any] = field(default_factory=dict)
    negative_behavior: dict[str, Any] = field(default_factory=dict)
    contrastive_type: str = ContrastiveType.PAIRED_CONTRASTIVE.value
    provenance: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    validation_signal: str = ""
    sanitized: bool = True
    redaction_count: int = 0
    evidence_mode: str = EvidenceMode.LIVE.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolDisciplineTrainingExample:
        return cls(**data)


@dataclass
class DatasetManifest:
    """Authoritative dataset-level reproducibility manifest (Stage 38 Section 23)."""

    dataset_id: str = "L0-TOOL-DISCIPLINE-DATA-v1"
    dataset_version: str = "1.0.0"
    parent_git_commit: str = "0d66dd9cf6b8e23289c3a92bda4d12268d2b8920"
    objective_id: str = "OBJ-TOOL-DISCIPLINE"
    source_manifests: list[str] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    selection_policy: str = "TOOL_DISCIPLINE_EVIDENCE_FIRST"
    split_policy: str = "DETERMINISTIC_TASK_DISJOINT"
    seed: int = 42
    train_count: int = 0
    validation_count: int = 0
    excluded_count: int = 0
    duplicate_count: int = 0
    leakage_results: dict[str, Any] = field(default_factory=dict)
    quality_results: dict[str, Any] = field(default_factory=dict)
    license_results: dict[str, Any] = field(default_factory=dict)
    sanitization_results: dict[str, Any] = field(default_factory=dict)
    hardware_note: str = "EXTERNAL_GPU_REQUIRED"
    evidence_modes: dict[str, int] = field(default_factory=dict)
    dataset_status: str = DatasetStatus.BLOCKED_BY_DATA.value
    creation_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    dataset_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        return cls(**data)


@dataclass
class Stage39TrainingContract:
    """Machine-readable training contract connecting Stage 38 to Stage 39 (Stage 38 Section 26)."""

    base_model: str = "gemma-4-31b-it-qat-w4a16-ct"
    objective_id: str = "OBJ-TOOL-DISCIPLINE"
    dataset_id: str = "L0-TOOL-DISCIPLINE-DATA-v1"
    dataset_version: str = "1.0.0"
    train_manifest_hash: str = ""
    validation_manifest_hash: str = ""
    held_out_manifest_hash: str = ""
    prompt_hash: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    tool_contract_hashes: dict[str, str] = field(default_factory=dict)
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    adapter_role: str = "ROOT_AGENT_ADAPTER"
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
    control_candidate: str = "M0"
    candidate_identifier: str = "L1"
    promotion_gate: str = "VALIDATION_IMPROVEMENT_AND_NO_HELD_OUT_REGRESSION"
    stop_conditions: list[str] = field(
        default_factory=lambda: [
            "HELD_OUT_REGRESSION",
            "TOOL_SCHEMA_VIOLATION",
            "NON_TARGET_BEHAVIOR_COLLATERAL_DROP",
            "COLLATERAL_PASS_TO_FAIL_REGRESSION",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stage39TrainingContract:
        return cls(**data)
