"""Testing Strategy Experiment Audit Reporting (Stage 34 Section 40).

Generates authoritative human-readable report.md for testing strategy experiments
with exact quantitative failure reductions, evidence yield metrics, cost metrics,
diagnostics, and reproducibility hashes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.fdd.models import FDDRunDelta
from local.testing_opt.diff import TestPolicyDiff, render_test_policy_diff_md
from local.testing_opt.models import (
    TestCandidateManifest,
    TestCostMetrics,
    TestDiagnostics,
    TestEvidenceMetrics,
    TestTaskPairOutcome,
)
from local.testing_opt.paired import summarize_paired_outcomes


def generate_testing_experiment_report(
    manifest: TestCandidateManifest,
    diff: TestPolicyDiff,
    quality: TestEvidenceMetrics,
    cost: TestCostMetrics,
    diagnostics: Optional[TestDiagnostics] = None,
    paired_outcomes: Optional[List[TestTaskPairOutcome]] = None,
    delta: Optional[FDDRunDelta] = None,
    smoke_passed: Optional[bool] = None,
    validation_passed: Optional[bool] = None,
    held_out_passed: Optional[bool] = None,
) -> str:
    """Generates human-readable markdown audit report for a testing strategy experiment."""
    lines: List[str] = [
        f"# Testing Strategy Experiment: {manifest.candidate_id} ({manifest.testing_variant})",
        "",
        "## Candidate Metadata",
        f"- **Candidate ID:** `{manifest.candidate_id}`",
        f"- **Testing Variant:** `{manifest.testing_variant}`",
        f"- **Policy Hash:** `{manifest.testing_policy_hash}`",
        f"- **Evidence Mode:** `{manifest.evidence_mode}`",
        f"- **Prompt ID:** `{manifest.prompt_id}` (SHA-256: `{manifest.prompt_sha256}`)",
        f"- **Retrieval Policy Hash:** `{manifest.retrieval_policy_hash}`",
        f"- **Test Skill Hash:** `{manifest.test_strategy_skill_sha256}`",
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
            f"- **Testing Change:** `{manifest.hypothesis.testing_change}`",
            f"- **Expected Metric Signal:** {manifest.hypothesis.expected_signal}",
            f"- **Rejection Condition:** {manifest.hypothesis.rejection_condition}",
        ])
    else:
        lines.append("- Baseline specification (no active intervention hypothesis).")

    lines.extend([
        "",
        "## Testing Policy Diff",
        render_test_policy_diff_md(diff),
        "",
        "## Evidence & Quality Metrics",
        f"- **Pass Rate:** {quality.pass_rate * 100:.2f}%",
        f"- **Failure Rate:** {quality.failure_rate * 100:.2f}%",
        f"- **Target Failure Mode:** `{quality.targeted_failure_mode}`",
        f"- **Target Failure Count:** {quality.targeted_failure_count}",
        f"- **Target Failure Rate:** {quality.targeted_failure_rate * 100:.2f}%",
        f"- **Regressions Caught:** {quality.regressions_detected}",
        f"- **Incomplete Fixes Caught:** {quality.incomplete_fixes_detected}",
        f"- **Targeted Behavior Confirmed:** {quality.targeted_behavior_confirmed}",
        f"- **Adjacent Failures Discovered:** {quality.adjacent_failures_discovered}",
        f"- **Subsystem Failures Discovered:** {quality.subsystem_failures_discovered}",
        f"- **Full Suite Failures Discovered:** {quality.full_suite_failures_discovered}",
        f"- **False-Confidence Cases Avoided:** {quality.false_confidence_count}",
        f"- **Earliest Detection Level:** `{quality.early_detection_level}`",
        f"- **Clean-Copy Verification:** {'PASSED' if quality.clean_copy_verification_success else 'FAILED'}",
        "",
        "## Cost Metrics",
        f"- **Total Test Commands:** {cost.total_test_commands}",
        f"  - Targeted Commands: {cost.targeted_commands}",
        f"  - Adjacent Commands: {cost.adjacent_commands}",
        f"  - Subsystem Commands: {cost.subsystem_commands}",
        f"  - Full Suite Commands: {cost.full_suite_commands}",
        f"- **Total Test Cases Executed:** {cost.total_tests_executed}",
        f"- **Total Test Runtime:** {cost.total_test_runtime_ms:.1f} ms",
        f"- **Mean Test Duration:** {f'{cost.mean_test_duration_ms:.1f} ms' if cost.mean_test_duration_ms is not None else 'N/A'}",
        f"- **Median Test Duration:** {f'{cost.median_test_duration_ms:.1f} ms' if cost.median_test_duration_ms is not None else 'N/A'}",
        f"- **p95 Test Duration:** {f'{cost.p95_test_duration_ms:.1f} ms' if cost.p95_test_duration_ms is not None else 'N/A'}",
        f"- **Total Output Volume:** {cost.total_output_bytes} bytes",
        f"- **Repeated Commands:** {cost.repeated_command_count}",
        f"- **Duplicate Test Cases:** {cost.duplicate_test_case_count}",
        f"- **Testing Tool-Call Share:** {f'{cost.testing_tool_call_share * 100:.1f}%' if cost.testing_tool_call_share is not None else 'N/A'}",
        "",
        "## Testing Diagnostics",
    ])

    if diagnostics:
        lines.extend([
            f"- **Duplicate Commands:** {diagnostics.duplicate_command_count}",
            f"- **Duplicate Test Cases:** {diagnostics.duplicate_case_count}",
            f"- **Reruns Without Edit:** {diagnostics.rerun_unchanged_code_count}",
            f"- **Unnecessary Full Suites:** {diagnostics.unnecessary_full_suite_count}",
            f"- **Zero-New-Evidence Adjacent Runs:** {diagnostics.zero_new_evidence_adjacent_count}",
            f"- **Zero-New-Evidence Subsystem Runs:** {diagnostics.zero_new_evidence_subsystem_count}",
            f"- **Repeated Identical Failures:** {diagnostics.repeated_failure_count}",
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
            f"- **PASS -> FAIL (Regressions Caught):** {psummary['PASS_TO_FAIL']}",
            f"- **FAIL -> OTHER_FAIL (Shifted):** {psummary['FAIL_TO_OTHER_FAIL']}",
            f"- **FAIL Unchanged:** {psummary['FAIL_UNCHANGED']}",
            f"- **PASS Unchanged:** {psummary['PASS_UNCHANGED']}",
            f"- **Baseline Test Commands:** {psummary['total_test_commands_baseline']}",
            f"- **Candidate Test Commands:** {psummary['total_test_commands_candidate']}",
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
