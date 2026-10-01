"""LoRA Training Subsystem for Stage 39 of IMPULSE."""

from local.lora_train.artifacts import ArtifactManager
from local.lora_train.config import (
    get_default_training_config,
    load_training_config,
    save_training_config,
    validate_hyperparameters_for_execution,
)
from local.lora_train.dataset import ToolDisciplineDatasetLoader
from local.lora_train.errors import (
    DataGateBlockedError,
    FixtureSafetyError,
    HardwareGateBlockedError,
    InvarianceViolationError,
    LoRATrainingError,
    UnresolvedHyperparameterError,
)
from local.lora_train.hardware import audit_training_hardware
from local.lora_train.invariance import InvarianceChecker
from local.lora_train.metrics import MetricsTracker, get_blocked_metrics
from local.lora_train.models import (
    BlockedRunRecord,
    ExecutionMode,
    HardwareAuditReport,
    HardwareStatus,
    RunManifest,
    Stage39Decision,
    TrainingConfig,
    TrainingMetrics,
    TrainingStatus,
    UNSELECTED,
)
from local.lora_train.reporting import (
    generate_stage39_detailed_report,
    generate_stage39_root_report,
)
from local.lora_train.runner import LoRATrainingRunner
from local.lora_train.validation import DataGateValidator

__all__ = [
    "ArtifactManager",
    "BlockedRunRecord",
    "DataGateBlockedError",
    "DataGateValidator",
    "ExecutionMode",
    "FixtureSafetyError",
    "HardwareAuditReport",
    "HardwareGateBlockedError",
    "HardwareStatus",
    "InvarianceChecker",
    "InvarianceViolationError",
    "LoRATrainingError",
    "LoRATrainingRunner",
    "MetricsTracker",
    "RunManifest",
    "Stage39Decision",
    "ToolDisciplineDatasetLoader",
    "TrainingConfig",
    "TrainingMetrics",
    "TrainingStatus",
    "UNSELECTED",
    "UnresolvedHyperparameterError",
    "audit_training_hardware",
    "generate_stage39_detailed_report",
    "generate_stage39_root_report",
    "get_blocked_metrics",
    "get_default_training_config",
    "load_training_config",
    "save_training_config",
    "validate_hyperparameters_for_execution",
]
