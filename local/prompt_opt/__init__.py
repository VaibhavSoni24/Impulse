"""Prompt Optimization Loop Package (Stage 32).

Provides:
- Controlled vocabulary and data models for prompt interventions
- Deterministic prompt diffing and cost calculation
- Instruction bloat diagnostics
- Single-dimension candidate validation
- Task-level paired comparison engine
- P0 baseline establishment and P(n) candidate management
- Audit report and artifact verification
"""

from __future__ import annotations

from local.prompt_opt.baseline import establish_p0_baseline
from local.prompt_opt.diff import (
    compute_prompt_cost,
    compute_prompt_diff,
    detect_prompt_bloat,
    render_prompt_diff_md,
)
from local.prompt_opt.experiment import PromptExperimentManager
from local.prompt_opt.models import (
    PromptBloatReport,
    PromptCandidateManifest,
    PromptChangeType,
    PromptCostMetrics,
    PromptDiff,
    PromptHypothesis,
    TaskPairOutcome,
    TaskTransition,
)
from local.prompt_opt.paired import (
    compute_task_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
    summarize_paired_outcomes,
)
from local.prompt_opt.reporting import generate_prompt_experiment_report
from local.prompt_opt.validator import (
    PromptValidationError,
    validate_prompt_candidate_integrity,
    validate_prompt_hypothesis,
)

__all__ = [
    "PromptChangeType",
    "TaskTransition",
    "PromptHypothesis",
    "PromptCostMetrics",
    "PromptBloatReport",
    "PromptDiff",
    "TaskPairOutcome",
    "PromptCandidateManifest",
    "compute_prompt_cost",
    "detect_prompt_bloat",
    "compute_prompt_diff",
    "render_prompt_diff_md",
    "compute_task_paired_comparison",
    "summarize_paired_outcomes",
    "save_paired_results_jsonl",
    "save_paired_results_csv",
    "validate_prompt_hypothesis",
    "validate_prompt_candidate_integrity",
    "PromptValidationError",
    "establish_p0_baseline",
    "generate_prompt_experiment_report",
    "PromptExperimentManager",
]
