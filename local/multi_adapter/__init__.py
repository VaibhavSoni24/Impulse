"""IMPULSE Multi-Adapter Experimentation Subsystem (Stage 41).

Provides multi-adapter orchestration, role isolation, and prerequisite gating.
"""

from __future__ import annotations

from local.multi_adapter.artifacts import MultiAdapterArtifactManager
from local.multi_adapter.errors import (
    BaseModelMismatchError,
    DryRunError,
    MultiAdapterError,
    RoleConflictError,
    SingleAdapterPrerequisiteError,
    UnvalidatedAdapterError,
)
from local.multi_adapter.evaluator import MultiAdapterEvaluator
from local.multi_adapter.matrix import MultiAdapterMatrixGenerator
from local.multi_adapter.models import (
    AdapterRole,
    AdapterStatus,
    BASE_MODEL_IDENTIFIER,
    FROZEN_ROOT_PROMPT_HASH,
    MultiAdapterCandidateConfig,
    MultiAdapterExecutionStatus,
    MultiAdapterMetrics,
    MultiAdapterReport,
    MultiAdapterRunManifest,
    PrerequisiteCheckResult,
    RoleAdapterAssignment,
    Stage41Decision,
)
from local.multi_adapter.prerequisites import SingleAdapterPrerequisiteChecker
from local.multi_adapter.reporting import MultiAdapterReporter
from local.multi_adapter.validation import MultiAdapterConfigValidator

__all__ = [
    "MultiAdapterError",
    "SingleAdapterPrerequisiteError",
    "RoleConflictError",
    "BaseModelMismatchError",
    "UnvalidatedAdapterError",
    "DryRunError",
    "AdapterRole",
    "AdapterStatus",
    "MultiAdapterExecutionStatus",
    "Stage41Decision",
    "BASE_MODEL_IDENTIFIER",
    "FROZEN_ROOT_PROMPT_HASH",
    "RoleAdapterAssignment",
    "MultiAdapterCandidateConfig",
    "PrerequisiteCheckResult",
    "MultiAdapterMetrics",
    "MultiAdapterRunManifest",
    "MultiAdapterReport",
    "SingleAdapterPrerequisiteChecker",
    "MultiAdapterMatrixGenerator",
    "MultiAdapterConfigValidator",
    "MultiAdapterArtifactManager",
    "MultiAdapterReporter",
    "MultiAdapterEvaluator",
]
