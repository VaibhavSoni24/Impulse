"""Prompt Experiment Audit Reporting (Stage 32 Section 25).

Generates the authoritative human-readable report.md for prompt experiments
with exact quantitative failure reductions, paired task outcomes, and reproducibility hashes.
"""

from __future__ import annotations

from typing import List, Optional

from local.fdd.models import FDDRunDelta
from local.prompt_opt.models import (
    PromptBloatReport,
    PromptCandidateManifest,
    PromptDiff,
    TaskPairOutcome,
    TaskTransition,
)
from local.prompt_opt.paired import summarize_paired_outcomes


def generate_prompt_experiment_report(
    manifest: PromptCandidateManifest,
    diff: PromptDiff,
    delta: Optional[FDDRunDelta] = None,
    paired_outcomes: Optional[List[TaskPairOutcome]] = None,
    smoke_passed: Optional[bool] = None,
    validation_passed: Optional[bool] = None,
    held_out_passed: Optional[bool] = None,
    bloat_report: Optional[PromptBloatReport] = None,
) -> str:
    """Generates human-readable markdown audit report for a prompt optimization experiment."""
    lines: List[str] = [
        "# Prompt Optimization Experiment",
        "",
        "## Candidate",
        f"- **Candidate ID:** `{manifest.candidate_id}`",
        f"- **Prompt ID:** `{manifest.prompt_id}`",
        f"- **Prompt Path:** `{manifest.prompt_path}`",
        f"- **Prompt SHA-256:** `{manifest.prompt_sha256}`",
        f"- **Evidence Mode:** `{manifest.evidence_mode}`",
        f"- **Topology:** `{manifest.topology_id}`",
        f"- **Model ID:** `{manifest.model_id}`",
        "",
        "## Parent",
        f"- **Parent Candidate:** `{manifest.parent_candidate_id or 'None (Root Baseline)'}`",
        f"- **Parent Prompt SHA-256:** `{manifest.parent_prompt_sha256 or 'N/A'}`",
        f"- **Creation Commit:** `{manifest.created_from_commit or 'HEAD'}`",
        "",
        "## Target Failure",
        f"- **Target Failure Mode:** `{manifest.target_failure_mode}`",
        f"- **Source Cluster ID:** `{manifest.source_failure_cluster_id or 'N/A'}`",
        "",
        "## Baseline Evidence",
    ]

    if manifest.hypothesis:
        lines.extend([
            f"- **Observation:** {manifest.hypothesis.observation}",
            f"- **Expected Behavior Change:** {manifest.hypothesis.expected_behavior}",
        ])
    else:
        lines.append("- **Observation:** Baseline prompt reference.")

    lines.extend([
        "",
        "## Hypothesis",
    ])

    if manifest.hypothesis:
        lines.extend([
            f"> {manifest.hypothesis.hypothesis}",
            "",
            f"- **Change Type:** `{manifest.intervention_type}`",
            f"- **Changed Section:** `{manifest.changed_section}`",
            f"- **Expected Signal:** {manifest.hypothesis.expected_metric_signal}",
            f"- **Rejection Condition:** {manifest.hypothesis.rejection_condition}",
        ])
    else:
        lines.append("- Baseline specification (no active intervention hypothesis).")

    lines.extend([
        "",
        "## Prompt Change",
    ])

    if manifest.hypothesis:
        lines.append(f"- **Intervention:** {manifest.hypothesis.intervention}")
    else:
        lines.append("- Baseline establishment.")

    lines.extend([
        "",
        "## Prompt Diff",
        f"- **Files Changed:** `{', '.join(diff.changed_files)}`",
        f"- **Lines Added:** +{diff.added_lines_count}",
        f"- **Lines Removed:** -{diff.removed_lines_count}",
        f"- **Net Line Delta:** {diff.cost_metrics.line_delta:+}",
        f"- **Character Delta:** {diff.cost_metrics.char_delta:+}",
        f"- **Estimated Token Delta:** {diff.cost_metrics.estimated_token_delta:+}",
        "",
        "```diff",
        diff.unified_diff.strip() if diff.unified_diff else "No content diff.",
        "```",
        "",
        "## Smoke Result",
        f"- **Smoke Gate:** {'PASSED' if smoke_passed is True else ('FAILED' if smoke_passed is False else 'SKIPPED')}",
        "",
        "## Validation Result",
        f"- **Validation Split:** `{manifest.benchmark_split}`",
        f"- **Validation Gate:** {'PASSED' if validation_passed is True else ('FAILED' if validation_passed is False else 'UNEXECUTED')}",
        "",
        "## Held-Out Result",
        f"- **Held-Out Evaluated:** {'YES' if held_out_passed is not None else 'NO (held-out protected)'}",
        f"- **Held-Out Gate:** {'PASSED' if held_out_passed is True else ('REGRESSED' if held_out_passed is False else 'UNEXECUTED')}",
        f"- **Held-Out Lock Hash:** `{manifest.held_out_lock_hash or 'N/A'}`",
        "",
        "## Targeted Failure Delta",
    ])

    if delta and delta.targeted_reduction is not None:
        lines.extend([
            f"- **Target Mode:** `{delta.target_failure_mode}`",
            f"- **Baseline Failures:** {delta.baseline_failure_count}",
            f"- **Candidate Failures:** {delta.candidate_failure_count}",
            f"- **Targeted Reduction:** {delta.targeted_reduction}",
            f"- **Pass Rate Delta:** {f'{delta.pass_rate_delta:+.2%}' if delta.pass_rate_delta is not None else 'N/A'}",
        ])
    else:
        lines.extend([
            f"- **Target Mode:** `{manifest.target_failure_mode}`",
            "- **Baseline Failures:** N/A",
            "- **Candidate Failures:** N/A",
            "- **Targeted Reduction:** N/A",
        ])

    lines.extend([
        "",
        "## Paired Task Outcomes",
    ])

    if paired_outcomes:
        psummary = summarize_paired_outcomes(paired_outcomes)
        lines.extend([
            f"- **Total Paired Tasks:** {psummary['total_paired']}",
            f"- **FAIL → PASS (Fixes):** {psummary['fail_to_pass']}",
            f"- **PASS → FAIL (Regressions):** {psummary['pass_to_fail']}",
            f"- **FAIL → Other FAIL (Category Shifts):** {psummary['fail_to_other_fail']}",
            f"- **FAIL Unchanged:** {psummary['fail_unchanged']}",
            f"- **PASS Unchanged:** {psummary['pass_unchanged']}",
        ])
    else:
        lines.append("- No task-level paired outcomes available (unexecuted or unaligned splits).")

    lines.extend([
        "",
        "## Collateral Effects",
    ])

    if delta and (delta.collateral_regressions or delta.collateral_improvements):
        if delta.collateral_regressions:
            lines.append("- **Collateral Regressions:**")
            for cat, cnt in sorted(delta.collateral_regressions.items()):
                lines.append(f"  - `{cat}`: +{cnt}")
        else:
            lines.append("- **Collateral Regressions:** None observed (0)")

        if delta.collateral_improvements:
            lines.append("- **Collateral Improvements:**")
            for cat, cnt in sorted(delta.collateral_improvements.items()):
                lines.append(f"  - `{cat}`: -{cnt}")
    else:
        lines.append("- **Collateral Regressions:** None observed / unmeasured")

    lines.extend([
        "",
        "## Prompt Cost",
        "| Metric | Parent | Candidate | Delta |",
        "|---|---|---|---|",
        f"| Characters | {diff.cost_metrics.char_count - (diff.cost_metrics.char_delta or 0)} | {diff.cost_metrics.char_count} | {diff.cost_metrics.char_delta:+} |",
        f"| Lines | {diff.cost_metrics.line_count - (diff.cost_metrics.line_delta or 0)} | {diff.cost_metrics.line_count} | {diff.cost_metrics.line_delta:+} |",
        f"| Estimated Tokens | {diff.cost_metrics.estimated_tokens - (diff.cost_metrics.estimated_token_delta or 0)} | {diff.cost_metrics.estimated_tokens} | {diff.cost_metrics.estimated_token_delta:+} |",
    ])

    if bloat_report and bloat_report.diagnostics:
        lines.append("")
        lines.append("### Bloat Diagnostics")
        for diag in bloat_report.diagnostics:
            lines.append(f"- {diag}")

    lines.extend([
        "",
        "## Decision",
        f"- **Authoritative Decision:** `{manifest.decision}`",
        f"- **Decision Rationale:** {manifest.decision_rationale or 'N/A'}",
        "",
        "## Reproducibility",
        f"- **Candidate Directory:** `experiments/prompts/{manifest.candidate_id}/`",
        f"- **Prompt SHA-256:** `{manifest.prompt_sha256}`",
        f"- **Benchmark Manifest SHA-256:** `{manifest.benchmark_manifest_hash or 'N/A'}`",
    ])

    for artifact, ahash in sorted(manifest.artifact_hashes.items()):
        if artifact != "report.md":
            lines.append(f"- **{artifact} SHA-256:** `{ahash}`")

    lines.append("")
    return "\n".join(lines)
