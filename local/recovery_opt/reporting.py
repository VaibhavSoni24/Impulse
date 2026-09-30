"""Audit and Evaluation Reporting for Recovery Experiments (Stage 35 Sections 38, 42, 52).

Generates comprehensive Markdown reports:
- Candidate audit report (`report.md`)
- Pareto Cost/Benefit Frontier table
- Comparative matrix table across candidates
- Comprehensive Stage 35 report
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.recovery_opt.diff import format_recovery_policy_diff_md
from local.recovery_opt.models import (
    RecoveryCandidateManifest,
    RecoveryCostMetrics,
    RecoveryDiagnostics,
    RecoveryHypothesis,
    RecoveryPolicy,
    RecoveryQualityMetrics,
    RecoveryTaskPairOutcome,
)


def generate_candidate_report_md(
    manifest: RecoveryCandidateManifest,
    policy: RecoveryPolicy,
    parent_policy: Optional[RecoveryPolicy],
    hypothesis: Optional[RecoveryHypothesis],
    cost_metrics: RecoveryCostMetrics,
    quality_metrics: RecoveryQualityMetrics,
    diagnostics: RecoveryDiagnostics,
    paired_outcomes: List[RecoveryTaskPairOutcome],
    promotion_decision: str,
    promotion_rationale: str,
) -> str:
    """Generates the authoritative Markdown audit report for an individual recovery candidate."""
    lines: list[str] = [
        f"# Recovery Optimization Experiment Report: Candidate `{manifest.candidate_id}`",
        "",
        "## Candidate Metadata",
        f"- **Candidate ID:** `{manifest.candidate_id}`",
        f"- **Parent Candidate:** `{manifest.parent_candidate}`",
        f"- **Policy Hash:** `{manifest.policy_hash}`",
        f"- **Evidence Mode:** `{manifest.evidence_mode}`",
        f"- **Benchmark Split:** `{manifest.benchmark_split}`",
        f"- **Promotion Decision:** `{promotion_decision}`",
        f"- **Decision Rationale:** {promotion_rationale}",
        "",
        "## Invariance Verification",
        f"- **Root Prompt Hash:** `{manifest.root_prompt_hash[:12]}...` (Invariant)",
        f"- **Retrieval Policy Hash:** `{manifest.retrieval_policy_hash[:12]}...` (Invariant R0)",
        f"- **Testing Policy Hash:** `{manifest.testing_policy_hash[:12]}...` (Invariant T0)",
        f"- **Topology:** `{manifest.topology_hash}` (Invariant)",
        f"- **Model ID:** `{manifest.model_id}` (Invariant)",
        f"- **Test Strategy Skill:** `{manifest.test_strategy_skill_hash[:12]}...` (Frozen)",
        f"- **Repo Triage Skill:** `{manifest.repo_triage_skill_hash[:12]}...` (Frozen)",
        "",
    ]

    # Hypothesis
    if hypothesis:
        lines.extend([
            "## Causal Recovery Hypothesis",
            f"- **Target Failure:** `{hypothesis.target_failure}`",
            f"- **Observation:** {hypothesis.observation}",
            f"- **Hypothesis:** {hypothesis.hypothesis}",
            f"- **Recovery Change:** {hypothesis.recovery_change}",
            f"- **Expected Signal:** {hypothesis.expected_metric_signal}",
            f"- **Rejection Condition:** {hypothesis.rejection_condition}",
            "",
        ])

    # Quality & Effectiveness Metrics
    lines.extend([
        "## Recovery Quality & Effectiveness",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Targeted Recovery Success Rate | {quality_metrics.targeted_recovery_success_rate * 100:.1f}% |",
        f"| Targeted Failure Reduction | {quality_metrics.targeted_failure_reduction} tasks |",
        f"| Recovery Loop Count | {quality_metrics.recovery_loop_count} |",
        f"| Detection Latency (Events) | {quality_metrics.detection_latency_events:.1f} |",
        f"| Detection Latency (Turns) | {quality_metrics.detection_latency_turns:.1f} |",
        f"| Average Recovery Attempts | {quality_metrics.average_recovery_attempts:.2f} |",
        f"| Tasks Recovered After Failure | {quality_metrics.tasks_recovered_after_failure} |",
        f"| Tasks Abandoned After Failure | {quality_metrics.tasks_abandoned_after_failure} |",
        f"| Alternate Path Success Rate | {quality_metrics.alternate_path_success_rate * 100:.1f}% |",
        f"| First-Attempt Success Rate | {quality_metrics.first_attempt_recovery_success_rate * 100:.1f}% |",
        "",
    ])

    # Cost Metrics
    lines.extend([
        "## Resource & Recovery Cost Metrics",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Total Recovery Tool Calls | {cost_metrics.recovery_tool_calls} |",
        f"| Recovery Turns Used | {cost_metrics.recovery_turns} |",
        f"| Total Retries Executed | {cost_metrics.retry_count} |",
        f"| Total Recovery Runtime | {cost_metrics.recovery_runtime_ms:.1f} ms |",
        f"| Additional Tests Caused | {cost_metrics.additional_tests_caused} |",
        f"| Additional Retrievals Caused | {cost_metrics.additional_retrieval_calls} |",
        f"| Additional Context Growth | {cost_metrics.additional_context_growth_bytes} bytes |",
        f"| Repeated Failed Interventions | {cost_metrics.repeated_failed_interventions} |",
        "",
    ])

    # Diagnostics
    lines.extend([
        "## Deterministic Diagnostics",
        f"- **Late Recovery:** `{'YES' if diagnostics.late_recovery else 'NO'}`",
        f"- **Repeated Identical Recovery:** `{'YES' if diagnostics.repeated_identical_recovery else 'NO'}`",
        f"- **Recovery Oscillation:** `{'YES' if diagnostics.recovery_oscillation else 'NO'}`",
        f"- **Retry Waste:** `{'YES' if diagnostics.retry_waste else 'NO'}`",
        f"- **Recovery Without State Change:** `{'YES' if diagnostics.recovery_without_state_change else 'NO'}`",
        f"- **Missed Recovery Opportunity:** `{'YES' if diagnostics.missed_recovery_opportunity else 'NO'}`",
        f"- **Failed Recovery:** `{'YES' if diagnostics.failed_recovery else 'NO'}`",
        f"- **Unrelated Regression Caused:** `{'YES' if diagnostics.recovery_causing_unrelated_regression else 'NO'}`",
        f"- **Excessive Testing:** `{'YES' if diagnostics.recovery_causing_excessive_testing else 'NO'}`",
        f"- **Excessive Retrieval:** `{'YES' if diagnostics.recovery_causing_excessive_retrieval else 'NO'}`",
        f"- **Budget Exhaustion:** `{'YES' if diagnostics.recovery_budget_exhaustion else 'NO'}`",
        f"- **Success After Unnecessary Repetitions:** `{'YES' if diagnostics.recovery_success_after_unnecessary_repetitions else 'NO'}`",
        "",
    ])
    if diagnostics.diagnostic_notes:
        lines.append("### Diagnostic Notes")
        for note in diagnostics.diagnostic_notes:
            lines.append(f"- {note}")
        lines.append("")

    # Paired comparisons
    if paired_outcomes:
        lines.extend([
            "## Paired Failure Set Results",
            f"Total tasks in failure set: **{len(paired_outcomes)}**",
            "",
            "| Task ID | Baseline | Candidate | Transition | Baseline Action | Candidate Action | Base Lat | Cand Lat | Base Loops | Cand Loops |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for p in paired_outcomes:
            b_lat = str(p.baseline_detection_latency) if p.baseline_detection_latency is not None else "-"
            c_lat = str(p.candidate_detection_latency) if p.candidate_detection_latency is not None else "-"
            lines.append(
                f"| `{p.task_id}` | `{p.baseline_task_result}` | `{p.candidate_task_result}` | "
                f"`{p.transition}` | `{p.baseline_recovery_action}` | `{p.candidate_recovery_action}` | "
                f"{b_lat} | {c_lat} | {p.baseline_loops} | {p.candidate_loops} |"
            )
        lines.append("")

    # Policy diff against parent
    if parent_policy:
        lines.extend([
            "## Policy Differences vs. Parent",
            format_recovery_policy_diff_md(parent_policy, policy),
            "",
        ])

    return "\n".join(lines)


def generate_pareto_frontier_md(
    candidates_data: List[dict[str, Any]],
) -> str:
    """Generates the transparent Pareto Cost/Benefit Frontier table (Stage 35 Section 42)."""
    lines: list[str] = [
        "## Recovery Cost / Benefit Pareto Frontier",
        "",
        "| Candidate | Recovery Success | Detection Latency (Ev/Turn) | Loops | Avg Attempts | Runtime (ms) | Tool Calls | Additional Tests | Decision |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in candidates_data:
        cid = c.get("candidate_id", "UNKNOWN")
        qm = c.get("quality_metrics", {})
        cm = c.get("cost_metrics", {})
        dec = c.get("decision", "UNKNOWN")

        succ = f"{qm.get('targeted_recovery_success_rate', 0.0) * 100:.1f}%"
        lat = f"{qm.get('detection_latency_events', 0.0):.1f} / {qm.get('detection_latency_turns', 0.0):.1f}"
        loops = str(qm.get("recovery_loop_count", 0))
        att = f"{qm.get('average_recovery_attempts', 0.0):.2f}"
        rt = f"{cm.get('recovery_runtime_ms', 0.0):.1f}"
        tc = str(cm.get("recovery_tool_calls", 0))
        tests = str(cm.get("additional_tests_caused", 0))

        lines.append(
            f"| `{cid}` | {succ} | {lat} | {loops} | {att} | {rt} | {tc} | {tests} | `{dec}` |"
        )

    lines.append("")
    return "\n".join(lines)
