"""IMPULSE Skill Optimization Loop Package (Stage 36).

Provides:
- Inventory and discovery of repository skills
- Immutable S0 baseline snapshots and S1 versioned candidates
- Deterministic skill diffing and context cost metrics
- Root-prompt duplication and internal redundancy analysis
- Contradiction and bloat heuristics
- Skill scope validation (domain boundaries)
- Paired per-task evaluation and task-scope matrix
- Integration with Stage 31 FDD promotion gates
"""

from local.skill_opt.analyzer import analyze_skill_content
from local.skill_opt.diff import diff_skills, estimate_tokens, render_skill_diff_md
from local.skill_opt.experiment import SkillExperimentManager
from local.skill_opt.inventory import SkillInventory
from local.skill_opt.metrics import (
    compare_skill_metrics,
    compute_skill_behavior_metrics,
    compute_skill_context_metrics,
)
from local.skill_opt.models import (
    InstructionDuplicationCategory,
    SkillBehaviorMetrics,
    SkillCandidateManifest,
    SkillChangeType,
    SkillContextCostMetrics,
    SkillContradiction,
    SkillDiagnostics,
    SkillDuplicationReport,
    SkillHypothesis,
    SkillRecord,
    SkillScope,
    SkillScopeType,
    SkillTaskPairOutcome,
    TaskBehaviorTransition,
)
from local.skill_opt.paired import (
    build_task_scope_matrix,
    compute_paired_task_comparisons,
    save_paired_results,
)
from local.skill_opt.reporting import generate_candidate_report_md, generate_top_level_matrix_md
from local.skill_opt.scope_validator import validate_skill_scope
from local.skill_opt.validator import (
    validate_candidate_single_skill_change,
    validate_skill_candidate_invariance,
    validate_skill_hypothesis,
)

__all__ = [
    "InstructionDuplicationCategory",
    "SkillBehaviorMetrics",
    "SkillCandidateManifest",
    "SkillChangeType",
    "SkillContextCostMetrics",
    "SkillContradiction",
    "SkillDiagnostics",
    "SkillDuplicationReport",
    "SkillExperimentManager",
    "SkillHypothesis",
    "SkillInventory",
    "SkillRecord",
    "SkillScope",
    "SkillScopeType",
    "SkillTaskPairOutcome",
    "TaskBehaviorTransition",
    "analyze_skill_content",
    "build_task_scope_matrix",
    "compare_skill_metrics",
    "compute_paired_task_comparisons",
    "compute_skill_behavior_metrics",
    "compute_skill_context_metrics",
    "diff_skills",
    "estimate_tokens",
    "generate_candidate_report_md",
    "generate_top_level_matrix_md",
    "render_skill_diff_md",
    "save_paired_results",
    "validate_candidate_single_skill_change",
    "validate_skill_candidate_invariance",
    "validate_skill_hypothesis",
    "validate_skill_scope",
]
