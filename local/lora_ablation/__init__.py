"""IMPULSE LoRA Ablation Subsystem (Stage 40).

Provides the controlled A/B/C/D evaluation framework:
- Condition A: BASELINE_NO_ADAPTER
- Condition B: L1_ADAPTER
- Condition C: L1_ADAPTER_PROMPT_VARIANT
- Condition D: L1_ADAPTER_RETRIEVAL_VARIANT
"""

from __future__ import annotations

from local.lora_ablation.adapter_gate import AdapterGateValidator
from local.lora_ablation.artifacts import AblationArtifactManager
from local.lora_ablation.conditions import ConditionManager
from local.lora_ablation.errors import (
    AblationError,
    DryRunError,
    HeldOutViolationError,
    InvalidAdapterError,
    InvarianceViolationError,
    MissingAdapterError,
    PromotionGateError,
    SecondaryConditionBlockedError,
)
from local.lora_ablation.evaluator import AblationEvaluator
from local.lora_ablation.invariance import AblationInvarianceChecker
from local.lora_ablation.metrics import ToolDisciplineMetricsCalculator
from local.lora_ablation.models import (
    AblationAggregateMetrics,
    AblationComparisonReport,
    AblationConditionConfig,
    AblationRunManifest,
    AdapterArtifactMetadata,
    AdapterGateStatus,
    CollateralStatus,
    ConditionStatus,
    ConditionType,
    FROZEN_BASELINE_DIMENSIONS,
    FROZEN_TOOL_CONTRACT_HASHES,
    PromotionGateDecision,
    Stage40Decision,
    TargetFailureTransition,
    TaskEvaluationRecord,
    TaskPairTransition,
)
from local.lora_ablation.paired import TaskPairedAnalyzer
from local.lora_ablation.promotion import CandidatePromotionGate
from local.lora_ablation.reporting import AblationReporter

__all__ = [
    "AblationError",
    "MissingAdapterError",
    "InvalidAdapterError",
    "InvarianceViolationError",
    "SecondaryConditionBlockedError",
    "HeldOutViolationError",
    "PromotionGateError",
    "DryRunError",
    "ConditionType",
    "ConditionStatus",
    "AdapterGateStatus",
    "TaskPairTransition",
    "TargetFailureTransition",
    "CollateralStatus",
    "PromotionGateDecision",
    "Stage40Decision",
    "FROZEN_BASELINE_DIMENSIONS",
    "FROZEN_TOOL_CONTRACT_HASHES",
    "AdapterArtifactMetadata",
    "AblationConditionConfig",
    "TaskEvaluationRecord",
    "AblationAggregateMetrics",
    "AblationRunManifest",
    "AblationComparisonReport",
    "AdapterGateValidator",
    "ConditionManager",
    "AblationInvarianceChecker",
    "ToolDisciplineMetricsCalculator",
    "TaskPairedAnalyzer",
    "CandidatePromotionGate",
    "AblationArtifactManager",
    "AblationReporter",
    "AblationEvaluator",
]
