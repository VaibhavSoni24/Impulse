"""Data models, schemas, and enums for Stage 41 Multi-Adapter Experimentation.

Defines schemas for:
- Role adapter assignments (ROOT, SCOUT, REVIEWER)
- Multi-adapter experiment matrix (MA0 through MA7)
- Prerequisite validation results
- Role-specific and cost metrics
- Run manifests and audit reports
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AdapterRole(str, Enum):
    """Specialized agent roles supported for adapter assignment (Section 5, 8)."""
    ROOT = "root"          # Coding/reasoning behavior
    SCOUT = "scout"        # Repository localization
    REVIEWER = "reviewer"  # Code review and defect detection


class AdapterStatus(str, Enum):
    """Validation lifecycle status for an individual role adapter (Section 6)."""
    UNAVAILABLE = "UNAVAILABLE"
    TRAINED = "TRAINED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class MultiAdapterExecutionStatus(str, Enum):
    """Execution status for multi-adapter experiments."""
    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Stage41Decision(str, Enum):
    """Authoritative Stage 41 completion statuses (Section 33)."""
    STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE = (
        "STAGE 41 COMPLETE, MULTI-ADAPTER FRAMEWORK VERIFIED, BLOCKED BY SINGLE-ADAPTER PREREQUISITE"
    )
    STAGE_41_COMPLETE_EXPERIMENT_EXECUTED_AND_VERIFIED = (
        "STAGE 41 COMPLETE, MULTI-ADAPTER EXPERIMENT EXECUTED AND VERIFIED"
    )
    STAGE_41_BLOCKED_EVIDENCE_RECORDED = (
        "STAGE 41 BLOCKED, EVIDENCE RECORDED"
    )


# Authoritative base model and baseline specifications
BASE_MODEL_IDENTIFIER = "gemma-4-31b-it-qat-w4a16-ct"
FROZEN_ROOT_PROMPT_HASH = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"


@dataclass
class RoleAdapterAssignment:
    """Assignment of a verified adapter to a specific agent role (Section 6, 8)."""
    role: AdapterRole
    adapter_id: Optional[str] = None
    adapter_path: Optional[str] = None
    adapter_sha256: Optional[str] = None
    adapter_config_hash: Optional[str] = None
    status: AdapterStatus = AdapterStatus.UNAVAILABLE
    objective_id: Optional[str] = None
    base_model: str = BASE_MODEL_IDENTIFIER
    training_run_id: Optional[str] = None
    provenance: Optional[str] = None
    allowed_agent_roles: List[AdapterRole] = field(default_factory=lambda: [AdapterRole.ROOT])

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        data["status"] = self.status.value
        data["allowed_agent_roles"] = [r.value for r in self.allowed_agent_roles]
        return data


@dataclass
class MultiAdapterCandidateConfig:
    """Configuration for a multi-adapter candidate in the experiment matrix (Section 7, 12)."""
    candidate_id: str                      # e.g., MA0, MA1, ..., MA7
    description: str
    base_model: str = BASE_MODEL_IDENTIFIER
    roles: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=lambda: {
        AdapterRole.ROOT.value: None,
        AdapterRole.SCOUT.value: None,
        AdapterRole.REVIEWER.value: None,
    })
    status: MultiAdapterExecutionStatus = MultiAdapterExecutionStatus.NOT_RUN
    prompt_hash: str = FROZEN_ROOT_PROMPT_HASH
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    benchmark_split: str = "dev"
    status_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class PrerequisiteCheckResult:
    """Result of checking the Stage 41 scientific prerequisite (Section 3, 11)."""
    eligible: bool
    single_adapter_validated: bool
    blocking_reasons: List[str]
    adapter_id: Optional[str] = None
    adapter_sha256: Optional[str] = None
    stage40_run_id: Optional[str] = None
    target_metric: str = "command_redundancy_count"
    validation_result: Optional[str] = None
    held_out_result: Optional[str] = None
    reproducibility_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiAdapterMetrics:
    """Specialized evaluation metrics for multi-adapter execution (Section 15, 16, 17)."""
    candidate_id: str
    task_count: int = 0
    overall_task_success_rate: float = 0.0
    root_metrics: Dict[str, Any] = field(default_factory=lambda: {
        "tool_discipline_score": "UNAVAILABLE",
        "repeated_failing_command_count": 0,
        "patch_validity_rate": 0.0,
    })
    scout_metrics: Dict[str, Any] = field(default_factory=lambda: {
        "localization_success_rate": "UNAVAILABLE",
        "irrelevant_localization_rate": "UNAVAILABLE",
        "scout_inference_latency_ms": 0.0,
    })
    reviewer_metrics: Dict[str, Any] = field(default_factory=lambda: {
        "defects_detected_count": "UNAVAILABLE",
        "false_positive_review_rate": "UNAVAILABLE",
        "reviewer_latency_ms": 0.0,
    })
    cost_metrics: Dict[str, Any] = field(default_factory=lambda: {
        "active_adapter_count": 0,
        "total_adapter_size_bytes": 0,
        "adapter_init_latency_ms": 0.0,
        "total_runtime_ms": 0.0,
        "total_turns": 0,
        "total_tool_calls": 0,
    })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MultiAdapterRunManifest:
    """Full reproducibility manifest for a multi-adapter run (Section 1, 15)."""
    run_id: str
    candidate_id: str
    parent_commit: str
    base_model: str = BASE_MODEL_IDENTIFIER
    role_mapping: Dict[str, Optional[str]] = field(default_factory=dict)
    prompt_hash: str = FROZEN_ROOT_PROMPT_HASH
    retrieval_version: str = "R0"
    testing_version: str = "T0"
    recovery_version: str = "REC0"
    topology: str = "root_only"
    benchmark_split: str = "dev"
    start_time: str = ""
    end_time: str = ""
    status: MultiAdapterExecutionStatus = MultiAdapterExecutionStatus.NOT_RUN
    evidence_mode: str = "REAL"
    manifest_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class MultiAdapterReport:
    """Comprehensive Stage 41 audit report data structure (Section 23)."""
    report_id: str
    parent_commit: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    prerequisite_result: Optional[PrerequisiteCheckResult] = None
    matrix_candidates: Dict[str, MultiAdapterCandidateConfig] = field(default_factory=dict)
    active_config: Optional[MultiAdapterCandidateConfig] = None
    metrics: Optional[MultiAdapterMetrics] = None
    overall_status: Stage41Decision = Stage41Decision.STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE
    decision_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "report_id": self.report_id,
            "parent_commit": self.parent_commit,
            "created_at": self.created_at,
            "overall_status": self.overall_status.value,
            "decision_reason": self.decision_reason,
            "prerequisite_result": self.prerequisite_result.to_dict() if self.prerequisite_result else None,
            "matrix_candidates": {k: v.to_dict() for k, v in self.matrix_candidates.items()},
            "active_config": self.active_config.to_dict() if self.active_config else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }
        return data
