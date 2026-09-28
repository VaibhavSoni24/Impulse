"""Data models and enums for Tool-Call Budgeting (Stage 26).

Defines:
- ToolCallCategory: READ_OBSERVATION, MUTATION, EXECUTION, SUBMISSION
- EvidenceNovelty: NEW_EVIDENCE, PARTIAL_NEW_EVIDENCE, NO_NEW_EVIDENCE
- WasteClassification: SAFE_REDUNDANT, POSSIBLY_REDUNDANT, NECESSARY_REPEAT, UNKNOWN
- ToolAssociation: ASSOCIATED_WITH_SUCCESS, ASSOCIATED_WITH_FAILURE, NO_RESOLUTION, INSUFFICIENT_DATA
- ToolCallEvent: Structured record of an individual tool call
- InformationValue: Decomposition of evidence novelty and information yield
- ToolDistributionMetrics: Aggregate call count and repetition metrics
- ToolBudgetProfile: Operational budgeting profile for a tool
- CacheEntry & CacheKey: Structured representation for bounded tool caching
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ToolCallCategory(str, Enum):
    """Categorical classification of tool invocation boundaries."""

    READ_OBSERVATION = "READ_OBSERVATION"
    MUTATION = "MUTATION"
    EXECUTION = "EXECUTION"
    SUBMISSION = "SUBMISSION"


class EvidenceNovelty(str, Enum):
    """Classification of empirical novelty produced by a tool call."""

    NEW_EVIDENCE = "NEW_EVIDENCE"
    PARTIAL_NEW_EVIDENCE = "PARTIAL_NEW_EVIDENCE"
    NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"


class WasteClassification(str, Enum):
    """Classification of potential call redundancy."""

    SAFE_REDUNDANT = "SAFE_REDUNDANT"
    POSSIBLY_REDUNDANT = "POSSIBLY_REDUNDANT"
    NECESSARY_REPEAT = "NECESSARY_REPEAT"
    UNKNOWN = "UNKNOWN"


class ToolAssociation(str, Enum):
    """Neutral associational relationship between tool usage and task resolution."""

    ASSOCIATED_WITH_SUCCESS = "ASSOCIATED_WITH_SUCCESS"
    ASSOCIATED_WITH_FAILURE = "ASSOCIATED_WITH_FAILURE"
    NO_RESOLUTION = "NO_RESOLUTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# The 9 canonical competition tools categorized by operation type
TOOL_CATEGORY_MAP: dict[str, ToolCallCategory] = {
    "read_file": ToolCallCategory.READ_OBSERVATION,
    "get_status": ToolCallCategory.READ_OBSERVATION,
    "search_similar_code": ToolCallCategory.READ_OBSERVATION,
    "get_code_neighbors": ToolCallCategory.READ_OBSERVATION,
    "get_code_subgraph": ToolCallCategory.READ_OBSERVATION,
    "edit_file": ToolCallCategory.MUTATION,
    "write_file": ToolCallCategory.MUTATION,
    "run_command": ToolCallCategory.EXECUTION,
    "submit_patch": ToolCallCategory.SUBMISSION,
}


@dataclass(frozen=True)
class InformationValue:
    """Decomposition of the information yield produced by a tool invocation."""

    evidence_units_new: int = 0
    evidence_units_total: int = 0
    novelty_ratio: float = 0.0
    novelty_class: EvidenceNovelty = EvidenceNovelty.NO_NEW_EVIDENCE
    new_files_count: int = 0
    changed_files_count: int = 0
    new_symbols_count: int = 0
    new_relations_count: int = 0
    new_test_results_count: int = 0
    new_failure_signatures_count: int = 0
    recovery_relevant: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["novelty_class"] = self.novelty_class.value
        return d


@dataclass
class ToolCallEvent:
    """Structured record of an individual tool call execution."""

    run_id: str
    task_id: str
    turn_id: int
    call_id: str
    tool_name: str
    category: ToolCallCategory
    normalized_arguments: dict[str, Any]
    repository_state_id: str  # Manifest digest or content fingerprint
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    success: bool = True
    result_class: str = "OK"  # "OK", "ERROR", "TIMEOUT", "SYNTAX_ERROR"
    produced_new_evidence: bool = False
    evidence_fingerprint: str = ""
    information_value: InformationValue = field(default_factory=InformationValue)
    cacheable: bool = False
    cache_hit: bool = False
    cache_invalidated: bool = False
    waste_class: WasteClassification = WasteClassification.UNKNOWN
    reason_for_call: str = ""
    related_failure_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["waste_class"] = self.waste_class.value
        d["information_value"] = self.information_value.to_dict()
        return d


@dataclass
class ToolDistributionMetrics:
    """Aggregate distribution metrics for a tool across runs or tasks."""

    tool_name: str
    category: ToolCallCategory
    total_calls: int = 0
    distinct_calls: int = 0
    repeated_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    new_evidence_calls: int = 0
    no_new_evidence_calls: int = 0
    safe_redundant_calls: int = 0
    possibly_redundant_calls: int = 0
    necessary_repeat_calls: int = 0
    unknown_waste_calls: int = 0
    average_information_ratio: float = 0.0
    calls_per_turn_mean: float = 0.0
    call_share_percent: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class ToolSuccessAssociation:
    """Observational association between tool usage and task outcomes."""

    tool_name: str
    successful_task_calls: int = 0
    unsuccessful_task_calls: int = 0
    avg_calls_per_successful_task: float = 0.0
    avg_calls_per_unsuccessful_task: float = 0.0
    new_evidence_on_success: int = 0
    new_evidence_on_failure: int = 0
    calls_before_resolution: int = 0
    calls_during_recovery: int = 0
    association_status: ToolAssociation = ToolAssociation.INSUFFICIENT_DATA

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["association_status"] = self.association_status.value
        return d


@dataclass
class ToolBudgetProfile:
    """Operational budgeting profile for monitoring and optional limits."""

    tool_name: str
    category: ToolCallCategory
    observed_call_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    duplicate_count: int = 0
    new_evidence_count: int = 0
    no_new_evidence_count: int = 0
    average_information_value: float = 0.0
    soft_limit: int | None = None
    hard_limit: int | None = None
    enforcement_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass(frozen=True)
class CacheKey:
    """Deterministic cache key incorporating tool identity, normalized args, and state."""

    tool_name: str
    arguments_digest: str
    repository_state_id: str
    target_path: str = ""
    index_version: str = ""

    def to_string(self) -> str:
        parts = [
            self.tool_name,
            self.arguments_digest,
            self.repository_state_id,
            self.target_path or "none",
            self.index_version or "none",
        ]
        return "|".join(parts)


@dataclass
class CacheEntry:
    """Bounded cache entry storing cached result payload and metadata."""

    key: CacheKey
    result_payload: Any
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 1
    size_bytes: int = 0
    associated_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.to_string(),
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "associated_paths": list(self.associated_paths),
        }
