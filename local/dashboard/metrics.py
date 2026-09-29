"""Deterministic metric computation and failure aggregation for Stage 30 Dashboard.

Computes:
- Overall pass rate and failure rate (Phase 6)
- Pass rate by repository (Phase 6)
- Pass rate by task type or explicit UNAVAILABLE status (Phase 5 & 23)
- Canonical E9 failure categories vs. Evaluator infrastructure stages (Phase 6)
- Statistical summaries for continuous metrics (runtime, tool calls, turns) (Phase 6 & 7)
- Recovery metrics (Phase 7)
- Clean-copy verification outcomes (Phase 7)
- Deterministic failed run extraction for failures.jsonl (Phase 11)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from benchmark.splits.models import SplitManifest
from local.dashboard.models import (
    DashboardReport,
    EvidenceMode,
    FailureCategorySummary,
    MetricStats,
    ReportStatus,
    RepositoryMetrics,
    RunSummary,
    TaskTypeMetrics,
)
from local.failures.models import FailureClass


def calculate_metric_stats(values: List[float]) -> MetricStats:
    """Computes count, mean, median, p95, min, max over a non-empty numeric sequence.

    Strictly returns null statistics when no values exist.
    """
    clean_vals = [float(v) for v in values if v is not None and not math.isnan(v)]
    if not clean_vals:
        return MetricStats(count=0)

    clean_vals.sort()
    count = len(clean_vals)
    mean_val = round(sum(clean_vals) / count, 2)

    # Median
    mid = count // 2
    if count % 2 == 1:
        median_val = round(clean_vals[mid], 2)
    else:
        median_val = round((clean_vals[mid - 1] + clean_vals[mid]) / 2.0, 2)

    # 95th Percentile (nearest rank)
    p95_idx = int(math.ceil(0.95 * count)) - 1
    p95_idx = max(0, min(p95_idx, count - 1))
    p95_val = round(clean_vals[p95_idx], 2)

    return MetricStats(
        count=count,
        mean=mean_val,
        median=median_val,
        p95=p95_val,
        min_val=round(clean_vals[0], 2),
        max_val=round(clean_vals[-1], 2),
    )


def determine_evidence_mode(runs: List[RunSummary]) -> EvidenceMode:
    """Classifies the aggregate evidence mode of the run set."""
    if not runs:
        return EvidenceMode.UNAVAILABLE

    modes = {r.execution_mode for r in runs}
    if modes == {EvidenceMode.LIVE.value}:
        return EvidenceMode.LIVE
    if modes == {EvidenceMode.FIXTURE.value}:
        return EvidenceMode.FIXTURE
    if modes == {EvidenceMode.UNAVAILABLE.value}:
        return EvidenceMode.UNAVAILABLE
    if modes == {EvidenceMode.INFRASTRUCTURE_ONLY.value}:
        return EvidenceMode.INFRASTRUCTURE_ONLY
    if len(modes) > 1:
        return EvidenceMode.MIXED
    return EvidenceMode.UNAVAILABLE


def aggregate_dashboard_report(
    candidate_id: str,
    split_name: str,
    runs: List[RunSummary],
    split_manifest: Optional[SplitManifest] = None,
    split_version: str = "v1",
    target_evidence_mode: Optional[EvidenceMode] = None,
    git_commit: str = "",
    source_db_sha256: str = "",
) -> DashboardReport:
    """Aggregates a list of RunSummary records into a complete DashboardReport.

    Follows zero-fabrication rules:
    - Never presents unobserved values as 0.
    - Preserves explicit UNAVAILABLE indicators.
    - Enforces isolation between LIVE and FIXTURE evidence.
    """
    evidence_mode = target_evidence_mode or determine_evidence_mode(runs)

    # 1. Total tasks in split (if manifest provided)
    total_tasks_in_split = 0
    repo_task_counts: Dict[str, int] = {}
    if split_manifest:
        norm_s = split_name.lower().strip()
        if norm_s in split_manifest.splits:
            sp_info = split_manifest.splits[norm_s]
            total_tasks_in_split = sp_info.task_count
            repo_task_counts = dict(sp_info.repo_counts)
        elif norm_s in ["all", ""]:
            total_tasks_in_split = split_manifest.source.record_count
            for s_info in split_manifest.splits.values():
                for rp, c in s_info.repo_counts.items():
                    repo_task_counts[rp] = repo_task_counts.get(rp, 0) + c

    total_runs = len(runs)

    # 2. Eligible runs filter (based on evidence mode)
    eligible_runs: list[RunSummary] = []
    unavailable_runs: list[RunSummary] = []
    skipped_runs: list[RunSummary] = []

    for r in runs:
        if r.execution_mode == EvidenceMode.UNAVAILABLE.value or r.success is None:
            unavailable_runs.append(r)
        elif target_evidence_mode and r.execution_mode != target_evidence_mode.value:
            skipped_runs.append(r)
        else:
            eligible_runs.append(r)

    eligible_count = len(eligible_runs)
    success_runs = [r for r in eligible_runs if r.success is True]
    failed_runs = [r for r in eligible_runs if r.success is False]
    success_count = len(success_runs)
    failure_count = len(failed_runs)
    completed_count = success_count + failure_count

    # Overall rates
    overall_pass_rate: Optional[float] = None
    overall_failure_rate: Optional[float] = None
    if completed_count > 0:
        overall_pass_rate = round(success_count / completed_count, 4)
        overall_failure_rate = round(failure_count / completed_count, 4)

    # 3. Report Status
    if total_runs == 0:
        report_status = ReportStatus.NO_RESULTS
    elif eligible_count == 0:
        if any(r.execution_mode == EvidenceMode.INFRASTRUCTURE_ONLY.value for r in runs):
            report_status = ReportStatus.INFRASTRUCTURE_UNAVAILABLE
        else:
            report_status = ReportStatus.NO_LIVE_RESULTS
    elif evidence_mode == EvidenceMode.FIXTURE:
        report_status = ReportStatus.FIXTURE_VERIFIED
    else:
        report_status = ReportStatus.PASS if overall_pass_rate == 1.0 else ReportStatus.FAIL

    # 4. Repository breakdown
    repos_seen = set(repo_task_counts.keys())
    for r in runs:
        if r.repository:
            repos_seen.add(r.repository)

    repo_results: list[RepositoryMetrics] = []
    for repo in sorted(repos_seen):
        r_runs = [r for r in eligible_runs if r.repository == repo]
        r_unav = [r for r in runs if r.repository == repo and r not in eligible_runs]
        r_succ = sum(1 for r in r_runs if r.success is True)
        r_fail = sum(1 for r in r_runs if r.success is False)
        r_comp = r_succ + r_fail
        r_rate = round(r_succ / r_comp, 4) if r_comp > 0 else None
        repo_results.append(
            RepositoryMetrics(
                repository=repo,
                total_tasks=repo_task_counts.get(repo, r_comp + len(r_unav)),
                completed_runs=r_comp,
                passed_runs=r_succ,
                failed_runs=r_fail,
                unavailable_runs=len(r_unav),
                pass_rate=r_rate,
            )
        )

    # 5. Task-Type breakdown (Phase 5 & 23: only if authoritative metadata exists)
    has_authoritative_task_type = any(
        r.task_type is not None and str(r.task_type).strip() != "" for r in runs
    )
    task_type_results: list[TaskTypeMetrics] = []
    if has_authoritative_task_type:
        tt_seen = {r.task_type for r in runs if r.task_type}
        for tt in sorted(tt_seen):
            t_runs = [r for r in eligible_runs if r.task_type == tt]
            t_succ = sum(1 for r in t_runs if r.success is True)
            t_fail = sum(1 for r in t_runs if r.success is False)
            t_comp = t_succ + t_fail
            t_rate = round(t_succ / t_comp, 4) if t_comp > 0 else None
            task_type_results.append(
                TaskTypeMetrics(
                    task_type=str(tt),
                    total_tasks=len(t_runs),
                    completed_runs=t_comp,
                    passed_runs=t_succ,
                    failed_runs=t_fail,
                    pass_rate=t_rate,
                    status="AVAILABLE",
                    reason="metadata present in evaluation records",
                )
            )
        task_type_status = "AVAILABLE"
        task_type_reason = "authoritative task-type metadata present"
    else:
        task_type_status = "UNAVAILABLE"
        task_type_reason = "source dataset does not provide task-type metadata"

    # 6. Failure Category Breakdown (Phase 6)
    # Canonical E9 classes
    canonical_counts: Dict[str, int] = {fc.value: 0 for fc in FailureClass}
    evaluator_counts: Dict[str, int] = {}
    term_reasons: Dict[str, int] = {}

    for r in runs:
        if r.termination_reason:
            term_reasons[r.termination_reason] = term_reasons.get(r.termination_reason, 0) + 1

        fc = (r.failure_class or "").strip().upper()
        fs = (r.failure_stage or "").strip().upper()

        if fc in canonical_counts:
            canonical_counts[fc] += 1
        elif fc:
            # Stage 28 evaluator failure class or custom infrastructure stage
            evaluator_counts[fc] = evaluator_counts.get(fc, 0) + 1

        if fs and fs not in ["UNKNOWN", ""]:
            evaluator_counts[f"STAGE_{fs}"] = evaluator_counts.get(f"STAGE_{fs}", 0) + 1

    total_canon = sum(canonical_counts.values())
    canonical_summaries: list[FailureCategorySummary] = []
    for cat in sorted(canonical_counts.keys()):
        cnt = canonical_counts[cat]
        pct = round((cnt / total_canon) * 100.0, 2) if total_canon > 0 else 0.0
        if cnt > 0 or total_canon == 0:
            canonical_summaries.append(
                FailureCategorySummary(
                    category=cat,
                    count=cnt,
                    percentage=pct,
                    is_evaluator_stage=False,
                )
            )

    evaluator_summaries: list[FailureCategorySummary] = []
    total_eval = sum(evaluator_counts.values())
    for cat in sorted(evaluator_counts.keys()):
        cnt = evaluator_counts[cat]
        pct = round((cnt / total_eval) * 100.0, 2) if total_eval > 0 else 0.0
        evaluator_summaries.append(
            FailureCategorySummary(
                category=cat,
                count=cnt,
                percentage=pct,
                is_evaluator_stage=True,
            )
        )

    # 7. Numerical Continuous Metrics (Phase 6 & 7)
    elapsed_vals = [r.elapsed_seconds for r in eligible_runs if r.elapsed_seconds is not None]
    tool_vals = [float(r.tool_calls) for r in eligible_runs if r.tool_calls is not None]
    turn_vals = [float(r.turns) for r in eligible_runs if r.turns is not None]
    patch_lines_vals = [float(r.patch_lines) for r in eligible_runs if r.patch_lines is not None]
    files_changed_vals = [float(r.files_changed) for r in eligible_runs if r.files_changed is not None]

    runtime_stats = calculate_metric_stats(elapsed_vals)
    tool_call_stats = calculate_metric_stats(tool_vals)
    turn_stats = calculate_metric_stats(turn_vals)
    patch_line_stats = calculate_metric_stats(patch_lines_vals)
    files_changed_stats = calculate_metric_stats(files_changed_vals)

    # 8. Recovery metrics (Phase 7)
    rec_attempts = sum(1 for r in runs if r.recovery_triggered is True)
    rec_successes = sum(1 for r in runs if r.recovery_success is True)
    rec_rate = round(rec_successes / rec_attempts, 4) if rec_attempts > 0 else None

    # 9. Clean Copy Evaluator specific counts (Phase 7)
    apply_conflicts = sum(
        1 for r in runs
        if str(r.patch_apply_status).upper() in ["CONFLICT", "FAILED", "PATCH_APPLY_CONFLICT"]
    )
    verif_failures = sum(
        1 for r in runs
        if str(r.verification_status).upper() in ["FAILED", "VERIFICATION_FAILED", "VERIFICATION_TEST_FAILURE"]
    )
    cc_verified = sum(1 for r in runs if r.clean_copy_verified is True)

    # 10. Extract failed run objects for failures.jsonl (Phase 11)
    failed_run_objs: list[dict[str, Any]] = []
    for r in runs:
        # Include all failed eligible runs, plus infrastructure failures
        if r.success is False or r.failure_class:
            failed_run_objs.append({
                "run_id": r.run_id,
                "task_id": r.task_id,
                "candidate_id": r.candidate_id,
                "split": r.split_name or split_name,
                "repository": r.repository,
                "execution_mode": r.execution_mode,
                "failure_class": r.failure_class or "UNKNOWN",
                "failure_stage": r.failure_stage or "UNKNOWN",
                "termination_reason": r.termination_reason or "",
                "elapsed_seconds": r.elapsed_seconds,
                "tool_calls": r.tool_calls,
                "turns": r.turns,
                "recovery_triggered": r.recovery_triggered,
                "recovery_success": r.recovery_success,
                "patch_apply_status": r.patch_apply_status or "",
                "verification_status": r.verification_status or "",
            })

    # Sort deterministically: split -> candidate -> task_id -> run_id
    failed_run_objs.sort(
        key=lambda f: (
            str(f.get("split", "")),
            str(f.get("candidate_id", "")),
            str(f.get("task_id", "")),
            str(f.get("run_id", "")),
        )
    )

    manifest_sha = split_manifest.manifest_sha256 if split_manifest else ""

    return DashboardReport(
        candidate_id=candidate_id,
        split_name=split_name,
        split_version=split_version,
        evidence_mode=evidence_mode,
        report_status=report_status,
        git_commit=git_commit,
        total_tasks_in_split=total_tasks_in_split,
        total_runs_recorded=total_runs,
        eligible_run_count=eligible_count,
        completed_run_count=completed_count,
        success_count=success_count,
        failure_count=failure_count,
        unavailable_count=len(unavailable_runs),
        skipped_count=len(skipped_runs),
        overall_pass_rate=overall_pass_rate,
        overall_failure_rate=overall_failure_rate,
        repository_results=repo_results,
        task_type_results=task_type_results,
        task_type_status=task_type_status,
        task_type_reason=task_type_reason,
        canonical_failures=canonical_summaries,
        evaluator_failures=evaluator_summaries,
        termination_reasons=term_reasons,
        runtime_stats=runtime_stats,
        tool_call_stats=tool_call_stats,
        turn_stats=turn_stats,
        patch_line_stats=patch_line_stats,
        files_changed_stats=files_changed_stats,
        recovery_attempts=rec_attempts,
        recovery_successes=rec_successes,
        recovery_success_rate=rec_rate,
        patch_apply_conflicts=apply_conflicts,
        verification_failures=verif_failures,
        clean_copy_verified_count=cc_verified,
        failed_runs=failed_run_objs,
        split_manifest_sha256=manifest_sha,
        source_db_sha256=source_db_sha256,
    )
