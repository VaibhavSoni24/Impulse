"""Data models and enums for Prompt Optimization Loop (Stage 32).

Defines:
- PromptChangeType: Controlled vocabulary for prompt interventions
- PromptHypothesis: Structured causal hypothesis specification
- PromptCostMetrics: Quantitative length, line, character, and token metrics
- PromptBloatReport: Diagnostics for instruction duplication and bloat
- PromptDiff: Deterministic prompt delta representation
- TaskTransition & TaskPairOutcome: Task-level paired comparisons
- PromptCandidateManifest: Reproducibility manifest for prompt experiments
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PromptChangeType(str, Enum):
    """Controlled vocabulary for prompt intervention types (Stage 32 Section 12)."""

    ADD_INSTRUCTION = "ADD_INSTRUCTION"
    REMOVE_INSTRUCTION = "REMOVE_INSTRUCTION"
    REWORD_INSTRUCTION = "REWORD_INSTRUCTION"
    REORDER_INSTRUCTION = "REORDER_INSTRUCTION"
    TIGHTEN_CONSTRAINT = "TIGHTEN_CONSTRAINT"
    RELAX_CONSTRAINT = "RELAX_CONSTRAINT"
    FORMAT_CHANGE = "FORMAT_CHANGE"
    PRIORITY_CHANGE = "PRIORITY_CHANGE"


class TaskTransition(str, Enum):
    """Categorized behavioral shift on an individual task (Stage 32 Section 14)."""

    FAIL_TO_PASS = "FAIL_TO_PASS"
    PASS_TO_FAIL = "PASS_TO_FAIL"
    FAIL_TO_OTHER_FAIL = "FAIL_TO_OTHER_FAIL"
    FAIL_UNCHANGED = "FAIL_UNCHANGED"
    PASS_UNCHANGED = "PASS_UNCHANGED"
    UNPAIRED = "UNPAIRED"


@dataclass
class PromptHypothesis:
    """Structured causal hypothesis for a prompt modification (Stage 32 Section 11)."""

    target_failure: str
    observation: str
    hypothesis: str
    intervention: str
    expected_behavior: str
    expected_metric_signal: str
    rejection_condition: str
    change_type: str = PromptChangeType.ADD_INSTRUCTION.value
    changed_section: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptHypothesis:
        return cls(**data)


@dataclass
class PromptCostMetrics:
    """Quantitative size and complexity metrics for prompt contents (Stage 32 Section 16)."""

    char_count: int
    line_count: int
    word_count: int
    estimated_tokens: int
    char_delta: Optional[int] = None
    line_delta: Optional[int] = None
    estimated_token_delta: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromptBloatReport:
    """Diagnostics for repetitive or non-operational prompt text (Stage 32 Section 17)."""

    is_bloated: bool
    duplicate_lines: list[str] = field(default_factory=list)
    filler_phrases_found: list[str] = field(default_factory=list)
    potential_contradictions: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromptDiff:
    """Structured, deterministic diff between parent and candidate prompts (Stage 32 Section 8)."""

    parent_candidate_id: str
    candidate_id: str
    parent_prompt_hash: str
    candidate_prompt_hash: str
    changed_files: list[str]
    added_lines_count: int
    removed_lines_count: int
    changed_lines_count: int
    added_text_snippets: list[str]
    removed_text_snippets: list[str]
    changed_sections: list[str]
    unified_diff: str
    cost_metrics: PromptCostMetrics

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["cost_metrics"] = self.cost_metrics.to_dict()
        return res


@dataclass
class TaskPairOutcome:
    """Paired outcome comparison for a single task instance (Stage 32 Section 14)."""

    task_id: str
    baseline_success: Optional[bool]
    candidate_success: Optional[bool]
    baseline_failure_category: str
    candidate_failure_category: str
    transition: TaskTransition

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["transition"] = self.transition.value if isinstance(self.transition, TaskTransition) else str(self.transition)
        return res


@dataclass
class PromptCandidateManifest:
    """Reproducibility manifest for a prompt candidate (Stage 32 Section 24)."""

    candidate_id: str
    parent_candidate_id: Optional[str]
    prompt_id: str
    prompt_path: str
    prompt_sha256: str
    parent_prompt_sha256: str
    source_failure_cluster_id: Optional[str] = None
    target_failure_mode: str = "UNKNOWN"
    hypothesis: Optional[PromptHypothesis] = None
    intervention_type: str = PromptChangeType.ADD_INSTRUCTION.value
    changed_section: str = ""
    changed_files: list[str] = field(default_factory=list)
    benchmark_split: str = "validation"
    benchmark_manifest_hash: str = ""
    held_out_lock_hash: str = ""
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    topology_id: str = "root_only"
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
    def from_dict(cls, data: dict[str, Any]) -> PromptCandidateManifest:
        d = dict(data)
        if d.get("hypothesis") and isinstance(d["hypothesis"], dict):
            d["hypothesis"] = PromptHypothesis.from_dict(d["hypothesis"])
        return cls(**d)
