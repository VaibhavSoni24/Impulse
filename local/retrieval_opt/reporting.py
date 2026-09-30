"""Retrieval Experiment Audit Reporting (Stage 33 Section 28).

Generates authoritative human-readable report.md for retrieval experiments
with exact quantitative failure reductions, cost metrics, paired task outcomes,
diagnostics, and reproducibility hashes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.fdd.models import FDDRunDelta
from local.retrieval_opt.diff import RetrievalPolicyDiff, render_retrieval_policy_diff_md
from local.retrieval_opt.models import (
    RetrievalCandidateManifest,
    RetrievalCostMetrics,
    RetrievalDiagnostics,
    RetrievalQualityMetrics,
    RetrievalTaskPairOutcome,
    TaskTransition,
)
from local.retrieval_opt.paired import summarize_paired_outcomes


def generate_retrieval_experiment_report(
    manifest: RetrievalCandidateManifest,
    diff: RetrievalPolicyDiff,
    quality: RetrievalQualityMetrics,
    cost: RetrievalCostMetrics,
    diagnostics: Optional[RetrievalDiagnostics] = None,
    paired_outcomes: Optional[List[RetrievalTaskPairOutcome]] = None,
    delta: Optional[FDDRunDelta] = None,
    smoke_passed: Optional[bool] = None,
    validation_passed: Optional[bool] = None,
    held_out_passed: Optional[bool] = None,
) -> str:
    """Generates human-readable markdown audit report for a retrieval optimization experiment."""
    lines: List[str] = [
        f"# Retrieval Optimization Experiment: {manifest.candidate_id} ({manifest.retrieval_variant})",
        "",
        "## Candidate Metadata",
        f"- **Candidate ID:** `{manifest.candidate_id}`",
        f"- **Retrieval Variant:** `{manifest.retrieval_variant}`",
        f"- **Policy Hash:** `{manifest.retrieval_policy_hash}`",
        f"- **Evidence Mode:** `{manifest.evidence_mode}`",
        f"- **Prompt ID:** `{manifest.prompt_id}` (SHA-256: `{manifest.prompt_sha256}`)",
        f"- **Topology:** `{manifest.topology_id}`",
        f"- **Model ID:** `{manifest.model_id}`",
        f"- **Created At:** `{manifest.created_at}`",
        "",
        "## Lineage",
        f"- **Parent Candidate:** `{manifest.parent_candidate_id or 'None (Root Baseline)'}`",
        f"- **Creation Commit:** `{manifest.created_from_commit or 'HEAD'}`",
        f"- **Experiment ID:** `{manifest.experiment_id}`",
        "",
        "## Target Failure & Hypothesis",
        f"- **Target Failure Mode:** `{manifest.target_failure_mode}`",
        f"- **Source Cluster ID:** `{manifest.source_failure_cluster_id or 'N/A'}`",
    ]

    if manifest.hypothesis:
        lines.extend([
            f"- **Observation:** {manifest.hypothesis.observation}",
            f"> **Hypothesis:** {manifest.hypothesis.hypothesis}",
            f"- **Retrieval Change:** `{manifest.hypothesis.retrieval_change}`",
            f"- **Expected Metric Signal:** {manifest.hypothesis.expected_signal}",
            f"- **Rejection Condition:** {manifest.hypothesis.rejection_condition}",
        ])
    else:
        lines.append("- Baseline specification (no active intervention hypothesis).")

    lines.extend([
        "",
        "## Retrieval Policy Diff",
        render_retrieval_policy_diff_md(diff),
        "",
        "## Quality Metrics",
        f"- **Pass Rate:** {quality.pass_rate * 100:.2f}%",
        f"- **Failure Rate:** {quality.failure_rate * 100:.2f}%",
        f"- **Target Failure Mode:** `{quality.targeted_failure_mode}`",
        f"- **Target Failure Count:** {quality.targeted_failure_count}",
        f"- **Target Failure Rate:** {quality.targeted_failure_rate * 100:.2f}%",
        f"- **Localization Failures:** {quality.localization_failure_count}",
        f"- **Clean-Copy Verification:** {'PASSED' if quality.clean_copy_verification_success else 'FAILED'}",
        f"- **Recovery Successes:** {quality.recovery_success_count}",
        "",
        "## Cost Metrics",
        f"- **Retrieval Call Count:** {cost.retrieval_call_count}",
        f"  - Semantic Calls: {cost.semantic_calls}",
        f"  - Neighbor Calls: {cost.neighbor_calls}",
        f"  - Subgraph Calls: {cost.subgraph_calls}",
        f"- **Retrieval Tool-Call Share:** {f'{cost.retrieval_tool_call_share * 100:.1f}%' if cost.retrieval_tool_call_share is not None else 'N/A'}",
        f"- **Mean Duration:** {f'{cost.mean_retrieval_duration_ms:.1f} ms' if cost.mean_retrieval_duration_ms is not None else 'N/A'}",
        f"- **Median Duration:** {f'{cost.median_retrieval_duration_ms:.1f} ms' if cost.median_retrieval_duration_ms is not None else 'N/A'}",
        f"- **p95 Duration:** {f'{cost.p95_retrieval_duration_ms:.1f} ms' if cost.p95_retrieval_duration_ms is not None else 'N/A'}",
        f"- **Retrieved Entities (Total):** {cost.retrieved_entities}",
        f"- **Unique Entities:** {cost.unique_entities}",
        f"- **Duplicate Entities:** {cost.duplicate_entities}",
        f"- **Source Files Exposed:** {cost.source_files_exposed}",
        f"- **Context Growth:** {f'{cost.total_context_growth_tokens} tokens' if cost.total_context_growth_tokens is not None else 'N/A'}",
        f"- **Cache Hits:** {cost.cache_hit_count} ({f'{cost.cache_hit_ratio * 100:.1f}%' if cost.cache_hit_ratio is not None else 'N/A'})",
        f"- **Info Gain Proxy (Entities/Call):** {cost.unique_entities_per_retrieval_call or 'N/A'}",
        f"- **Info Gain Proxy (Files/Call):** {cost.unique_files_per_retrieval_call or 'N/A'}",
        "",
        "## Retrieval Diagnostics",
    ])

    if diagnostics:
        lines.extend([
            f"- **Redundancy Count:** {diagnostics.redundancy_count}",
            f"- **Dead Retrieval Count:** {diagnostics.dead_retrieval_count}",
            f"- **Over-Expansion Count:** {diagnostics.over_expansion_count}",
            f"- **Under-Expansion Count:** {diagnostics.under_expansion_count}",
            f"- **Late Retrieval Count:** {diagnostics.late_retrieval_count}",
            f"- **Misleading Retrieval Count:** {diagnostics.misleading_retrieval_count}",
        ])
        if diagnostics.diagnostic_messages:
            lines.append("- **Diagnostic Details:**")
            for msg in diagnostics.diagnostic_messages[:5]:
                lines.append(f"  - {msg}")
    else:
        lines.append("- No diagnostics recorded.")

    lines.extend([
        "",
        "## Paired Task Comparison",
    ])

    if paired_outcomes:
        psummary = summarize_paired_outcomes(paired_outcomes)
        lines.extend([
            f"- **Total Paired Tasks:** {psummary['total_paired']}",
            f"- **FAIL -> PASS (Direct Fixes):** {psummary['FAIL_TO_PASS']}",
            f"- **PASS -> FAIL (Regressions):** {psummary['PASS_TO_FAIL']}",
            f"- **FAIL -> OTHER_FAIL (Shifted):** {psummary['FAIL_TO_OTHER_FAIL']}",
            f"- **FAIL Unchanged:** {psummary['FAIL_UNCHANGED']}",
            f"- **PASS Unchanged:** {psummary['PASS_UNCHANGED']}",
            f"- **Baseline Retrieval Calls:** {psummary['total_retrieval_calls_baseline']}",
            f"- **Candidate Retrieval Calls:** {psummary['total_retrieval_calls_candidate']}",
        ])
    else:
        lines.append("- No paired baseline comparison executed.")

    lines.extend([
        "",
        "## Evaluation Gates",
        f"- **Smoke Gate:** {'PASSED' if smoke_passed is True else ('FAILED' if smoke_passed is False else 'SKIPPED')}",
        f"- **Validation Gate:** {'PASSED' if validation_passed is True else ('FAILED' if validation_passed is False else 'UNEXECUTED')}",
        f"- **Held-Out Gate:** {'PASSED' if held_out_passed is True else ('REGRESSED' if held_out_passed is False else 'UNEXECUTED (held-out protected)')}",
        f"- **Authoritative Decision:** `{manifest.decision}`",
        f"- **Decision Rationale:** {manifest.decision_rationale or 'N/A'}",
        "",
        "## Artifact Hashes",
    ])

    if manifest.artifact_hashes:
        for fname, hval in sorted(manifest.artifact_hashes.items()):
            lines.append(f"- `{fname}`: `{hval}`")
    else:
        lines.append("- None recorded.")

    return "\n".join(lines)
