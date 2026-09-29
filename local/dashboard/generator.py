"""Deterministic report artifact generator for IMPULSE Failure Dashboard (Stage 30).

Produces for each candidate & split:
- summary.md
- failures.jsonl
- metrics.csv
- manifest.json
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.hashing import compute_file_sha256
from benchmark.splits.models import SplitManifest
from local.dashboard.integrity import verify_split_before_dashboard
from local.dashboard.metrics import aggregate_dashboard_report
from local.dashboard.models import DashboardReport, EvidenceMode, RunSummary
from local.dashboard.queries import build_tasks_lookup, fetch_runs_from_db, load_runs_from_jsonl
from local.diff_discipline.detectors import scan_content_for_secrets


def get_git_commit(repo_root: Path) -> str:
    """Retrieves current Git HEAD commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def format_pct(val: Optional[float]) -> str:
    """Formats float to percentage string or N/A."""
    if val is None:
        return "N/A"
    return f"{round(val * 100.0, 2)}%"


def format_num(val: Optional[float], decimals: int = 2) -> str:
    """Formats float to rounded string or N/A."""
    if val is None:
        return "N/A"
    return str(round(val, decimals))


def format_csv_val(val: Any) -> str:
    """Formats value for CSV, outputting empty string for null."""
    if val is None:
        return ""
    return str(val)


def render_summary_markdown(report: DashboardReport) -> str:
    """Renders human-readable summary.md from DashboardReport."""
    md = io.StringIO()

    md.write(f"# Candidate / Split Summary: {report.candidate_id} ({report.split_name.upper()})\n\n")
    md.write(f"- **Status:** {report.report_status.value}\n")
    md.write(f"- **Evidence Mode:** {report.evidence_mode.value}\n")
    md.write(f"- **Candidate:** `{report.candidate_id}`\n")
    md.write(f"- **Split:** `{report.split_name}`\n")
    md.write(f"- **Split Version:** `{report.split_version}`\n")
    md.write(f"- **Report Version:** {report.generator_version}\n")
    md.write(f"- **Git Commit:** `{report.git_commit}`\n")
    md.write(f"- **Generated At:** {report.generated_at}\n\n")

    # Dataset
    md.write("## 1. Dataset Overview\n\n")
    md.write(f"- Total Tasks in Split: **{report.total_tasks_in_split}**\n")
    md.write(f"- Total Runs Recorded: **{report.total_runs_recorded}**\n")
    md.write(f"- Completed Eligible Runs: **{report.completed_run_count}**\n")
    md.write(f"- Unavailable Runs: **{report.unavailable_count}**\n")
    md.write(f"- Skipped Runs: **{report.skipped_count}**\n\n")

    # Overall Results
    md.write("## 2. Overall Results\n\n")
    md.write(f"- Pass Rate: **{format_pct(report.overall_pass_rate)}**\n")
    md.write(f"- Failure Rate: **{format_pct(report.overall_failure_rate)}**\n")
    md.write(f"- Eligible Run Count: **{report.eligible_run_count}**\n")
    md.write(f"- Passed Runs: **{report.success_count}**\n")
    md.write(f"- Failed Runs: **{report.failure_count}**\n\n")

    # Repository Results
    md.write("## 3. Repository Results\n\n")
    md.write("| Repository | Tasks | Completed | Passed | Failed | Unavailable | Pass Rate |\n")
    md.write("|---|---|---|---|---|---|---|\n")
    for r in report.repository_results:
        md.write(
            f"| `{r.repository}` | {r.total_tasks} | {r.completed_runs} | {r.passed_runs} | "
            f"{r.failed_runs} | {r.unavailable_runs} | {format_pct(r.pass_rate)} |\n"
        )
    if not report.repository_results:
        md.write("| *None* | 0 | 0 | 0 | 0 | 0 | N/A |\n")
    md.write("\n")

    # Task-Type Results
    md.write("## 4. Task-Type Results\n\n")
    if report.task_type_status == "AVAILABLE" and report.task_type_results:
        md.write("| Task Type | Tasks | Completed | Passed | Failed | Pass Rate |\n")
        md.write("|---|---|---|---|---|---|\n")
        for t in report.task_type_results:
            md.write(
                f"| `{t.task_type}` | {t.total_tasks} | {t.completed_runs} | {t.passed_runs} | "
                f"{t.failed_runs} | {format_pct(t.pass_rate)} |\n"
            )
    else:
        md.write(f"- **Status:** `{report.task_type_status}`\n")
        md.write(f"- **Reason:** {report.task_type_reason}\n")
    md.write("\n")

    # Failure Categories
    md.write("## 5. Failure Categories\n\n")
    md.write("### 5.1 Canonical E9 Failure Classes\n\n")
    md.write("| Failure Category | Count | Percentage |\n")
    md.write("|---|---|---|\n")
    for c in report.canonical_failures:
        md.write(f"| `{c.category}` | {c.count} | {format_pct(c.percentage / 100.0 if c.percentage else 0.0)} |\n")
    if not report.canonical_failures:
        md.write("| *None recorded* | 0 | 0.0% |\n")
    md.write("\n")

    if report.evaluator_failures:
        md.write("### 5.2 Evaluator Infrastructure / Pipeline Stages\n\n")
        md.write("| Failure Stage / Class | Count | Percentage |\n")
        md.write("|---|---|---|\n")
        for e in report.evaluator_failures:
            md.write(f"| `{e.category}` | {e.count} | {format_pct(e.percentage / 100.0 if e.percentage else 0.0)} |\n")
        md.write("\n")

    # Runtime
    md.write("## 6. Runtime Statistics\n\n")
    md.write(f"- Mean: **{format_num(report.runtime_stats.mean)}s**\n")
    md.write(f"- Median: **{format_num(report.runtime_stats.median)}s**\n")
    md.write(f"- P95: **{format_num(report.runtime_stats.p95)}s**\n")
    md.write(f"- Sample Count: **{report.runtime_stats.count}**\n\n")

    # Tool Calls
    md.write("## 7. Tool Calls Statistics\n\n")
    md.write(f"- Mean: **{format_num(report.tool_call_stats.mean)}**\n")
    md.write(f"- Median: **{format_num(report.tool_call_stats.median)}**\n")
    md.write(f"- P95: **{format_num(report.tool_call_stats.p95)}**\n")
    md.write(f"- Sample Count: **{report.tool_call_stats.count}**\n\n")

    # Turns
    md.write("## 8. Turns & Code Modifications\n\n")
    md.write(f"- Average Turns: **{format_num(report.turn_stats.mean)}** (Median: {format_num(report.turn_stats.median)})\n")
    md.write(f"- Average Patch Lines: **{format_num(report.patch_line_stats.mean)}**\n")
    md.write(f"- Average Files Changed: **{format_num(report.files_changed_stats.mean)}**\n\n")

    # Recovery
    md.write("## 9. Recovery Path Performance\n\n")
    md.write(f"- Recovery Triggered: **{report.recovery_attempts}**\n")
    md.write(f"- Recovery Successful: **{report.recovery_successes}**\n")
    md.write(f"- Recovery Success Rate: **{format_pct(report.recovery_success_rate)}**\n\n")

    # Evaluator Failures
    md.write("## 10. Evaluator Clean-Copy Specifics\n\n")
    md.write(f"- Clean-Copy Verified Runs: **{report.clean_copy_verified_count}**\n")
    md.write(f"- Patch Apply Conflicts: **{report.patch_apply_conflicts}**\n")
    md.write(f"- Verification Failures: **{report.verification_failures}**\n\n")

    # Evidence Limitations
    md.write("## 11. Evidence Limitations & Boundary Rules\n\n")
    md.write(f"- **Current Evidence Mode:** `{report.evidence_mode.value}`\n")
    md.write("- **Zero Fabrication:** Unobserved metrics are strictly reported as `N/A`, never as zero.\n")
    md.write("- **Strict Isolation:** Synthetic `FIXTURE` execution records are never merged with `LIVE` competition benchmarks.\n")
    if report.evidence_mode == EvidenceMode.UNAVAILABLE or report.completed_run_count == 0:
        md.write("- **Hardware Constraint:** Live competition inference (Gemma 4 31B, 96 GB VRAM) is unavailable on this host; results reflect local infrastructure limits.\n")

    return md.getvalue()


def render_failures_jsonl(failed_runs: List[dict[str, Any]]) -> str:
    """Renders deterministic JSON lines string for failed runs."""
    lines: list[str] = []
    for f in failed_runs:
        clean_record = {
            "run_id": f.get("run_id"),
            "task_id": f.get("task_id"),
            "candidate_id": f.get("candidate_id"),
            "split": f.get("split"),
            "repository": f.get("repository"),
            "execution_mode": f.get("execution_mode"),
            "failure_class": f.get("failure_class"),
            "failure_stage": f.get("failure_stage"),
            "termination_reason": f.get("termination_reason"),
            "elapsed_seconds": f.get("elapsed_seconds"),
            "tool_calls": f.get("tool_calls"),
            "turns": f.get("turns"),
            "recovery_triggered": f.get("recovery_triggered"),
            "recovery_success": f.get("recovery_success"),
            "patch_apply_status": f.get("patch_apply_status"),
            "verification_status": f.get("verification_status"),
        }
        lines.append(json.dumps(clean_record, sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")


def render_metrics_csv(report: DashboardReport) -> str:
    """Renders machine-readable metrics.csv."""
    headers = [
        "candidate_id",
        "split",
        "split_version",
        "evidence_mode",
        "task_count",
        "eligible_run_count",
        "completed_run_count",
        "success_count",
        "failure_count",
        "pass_rate",
        "avg_runtime_seconds",
        "median_runtime_seconds",
        "p95_runtime_seconds",
        "avg_tool_calls",
        "median_tool_calls",
        "avg_turns",
        "median_turns",
        "avg_patch_lines",
        "avg_files_changed",
        "recovery_attempts",
        "recovery_successes",
        "recovery_success_rate",
        "runtime_unavailable_count",
        "patch_apply_conflicts",
        "verification_failures",
        "report_status",
    ]

    row = [
        format_csv_val(report.candidate_id),
        format_csv_val(report.split_name),
        format_csv_val(report.split_version),
        format_csv_val(report.evidence_mode.value),
        format_csv_val(report.total_tasks_in_split),
        format_csv_val(report.eligible_run_count),
        format_csv_val(report.completed_run_count),
        format_csv_val(report.success_count),
        format_csv_val(report.failure_count),
        format_csv_val(report.overall_pass_rate),
        format_csv_val(report.runtime_stats.mean),
        format_csv_val(report.runtime_stats.median),
        format_csv_val(report.runtime_stats.p95),
        format_csv_val(report.tool_call_stats.mean),
        format_csv_val(report.tool_call_stats.median),
        format_csv_val(report.turn_stats.mean),
        format_csv_val(report.turn_stats.median),
        format_csv_val(report.patch_line_stats.mean),
        format_csv_val(report.files_changed_stats.mean),
        format_csv_val(report.recovery_attempts),
        format_csv_val(report.recovery_successes),
        format_csv_val(report.recovery_success_rate),
        format_csv_val(report.unavailable_count),
        format_csv_val(report.patch_apply_conflicts),
        format_csv_val(report.verification_failures),
        format_csv_val(report.report_status.value),
    ]

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(headers)
    writer.writerow(row)
    return out.getvalue()


class DashboardGenerator:
    """Generates deterministic dashboard reports for candidates and splits."""

    def __init__(
        self,
        repo_root: Path,
        output_dir: Optional[Path] = None,
        splits_root: Optional[Path] = None,
        split_version: str = "v1",
    ) -> None:
        self.repo_root = Path(repo_root)
        self.output_dir = Path(output_dir) if output_dir else self.repo_root / "experiments" / "dashboard"
        self.splits_root = Path(splits_root) if splits_root else self.repo_root / "benchmark" / "splits"
        self.split_version = split_version
        self.git_commit = get_git_commit(self.repo_root)

    def generate(
        self,
        candidate_id: str,
        split_name: str,
        runs: List[RunSummary],
        target_evidence_mode: Optional[EvidenceMode] = None,
        source_db_sha256: str = "",
        force: bool = True,
    ) -> Tuple[DashboardReport, Path]:
        """Generates all 4 artifacts into output_dir/<candidate>/<split>/.

        Returns:
            Tuple of (DashboardReport, target_directory).
        """
        # 1. Split integrity verification
        split_manifest, _ = verify_split_before_dashboard(
            split_name=split_name,
            split_version=self.split_version,
            splits_root=self.splits_root,
        )

        # 2. Metric aggregation
        report = aggregate_dashboard_report(
            candidate_id=candidate_id,
            split_name=split_name,
            runs=runs,
            split_manifest=split_manifest,
            split_version=self.split_version,
            target_evidence_mode=target_evidence_mode,
            git_commit=self.git_commit,
            source_db_sha256=source_db_sha256,
        )

        # 3. Target output directory
        target_dir = self.output_dir / candidate_id / split_name.lower().strip()
        target_dir.mkdir(parents=True, exist_ok=True)

        summary_p = target_dir / "summary.md"
        failures_p = target_dir / "failures.jsonl"
        metrics_p = target_dir / "metrics.csv"
        manifest_p = target_dir / "manifest.json"

        # 4. Render content
        summary_content = render_summary_markdown(report)
        failures_content = render_failures_jsonl(report.failed_runs)
        metrics_content = render_metrics_csv(report)

        # 5. Security check on text artifacts (Phase 28)
        findings = scan_content_for_secrets(summary_p, summary_content)
        if findings:
            raise ValueError(f"Secret detected in summary.md: {[f.message for f in findings]}")
        f_findings = scan_content_for_secrets(failures_p, failures_content)
        if f_findings:
            raise ValueError(f"Secret detected in failures.jsonl: {[f.message for f in f_findings]}")

        # 6. Write files
        summary_p.write_text(summary_content, encoding="utf-8")
        failures_p.write_text(failures_content, encoding="utf-8")
        metrics_p.write_text(metrics_content, encoding="utf-8")

        # 7. Compute artifact hashes
        artifact_hashes = {
            "summary_md": compute_file_sha256(summary_p),
            "failures_jsonl": compute_file_sha256(failures_p),
            "metrics_csv": compute_file_sha256(metrics_p),
        }

        # 8. Render and write manifest.json (Phase 13)
        manifest_data = {
            "generator_version": report.generator_version,
            "git_commit": self.git_commit,
            "candidate_id": report.candidate_id,
            "split_name": report.split_name,
            "split_version": report.split_version,
            "split_manifest_sha256": report.split_manifest_sha256,
            "source_db_sha256": report.source_db_sha256,
            "evidence_mode": report.evidence_mode.value,
            "report_status": report.report_status.value,
            "record_counts": {
                "total_tasks_in_split": report.total_tasks_in_split,
                "total_runs_recorded": report.total_runs_recorded,
                "eligible_run_count": report.eligible_run_count,
                "completed_run_count": report.completed_run_count,
                "success_count": report.success_count,
                "failure_count": report.failure_count,
                "unavailable_count": report.unavailable_count,
                "failed_runs_extracted": len(report.failed_runs),
            },
            "artifact_hashes": artifact_hashes,
            "generated_at": report.generated_at,
        }
        manifest_p.write_text(json.dumps(manifest_data, indent=2, sort_keys=True), encoding="utf-8")

        return report, target_dir


def verify_dashboard_artifacts(target_dir: Path | str) -> Tuple[bool, List[str]]:
    """Verifies hashes and files in a generated dashboard directory."""
    errors: list[str] = []
    dir_p = Path(target_dir)
    manifest_p = dir_p / "manifest.json"
    if not manifest_p.is_file():
        return False, [f"manifest.json missing in {dir_p}"]

    try:
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"Invalid manifest.json: {e}"]

    artifact_hashes = manifest.get("artifact_hashes", {})
    for fname, exp_hash in artifact_hashes.items():
        actual_name = fname.replace("_", ".")
        actual_file = dir_p / actual_name
        if not actual_file.is_file():
            errors.append(f"Required artifact {actual_name} missing")
            continue
        actual_hash = compute_file_sha256(actual_file)
        if actual_hash != exp_hash:
            errors.append(f"Hash mismatch for {actual_name}: expected {exp_hash[:8]}, got {actual_hash[:8]}")

    return len(errors) == 0, errors
