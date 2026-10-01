"""Data models and schemas for Stage 39 LoRA Training subsystem.

Defines schemas for:
- TrainingStatus & HardwareStatus enums
- TrainingConfig: Complete configuration schema with unselected parameter detection
- HardwareAuditReport: Detailed runtime hardware and environment audit
- TrainingMetrics: Training performance and telemetry metrics
- RunManifest: Comprehensive machine-readable execution manifest
- BlockedRunRecord: Deterministic audit record for data/hardware blocked runs
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TrainingStatus(str, Enum):
    """Authoritative training execution states."""

    TRAINING_COMPLETED = "TRAINING_COMPLETED"
    BLOCKED_BY_DATA = "BLOCKED_BY_DATA"
    BLOCKED_BY_HARDWARE = "BLOCKED_BY_HARDWARE"
    TRAINING_FAILED = "TRAINING_FAILED"
    DRY_RUN_PASSED = "DRY_RUN_PASSED"
    NOT_RUN = "NOT_RUN"


class HardwareStatus(str, Enum):
    """Hardware capability classification for training (Section 8)."""

    TRAINING_HARDWARE_READY = "TRAINING_HARDWARE_READY"
    TRAINING_HARDWARE_UNAVAILABLE = "TRAINING_HARDWARE_UNAVAILABLE"
    TRAINING_SOFTWARE_INCOMPATIBLE = "TRAINING_SOFTWARE_INCOMPATIBLE"
    TRAINING_HARDWARE_UNKNOWN = "TRAINING_HARDWARE_UNKNOWN"


class ExecutionMode(str, Enum):
    """Execution mode distinguishing real training from dry-run or test mocks."""

    REAL_TRAINING = "REAL_TRAINING"
    DRY_RUN = "DRY_RUN"
    VERIFY_ONLY = "VERIFY_ONLY"
    TRAINING_ORCHESTRATION_FIXTURE = "TRAINING_ORCHESTRATION_FIXTURE"


class Stage39Decision(str, Enum):
    """Authoritative Stage 39 completion gate decisions (Section 32)."""

    STAGE_39_COMPLETE_TRAINING_PIPELINE_VERIFIED_TRAINING_BLOCKED_BY_DATA = (
        "STAGE 39 COMPLETE, TRAINING PIPELINE VERIFIED, TRAINING BLOCKED BY DATA"
    )
    STAGE_39_COMPLETE_ADAPTER_TRAINED_AND_VERIFIED = (
        "STAGE 39 COMPLETE, ADAPTER TRAINED AND VERIFIED"
    )
    STAGE_39_BLOCKED_EVIDENCE_RECORDED = (
        "STAGE 39 BLOCKED, EVIDENCE RECORDED"
    )


UNSELECTED = "UNSELECTED"


@dataclass
class HardwareAuditReport:
    """Audit of host hardware and ML software runtime stack (Section 8)."""

    os_name: str
    os_release: str
    python_version: str
    cuda_available: bool
    gpu_model: Optional[str]
    gpu_count: int
    per_gpu_vram_gb: Optional[float]
    total_ram_gb: float
    free_disk_gb: float
    torch_version: Optional[str]
    transformers_version: Optional[str]
    peft_version: Optional[str]
    classification: str = HardwareStatus.TRAINING_HARDWARE_UNAVAILABLE.value
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HardwareAuditReport:
        return cls(**data)


@dataclass
class TrainingConfig:
    """Versioned LoRA training configuration schema (Section 11)."""

    candidate_id: str = "L1"
    base_model: str = "gemma-4-31b-it-qat-w4a16-ct"
    objective_id: str = "OBJ-TOOL-DISCIPLINE"
    dataset_id: str = "L0-TOOL-DISCIPLINE-DATA-v1"
    dataset_version: str = "1.0.0"
    train_manifest_hash: str = ""
    validation_manifest_hash: str = ""
    prompt_hash: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    tool_contract_hashes: dict[str, str] = field(default_factory=dict)
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"

    # Hyperparameters - UNSELECTED by default until experimentally tuned
    rank: Any = UNSELECTED
    alpha: Any = UNSELECTED
    dropout: Any = UNSELECTED
    learning_rate: Any = UNSELECTED
    batch_size: Any = UNSELECTED
    gradient_accumulation_steps: Any = UNSELECTED
    epochs: Any = UNSELECTED
    max_steps: Any = UNSELECTED
    sequence_length: Any = UNSELECTED
    seed: int = 42
    precision: str = "bf16"
    gradient_checkpointing: bool = True
    output_dir: str = "experiments/lora/runs/L1"
    software_versions: dict[str, Optional[str]] = field(default_factory=dict)

    def get_unresolved_hyperparameters(self) -> list[str]:
        """Identifies mandatory hyperparameters that remain UNSELECTED."""
        mandatory = [
            ("rank", self.rank),
            ("alpha", self.alpha),
            ("dropout", self.dropout),
            ("learning_rate", self.learning_rate),
            ("batch_size", self.batch_size),
            ("gradient_accumulation_steps", self.gradient_accumulation_steps),
            ("epochs", self.epochs),
            ("sequence_length", self.sequence_length),
        ]
        return [name for name, val in mandatory if val == UNSELECTED or val is None]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingConfig:
        return cls(**data)


@dataclass
class TrainingMetrics:
    """Telemetry and performance metrics for a training run (Section 21)."""

    training_loss: Optional[float] = None
    validation_loss: Optional[float] = None
    steps_completed: int = 0
    total_steps: int = 0
    epochs_completed: float = 0.0
    learning_rate: Optional[float] = None
    effective_batch_size: int = 0
    runtime_ms: float = 0.0
    peak_gpu_memory_gb: Optional[float] = None
    throughput_examples_sec: Optional[float] = None
    status: str = TrainingStatus.NOT_RUN.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingMetrics:
        return cls(**data)


@dataclass
class RunManifest:
    """Comprehensive machine-readable execution manifest for an actual run (Section 18)."""

    run_id: str
    candidate_id: str = "L1"
    parent_commit: str = "65a0cc0f8b6f218fb2650ad1587475d4f48fc799"
    base_model: str = "gemma-4-31b-it-qat-w4a16-ct"
    dataset_id: str = "L0-TOOL-DISCIPLINE-DATA-v1"
    dataset_version: str = "1.0.0"
    dataset_sha256: str = ""
    train_hash: str = ""
    validation_hash: str = ""
    objective_id: str = "OBJ-TOOL-DISCIPLINE"
    prompt_hash: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    skill_hashes: dict[str, str] = field(default_factory=dict)
    tool_contract_hashes: dict[str, str] = field(default_factory=dict)
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    hardware: dict[str, Any] = field(default_factory=dict)
    software_versions: dict[str, Optional[str]] = field(default_factory=dict)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    seed: int = 42
    start_time: str = ""
    end_time: str = ""
    status: str = TrainingStatus.NOT_RUN.value
    adapter_sha256: Optional[str] = None
    execution_mode: str = ExecutionMode.REAL_TRAINING.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        return cls(**data)


@dataclass
class BlockedRunRecord:
    """Deterministic audit record emitted when training is prohibited by a gate."""

    status: str
    reason: str
    details: dict[str, Any]
    hardware_status: str
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
