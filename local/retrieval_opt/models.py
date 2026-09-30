"""Data models and representations for Retrieval Optimization Loop (Stage 33).

Defines:
- RetrievalVariant: Canonical retrieval variants (R0, R1, R2, R3, R4)
- RetrievalType: Categorical retrieval tool operations
- RetrievalPolicy: Structured typed retrieval policy configuration
- RetrievalEvent: Structured audit event for every retrieval invocation
- DynamicRoundTrace: Round-by-round trace for R4 adaptive retrieval depth
- RetrievalCostMetrics: Quantitative resource and cost metrics
- RetrievalQualityMetrics: Quantitative task-solving quality metrics
- RetrievalDiagnostics: Auditable diagnostic flags (redundancy, dead retrieval, etc.)
- RetrievalHypothesis: Structured causal hypothesis specification
- RetrievalTaskPairOutcome: Paired per-task outcome comparison with retrieval diff
- RetrievalCandidateManifest: Reproducibility manifest for retrieval experiments
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class RetrievalVariant(str, Enum):
    """Canonical retrieval variants defined by PLAN.md Stage 33 Section 3."""

    R0 = "R0"  # Baseline: No semantic retrieval (exact text search / file inspection only)
    R1 = "R1"  # Semantic retrieval (search_similar_code enabled under controlled policy)
    R2 = "R2"  # Semantic retrieval + selective code neighbors (get_code_neighbors)
    R3 = "R3"  # Semantic retrieval + selective subgraph (get_code_subgraph)
    R4 = "R4"  # Dynamic retrieval depth (adaptive depth & early stopping based on evidence)


class RetrievalType(str, Enum):
    """Specific retrieval tool invocation type."""

    EXACT_SEARCH = "EXACT_SEARCH"
    SEMANTIC = "SEMANTIC"
    NEIGHBORS = "NEIGHBORS"
    SUBGRAPH = "SUBGRAPH"


class TaskTransition(str, Enum):
    """Categorized behavioral shift on an individual task."""

    FAIL_TO_PASS = "FAIL_TO_PASS"
    PASS_TO_FAIL = "PASS_TO_FAIL"
    FAIL_TO_OTHER_FAIL = "FAIL_TO_OTHER_FAIL"
    FAIL_UNCHANGED = "FAIL_UNCHANGED"
    PASS_UNCHANGED = "PASS_UNCHANGED"
    UNPAIRED = "UNPAIRED"


@dataclass
class RetrievalHypothesis:
    """Structured causal hypothesis for a retrieval modification (Stage 33 Section 18)."""

    target_failure: str
    observation: str
    hypothesis: str
    retrieval_change: str
    expected_signal: str
    rejection_condition: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalHypothesis:
        return cls(**data)


@dataclass
class RetrievalPolicy:
    """Typed representation of a retrieval policy configuration (Stage 33 Section 6)."""

    variant: str = RetrievalVariant.R0.value
    candidate_id: str = "R0"
    semantic_retrieval_enabled: bool = False
    neighbor_retrieval_enabled: bool = False
    subgraph_retrieval_enabled: bool = False
    dynamic_depth_enabled: bool = False

    semantic_top_k: int = 5
    neighbor_depth: int = 1
    subgraph_depth: int = 1
    subgraph_breadth_k: int = 4

    max_retrieval_calls: int = 6
    max_semantic_calls: int = 2
    max_neighbor_calls: int = 3
    max_subgraph_calls: int = 2
    max_retrieved_items: int = 20

    similarity_threshold: float = 0.50
    expansion_policy: str = "none"

    trigger_conditions: dict[str, Any] = field(
        default_factory=lambda: {
            "require_exact_ambiguity": True,
            "require_promising_symbol": False,
            "require_multi_symbol_relation": False,
        }
    )

    dynamic_config: dict[str, Any] = field(
        default_factory=lambda: {
            "min_depth": 1,
            "max_depth": 3,
            "max_rounds": 3,
            "redundancy_stop_threshold": 0.5,
            "early_stop_on_sufficient": True,
        }
    )

    fallback_behavior: dict[str, str] = field(
        default_factory=lambda: {
            "on_semantic_failure": "EXACT_SEARCH",
            "on_neighbor_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_subgraph_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_policy_hash(self) -> str:
        """Computes deterministic SHA-256 hash of canonical policy parameters."""
        data = {
            "variant": self.variant,
            "semantic_retrieval_enabled": self.semantic_retrieval_enabled,
            "neighbor_retrieval_enabled": self.neighbor_retrieval_enabled,
            "subgraph_retrieval_enabled": self.subgraph_retrieval_enabled,
            "dynamic_depth_enabled": self.dynamic_depth_enabled,
            "semantic_top_k": self.semantic_top_k,
            "neighbor_depth": self.neighbor_depth,
            "subgraph_depth": self.subgraph_depth,
            "subgraph_breadth_k": self.subgraph_breadth_k,
            "max_retrieval_calls": self.max_retrieval_calls,
            "max_semantic_calls": self.max_semantic_calls,
            "max_neighbor_calls": self.max_neighbor_calls,
            "max_subgraph_calls": self.max_subgraph_calls,
            "max_retrieved_items": self.max_retrieved_items,
            "similarity_threshold": self.similarity_threshold,
            "expansion_policy": self.expansion_policy,
            "trigger_conditions": self.trigger_conditions,
            "dynamic_config": self.dynamic_config,
            "fallback_behavior": self.fallback_behavior,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalPolicy:
        return cls(**data)


@dataclass
class RetrievalEvent:
    """Structured audit event for every retrieval invocation (Stage 33 Section 13)."""

    run_id: str
    task_id: str
    candidate_id: str
    retrieval_variant: str
    retrieval_type: str
    query: str
    seed_nodes: list[str] = field(default_factory=list)
    requested_k: Optional[int] = None
    requested_depth: Optional[int] = None
    returned_count: int = 0
    unique_returned_count: int = 0
    selected_count: int = 0
    inspected_count: int = 0
    duplicate_count: int = 0
    retrieval_duration_ms: float = 0.0
    turn: int = 0
    tool_call_index: int = 0
    evidence_mode: str = "FIXTURE"
    cache_hit: bool = False
    returned_entities: list[str] = field(default_factory=list)
    source_files_exposed: list[str] = field(default_factory=list)
    context_token_growth: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalEvent:
        return cls(**data)


@dataclass
class DynamicRoundTrace:
    """Structured trace for an individual round of adaptive dynamic retrieval (R4)."""

    round_index: int
    current_evidence_state: dict[str, Any]
    action_taken: str
    new_evidence_gained: list[str]
    duplicate_evidence: list[str]
    decision: str  # "CONTINUE" | "STOP"
    decision_rationale: str
    budget_remaining: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DynamicRoundTrace:
        return cls(**data)


@dataclass
class RetrievalCostMetrics:
    """Quantitative cost and resource metrics for a retrieval candidate (Stage 33 Section 14)."""

    retrieval_call_count: int
    semantic_calls: int
    neighbor_calls: int
    subgraph_calls: int
    retrieval_tool_call_share: Optional[float] = None
    mean_retrieval_duration_ms: Optional[float] = None
    median_retrieval_duration_ms: Optional[float] = None
    p95_retrieval_duration_ms: Optional[float] = None
    retrieved_entities: int = 0
    unique_entities: int = 0
    duplicate_entities: int = 0
    source_files_exposed: int = 0
    total_context_growth_tokens: Optional[int] = None
    total_agent_tool_calls: Optional[int] = None
    total_runtime_ms: Optional[float] = None
    turns: Optional[int] = None
    cache_hit_count: int = 0
    cache_hit_ratio: Optional[float] = None
    unique_entities_per_retrieval_call: Optional[float] = None
    unique_files_per_retrieval_call: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalCostMetrics:
        return cls(**data)


@dataclass
class RetrievalQualityMetrics:
    """Quantitative task-solving quality metrics for a retrieval candidate (Stage 33 Section 15)."""

    pass_rate: float
    failure_rate: float
    targeted_failure_mode: str
    targeted_failure_count: int
    targeted_failure_rate: float
    localization_failure_count: int
    fail_to_pass_count: int = 0
    pass_to_fail_count: int = 0
    fail_to_other_fail_count: int = 0
    unchanged_failure_count: int = 0
    clean_copy_verification_success: bool = True
    recovery_success_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalQualityMetrics:
        return cls(**data)


@dataclass
class RetrievalDiagnostics:
    """Auditable diagnostic flags for retrieval pathology detection (Stage 33 Section 26)."""

    redundancy_count: int = 0
    dead_retrieval_count: int = 0
    over_expansion_count: int = 0
    under_expansion_count: int = 0
    late_retrieval_count: int = 0
    misleading_retrieval_count: int = 0
    diagnostic_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalDiagnostics:
        return cls(**data)


@dataclass
class RetrievalTaskPairOutcome:
    """Task-level paired outcome comparison between baseline and candidate (Stage 33 Section 17)."""

    task_id: str
    baseline_success: Optional[bool]
    candidate_success: Optional[bool]
    baseline_failure_category: str
    candidate_failure_category: str
    transition: TaskTransition
    baseline_retrieval_calls: int = 0
    candidate_retrieval_calls: int = 0
    retrieval_call_delta: int = 0
    retrieval_behavior_diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["transition"] = (
            self.transition.value
            if isinstance(self.transition, TaskTransition)
            else str(self.transition)
        )
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalTaskPairOutcome:
        d = dict(data)
        if "transition" in d and isinstance(d["transition"], str):
            d["transition"] = TaskTransition(d["transition"])
        return cls(**d)


@dataclass
class RetrievalCandidateManifest:
    """Reproducibility manifest for a retrieval candidate (Stage 33 Section 5)."""

    candidate_id: str
    parent_candidate_id: Optional[str]
    retrieval_variant: str
    retrieval_policy_hash: str
    source_failure_cluster_id: Optional[str] = None
    target_failure_mode: str = "UNKNOWN"
    hypothesis: Optional[RetrievalHypothesis] = None
    benchmark_split: str = "validation"
    benchmark_manifest_hash: str = ""
    held_out_lock_hash: str = ""
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    topology_id: str = "root_only"
    prompt_id: str = "P0"
    prompt_sha256: str = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
    tool_budget_id: str = "standard_stage26"
    evidence_mode: str = "UNAVAILABLE"
    created_from_commit: str = ""
    experiment_id: str = ""
    decision: str = "INCONCLUSIVE"
    decision_rationale: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    artifact_hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.hypothesis:
            res["hypothesis"] = self.hypothesis.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetrievalCandidateManifest:
        d = dict(data)
        if d.get("hypothesis") and isinstance(d["hypothesis"], dict):
            d["hypothesis"] = RetrievalHypothesis.from_dict(d["hypothesis"])
        return cls(**d)
