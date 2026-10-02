"""Validation and Held-Out comparison logic for Stage 44 promotion gate.

Implements:
- Metric directionality and primary metric resolution
- Contingency table calculation (task-paired pass/fail tracking)
- Regression detection on held-out tasks without tuning leakage
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.promotion.models import (
    EvidenceMode,
    GateDimensionStatus,
    HeldOutComparisonResult,
    MetricDirection,
    TaskPairOutcome,
    ValidationComparisonResult,
)
from local.versioning.models import CandidateManifest


def resolve_primary_metric(manifest: CandidateManifest) -> tuple[str, str]:
    """Determines primary metric and direction for the candidate."""
    primary_dim = manifest.primary_dimension
    # Check if this is an adapter optimization experiment focused on tool discipline
    if primary_dim == "adapter":
        return "command_redundancy_count", MetricDirection.LOWER_IS_BETTER.value
    # Default metric for software engineering agents
    return "task_success_rate", MetricDirection.HIGHER_IS_BETTER.value


def compare_validation(
    candidate_manifest: CandidateManifest,
    candidate_runs: List[Dict[str, Any]],
    baseline_manifest: Optional[CandidateManifest] = None,
    baseline_runs: Optional[List[Dict[str, Any]]] = None,
    evidence_mode: str = EvidenceMode.UNAVAILABLE.value,
    metric_override: Optional[str] = None,
    direction_override: Optional[str] = None,
) -> ValidationComparisonResult:
    """Evaluates validation improvement dimension between candidate and baseline."""
    baseline_runs = baseline_runs or []
    metric_name, direction = resolve_primary_metric(candidate_manifest)
    if metric_override:
        metric_name = metric_override
    if direction_override:
        direction = direction_override

    # If candidate is a root baseline with no parent/baseline
    if baseline_manifest is None:
        return ValidationComparisonResult(
            dimension_status=GateDimensionStatus.NOT_APPLICABLE.value,
            primary_metric_name=metric_name,
            direction=direction,
            baseline_value=None,
            candidate_value=None,
            delta=None,
            task_pairs=None,
            evidence_mode=evidence_mode,
            notes="Root baseline candidate has no parent baseline for validation comparison.",
        )

    # Fixture, infrastructure-only, or unavailable evidence cannot satisfy live promotion gate
    if evidence_mode != EvidenceMode.LIVE.value:
        return ValidationComparisonResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            primary_metric_name=metric_name,
            direction=direction,
            baseline_value=None,
            candidate_value=None,
            delta=None,
            task_pairs=None,
            evidence_mode=evidence_mode,
            notes=f"Validation improvement cannot be verified without LIVE benchmark evidence (current: {evidence_mode}).",
        )

    # Filter runs for validation / dev splits
    val_cand_runs = [
        r for r in candidate_runs if r.get("split_name") in ("dev", "validation") or r.get("split_name") is None
    ]
    val_base_runs = [
        r for r in baseline_runs if r.get("split_name") in ("dev", "validation") or r.get("split_name") is None
    ]

    if not val_cand_runs:
        return ValidationComparisonResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            primary_metric_name=metric_name,
            direction=direction,
            baseline_value=None,
            candidate_value=None,
            delta=None,
            task_pairs=None,
            evidence_mode=evidence_mode,
            notes="No completed validation runs recorded for candidate.",
        )

    # Task-paired contingency matching
    base_by_task = {str(r.get("task_id")): r for r in val_base_runs if r.get("task_id")}
    cand_by_task = {str(r.get("task_id")): r for r in val_cand_runs if r.get("task_id")}

    common_tasks = set(base_by_task.keys()) & set(cand_by_task.keys())
    pass_pass = 0
    pass_fail = 0
    fail_pass = 0
    fail_fail = 0

    for t_id in common_tasks:
        b_pass = bool(base_by_task[t_id].get("success"))
        c_pass = bool(cand_by_task[t_id].get("success"))
        if b_pass and c_pass:
            pass_pass += 1
        elif b_pass and not c_pass:
            pass_fail += 1
        elif not b_pass and c_pass:
            fail_pass += 1
        else:
            fail_fail += 1

    task_pairs = TaskPairOutcome(
        baseline_pass_candidate_pass=pass_pass,
        baseline_pass_candidate_fail=pass_fail,
        baseline_fail_candidate_pass=fail_pass,
        baseline_fail_candidate_fail=fail_fail,
        validation_tasks_total=len(common_tasks) if common_tasks else len(val_cand_runs),
        validation_tasks_changed=pass_fail + fail_pass,
    )

    # Compute metric values
    if metric_name == "command_redundancy_count":
        # Lower is better
        b_vals = [float(r.get("command_redundancy_count", 0)) for r in val_base_runs if "command_redundancy_count" in r]
        c_vals = [float(r.get("command_redundancy_count", 0)) for r in val_cand_runs if "command_redundancy_count" in r]
        b_score = (sum(b_vals) / len(b_vals)) if b_vals else 0.0
        c_score = (sum(c_vals) / len(c_vals)) if c_vals else 0.0
        delta = c_score - b_score
        is_improved = delta < 0
    else:
        # Default: task success rate (Higher is better)
        b_success = sum(1 for r in val_base_runs if bool(r.get("success")))
        c_success = sum(1 for r in val_cand_runs if bool(r.get("success")))
        b_score = (b_success / len(val_base_runs)) if val_base_runs else 0.0
        c_score = (c_success / len(val_cand_runs)) if val_cand_runs else 0.0
        delta = c_score - b_score
        is_improved = delta > 0

    status = GateDimensionStatus.PASS.value if is_improved else GateDimensionStatus.FAIL.value
    notes = (
        f"Validation delta: {delta:+.4f} ({metric_name}). "
        f"Candidate: {c_score:.4f}, Baseline: {b_score:.4f}."
    )

    return ValidationComparisonResult(
        dimension_status=status,
        primary_metric_name=metric_name,
        direction=direction,
        baseline_value=round(b_score, 4),
        candidate_value=round(c_score, 4),
        delta=round(delta, 4),
        task_pairs=task_pairs,
        evidence_mode=evidence_mode,
        notes=notes,
    )


def compare_held_out(
    candidate_manifest: CandidateManifest,
    candidate_runs: List[Dict[str, Any]],
    baseline_manifest: Optional[CandidateManifest] = None,
    baseline_runs: Optional[List[Dict[str, Any]]] = None,
    evidence_mode: str = EvidenceMode.UNAVAILABLE.value,
) -> HeldOutComparisonResult:
    """Evaluates held-out regression dimension against frozen held-out test split."""
    baseline_runs = baseline_runs or []

    if baseline_manifest is None:
        return HeldOutComparisonResult(
            dimension_status=GateDimensionStatus.NOT_APPLICABLE.value,
            baseline_result=None,
            candidate_result=None,
            regression_count=0,
            changed_tasks=0,
            evidence_mode=evidence_mode,
            notes="Root baseline candidate has no parent for held-out regression comparison.",
        )

    if evidence_mode != EvidenceMode.LIVE.value:
        return HeldOutComparisonResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            baseline_result=None,
            candidate_result=None,
            regression_count=0,
            changed_tasks=0,
            evidence_mode=evidence_mode,
            notes=f"Held-out confirmation requires LIVE evidence (current: {evidence_mode}).",
        )

    held_cand_runs = [r for r in candidate_runs if r.get("split_name") == "held_out"]
    held_base_runs = [r for r in baseline_runs if r.get("split_name") == "held_out"]

    if not held_cand_runs:
        return HeldOutComparisonResult(
            dimension_status=GateDimensionStatus.UNKNOWN.value,
            baseline_result=None,
            candidate_result=None,
            regression_count=0,
            changed_tasks=0,
            evidence_mode=evidence_mode,
            notes="No completed held-out runs recorded for candidate.",
        )

    base_by_task = {str(r.get("task_id")): r for r in held_base_runs if r.get("task_id")}
    cand_by_task = {str(r.get("task_id")): r for r in held_cand_runs if r.get("task_id")}

    common_tasks = set(base_by_task.keys()) & set(cand_by_task.keys())
    regressions = 0
    changed = 0

    for t_id in common_tasks:
        b_pass = bool(base_by_task[t_id].get("success"))
        c_pass = bool(cand_by_task[t_id].get("success"))
        if b_pass and not c_pass:
            regressions += 1
            changed += 1
        elif not b_pass and c_pass:
            changed += 1

    c_pass_count = sum(1 for r in held_cand_runs if bool(r.get("success")))
    b_pass_count = sum(1 for r in held_base_runs if bool(r.get("success")))
    c_rate = (c_pass_count / len(held_cand_runs)) if held_cand_runs else 0.0
    b_rate = (b_pass_count / len(held_base_runs)) if held_base_runs else 0.0

    if regressions > 0:
        status = GateDimensionStatus.FAIL.value
        notes = f"Unacceptable held-out regression detected: {regressions} task(s) regressed from PASS to FAIL."
    elif c_rate < b_rate:
        status = GateDimensionStatus.FAIL.value
        notes = f"Overall held-out pass rate dropped: candidate={c_rate:.4f} < baseline={b_rate:.4f}."
    else:
        status = GateDimensionStatus.PASS.value
        notes = f"Zero held-out regressions observed across {len(common_tasks)} tasks."

    return HeldOutComparisonResult(
        dimension_status=status,
        baseline_result=round(b_rate, 4),
        candidate_result=round(c_rate, 4),
        regression_count=regressions,
        changed_tasks=changed,
        evidence_mode=evidence_mode,
        notes=notes,
    )
