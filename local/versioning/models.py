"""Data models, enums, and schemas for Stage 43 Candidate Versioning.

Establishes:
- Canonical candidate identification vocabulary
- Strict immutable candidate status and promotion models
- Manifest structure and JSON serialization
- Append-only lifecycle event model
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CandidateStatus(str, Enum):
    """Lifecycle statuses for candidate versions."""
    DRAFT = "DRAFT"
    CONFIGURED = "CONFIGURED"
    SMOKE_PASSED = "SMOKE_PASSED"
    VALIDATED = "VALIDATED"
    HELD_OUT_CONFIRMED = "HELD_OUT_CONFIRMED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"
    RESERVED = "RESERVED"


class PromotionStatus(str, Enum):
    """Promotion and selection status separate from lifecycle status."""
    NOT_PROMOTED = "NOT_PROMOTED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    PENDING_EVALUATION = "PENDING_EVALUATION"
    BLOCKED = "BLOCKED"
    RESERVED = "RESERVED"


class ExperimentDimension(str, Enum):
    """Controlled primary experiment dimensions."""
    BASELINE = "baseline"
    PROMPT = "prompt"
    STATE = "state"
    RETRIEVAL = "retrieval"
    TESTING = "testing"
    RECOVERY = "recovery"
    TOPOLOGY = "topology"
    SKILL = "skill"
    ADAPTER = "adapter"
    MULTI_ADAPTER = "multi_adapter"
    PACKAGING = "packaging"
    COMBINED_ABLATION = "combined_ablation"


class EvidenceMode(str, Enum):
    """Evidence validity classifications."""
    LIVE = "LIVE"
    FIXTURE = "FIXTURE"
    INFRASTRUCTURE_ONLY = "INFRASTRUCTURE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class LifecycleEventType(str, Enum):
    """Types of candidate lifecycle transitions."""
    REGISTERED = "REGISTERED"
    SMOKE_PASSED = "SMOKE_PASSED"
    VALIDATED = "VALIDATED"
    HELD_OUT_CONFIRMED = "HELD_OUT_CONFIRMED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"
    METADATA_CORRECTED = "METADATA_CORRECTED"


class Stage43Decision(str, Enum):
    """Authoritative Stage 43 decisions."""
    COMPLETE_VERIFIED = "STAGE 43 COMPLETE, CANDIDATE VERSIONING VERIFIED"
    BLOCKED = "STAGE 43 BLOCKED, EVIDENCE RECORDED"


@dataclass
class ChangeSummary:
    """Detailed change contract for a candidate relative to its parent."""
    primary_dimension: str
    changed_components: List[str] = field(default_factory=list)
    unchanged_components: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateManifest:
    """Canonical immutable manifest for a versioned candidate."""
    candidate_id: str
    candidate_version: str
    status: str
    parent_candidate_id: Optional[str]
    git_commit: str
    created_at: str
    description: str
    experiment_type: str
    primary_dimension: str
    change_summary: Dict[str, Any]
    base_model: str
    model_revision: Optional[str]
    root_prompt_hash: str
    skill_hashes: Dict[str, str]
    sub_agent_hashes: Dict[str, str]
    tool_contract_hashes: Dict[str, str]
    retrieval_version: str
    testing_version: str
    recovery_version: str
    topology: str
    adapter_id: Optional[str]
    adapter_sha256: Optional[str]
    benchmark_manifest_hash: str
    dev_split_hash: str
    validation_split_hash: str
    held_out_split_hash: str
    runtime_settings: Dict[str, Any]
    sampling_settings: Dict[str, Any]
    compute_environment_id: str
    evidence_mode: str
    result_status: str
    promotion_status: str
    manifest_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LifecycleEvent:
    """Immutable audit trail record for candidate lifecycle transitions."""
    candidate_id: str
    event_type: str
    timestamp: str
    git_commit: str
    actor: str
    reason: str
    source_manifest_hash: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonResult:
    """Deterministic comparison between parent and candidate manifests."""
    parent_id: Optional[str]
    candidate_id: str
    is_multi_dimension: bool
    changed_dimensions: List[str]
    unchanged_dimensions: List[str]
    hash_changes: Dict[str, Dict[str, Optional[str]]]
    configuration_changes: Dict[str, Dict[str, Any]]
    benchmark_changes: Dict[str, Dict[str, Optional[str]]]
    adapter_changes: Dict[str, Dict[str, Optional[str]]]
    runtime_changes: Dict[str, Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CurrentBestPointer:
    """Machine-readable pointer to the active best candidate."""
    candidate_id: str
    candidate_version: str
    status: str
    updated_at: str
    git_commit: str
    manifest_hash: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
