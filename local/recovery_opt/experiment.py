"""Recovery Optimization Experiment Manager (Stage 35 Sections 4, 11, 29, 38).

Orchestrates candidate generation, isolation, execution analysis, and promotion gating
for recovery optimization experiments under `experiments/recovery/`:
- Candidate REC0 (Baseline: Stage 20 canonical recovery paths)
- Candidate REC1 (Proactive early detection & rapid fallback)
- Candidate REC2 (Alternate path routing on repeated failure)
- Candidate REC3 (Adaptive loop guard & bounded retries)

Enforces:
- `InterventionScope.RECOVERY`
- Full reproducibility manifests with invariant baseline hashes (P0, R0, T0, Model, Topology, Frozen Skills)
- Paired evaluation across the exact same failure set
- Strict loop regression checks
- Zero fabrication of unobserved live metrics
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.fdd.gates import evaluate_promotion_gate
from local.fdd.models import FDDRunDelta, Intervention, InterventionScope, PromotionDecision
from local.recovery_opt.diff import diff_recovery_policies, format_recovery_policy_diff_md
from local.recovery_opt.earliest_detection import analyze_early_detection
from local.recovery_opt.loop_detector import RecoveryLoopDetector, is_loop_regression
from local.recovery_opt.metrics import compute_recovery_cost_metrics, compute_recovery_quality_metrics
from local.recovery_opt.models import (
    RecoveryCandidateManifest,
    RecoveryCluster,
    RecoveryCostMetrics,
    RecoveryDiagnostics,
    RecoveryExecutionEvent,
    RecoveryFailureRecord,
    RecoveryHypothesis,
    RecoveryInterventionType,
    RecoveryOutcome,
    RecoveryPolicy,
    RecoveryQualityMetrics,
    RecoveryTaskPairOutcome,
    RecoveryVariant,
)
from local.recovery_opt.paired import compute_paired_recovery_comparisons, save_paired_results
from local.recovery_opt.policy import (
    build_rec0_baseline_policy,
    build_rec1_early_detection_policy,
    build_rec2_alternate_path_policy,
    build_rec3_adaptive_loop_guard_policy,
    get_canonical_recovery_policy,
)
from local.recovery_opt.reporting import generate_candidate_report_md, generate_pareto_frontier_md
from local.recovery_opt.trace import RecoveryTraceCollector
from local.recovery_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
    validate_recovery_candidate_integrity,
    validate_recovery_hypothesis,
)


class RecoveryExperimentManager:
    """Manages recovery experiment candidates under experiments/recovery/."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.exp_root = self.repo_root / "experiments" / "recovery"

    def get_candidate_dir(self, candidate_id: str) -> Path:
        """Returns the isolated directory path for a candidate."""
        return self.exp_root / candidate_id

    def setup_canonical_candidates(self) -> dict[str, Path]:
        """Initializes canonical candidate directories and baseline artifacts for REC0..REC3."""
        paths: dict[str, Path] = {}
        variants = [
            ("REC0", build_rec0_baseline_policy(), "REC0"),
            ("REC1", build_rec1_early_detection_policy(), "REC0"),
            ("REC2", build_rec2_alternate_path_policy(), "REC0"),
            ("REC3", build_rec3_adaptive_loop_guard_policy(), "REC0"),
        ]

        hypotheses = {
            "REC0": RecoveryHypothesis(
                target_failure="Baseline Canonical Recovery Paths",
                observation="Stage 20 baseline recovery paths reacting after failure recurrence.",
                hypothesis="Baseline configuration for bounded recovery across 5 families.",
                recovery_change="None (Baseline)",
                expected_behavior="Establish baseline recovery latency, cost, and loop metrics.",
                expected_metric_signal="Baseline metrics established.",
                rejection_condition="Baseline is immutable.",
                intervention_type=RecoveryInterventionType.MODIFY_RECOVERY_TRIGGER.value,
            ),
            "REC1": RecoveryHypothesis(
                target_failure="LATE_RECOVERY / REPEATED_COMMAND",
                observation="Commands and errors repeat multiple turns before recovery initiates.",
                hypothesis="Triggering recovery on the first failure recurrence will decrease latency without increasing loops.",
                recovery_change="Enable early detection on 1st error recurrence; reduce no_progress threshold to 1 turn.",
                expected_behavior="Recovery initiates 2-3 turns earlier on repeated failures.",
                expected_metric_signal="detection_latency_events reduces by >= 2; zero loop regression.",
                rejection_condition="New recovery loops or collateral regressions.",
                intervention_type=RecoveryInterventionType.MODIFY_RECOVERY_TRIGGER.value,
            ),
            "REC2": RecoveryHypothesis(
                target_failure="FAILED_RECOVERY / RETRY_WASTE",
                observation="Repeated same-action retries fail to alter repository state.",
                hypothesis="Routing immediately to an alternate recovery tool/path avoids wasted retries.",
                recovery_change="Route to alternate tool/search on primary action failure instead of repeating.",
                expected_behavior="Eliminates wasted retries on failed actions; increases alternate path success.",
                expected_metric_signal="retry_count decreases; alternate_path_success_rate increases.",
                rejection_condition="New recovery loops or collateral regressions.",
                intervention_type=RecoveryInterventionType.ADD_ALTERNATE_PATH.value,
            ),
            "REC3": RecoveryHypothesis(
                target_failure="RECOVERY_LOOP / RECOVERY_THRASHING",
                observation="Alternating recovery actions can oscillate without progress.",
                hypothesis="Explicit state-fingerprint checking and oscillation suppression will terminate loops cleanly.",
                recovery_change="Enable loop guard signature checks; add oscillation stop condition.",
                expected_behavior="Stops execution cleanly on cycle detection; prevents runaway recovery tool calls.",
                expected_metric_signal="recovery_loop_count reaches 0; runtime decreases.",
                rejection_condition="Collateral regressions or premature termination of solvable tasks.",
                intervention_type=RecoveryInterventionType.ADD_RECOVERY_GUARD.value,
            ),
        }

        for cid, policy, parent in variants:
            cdir = self.get_candidate_dir(cid)
            cdir.mkdir(parents=True, exist_ok=True)
            paths[cid] = cdir

            # 1. Manifest
            manifest = RecoveryCandidateManifest(
                candidate_id=cid,
                parent_candidate=parent,
                policy_hash=policy.compute_policy_hash(),
                intervention_id=f"int_{cid.lower()}",
                root_prompt_hash=EXPECTED_P0_PROMPT_SHA256,
                retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
                testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
                topology_hash=EXPECTED_TOPOLOGY_ID,
                model_id=EXPECTED_MODEL_ID,
                test_strategy_skill_hash=EXPECTED_TEST_STRATEGY_SKILL_SHA256,
                repo_triage_skill_hash=EXPECTED_REPO_TRIAGE_SKILL_SHA256,
                evidence_mode="UNAVAILABLE",
                benchmark_split="dev",
            )
            (cdir / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

            # 2. Policy
            (cdir / "policy.json").write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")

            # 3. Failure cluster
            cluster = RecoveryCluster(
                cluster_id=f"cluster_{cid.lower()}",
                pattern_type="REPEATED_FAILURE",
                canonical_signature="Repeated command or error signature",
                affected_runs=[],
                affected_unique_tasks=[],
                evidence_modes=["UNAVAILABLE"],
                actionable_status=False,
                actionability_reason="Local Windows host lacks 4x L4 GPUs for live inference.",
            )
            (cdir / "failure_cluster.json").write_text(json.dumps(cluster.to_dict(), indent=2), encoding="utf-8")

            # 4. Intervention
            hyp = hypotheses[cid]
            interv = Intervention(
                intervention_id=f"int_{cid.lower()}",
                source_cluster_id=f"cluster_{cid.lower()}",
                target_failure_mode=hyp.target_failure,
                hypothesis=hyp.hypothesis,
                expected_behavior_change=hyp.expected_behavior,
                intervention_scope=InterventionScope.RECOVERY.value,
                changed_dimensions=["recovery_policy"],
                affected_files=[f"experiments/recovery/{cid}/policy.json"],
                baseline_candidate=parent,
                candidate_id=cid,
                success_metric=hyp.expected_metric_signal,
                rejection_condition=hyp.rejection_condition,
                status="PROPOSED" if cid != "REC0" else "BASELINE",
            )
            (cdir / "intervention.json").write_text(json.dumps(interv.to_dict(), indent=2), encoding="utf-8")

            # 5. Recovery trace (empty for unavailable)
            trace_path = cdir / "recovery_trace.jsonl"
            if not trace_path.exists():
                trace_path.write_text("", encoding="utf-8")

            # 6. Metrics
            metrics_dict = {
                "quality_metrics": RecoveryQualityMetrics().to_dict(),
                "cost_metrics": RecoveryCostMetrics().to_dict(),
            }
            (cdir / "metrics.json").write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")

            # 7. Paired results
            (cdir / "paired_results.jsonl").write_text("", encoding="utf-8")
            (cdir / "paired_results.csv").write_text("task_id,baseline_task_result,candidate_task_result,transition\n", encoding="utf-8")

            # 8. Report
            rep_md = generate_candidate_report_md(
                manifest=manifest,
                policy=policy,
                parent_policy=get_canonical_recovery_policy(parent) if parent != cid else None,
                hypothesis=hyp,
                cost_metrics=RecoveryCostMetrics(),
                quality_metrics=RecoveryQualityMetrics(),
                diagnostics=RecoveryDiagnostics(),
                paired_outcomes=[],
                promotion_decision=PromotionDecision.NO_ACTIONABLE_DATA.value if cid != "REC0" else "BASELINE",
                promotion_rationale="Candidate initialized in UNAVAILABLE evidence mode (local hardware limitation).",
            )
            (cdir / "report.md").write_text(rep_md, encoding="utf-8")

        return paths

    def verify_candidate(self, candidate_id: str) -> Tuple[bool, List[str]]:
        """Verifies candidate reproducibility, single-dimension isolation, and frozen baselines."""
        cdir = self.get_candidate_dir(candidate_id)
        if not cdir.exists():
            return False, [f"Candidate directory '{cdir}' does not exist."]

        # Check required files
        req_files = [
            "manifest.json",
            "policy.json",
            "failure_cluster.json",
            "intervention.json",
            "recovery_trace.jsonl",
            "metrics.json",
            "paired_results.jsonl",
            "paired_results.csv",
            "report.md",
        ]
        missing = [f for f in req_files if not (cdir / f).exists()]
        if missing:
            return False, [f"Candidate {candidate_id} missing required files: {missing}"]

        # Load manifest and policy
        try:
            m_data = json.loads((cdir / "manifest.json").read_text(encoding="utf-8"))
            manifest = RecoveryCandidateManifest.from_dict(m_data)
            p_data = json.loads((cdir / "policy.json").read_text(encoding="utf-8"))
            policy = RecoveryPolicy.from_dict(p_data)
        except Exception as e:
            return False, [f"Failed to load candidate artifacts: {e}"]

        # Validate integrity
        ok, errs = validate_recovery_candidate_integrity(
            manifest=manifest,
            policy=policy,
            repo_root=self.repo_root,
            verify_frozen=True,
        )
        return ok, errs

    def evaluate_candidate(
        self,
        candidate_id: str,
        baseline_events: List[RecoveryExecutionEvent],
        candidate_events: List[RecoveryExecutionEvent],
        target_failure_mode: str = "",
        allow_fixture: bool = False,
    ) -> Tuple[PromotionDecision, str, dict[str, Any]]:
        """Evaluates a candidate against baseline events using FDD + Loop Regression gating."""
        cdir = self.get_candidate_dir(candidate_id)
        cdir.mkdir(parents=True, exist_ok=True)

        policy = get_canonical_recovery_policy(candidate_id)
        parent_id = "REC0"
        parent_policy = get_canonical_recovery_policy(parent_id)

        # 1. Compute Cost & Quality Metrics
        cost_metrics = compute_recovery_cost_metrics(candidate_events)
        paired = compute_paired_recovery_comparisons(baseline_events, candidate_events)
        quality_metrics = compute_recovery_quality_metrics(
            candidate_events,
            target_failure_mode=target_failure_mode,
            paired_outcomes=paired,
        )

        # 2. Trace Diagnostics
        trace_collector = RecoveryTraceCollector()
        diagnostics = trace_collector.evaluate_diagnostics(candidate_events)

        # 3. Baseline loop count vs Candidate loop count
        b_loop_det = RecoveryLoopDetector()
        b_loop_res = b_loop_det.analyze_events(baseline_events)
        c_loop_res = b_loop_det.analyze_events(candidate_events)

        b_loops = sum(1 for e in baseline_events if e.loop_detected) + (1 if b_loop_res.loop_detected else 0)
        c_loops = sum(1 for e in candidate_events if e.loop_detected) + (1 if c_loop_res.loop_detected else 0)

        # Loop regression check (Stage 35 Section 35: Y_loops > X_loops -> REJECT)
        is_loop_reg, loop_rationale = is_loop_regression(b_loops, c_loops)
        if is_loop_reg:
            decision = PromotionDecision.REJECTED
            rationale = loop_rationale
        else:
            # Check delta & promotion gate
            base_fail_count = sum(1 for p in paired if p.baseline_task_result == "FAIL")
            cand_fail_count = sum(1 for p in paired if p.candidate_task_result == "FAIL")
            targeted_red = base_fail_count - cand_fail_count

            # Check collateral regression
            collateral_reg = sum(1 for p in paired if p.transition == "PASS_TO_FAIL")

            delta = FDDRunDelta(
                target_failure_mode=target_failure_mode,
                baseline_failure_count=base_fail_count,
                candidate_failure_count=cand_fail_count,
                targeted_reduction=targeted_red,
                baseline_pass_rate=(len(paired) - base_fail_count) / len(paired) if paired else None,
                candidate_pass_rate=(len(paired) - cand_fail_count) / len(paired) if paired else None,
                collateral_regressions={"UNEXPECTED_REGRESSION": collateral_reg} if collateral_reg > 0 else {},
            )

            has_actionable = allow_fixture or any(e.evidence_mode == "LIVE" for e in candidate_events)
            decision, rationale = evaluate_promotion_gate(
                delta=delta,
                smoke_passed=True,
                max_collateral_regression=0,
                has_actionable_runs=has_actionable,
            )

        # Persist artifacts
        ev_mode = candidate_events[0].evidence_mode if candidate_events else "UNAVAILABLE"
        manifest = RecoveryCandidateManifest(
            candidate_id=candidate_id,
            parent_candidate=parent_id,
            policy_hash=policy.compute_policy_hash(),
            intervention_id=f"int_{candidate_id.lower()}",
            root_prompt_hash=EXPECTED_P0_PROMPT_SHA256,
            retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
            testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
            topology_hash=EXPECTED_TOPOLOGY_ID,
            model_id=EXPECTED_MODEL_ID,
            test_strategy_skill_hash=EXPECTED_TEST_STRATEGY_SKILL_SHA256,
            repo_triage_skill_hash=EXPECTED_REPO_TRIAGE_SKILL_SHA256,
            evidence_mode=ev_mode,
        )
        (cdir / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        (cdir / "policy.json").write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")

        # Save paired results
        save_paired_results(paired, cdir / "paired_results.jsonl", cdir / "paired_results.csv")

        # Save recovery trace
        with (cdir / "recovery_trace.jsonl").open("w", encoding="utf-8") as f:
            for ev in candidate_events:
                f.write(json.dumps(ev.to_dict()) + "\n")

        # Save metrics
        metrics_dict = {
            "quality_metrics": quality_metrics.to_dict(),
            "cost_metrics": cost_metrics.to_dict(),
            "diagnostics": diagnostics.to_dict(),
            "baseline_loops": b_loops,
            "candidate_loops": c_loops,
            "decision": decision.value,
            "rationale": rationale,
        }
        (cdir / "metrics.json").write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")

        # Generate report
        report_md = generate_candidate_report_md(
            manifest=manifest,
            policy=policy,
            parent_policy=parent_policy,
            hypothesis=RecoveryHypothesis(
                target_failure=target_failure_mode or "Target Failure",
                observation="Targeted failure pattern observed in baseline.",
                hypothesis="Recovery intervention resolves failure earlier and reliably.",
                recovery_change=f"Adopt {candidate_id} policy parameters.",
                expected_behavior="Reduced failures, bounded cost, no new loops.",
                expected_metric_signal="Target failure reduction > 0, zero loop regression.",
                rejection_condition="New recovery loops or collateral regressions.",
            ),
            cost_metrics=cost_metrics,
            quality_metrics=quality_metrics,
            diagnostics=diagnostics,
            paired_outcomes=paired,
            promotion_decision=decision.value,
            promotion_rationale=rationale,
        )
        (cdir / "report.md").write_text(report_md, encoding="utf-8")

        return decision, rationale, metrics_dict
