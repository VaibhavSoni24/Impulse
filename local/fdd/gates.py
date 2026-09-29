"""Promotion Gates and Delta Evaluation for FDD (Stage 31 Sections 11, 12, 13, 14).

Calculates targeted failure reduction vs. collateral regressions and deterministically
evaluates candidate promotion/rejection according to rigorous evidence-based criteria.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from local.fdd.models import FDDRunDelta, FailureRecord, PromotionDecision


def compute_run_delta(
    baseline_records: List[FailureRecord],
    candidate_records: List[FailureRecord],
    target_failure_mode: str,
    held_out_baseline: Optional[List[FailureRecord]] = None,
    held_out_candidate: Optional[List[FailureRecord]] = None,
) -> FDDRunDelta:
    """Computes targeted failure reduction and collateral category shifts.

    Distinguishes strictly between unobserved/unavailable values (None) and real 0s.
    """
    target_norm = target_failure_mode.strip().upper()

    def _matches_target(rec: FailureRecord) -> bool:
        rec_cat = (rec.failure_category or "").strip().upper()
        rec_sig = (rec.termination_reason or "").strip().upper()
        return target_norm in rec_cat or target_norm in rec_sig or rec_cat in target_norm

    # Baseline target failure count
    base_eligible = [r for r in baseline_records if r.run_status not in ["UNKNOWN", "NOT_FOUND"]]
    cand_eligible = [r for r in candidate_records if r.run_status not in ["UNKNOWN", "NOT_FOUND"]]

    if not base_eligible or not cand_eligible:
        # Cannot calculate delta if either set has no executed/evaluated runs
        return FDDRunDelta(target_failure_mode=target_failure_mode)

    base_target_failures = [r for r in base_eligible if r.success is False and _matches_target(r)]
    cand_target_failures = [r for r in cand_eligible if r.success is False and _matches_target(r)]

    base_count = len(base_target_failures)
    cand_count = len(cand_target_failures)
    targeted_reduction = base_count - cand_count

    # Pass rates
    base_passes = len([r for r in base_eligible if r.success is True])
    cand_passes = len([r for r in cand_eligible if r.success is True])
    base_pr = (base_passes / len(base_eligible)) if base_eligible else None
    cand_pr = (cand_passes / len(cand_eligible)) if cand_eligible else None
    pr_delta = (cand_pr - base_pr) if (cand_pr is not None and base_pr is not None) else None

    # Runtime means
    base_runtimes = [r.runtime_seconds for r in base_eligible if r.runtime_seconds is not None]
    cand_runtimes = [r.runtime_seconds for r in cand_eligible if r.runtime_seconds is not None]
    base_rt_mean = (sum(base_runtimes) / len(base_runtimes)) if base_runtimes else None
    cand_rt_mean = (sum(cand_runtimes) / len(cand_runtimes)) if cand_runtimes else None

    # Tool calls means
    base_tcs = [r.tool_calls for r in base_eligible if r.tool_calls is not None]
    cand_tcs = [r.tool_calls for r in cand_eligible if r.tool_calls is not None]
    base_tc_mean = (sum(base_tcs) / len(base_tcs)) if base_tcs else None
    cand_tc_mean = (sum(cand_tcs) / len(cand_tcs)) if cand_tcs else None

    # Collateral category tracking (unrelated failure classes)
    base_cat_counts: Dict[str, int] = {}
    for r in base_eligible:
        if r.success is False and not _matches_target(r):
            cat = r.failure_category or "UNKNOWN"
            base_cat_counts[cat] = base_cat_counts.get(cat, 0) + 1

    cand_cat_counts: Dict[str, int] = {}
    for r in cand_eligible:
        if r.success is False and not _matches_target(r):
            cat = r.failure_category or "UNKNOWN"
            cand_cat_counts[cat] = cand_cat_counts.get(cat, 0) + 1

    all_other_cats = set(base_cat_counts.keys()).union(set(cand_cat_counts.keys()))
    collateral_regressions: Dict[str, int] = {}
    collateral_improvements: Dict[str, int] = {}

    for cat in sorted(all_other_cats):
        b_c = base_cat_counts.get(cat, 0)
        c_c = cand_cat_counts.get(cat, 0)
        diff = c_c - b_c
        if diff > 0:
            collateral_regressions[cat] = diff
        elif diff < 0:
            collateral_improvements[cat] = -diff

    # Held-out comparison
    ho_base_pr: Optional[float] = None
    ho_cand_pr: Optional[float] = None
    ho_regression: Optional[bool] = None

    if held_out_baseline is not None and held_out_candidate is not None:
        ho_b_exec = [r for r in held_out_baseline if r.run_status not in ["UNKNOWN", "NOT_FOUND"]]
        ho_c_exec = [r for r in held_out_candidate if r.run_status not in ["UNKNOWN", "NOT_FOUND"]]
        if ho_b_exec and ho_c_exec:
            ho_b_passes = len([r for r in ho_b_exec if r.success is True])
            ho_c_passes = len([r for r in ho_c_exec if r.success is True])
            ho_base_pr = ho_b_passes / len(ho_b_exec)
            ho_cand_pr = ho_c_passes / len(ho_c_exec)
            ho_regression = ho_cand_pr < ho_base_pr

    return FDDRunDelta(
        target_failure_mode=target_failure_mode,
        baseline_failure_count=base_count,
        candidate_failure_count=cand_count,
        targeted_reduction=targeted_reduction,
        baseline_pass_rate=base_pr,
        candidate_pass_rate=cand_pr,
        pass_rate_delta=pr_delta,
        baseline_runtime_mean=base_rt_mean,
        candidate_runtime_mean=cand_rt_mean,
        baseline_tool_calls_mean=base_tc_mean,
        candidate_tool_calls_mean=cand_tc_mean,
        collateral_regressions=collateral_regressions,
        collateral_improvements=collateral_improvements,
        held_out_pass_rate_baseline=ho_base_pr,
        held_out_pass_rate_candidate=ho_cand_pr,
        held_out_regression=ho_regression,
    )


def evaluate_promotion_gate(
    delta: FDDRunDelta,
    smoke_passed: bool = True,
    max_collateral_regression: int = 0,
    has_actionable_runs: bool = True,
) -> Tuple[PromotionDecision, str]:
    """Deterministically applies the promotion gate to an evaluated intervention.

    Returns:
        (decision, rationale)
    """
    if not smoke_passed:
        return (
            PromotionDecision.REJECTED,
            "Intervention rejected at smoke gate: smoke evaluation failed.",
        )

    if not has_actionable_runs or delta.baseline_failure_count is None or delta.candidate_failure_count is None:
        return (
            PromotionDecision.NO_ACTIONABLE_DATA,
            "Evaluation completed without actionable or measurable live failure delta.",
        )

    # Check targeted reduction
    red = delta.targeted_reduction
    if red is None:
        return (
            PromotionDecision.INCONCLUSIVE,
            "Targeted failure reduction could not be determined from available evaluation records.",
        )

    if red < 0:
        return (
            PromotionDecision.REJECTED,
            f"Targeted failure mode worsened: increased by {-red} failures (baseline={delta.baseline_failure_count}, candidate={delta.candidate_failure_count}).",
        )

    if red == 0:
        return (
            PromotionDecision.REJECTED,
            f"Targeted failure mode remained unchanged at {delta.baseline_failure_count} failures.",
        )

    # Targeted failure decreased (red > 0)! Now check collateral effects
    total_collateral_reg = sum(delta.collateral_regressions.values())
    if total_collateral_reg > max_collateral_regression:
        details = ", ".join(f"{k}: +{v}" for k, v in delta.collateral_regressions.items())
        return (
            PromotionDecision.REJECTED,
            f"Target failure improved by {red}, but collateral regressions occurred in other failure classes: {details}.",
        )

    # Check held-out confirmation if held-out was evaluated
    if delta.held_out_regression is True:
        return (
            PromotionDecision.REJECTED,
            f"Target failure improved on validation, but held-out confirmation regressed "
            f"(baseline pass rate={delta.held_out_pass_rate_baseline}, candidate pass rate={delta.held_out_pass_rate_candidate}).",
        )

    # All gates passed!
    return (
        PromotionDecision.PROMOTED,
        f"Promoted: targeted failure mode reduced by {red} failures (from {delta.baseline_failure_count} to {delta.candidate_failure_count}) "
        f"with zero collateral regressions and no held-out degradation.",
    )
