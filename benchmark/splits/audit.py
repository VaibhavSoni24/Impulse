"""Statistical audit and reporting subsystem for benchmark splits (Stage 29 Phase 18, 19).

Produces:
- Structured distribution statistics (tasks per split, repos per split, proportions)
- Human-readable Markdown summary reports for audit and review
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from benchmark.splits.models import (
    DistributionReport,
    LeakageAuditReport,
    SplitManifest,
)


def generate_distribution_report(
    splits: dict[str, list[dict[str, Any]]],
    total_source_count: int,
) -> DistributionReport:
    """Computes descriptive distribution metrics across benchmark splits."""
    split_counts: dict[str, int] = {}
    split_proportions: dict[str, float] = {}
    repos_per_split: dict[str, list[str]] = {}
    tasks_per_repo: Counter[str] = Counter()
    tasks_per_repo_per_split: dict[str, dict[str, int]] = {}

    for s_name, tasks in splits.items():
        count = len(tasks)
        split_counts[s_name] = count
        prop = (count / total_source_count) if total_source_count > 0 else 0.0
        split_proportions[s_name] = round(prop, 4)

        repo_counter: Counter[str] = Counter()
        for t in tasks:
            repo = str(t.get("repo", "unknown")).strip()
            repo_counter[repo] += 1
            tasks_per_repo[repo] += 1

        repos_per_split[s_name] = sorted(list(repo_counter.keys()))
        tasks_per_repo_per_split[s_name] = dict(repo_counter)

    return DistributionReport(
        total_records=total_source_count,
        split_counts=split_counts,
        split_proportions=split_proportions,
        repos_per_split=repos_per_split,
        tasks_per_repo=dict(tasks_per_repo),
        tasks_per_repo_per_split=tasks_per_repo_per_split,
    )


def format_audit_summary_markdown(
    manifest: SplitManifest,
    leakage_report: LeakageAuditReport,
    dist_report: DistributionReport,
) -> str:
    """Renders a comprehensive Markdown audit report."""
    lines = [
        "# Benchmark Dataset Splits Audit Report (Stage 29)",
        "",
        f"- **Audit Status:** {leakage_report.status}",
        f"- **Policy Name:** `{manifest.policy_name}` (Version {manifest.policy_version})",
        f"- **Manifest SHA-256:** `{manifest.manifest_sha256[:16]}`",
        f"- **Source Dataset:** `{manifest.source.source_path}`",
        f"- **Source Records:** {manifest.source.record_count}",
        f"- **Source SHA-256:** `{manifest.source.source_sha256[:16]}`",
        f"- **Git Commit:** `{manifest.git_commit}`",
        f"- **Generated At:** {manifest.created_at}",
        "",
        "## 1. Split Allocation Summary",
        "",
        "| Split | Task Count | Proportion | Repositories | Task Set SHA-256 | File SHA-256 |",
        "|---|---|---|---|---|---|",
    ]

    for s_name, s_info in manifest.splits.items():
        prop = dist_report.split_proportions.get(s_name, 0.0) * 100
        repos = ", ".join(f"`{r}` ({c})" for r, c in s_info.repo_counts.items())
        lines.append(
            f"| **{s_name.upper()}** | {s_info.task_count} | {prop:.2f}% | {repos} | `{s_info.task_set_sha256[:12]}` | `{s_info.file_sha256[:12]}` |"
        )

    lines.extend([
        "",
        "## 2. Leakage and Isolation Verification",
        "",
        "| Audit Check | Status | Details |",
        "|---|---|---|",
        f"| Internal Uniqueness | {'PASS' if leakage_report.checks.get('internal_uniqueness') else 'FAIL'} | Task IDs unique within each split |",
        f"| Cross-Split Task Disjointness | {'PASS' if leakage_report.checks.get('cross_split_task_disjointness') else 'FAIL'} | Overlap: {len(leakage_report.cross_split_task_overlap)} tasks |",
        f"| No Duplicate Text Across Splits | {'PASS' if leakage_report.checks.get('no_cross_split_duplicate_text') else 'FAIL'} | Overlap: {len(leakage_report.duplicate_problem_statements)} descriptions |",
        f"| Repository Isolation | {'PASS' if leakage_report.checks.get('repository_isolation') else 'FAIL'} | Policy: `{manifest.policy_name}` |",
        f"| Commit Snapshot Isolation | {'PASS' if leakage_report.checks.get('commit_snapshot_isolation') else 'FAIL'} | Zero tasks sharing a base commit cross splits |",
        f"| Source Fidelity | {'PASS' if leakage_report.checks.get('source_fidelity') else 'FAIL'} | Content verified against source |",
        f"| Accounting Completeness | {'PASS' if leakage_report.checks.get('accounting_completeness') else 'FAIL'} | Total accounted: {dist_report.total_records} |",
        "",
        "## 3. Exclusions",
        "",
    ])

    if manifest.exclusions:
        lines.append("| Instance ID | Reason | Policy Rule |")
        lines.append("|---|---|---|")
        for exc in manifest.exclusions:
            lines.append(f"| `{exc.instance_id}` | {exc.reason} | `{exc.policy_rule}` |")
    else:
        lines.append("Zero records excluded. 100% of source dataset validly partitioned.")

    lines.append("")
    return "\n".join(lines)
