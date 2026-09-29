"""FDD Loop State Machine and Orchestrator (Stage 31 Section 10).

Manages valid transitions, experiment checkpointing, interruption recovery,
and sequential execution of the Failure-Driven Development control loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from local.clean_copy.adapter import FixtureAgentSpec
from local.clean_copy.models import ExecutionMode
from local.dashboard.models import EvidenceMode, RunSummary
from local.dashboard.queries import build_tasks_lookup, fetch_runs_from_db
from local.evaluation.db import get_connection
from local.fdd.clustering import cluster_failures
from local.fdd.evaluator import FDDEvaluator
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.interventions import (
    create_candidate_from_baseline,
    validate_intervention,
)
from local.fdd.models import (
    FDDExperimentManifest,
    FDDRunDelta,
    FDDState,
    FailureCluster,
    FailureRecord,
    Intervention,
    PromotionDecision,
)
from local.fdd.normalization import (
    normalize_failure_record,
    normalize_failures_from_jsonl,
    normalize_failures_from_summaries,
)
from local.fdd.prioritization import (
    STATUS_NO_ACTIONABLE,
    STATUS_NO_ACTIONABLE_LIVE,
    select_highest_value_cluster,
)
from local.fdd.reporting import save_fdd_experiment_artifacts


class InvalidStateTransitionError(Exception):
    """Raised when an illegal FDD state transition is attempted."""
    pass


# Strict transition graph
VALID_TRANSITIONS: Dict[FDDState, Set[FDDState]] = {
    FDDState.IDLE: {
        FDDState.BENCHMARK_COLLECTED,
        FDDState.NO_ACTIONABLE_FAILURES,
        FDDState.INFRASTRUCTURE_BLOCKED,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.BENCHMARK_COLLECTED: {
        FDDState.FAILURES_NORMALIZED,
        FDDState.NO_ACTIONABLE_FAILURES,
        FDDState.INFRASTRUCTURE_BLOCKED,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.FAILURES_NORMALIZED: {
        FDDState.FAILURES_CLUSTERED,
        FDDState.NO_ACTIONABLE_FAILURES,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.FAILURES_CLUSTERED: {
        FDDState.CLUSTER_SELECTED,
        FDDState.NO_ACTIONABLE_FAILURES,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.CLUSTER_SELECTED: {
        FDDState.INTERVENTION_FORMED,
        FDDState.NO_ACTIONABLE_FAILURES,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.INTERVENTION_FORMED: {
        FDDState.CANDIDATE_CREATED,
        FDDState.REJECTED,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.CANDIDATE_CREATED: {
        FDDState.SMOKE_TESTED,
        FDDState.REJECTED,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.SMOKE_TESTED: {
        FDDState.VALIDATED,
        FDDState.REJECTED,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.VALIDATED: {
        FDDState.HELD_OUT_CHECKED,
        FDDState.PROMOTED,
        FDDState.REJECTED,
        FDDState.INCONCLUSIVE,
        FDDState.EVALUATION_ERROR,
    },
    FDDState.HELD_OUT_CHECKED: {
        FDDState.PROMOTED,
        FDDState.REJECTED,
        FDDState.INCONCLUSIVE,
        FDDState.EVALUATION_ERROR,
    },
    # Terminal states
    FDDState.PROMOTED: set(),
    FDDState.REJECTED: set(),
    FDDState.INCONCLUSIVE: set(),
    FDDState.NO_ACTIONABLE_FAILURES: set(),
    FDDState.INFRASTRUCTURE_BLOCKED: set(),
    FDDState.EVALUATION_ERROR: set(),
}


class FDDLoop:
    """Stateful orchestrator for the Failure-Driven Development Loop."""

    def __init__(
        self,
        experiment_id: str,
        baseline_candidate: str,
        repo_root: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
        splits_root: Path | str = Path("benchmark/splits"),
    ) -> None:
        self.experiment_id = experiment_id
        self.baseline_candidate = baseline_candidate
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.db_path = Path(db_path) if db_path else Path("experiments/evaluation.db")
        self.splits_root = Path(splits_root)

        self.state = FDDState.IDLE
        self.manifest = FDDExperimentManifest(
            experiment_id=experiment_id,
            intervention_id="",
            baseline_candidate=baseline_candidate,
            candidate_id="",
            target_failure_mode="",
            state=FDDState.IDLE,
        )

        self.normalized_failures: List[FailureRecord] = []
        self.clusters: List[FailureCluster] = []
        self.selected_cluster: Optional[FailureCluster] = None
        self.intervention: Optional[Intervention] = None

        self.smoke_records: List[FailureRecord] = []
        self.validation_records: List[FailureRecord] = []
        self.held_out_records: Optional[List[FailureRecord]] = None
        self.run_delta: Optional[FDDRunDelta] = None

    def transition_to(self, new_state: FDDState, reason: str = "") -> None:
        """Transitions to a new state after validating transition legality."""
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal state transition from {self.state.value} to {new_state.value}. "
                f"Allowed target states: {[s.value for s in allowed]}"
            )
        self.state = new_state
        self.manifest.state = new_state
        if reason:
            self.manifest.decision_rationale = reason

    def load_baseline_runs(
        self,
        split_name: Optional[str] = None,
        jsonl_results_file: Optional[Path | str] = None,
    ) -> List[FailureRecord]:
        """Collects baseline evaluation records and normalizes them."""
        self.transition_to(FDDState.BENCHMARK_COLLECTED)

        records: List[FailureRecord] = []
        if jsonl_results_file and Path(jsonl_results_file).is_file():
            records = normalize_failures_from_jsonl(jsonl_results_file)
        elif self.db_path.is_file():
            conn = get_connection(self.db_path)
            try:
                tasks_lookup = build_tasks_lookup(splits_root=self.splits_root)
                runs = fetch_runs_from_db(conn, self.baseline_candidate, split_name=split_name, tasks_lookup=tasks_lookup)
                records = normalize_failures_from_summaries(runs, source_ref=f"db:{self.baseline_candidate}")
            finally:
                conn.close()
        else:
            # Check experiments/baseline/<candidate>/results.jsonl
            base_jsonl = Path(f"experiments/baseline/{self.baseline_candidate}/results.jsonl")
            if base_jsonl.is_file():
                records = normalize_failures_from_jsonl(base_jsonl)

        self.normalized_failures = records
        self.transition_to(FDDState.FAILURES_NORMALIZED)

        # Detect overall evidence mode
        if not records:
            self.manifest.evidence_mode = EvidenceMode.UNAVAILABLE.value
        else:
            modes = {r.evidence_mode for r in records}
            if len(modes) == 1:
                self.manifest.evidence_mode = next(iter(modes))
            else:
                self.manifest.evidence_mode = EvidenceMode.MIXED.value

        return records

    def cluster_and_prioritize(
        self,
        require_live: bool = True,
    ) -> Tuple[Optional[FailureCluster], str]:
        """Clusters normalized failures and selects the highest-value cluster."""
        self.clusters = cluster_failures(self.normalized_failures)
        self.transition_to(FDDState.FAILURES_CLUSTERED)

        best_cluster, status = select_highest_value_cluster(
            self.clusters,
            require_live=require_live,
        )

        if not best_cluster:
            self.selected_cluster = None
            self.manifest.decision = PromotionDecision.NO_ACTIONABLE_DATA
            self.transition_to(
                FDDState.NO_ACTIONABLE_FAILURES,
                reason=f"No actionable failure cluster identified (status: {status}).",
            )
            return None, status

        self.selected_cluster = best_cluster
        self.manifest.cluster_id = best_cluster.cluster_id
        self.manifest.target_failure_mode = best_cluster.failure_category
        self.transition_to(FDDState.CLUSTER_SELECTED)
        return best_cluster, status

    def set_intervention(self, intervention: Intervention) -> None:
        """Sets and validates the single intervention for this experiment iteration."""
        is_valid, errors = validate_intervention(intervention, repo_root=self.repo_root)
        if not is_valid:
            self.transition_to(
                FDDState.REJECTED,
                reason=f"Intervention validation failed: {'; '.join(errors)}",
            )
            self.manifest.decision = PromotionDecision.REJECTED
            return

        self.intervention = intervention
        self.manifest.intervention_id = intervention.intervention_id
        self.manifest.candidate_id = intervention.candidate_id
        self.manifest.target_failure_mode = intervention.target_failure_mode
        self.transition_to(FDDState.INTERVENTION_FORMED)

    def prepare_candidate(self, clone_baseline: bool = False) -> Path:
        """Prepares the candidate directory, ensuring baseline isolation."""
        if not self.intervention:
            raise ValueError("Intervention must be set before preparing candidate.")

        cand_dir = Path("experiments/candidates") / self.intervention.candidate_id
        if clone_baseline and not cand_dir.exists():
            create_candidate_from_baseline(
                baseline_id=self.intervention.baseline_candidate,
                new_candidate_id=self.intervention.candidate_id,
            )

        self.transition_to(FDDState.CANDIDATE_CREATED)
        return cand_dir

    def evaluate_smoke(
        self,
        evaluator: Optional[FDDEvaluator] = None,
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        smoke_records: Optional[List[FailureRecord]] = None,
    ) -> bool:
        """Runs smoke evaluation. If smoke fails, intervention is rejected immediately."""
        if not self.intervention:
            raise ValueError("Intervention must be formed before smoke evaluation.")

        if smoke_records is not None:
            self.smoke_records = smoke_records
            all_passed = all(r.success is True for r in smoke_records)
        else:
            ev = evaluator or FDDEvaluator(repo_root=self.repo_root, splits_root=self.splits_root)
            all_passed, self.smoke_records = ev.run_smoke(
                candidate_id=self.intervention.candidate_id,
                smoke_tasks=self.intervention.smoke_tasks,
                mode=mode,
                fixture_spec=fixture_spec,
            )

        self.manifest.smoke_passed = all_passed
        if not all_passed:
            self.manifest.decision = PromotionDecision.REJECTED
            self.transition_to(
                FDDState.REJECTED,
                reason="Candidate failed smoke testing on targeted tasks.",
            )
            return False

        self.transition_to(FDDState.SMOKE_TESTED)
        return True

    def evaluate_validation(
        self,
        evaluator: Optional[FDDEvaluator] = None,
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        tasks_limit: Optional[int] = None,
        validation_records: Optional[List[FailureRecord]] = None,
    ) -> List[FailureRecord]:
        """Runs validation split benchmark evaluation."""
        if not self.intervention:
            raise ValueError("Intervention must be formed before validation evaluation.")

        if validation_records is not None:
            self.validation_records = validation_records
        else:
            ev = evaluator or FDDEvaluator(repo_root=self.repo_root, splits_root=self.splits_root)
            self.validation_records = ev.run_validation(
                candidate_id=self.intervention.candidate_id,
                split_name=self.intervention.validation_split,
                mode=mode,
                fixture_spec=fixture_spec,
                tasks_limit=tasks_limit,
            )

        self.transition_to(FDDState.VALIDATED)
        return self.validation_records

    def evaluate_held_out(
        self,
        evaluator: Optional[FDDEvaluator] = None,
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        tasks_limit: Optional[int] = None,
        held_out_records: Optional[List[FailureRecord]] = None,
    ) -> List[FailureRecord]:
        """Runs held-out confirmation with cryptographic lock verification."""
        if not self.intervention:
            raise ValueError("Intervention must be formed before held-out evaluation.")

        if held_out_records is not None:
            self.held_out_records = held_out_records
        else:
            ev = evaluator or FDDEvaluator(repo_root=self.repo_root, splits_root=self.splits_root)
            self.held_out_records = ev.run_held_out(
                candidate_id=self.intervention.candidate_id,
                mode=mode,
                fixture_spec=fixture_spec,
                tasks_limit=tasks_limit,
            )

        self.transition_to(FDDState.HELD_OUT_CHECKED)
        return self.held_out_records

    def apply_promotion_gate(
        self,
        baseline_validation_records: Optional[List[FailureRecord]] = None,
        held_out_baseline_records: Optional[List[FailureRecord]] = None,
        max_collateral_regression: int = 0,
    ) -> PromotionDecision:
        """Computes failure delta and evaluates promotion gate."""
        if not self.intervention:
            raise ValueError("Intervention must be present to evaluate promotion gate.")

        # Baseline records for validation split comparison
        base_records = baseline_validation_records or [
            r for r in self.normalized_failures if r.split == self.intervention.validation_split
        ]
        if not base_records:
            base_records = self.normalized_failures

        # Compute delta
        self.run_delta = compute_run_delta(
            baseline_records=base_records,
            candidate_records=self.validation_records,
            target_failure_mode=self.intervention.target_failure_mode,
            held_out_baseline=held_out_baseline_records,
            held_out_candidate=self.held_out_records,
        )
        self.manifest.run_delta = self.run_delta

        # Actionable run check
        has_actionable = any(r.is_actionable for r in self.validation_records) or any(
            r.is_actionable for r in base_records
        )

        decision, rationale = evaluate_promotion_gate(
            delta=self.run_delta,
            smoke_passed=(self.manifest.smoke_passed is not False),
            max_collateral_regression=max_collateral_regression,
            has_actionable_runs=has_actionable,
        )

        self.manifest.decision = decision
        self.manifest.decision_rationale = rationale

        if decision == PromotionDecision.PROMOTED:
            self.manifest.validation_passed = True
            self.transition_to(FDDState.PROMOTED, reason=rationale)
        elif decision == PromotionDecision.REJECTED:
            self.manifest.validation_passed = False
            self.transition_to(FDDState.REJECTED, reason=rationale)
        elif decision == PromotionDecision.NO_ACTIONABLE_DATA:
            self.transition_to(FDDState.NO_ACTIONABLE_FAILURES, reason=rationale)
        else:
            self.transition_to(FDDState.INCONCLUSIVE, reason=rationale)

        return decision

    def save_experiment(self, base_output_dir: Path | str = Path("experiments/fdd")) -> Path:
        """Saves complete experiment artifacts and manifest."""
        if not self.intervention:
            # Fallback dummy intervention if stopped before forming intervention
            self.intervention = Intervention(
                intervention_id=self.experiment_id,
                source_cluster_id=self.selected_cluster.cluster_id if self.selected_cluster else None,
                target_failure_mode=self.manifest.target_failure_mode or "NONE",
                hypothesis="Analysis-only or blocked run; no intervention applied.",
                expected_behavior_change="None",
                intervention_scope="PROMPT",
                changed_dimensions=["none"],
                affected_files=[],
                baseline_candidate=self.baseline_candidate,
                candidate_id=self.manifest.candidate_id or self.baseline_candidate,
            )

        exp_dir = Path(base_output_dir) / self.intervention.intervention_id
        save_fdd_experiment_artifacts(
            experiment_dir=exp_dir,
            manifest=self.manifest,
            intervention=self.intervention,
            cluster=self.selected_cluster,
            delta=self.run_delta,
            smoke_records=self.smoke_records,
            validation_records=self.validation_records,
            held_out_records=self.held_out_records,
        )
        return exp_dir
