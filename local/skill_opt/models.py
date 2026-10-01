"""Data models and representations for the Skill Optimization Loop (Stage 36).

Defines:
- SkillScopeType: Controlled domain boundaries (TESTING, REPOSITORY_TRIAGE, GENERAL)
- SkillChangeType: Vocabulary for single-change skill interventions
- InstructionDuplicationCategory: Lexical overlap status against root prompt
- TaskBehaviorTransition: Categorized behavioral transition per task
- SkillRecord: Skill inventory metadata record
- SkillScope: Structured definition of scope boundaries
- SkillHypothesis: Structured causal hypothesis for skill modification
- SkillContextCostMetrics: Resource cost and token metrics
- SkillDuplicationReport: Root prompt and internal duplication analysis results
- SkillContradiction: Conflicting instruction diagnostics
- SkillDiagnostics: Auditable diagnostic flags (bloat, leakage, contradiction)
- SkillTaskPairOutcome: Paired per-task outcome on the same benchmark task set
- SkillCandidateManifest: Complete reproducibility manifest with invariance hashes
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class SkillScopeType(str, Enum):
    """Controlled domain boundaries for skills (Stage 36 Section 5)."""

    TESTING = "TESTING"
    REPOSITORY_TRIAGE = "REPOSITORY_TRIAGE"
    GENERAL = "GENERAL"


class SkillChangeType(str, Enum):
    """Controlled vocabulary for single-change skill interventions (Stage 36 Section 12)."""

    ADD_INSTRUCTION = "ADD_INSTRUCTION"
    REMOVE_INSTRUCTION = "REMOVE_INSTRUCTION"
    REWORD_INSTRUCTION = "REWORD_INSTRUCTION"
    REORDER_INSTRUCTION = "REORDER_INSTRUCTION"
    TIGHTEN_SCOPE = "TIGHTEN_SCOPE"
    RELAX_SCOPE = "RELAX_SCOPE"
    ADD_SCOPE_BOUNDARY = "ADD_SCOPE_BOUNDARY"
    REMOVE_REDUNDANCY = "REMOVE_REDUNDANCY"
    CLARIFY_CONDITION = "CLARIFY_CONDITION"


class InstructionDuplicationCategory(str, Enum):
    """Duplication classification against root prompt or sibling instructions (Stage 36 Section 9)."""

    DUPLICATE = "DUPLICATE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    UNIQUE = "UNIQUE"
    CONTRADICTORY = "CONTRADICTORY"


class TaskBehaviorTransition(str, Enum):
    """Categorized behavioral and performance shift on an individual task (Stage 36 Section 21)."""

    PASS_TO_PASS = "PASS_TO_PASS"
    PASS_TO_FAIL = "PASS_TO_FAIL"
    FAIL_TO_PASS = "FAIL_TO_PASS"
    FAIL_TO_OTHER_FAIL = "FAIL_TO_OTHER_FAIL"
    FAIL_UNCHANGED = "FAIL_UNCHANGED"
    REDUNDANT_TO_NON_REDUNDANT = "REDUNDANT_TO_NON_REDUNDANT"
    MISSING_DISCOVERY_TO_CORRECT_DISCOVERY = "MISSING_DISCOVERY_TO_CORRECT_DISCOVERY"
    LATE_DISCOVERY_TO_EARLY_DISCOVERY = "LATE_DISCOVERY_TO_EARLY_DISCOVERY"
    UNPAIRED = "UNPAIRED"


@dataclass
class SkillRecord:
    """Metadata record for a skill within the repository skill inventory (Stage 36 Section 4)."""

    skill_id: str
    path: str
    current_hash: str
    scope: str
    intended_role: str
    is_frozen: bool = True
    is_optimizer_eligible: bool = True
    dependencies: list[str] = field(default_factory=list)
    loading_mechanism: str = "DECLARATIVE_YAML_AND_PROMPT_REFERENCE"
    competition_packaging_relevance: str = "ROOT_AGENT_SKILL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillRecord:
        return cls(**data)


@dataclass
class SkillScope:
    """Structured scope boundaries for skill execution (Stage 36 Section 5, 15)."""

    scope_type: str = SkillScopeType.GENERAL.value
    target_behaviors: list[str] = field(default_factory=list)
    applicable_tasks: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    excluded_situations: list[str] = field(default_factory=list)
    expected_behavior_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillScope:
        return cls(**data)


@dataclass
class SkillHypothesis:
    """Structured causal hypothesis for a skill revision (Stage 36 Section 11)."""

    target_behavior: str
    observation: str
    hypothesis: str
    intervention: str
    expected_behavior: str
    expected_metric_signal: str
    rejection_condition: str
    change_type: str = SkillChangeType.REMOVE_REDUNDANCY.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillHypothesis:
        return cls(**data)


@dataclass
class SkillContextCostMetrics:
    """Resource and context cost metrics for a skill artifact (Stage 36 Section 22)."""

    char_count: int = 0
    line_count: int = 0
    word_count: int = 0
    estimated_tokens: int = 0
    char_delta: int = 0
    line_delta: int = 0
    word_delta: int = 0
    token_delta: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillContextCostMetrics:
        return cls(**data)


@dataclass
class SkillBehaviorMetrics:
    """Quantitative behavioral and task metrics for a candidate skill (Stage 36 Section 19, 20)."""

    task_success_rate: float = 0.0
    target_failure_count: int = 0
    target_failure_rate: float = 0.0
    command_redundancy_count: int = 0
    repeated_reconnaissance_count: int = 0
    test_discovery_repetitions: int = 0
    irrelevant_test_executions: int = 0
    unnecessary_tree_scans: int = 0
    redundant_file_reads: int = 0
    package_manager_detected: Optional[bool] = None
    framework_detected: Optional[bool] = None
    test_framework_detected: Optional[bool] = None
    entry_points_discovered: Optional[bool] = None
    avg_tool_calls: float = 0.0
    avg_turns: float = 0.0
    avg_runtime_ms: float = 0.0
    files_read_count: int = 0
    files_changed_count: int = 0
    retrieval_interactions: int = 0
    recovery_interactions: int = 0
    test_selection_quality: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillBehaviorMetrics:
        return cls(**data)


@dataclass
class SkillContradiction:
    """Diagnostic detail for a detected instruction contradiction (Stage 36 Section 24)."""

    line_number_a: int
    line_number_b: int
    instruction_a: str
    instruction_b: str
    contradiction_type: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillContradiction:
        return cls(**data)


@dataclass
class SkillDuplicationReport:
    """Duplication analysis results against root prompt or internal sections (Stage 36 Section 9)."""

    total_skill_lines: int = 0
    exact_duplicate_lines: int = 0
    near_duplicate_lines: int = 0
    unique_lines: int = 0
    duplication_ratio: float = 0.0
    duplicate_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillDuplicationReport:
        return cls(**data)


@dataclass
class SkillDiagnostics:
    """Diagnostic flags for bloat, duplication, contradictions, and scope leakage (Stage 36 Section 23)."""

    has_root_duplication: bool = False
    has_internal_duplication: bool = False
    has_contradictions: bool = False
    has_scope_leakage: bool = False
    has_bloat: bool = False
    is_overly_generic: bool = False
    diagnostic_notes: list[str] = field(default_factory=list)
    contradictions: list[SkillContradiction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["contradictions"] = [c.to_dict() if isinstance(c, SkillContradiction) else c for c in self.contradictions]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillDiagnostics:
        d = dict(data)
        if "contradictions" in d and isinstance(d["contradictions"], list):
            d["contradictions"] = [
                SkillContradiction.from_dict(c) if isinstance(c, dict) else c
                for c in d["contradictions"]
            ]
        return cls(**d)


@dataclass
class SkillTaskPairOutcome:
    """Paired per-task outcome comparing parent vs candidate skill (Stage 36 Section 21)."""

    task_id: str
    skill_id: str
    parent_candidate: str
    candidate_id: str
    parent_result: str = "FAIL"  # "PASS" | "FAIL"
    candidate_result: str = "FAIL"
    transition: str = TaskBehaviorTransition.FAIL_UNCHANGED.value
    parent_behavior_metric: float = 0.0
    candidate_behavior_metric: float = 0.0
    behavior_transition: str = "UNCHANGED"
    diff_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillTaskPairOutcome:
        return cls(**data)


@dataclass
class SkillCandidateManifest:
    """Complete candidate manifest guaranteeing full reproducibility and provenance (Stage 36 Section 6, 13)."""

    candidate_id: str  # e.g. "S0", "S1", "S2"
    parent_candidate_id: str  # e.g. "S0"
    skill_id: str  # e.g. "test_strategy", "repo_triage"
    skill_version: str  # e.g. "1.0.0"
    skill_hash: str
    parent_skill_hash: str
    intervention_id: str
    scope: str
    change_type: str
    changed_section: str
    target_failure: str
    hypothesis: str
    expected_behavior: str
    benchmark_task_set: list[str] = field(default_factory=list)
    benchmark_split: str = "dev"
    benchmark_manifest_hash: str = ""
    prompt_hash: str = ""
    retrieval_policy_hash: str = ""
    testing_policy_hash: str = ""
    recovery_policy_hash: str = ""
    topology_identity: str = "root_only"
    model_id: str = "gemma-4-31b-it-qat-w4a16-ct"
    evidence_mode: str = "UNAVAILABLE"
    status: str = "PROPOSED"
    decision: str = "NO_ACTIONABLE_DATA"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillCandidateManifest:
        return cls(**data)
