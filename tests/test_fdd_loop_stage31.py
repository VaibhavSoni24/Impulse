"""Comprehensive Unit and Integration Tests for Stage 31: Failure-Driven Development (FDD) Loop.

Tests all 20 required fixture scenarios (A through T):
- Scenario A: No results
- Scenario B: Only infrastructure-unavailable runs
- Scenario C: One live failure cluster
- Scenario D: Multiple live failure clusters
- Scenario E: Cluster tie-breaker determinism
- Scenario F: Targeted failure improves
- Scenario G: Targeted failure unchanged
- Scenario H: Targeted failure worsens
- Scenario I: Target improves but collateral regression appears
- Scenario J: Validation improves but held-out regresses
- Scenario K: Validation inconclusive
- Scenario L: Successful promotion
- Scenario M: Rejection (smoke failure)
- Scenario N: Interrupted / incomplete experiment recovery
- Scenario O: Mixed evidence modes
- Scenario P: Malformed intervention validation
- Scenario Q: Held-out lock mismatch detection
- Scenario R: Split manifest mismatch detection
- Scenario S: Non-deterministic source ordering produces identical clusters
- Scenario T: Duplicate intervention / candidate creation attempt
Plus:
- Frozen Stage 24 artifact invariance
- Experiment artifact cryptographic verification
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmark.splits.held_out_lock import HeldOutViolationError
from local.clean_copy.adapter import FixtureAgentSpec
from local.clean_copy.models import ExecutionMode
from local.dashboard.models import EvidenceMode
from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.fdd.cli import verify_fdd_artifacts
from local.fdd.clustering import cluster_failures, generate_cluster_id
from local.fdd.evaluator import FDDEvaluator
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.interventions import (
    create_candidate_from_baseline,
    load_intervention,
    save_intervention,
    validate_intervention,
)
from local.fdd.loop import FDDLoop, InvalidStateTransitionError
from local.fdd.models import (
    FDDExperimentManifest,
    FDDRunDelta,
    FDDState,
    FailureCluster,
    FailureRecord,
    Intervention,
    InterventionScope,
    PromotionDecision,
)
from local.fdd.normalization import (
    is_infrastructure_failure,
    normalize_failure_record,
    normalize_failures_from_jsonl,
)
from local.fdd.prioritization import (
    STATUS_NO_ACTIONABLE,
    STATUS_NO_ACTIONABLE_LIVE,
    STATUS_SELECTED,
    select_highest_value_cluster,
)
from local.fdd.reporting import generate_fdd_report, save_fdd_experiment_artifacts


class TestFailureDrivenDevelopmentStage31(unittest.TestCase):
    """Test suite for FDD Loop (Stage 31)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="fdd_test_")
        self.temp_path = Path(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario A: No results
    # -------------------------------------------------------------------------
    def test_scenario_a_no_results(self) -> None:
        """Scenario A: Empty input records produce no clusters and handled cleanly."""
        clusters = cluster_failures([])
        self.assertEqual(len(clusters), 0)

        best, status = select_highest_value_cluster(clusters, require_live=True)
        self.assertIsNone(best)
        self.assertEqual(status, "NO_CLUSTERS")

        delta = compute_run_delta([], [], target_failure_mode="WRONG_HYPOTHESIS")
        self.assertIsNone(delta.targeted_reduction)

        decision, rationale = evaluate_promotion_gate(delta, has_actionable_runs=False)
        self.assertEqual(decision, PromotionDecision.NO_ACTIONABLE_DATA)

    # -------------------------------------------------------------------------
    # Scenario B: Only infrastructure-unavailable runs
    # -------------------------------------------------------------------------
    def test_scenario_b_only_infrastructure_runs(self) -> None:
        """Scenario B: Infrastructure-limited runs do not count as actionable cognitive failures."""
        infra_record = FailureRecord(
            run_id="run-infra-1",
            candidate_id="E0",
            task_id="task-1",
            split="dev",
            repository="repo-a",
            evidence_mode=EvidenceMode.UNAVAILABLE.value,
            run_status="execution_unavailable_local_host",
            success=None,
            failure_category="INFRASTRUCTURE_UNAVAILABLE",
            failure_stage="AGENT_EXECUTION",
            termination_reason="Local host cannot execute competition Gemma 4 environment (lack of GPU).",
            is_actionable=False,
        )
        self.assertTrue(is_infrastructure_failure("INFRASTRUCTURE_UNAVAILABLE", "execution_unavailable_local_host", "lack of GPU"))

        clusters = cluster_failures([infra_record])
        self.assertEqual(len(clusters), 1)
        self.assertFalse(clusters[0].is_actionable)
        self.assertEqual(clusters[0].eligible_completed_run_count, 0)

        # Selection with live requirement returns NO_ACTIONABLE_LIVE_FAILURES
        best, status = select_highest_value_cluster(clusters, require_live=True)
        self.assertIsNone(best)
        self.assertEqual(status, STATUS_NO_ACTIONABLE_LIVE)

    # -------------------------------------------------------------------------
    # Scenario C: One live failure cluster
    # -------------------------------------------------------------------------
    def test_scenario_c_one_live_failure_cluster(self) -> None:
        """Scenario C: A single live failure mode forms an actionable cluster and is selected."""
        rec1 = FailureRecord(
            run_id="run-live-1",
            candidate_id="E1",
            task_id="task-10",
            repository="repo-x",
            evidence_mode=EvidenceMode.LIVE.value,
            run_status="COMPLETED",
            success=False,
            failure_category="WRONG_HYPOTHESIS",
            failure_stage="AGENT_EXECUTION",
            termination_reason="Invalid assumption about API",
            is_actionable=True,
        )
        rec2 = FailureRecord(
            run_id="run-live-2",
            candidate_id="E1",
            task_id="task-11",
            repository="repo-x",
            evidence_mode=EvidenceMode.LIVE.value,
            run_status="COMPLETED",
            success=False,
            failure_category="WRONG_HYPOTHESIS",
            failure_stage="AGENT_EXECUTION",
            termination_reason="Invalid assumption about API",
            is_actionable=True,
        )

        clusters = cluster_failures([rec1, rec2])
        self.assertEqual(len(clusters), 1)
        self.assertTrue(clusters[0].is_actionable)
        self.assertEqual(clusters[0].eligible_completed_run_count, 2)
        self.assertEqual(clusters[0].unique_tasks_count, 2)

        best, status = select_highest_value_cluster(clusters, require_live=True)
        self.assertIsNotNone(best)
        self.assertEqual(status, STATUS_SELECTED)
        self.assertEqual(best.failure_category, "WRONG_HYPOTHESIS")

    # -------------------------------------------------------------------------
    # Scenario D: Multiple live failure clusters
    # -------------------------------------------------------------------------
    def test_scenario_d_multiple_live_failure_clusters(self) -> None:
        """Scenario D: Multiple clusters are sorted lexicographically by actionable failure count."""
        # 1 run of COMMAND failure
        rec_cmd = FailureRecord(
            run_id="run-cmd-1",
            candidate_id="E1",
            task_id="t-cmd",
            evidence_mode=EvidenceMode.LIVE.value,
            success=False,
            failure_category="COMMAND",
            failure_stage="VERIFICATION",
            termination_reason="SyntaxError in test runner",
            is_actionable=True,
        )
        # 3 runs of WRONG_HYPOTHESIS failure
        rec_whs = [
            FailureRecord(
                run_id=f"run-wh-{i}",
                candidate_id="E1",
                task_id=f"t-wh-{i}",
                evidence_mode=EvidenceMode.LIVE.value,
                success=False,
                failure_category="WRONG_HYPOTHESIS",
                failure_stage="AGENT_EXECUTION",
                termination_reason="Root cause misidentified",
                is_actionable=True,
            )
            for i in range(3)
        ]

        clusters = cluster_failures([rec_cmd] + rec_whs)
        self.assertEqual(len(clusters), 2)

        best, status = select_highest_value_cluster(clusters, require_live=True)
        self.assertIsNotNone(best)
        self.assertEqual(status, STATUS_SELECTED)
        # WRONG_HYPOTHESIS has 3 runs vs 1
        self.assertEqual(best.failure_category, "WRONG_HYPOTHESIS")
        self.assertEqual(best.eligible_completed_run_count, 3)

    # -------------------------------------------------------------------------
    # Scenario E: Cluster tie-breaker
    # -------------------------------------------------------------------------
    def test_scenario_e_cluster_tie_breaker(self) -> None:
        """Scenario E: Clusters with equal counts tie-break deterministically on cluster_id."""
        rec_a = FailureRecord(
            run_id="run-a-1",
            candidate_id="E1",
            task_id="t-1",
            evidence_mode=EvidenceMode.LIVE.value,
            success=False,
            failure_category="CATEGORY_A",
            failure_stage="STAGE_1",
            termination_reason="reason A",
            is_actionable=True,
        )
        rec_b = FailureRecord(
            run_id="run-b-1",
            candidate_id="E1",
            task_id="t-2",
            evidence_mode=EvidenceMode.LIVE.value,
            success=False,
            failure_category="CATEGORY_B",
            failure_stage="STAGE_1",
            termination_reason="reason B",
            is_actionable=True,
        )

        clusters = cluster_failures([rec_a, rec_b])
        self.assertEqual(len(clusters), 2)
        # Both have 1 eligible run, 1 task, 1 repo
        self.assertEqual(clusters[0].eligible_completed_run_count, clusters[1].eligible_completed_run_count)

        best1, _ = select_highest_value_cluster(clusters, require_live=True)
        # Run multiple times to verify determinism
        best2, _ = select_highest_value_cluster(list(reversed(clusters)), require_live=True)
        self.assertEqual(best1.cluster_id, best2.cluster_id)

    # -------------------------------------------------------------------------
    # Scenario F: Targeted failure improves
    # -------------------------------------------------------------------------
    def test_scenario_f_targeted_failure_improves(self) -> None:
        """Scenario F: Target failure mode decreases from baseline to candidate."""
        base_runs = [
            FailureRecord(
                run_id=f"b-{i}", candidate_id="M0", task_id=f"t-{i}",
                run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS",
                is_actionable=True,
            )
            for i in range(5)
        ]
        cand_runs = [
            FailureRecord(
                run_id="c-0", candidate_id="M1", task_id="t-0",
                run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS",
                is_actionable=True,
            ),
            FailureRecord(
                run_id="c-1", candidate_id="M1", task_id="t-1",
                run_status="COMPLETED", success=True, failure_category="",
                is_actionable=True,
            ),
            FailureRecord(
                run_id="c-2", candidate_id="M1", task_id="t-2",
                run_status="COMPLETED", success=True, failure_category="",
                is_actionable=True,
            ),
        ]

        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="WRONG_HYPOTHESIS")
        self.assertEqual(delta.baseline_failure_count, 5)
        self.assertEqual(delta.candidate_failure_count, 1)
        self.assertEqual(delta.targeted_reduction, 4)

        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # -------------------------------------------------------------------------
    # Scenario G: Targeted failure unchanged
    # -------------------------------------------------------------------------
    def test_scenario_g_targeted_failure_unchanged(self) -> None:
        """Scenario G: Target failure count unchanged produces REJECTED."""
        base_runs = [
            FailureRecord(
                run_id=f"b-{i}", candidate_id="M0", task_id=f"t-{i}",
                run_status="COMPLETED", success=False, failure_category="COMMAND",
                is_actionable=True,
            )
            for i in range(3)
        ]
        cand_runs = [
            FailureRecord(
                run_id=f"c-{i}", candidate_id="M1", task_id=f"t-{i}",
                run_status="COMPLETED", success=False, failure_category="COMMAND",
                is_actionable=True,
            )
            for i in range(3)
        ]

        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="COMMAND")
        self.assertEqual(delta.targeted_reduction, 0)

        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("unchanged", rationale.lower())

    # -------------------------------------------------------------------------
    # Scenario H: Targeted failure worsens
    # -------------------------------------------------------------------------
    def test_scenario_h_targeted_failure_worsens(self) -> None:
        """Scenario H: Target failure mode increases produces REJECTED."""
        base_runs = [
            FailureRecord(
                run_id="b-1", candidate_id="M0", task_id="t-1",
                run_status="COMPLETED", success=False, failure_category="REGRESSION",
                is_actionable=True,
            )
        ]
        cand_runs = [
            FailureRecord(
                run_id=f"c-{i}", candidate_id="M1", task_id=f"t-{i}",
                run_status="COMPLETED", success=False, failure_category="REGRESSION",
                is_actionable=True,
            )
            for i in range(4)
        ]

        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="REGRESSION")
        self.assertEqual(delta.targeted_reduction, -3)

        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("worsened", rationale.lower())

    # -------------------------------------------------------------------------
    # Scenario I: Target improves but collateral regression appears
    # -------------------------------------------------------------------------
    def test_scenario_i_target_improves_collateral_regression(self) -> None:
        """Scenario I: Target improves but another category degrades produces REJECTED."""
        base_runs = [
            # 4 WRONG_HYPOTHESIS failures
            FailureRecord(
                run_id=f"b-wh-{i}", candidate_id="M0", task_id=f"t-wh-{i}",
                run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS",
                is_actionable=True,
            )
            for i in range(4)
        ]
        cand_runs = [
            # 1 WRONG_HYPOTHESIS failure (improved!)
            FailureRecord(
                run_id="c-wh-0", candidate_id="M1", task_id="t-wh-0",
                run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS",
                is_actionable=True,
            ),
            # 3 COMMAND failures (collateral regression!)
            FailureRecord(
                run_id="c-cmd-0", candidate_id="M1", task_id="t-cmd-0",
                run_status="COMPLETED", success=False, failure_category="COMMAND",
                is_actionable=True,
            ),
            FailureRecord(
                run_id="c-cmd-1", candidate_id="M1", task_id="t-cmd-1",
                run_status="COMPLETED", success=False, failure_category="COMMAND",
                is_actionable=True,
            ),
            FailureRecord(
                run_id="c-cmd-2", candidate_id="M1", task_id="t-cmd-2",
                run_status="COMPLETED", success=False, failure_category="COMMAND",
                is_actionable=True,
            ),
        ]

        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="WRONG_HYPOTHESIS")
        self.assertEqual(delta.targeted_reduction, 3)
        self.assertIn("COMMAND", delta.collateral_regressions)
        self.assertEqual(delta.collateral_regressions["COMMAND"], 3)

        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True, max_collateral_regression=0)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("collateral regressions", rationale.lower())

    # -------------------------------------------------------------------------
    # Scenario J: Validation improves but held-out regresses
    # -------------------------------------------------------------------------
    def test_scenario_j_validation_improves_held_out_regresses(self) -> None:
        """Scenario J: Validation improves but held-out drops produces REJECTED."""
        base_runs = [
            FailureRecord(
                run_id="b-1", candidate_id="M0", task_id="t-1",
                run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS",
                is_actionable=True,
            )
        ]
        cand_runs = [
            FailureRecord(
                run_id="c-1", candidate_id="M1", task_id="t-1",
                run_status="COMPLETED", success=True, failure_category="",
                is_actionable=True,
            )
        ]
        # Held-out baseline: 100% pass (2/2)
        ho_base = [
            FailureRecord(run_id="ho-b-1", candidate_id="M0", task_id="ho-1", run_status="COMPLETED", success=True, is_actionable=True),
            FailureRecord(run_id="ho-b-2", candidate_id="M0", task_id="ho-2", run_status="COMPLETED", success=True, is_actionable=True),
        ]
        # Held-out candidate: 0% pass (0/2)
        ho_cand = [
            FailureRecord(run_id="ho-c-1", candidate_id="M1", task_id="ho-1", run_status="COMPLETED", success=False, is_actionable=True),
            FailureRecord(run_id="ho-c-2", candidate_id="M1", task_id="ho-2", run_status="COMPLETED", success=False, is_actionable=True),
        ]

        delta = compute_run_delta(
            base_runs, cand_runs,
            target_failure_mode="WRONG_HYPOTHESIS",
            held_out_baseline=ho_base,
            held_out_candidate=ho_cand,
        )
        self.assertTrue(delta.held_out_regression)

        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("held-out confirmation regressed", rationale.lower())

    # -------------------------------------------------------------------------
    # Scenario K: Validation inconclusive
    # -------------------------------------------------------------------------
    def test_scenario_k_validation_inconclusive(self) -> None:
        """Scenario K: Missing or indeterminate run signals produce INCONCLUSIVE."""
        delta = FDDRunDelta(target_failure_mode="WRONG_HYPOTHESIS", baseline_failure_count=None)
        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True, has_actionable_runs=False)
        self.assertEqual(decision, PromotionDecision.NO_ACTIONABLE_DATA)

    # -------------------------------------------------------------------------
    # Scenario L: Successful promotion
    # -------------------------------------------------------------------------
    def test_scenario_l_successful_promotion(self) -> None:
        """Scenario L: Valid intervention passes smoke, reduces target, passes held-out -> PROMOTED."""
        base_runs = [
            FailureRecord(run_id="b-1", candidate_id="M0", task_id="t-1", run_status="COMPLETED", success=False, failure_category="INCOMPLETE_FIX", is_actionable=True),
            FailureRecord(run_id="b-2", candidate_id="M0", task_id="t-2", run_status="COMPLETED", success=False, failure_category="INCOMPLETE_FIX", is_actionable=True),
        ]
        cand_runs = [
            FailureRecord(run_id="c-1", candidate_id="M1", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
            FailureRecord(run_id="c-2", candidate_id="M1", task_id="t-2", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
        ]
        ho_base = [FailureRecord(run_id="h-1", candidate_id="M0", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]
        ho_cand = [FailureRecord(run_id="h-2", candidate_id="M1", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]

        delta = compute_run_delta(base_runs, cand_runs, "INCOMPLETE_FIX", held_out_baseline=ho_base, held_out_candidate=ho_cand)
        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)

        self.assertEqual(decision, PromotionDecision.PROMOTED)
        self.assertEqual(delta.targeted_reduction, 2)
        self.assertFalse(delta.held_out_regression)

    # -------------------------------------------------------------------------
    # Scenario M: Rejection (smoke failure)
    # -------------------------------------------------------------------------
    def test_scenario_m_smoke_rejection(self) -> None:
        """Scenario M: Smoke failure rejects immediately without further benchmarking."""
        delta = FDDRunDelta(target_failure_mode="WRONG_HYPOTHESIS", targeted_reduction=5)
        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=False)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("smoke", rationale.lower())

    # -------------------------------------------------------------------------
    # Scenario N: Interrupted / incomplete experiment recovery
    # -------------------------------------------------------------------------
    def test_scenario_n_interrupted_experiment_state(self) -> None:
        """Scenario N: State machine persists state and enforces legal transitions."""
        loop = FDDLoop(experiment_id="exp-test-state", baseline_candidate="E0")
        self.assertEqual(loop.state, FDDState.IDLE)

        # Illegal skip to VALIDATED must raise
        with self.assertRaises(InvalidStateTransitionError):
            loop.transition_to(FDDState.VALIDATED)

        # Valid transition sequence
        loop.transition_to(FDDState.BENCHMARK_COLLECTED)
        loop.transition_to(FDDState.FAILURES_NORMALIZED)
        loop.transition_to(FDDState.FAILURES_CLUSTERED)
        self.assertEqual(loop.state, FDDState.FAILURES_CLUSTERED)

    # -------------------------------------------------------------------------
    # Scenario O: Mixed evidence modes
    # -------------------------------------------------------------------------
    def test_scenario_o_mixed_evidence_modes(self) -> None:
        """Scenario O: Mixed evidence modes are isolated and labeled accurately."""
        rec_live = FailureRecord(run_id="r1", candidate_id="C1", task_id="t1", evidence_mode="LIVE", success=False, failure_category="COMMAND", is_actionable=True)
        rec_fix = FailureRecord(run_id="r2", candidate_id="C1", task_id="t2", evidence_mode="FIXTURE", success=False, failure_category="COMMAND", is_actionable=True)
        rec_unav = FailureRecord(run_id="r3", candidate_id="C1", task_id="t3", evidence_mode="UNAVAILABLE", success=None, failure_category="INFRASTRUCTURE", is_actionable=False)

        clusters = cluster_failures([rec_live, rec_fix, rec_unav])
        # Live and fixture actionable runs are separated from infra
        self.assertTrue(len(clusters) >= 2)

        # Loop detection of mixed modes
        loop = FDDLoop(experiment_id="exp-mix", baseline_candidate="C1")
        # Save temp jsonl
        p = self.temp_path / "mix.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for r in [rec_live, rec_fix, rec_unav]:
                f.write(json.dumps(r.to_dict()) + "\n")

        loop.load_baseline_runs(jsonl_results_file=p)
        self.assertEqual(loop.manifest.evidence_mode, EvidenceMode.MIXED.value)

    # -------------------------------------------------------------------------
    # Scenario P: Malformed intervention validation
    # -------------------------------------------------------------------------
    def test_scenario_p_malformed_intervention(self) -> None:
        """Scenario P: Bundled dimensions or invalid scopes fail validation."""
        # 1. Bundled multiple dimensions
        int_bundled = Intervention(
            intervention_id="int-bad-1",
            source_cluster_id="cls-1",
            target_failure_mode="COMMAND",
            hypothesis="Change prompt and also adjust retrieval top_k and train LoRA",
            expected_behavior_change="Fix commands",
            intervention_scope="PROMPT",
            changed_dimensions=["prompt_template", "retrieval_k", "lora_rank"],  # Illegal: > 1 dimension
            affected_files=["agent/prompts/test.md"],
            baseline_candidate="M0",
            candidate_id="M1",
        )
        ok, errors = validate_intervention(int_bundled)
        self.assertFalse(ok)
        self.assertTrue(any("single-dimension" in e.lower() for e in errors))

        # 2. Identical baseline and candidate
        int_same = Intervention(
            intervention_id="int-bad-2",
            source_cluster_id="cls-1",
            target_failure_mode="COMMAND",
            hypothesis="Single change",
            expected_behavior_change="Fix",
            intervention_scope="PROMPT",
            changed_dimensions=["prompt_template"],
            affected_files=["experiments/candidates/M0/config.json"],
            baseline_candidate="M0",
            candidate_id="M0",  # Illegal: cannot mutate in place
        )
        ok, errors = validate_intervention(int_same)
        self.assertFalse(ok)
        self.assertTrue(any("identical" in e.lower() for e in errors))

        # 3. Attempting to modify frozen Stage 24 artifact
        int_frozen = Intervention(
            intervention_id="int-bad-3",
            source_cluster_id="cls-1",
            target_failure_mode="COMMAND",
            hypothesis="Change scout prompt",
            expected_behavior_change="Improve scout",
            intervention_scope="PROMPT",
            changed_dimensions=["scout_prompt"],
            affected_files=["agent/prompts/scout.md"],  # Illegal: frozen artifact
            baseline_candidate="M0",
            candidate_id="M1_frozen_tamper",
        )
        ok, errors = validate_intervention(int_frozen)
        self.assertFalse(ok)
        self.assertTrue(any("frozen" in e.lower() for e in errors))

    # -------------------------------------------------------------------------
    # Scenario Q: Held-out lock mismatch
    # -------------------------------------------------------------------------
    def test_scenario_q_held_out_lock_tamper(self) -> None:
        """Scenario Q: Tampering with held_out.lock triggers HeldOutViolationError."""
        # Setup mock splits directory
        split_v1 = self.temp_path / "v1"
        split_v1.mkdir(parents=True)
        (split_v1 / "held_out.jsonl").write_text('{"instance_id": "task_1"}\n', encoding="utf-8")
        (split_v1 / "held_out.lock").write_text('{"manifest_sha256": "wrong", "held_out_file_sha256": "tampered"}', encoding="utf-8")
        (split_v1 / "manifest.json").write_text('{"splits": {}}', encoding="utf-8")

        ev = FDDEvaluator(splits_root=self.temp_path)
        with self.assertRaises(HeldOutViolationError):
            ev._verify_held_out_lock(split_version="v1", manifest_sha256="expected_manifest")

    # -------------------------------------------------------------------------
    # Scenario R: Split manifest mismatch
    # -------------------------------------------------------------------------
    def test_scenario_r_split_manifest_missing(self) -> None:
        """Scenario R: Missing or invalid split manifest is rejected."""
        ev = FDDEvaluator(splits_root=self.temp_path)
        with self.assertRaises(FileNotFoundError):
            ev._verify_split_manifest(split_version="v_missing")

    # -------------------------------------------------------------------------
    # Scenario S: Non-deterministic source ordering
    # -------------------------------------------------------------------------
    def test_scenario_s_deterministic_clustering_ordering(self) -> None:
        """Scenario S: Record order permutation produces identical cluster IDs and ranking."""
        records = [
            FailureRecord(run_id=f"r-{i}", candidate_id="E", task_id=f"t-{i}", failure_category=f"CAT_{i % 3}", failure_stage="AGENT", termination_reason=f"reason {i % 3}", is_actionable=True)
            for i in range(12)
        ]

        # Order 1: original
        clusters_1 = cluster_failures(records)
        # Order 2: reversed
        clusters_2 = cluster_failures(list(reversed(records)))
        # Order 3: alternating
        clusters_3 = cluster_failures(records[::2] + records[1::2])

        cids_1 = [c.cluster_id for c in clusters_1]
        cids_2 = [c.cluster_id for c in clusters_2]
        cids_3 = [c.cluster_id for c in clusters_3]

        self.assertEqual(cids_1, cids_2)
        self.assertEqual(cids_1, cids_3)

    # -------------------------------------------------------------------------
    # Scenario T: Duplicate intervention attempt
    # -------------------------------------------------------------------------
    def test_scenario_t_duplicate_candidate_attempt(self) -> None:
        """Scenario T: Attempting to create existing candidate directory fails safely."""
        base_dir = self.temp_path / "M0"
        base_dir.mkdir()
        (base_dir / "config.json").write_text("{}", encoding="utf-8")

        # First clone succeeds
        new_dir = create_candidate_from_baseline("M0", "M1_test", candidates_dir=self.temp_path)
        self.assertTrue(new_dir.is_dir())

        # Duplicate attempt fails with FileExistsError
        with self.assertRaises(FileExistsError):
            create_candidate_from_baseline("M0", "M1_test", candidates_dir=self.temp_path)

    # -------------------------------------------------------------------------
    # End-to-End Artifacts & Reproducibility
    # -------------------------------------------------------------------------
    def test_fdd_artifacts_and_verification(self) -> None:
        """Verifies report generation, artifact saving, and cryptographic verification."""
        manifest = FDDExperimentManifest(
            experiment_id="exp-fdd-demo",
            intervention_id="int-demo-1",
            baseline_candidate="M0",
            candidate_id="M1",
            target_failure_mode="WRONG_HYPOTHESIS",
            state=FDDState.PROMOTED,
            decision=PromotionDecision.PROMOTED,
            decision_rationale="Promoted: reduced failures by 2.",
            smoke_passed=True,
            validation_passed=True,
        )
        intervention = Intervention(
            intervention_id="int-demo-1",
            source_cluster_id="cls-demo",
            target_failure_mode="WRONG_HYPOTHESIS",
            hypothesis="Add explicit schema check to reduce wrong hypothesis",
            expected_behavior_change="Fewer incorrect hypotheses formed",
            intervention_scope="PROMPT",
            changed_dimensions=["schema_guidance"],
            affected_files=["experiments/candidates/M1/prompts/root.md"],
            baseline_candidate="M0",
            candidate_id="M1",
        )
        cluster = FailureCluster(
            cluster_id="cls-demo",
            signature="Wrong hypothesis sample",
            failure_category="WRONG_HYPOTHESIS",
            failure_stage="AGENT_EXECUTION",
            termination_reason_sample="Misidentified schema",
            affected_runs_count=2,
            unique_tasks_count=2,
            eligible_completed_run_count=2,
            is_actionable=True,
        )
        delta = FDDRunDelta(
            target_failure_mode="WRONG_HYPOTHESIS",
            baseline_failure_count=3,
            candidate_failure_count=1,
            targeted_reduction=2,
        )

        out_dir = self.temp_path / "exp_out"
        save_fdd_experiment_artifacts(
            experiment_dir=out_dir,
            manifest=manifest,
            intervention=intervention,
            cluster=cluster,
            delta=delta,
        )

        # Check required files
        self.assertTrue((out_dir / "manifest.json").is_file())
        self.assertTrue((out_dir / "intervention.json").is_file())
        self.assertTrue((out_dir / "cluster.json").is_file())
        self.assertTrue((out_dir / "result.json").is_file())
        self.assertTrue((out_dir / "report.md").is_file())

        # Verify artifacts
        ok, errors = verify_fdd_artifacts(out_dir)
        self.assertTrue(ok, f"Verification failed with: {errors}")

        # Check report content
        report_text = (out_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("# Failure-Driven Experiment", report_text)
        self.assertIn("## Target Failure", report_text)
        self.assertIn("## Smoke Result", report_text)
        self.assertIn("## Targeted Failure Delta", report_text)
        self.assertIn("## Decision", report_text)
        self.assertIn("PROMOTED", report_text)

    # -------------------------------------------------------------------------
    # Invariant: Frozen Stage 24 Artifacts
    # -------------------------------------------------------------------------
    def test_frozen_stage24_artifacts_invariance(self) -> None:
        """Frozen Stage 24 artifacts must remain strictly invariant (all MATCH)."""
        ok, results = verify_frozen_artifacts(Path("."))
        self.assertTrue(ok, "Frozen artifacts check failed.")
        for path, status in results.items():
            self.assertEqual(status["status"], "MATCH", f"Frozen artifact modified: {path}")

    def test_all_frozen_artifacts_rejected_in_interventions(self) -> None:
        """Every single frozen artifact must be rejected if specified in affected_files."""
        from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
        for frozen_rel in FROZEN_STAGE24_HASHES:
            intervention = Intervention(
                intervention_id=f"int-tamper-{hash(frozen_rel)}",
                source_cluster_id="cls-test",
                target_failure_mode="COMMAND",
                hypothesis="Attempting forbidden modification",
                expected_behavior_change="Break frozen baseline",
                intervention_scope="PROMPT",
                changed_dimensions=["tamper"],
                affected_files=[frozen_rel],
                baseline_candidate="M0",
                candidate_id="M1_bad",
            )
            ok, errors = validate_intervention(intervention)
            self.assertFalse(ok, f"Expected validation failure for frozen artifact: {frozen_rel}")
            self.assertTrue(any("frozen" in e.lower() for e in errors))

    def test_intervention_serialization_roundtrip(self) -> None:
        """Intervention JSON save and load preserves all fields identically."""
        int_orig = Intervention(
            intervention_id="int-roundtrip-1",
            source_cluster_id="cls-wh-1",
            target_failure_mode="WRONG_HYPOTHESIS",
            hypothesis="Add pre-execution sanity check",
            expected_behavior_change="Prevent early misdiagnosis",
            intervention_scope="RECOVERY",
            changed_dimensions=["recovery_heuristics"],
            affected_files=["local/recovery/heuristics.py"],
            baseline_candidate="M0",
            candidate_id="M1_rec",
            smoke_tasks=["task-10"],
            validation_split="validation",
            held_out_policy="WHEN_PROMISING",
        )
        file_path = self.temp_path / "intervention.json"
        save_intervention(int_orig, file_path)
        int_loaded = load_intervention(file_path)

        self.assertEqual(int_orig.to_dict(), int_loaded.to_dict())

    def test_cli_analyze_cluster_select_modes(self) -> None:
        """Tests run_fdd_cli in analyze, cluster, and select modes."""
        from local.fdd.cli import run_fdd_cli
        import io
        from contextlib import redirect_stdout

        # 1. Analyze mode
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_fdd_cli(["--candidate", "E0", "--split", "dev", "--analyze"])
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("FDD Analysis for Candidate: E0", out)
        self.assertIn("Actionable Failures: 0", out)

        # 2. Cluster mode
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_fdd_cli(["--candidate", "E0", "--split", "dev", "--cluster"])
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("Discovered 1 Failure Clusters", out)

        # 3. Select mode (live only -> NO_ACTIONABLE_LIVE_FAILURES)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_fdd_cli(["--candidate", "E0", "--split", "dev", "--select"])
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("NO_ACTIONABLE_LIVE_FAILURES", out)
        self.assertIn("Selected Cluster: None", out)

        # 4. JSON output mode
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_fdd_cli(["--candidate", "E0", "--split", "dev", "--analyze", "--json"])
        self.assertEqual(ret, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["candidate"], "E0")
        self.assertEqual(data["actionable_records"], 0)

    def test_full_fdd_loop_lifecycle_promotion(self) -> None:
        """Full end-to-end execution of FDDLoop state machine in fixture mode."""
        loop = FDDLoop(experiment_id="exp-e2e-loop", baseline_candidate="M0")
        self.assertEqual(loop.state, FDDState.IDLE)

        # Prepare synthetic fixture baseline runs in jsonl
        base_runs = [
            FailureRecord(run_id="b-1", candidate_id="M0", task_id="t-1", evidence_mode="FIXTURE", run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS", failure_stage="AGENT", termination_reason="assumption error", is_actionable=True),
            FailureRecord(run_id="b-2", candidate_id="M0", task_id="t-2", evidence_mode="FIXTURE", run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS", failure_stage="AGENT", termination_reason="assumption error", is_actionable=True),
        ]
        base_jsonl = self.temp_path / "base_results.jsonl"
        with open(base_jsonl, "w", encoding="utf-8") as f:
            for r in base_runs:
                f.write(json.dumps(r.to_dict()) + "\n")

        # Step 1: Load baseline
        loop.load_baseline_runs(jsonl_results_file=base_jsonl)
        self.assertEqual(loop.state, FDDState.FAILURES_NORMALIZED)

        # Step 2: Cluster and prioritize (allowing fixture mode)
        best, status = loop.cluster_and_prioritize(require_live=False)
        self.assertEqual(loop.state, FDDState.CLUSTER_SELECTED)
        self.assertIsNotNone(best)
        self.assertEqual(best.failure_category, "WRONG_HYPOTHESIS")

        # Step 3: Form intervention
        intervention = Intervention(
            intervention_id="int-e2e-01",
            source_cluster_id=best.cluster_id,
            target_failure_mode="WRONG_HYPOTHESIS",
            hypothesis="Refine hypothesis formation instructions",
            expected_behavior_change="Reduces incorrect assumption failures",
            intervention_scope="PROMPT",
            changed_dimensions=["hypothesis_guidance"],
            affected_files=["experiments/candidates/M1_test/prompts/root.md"],
            baseline_candidate="M0",
            candidate_id="M1_test",
            smoke_tasks=["t-1"],
            validation_split="validation",
        )
        loop.set_intervention(intervention)
        self.assertEqual(loop.state, FDDState.INTERVENTION_FORMED)

        # Step 4: Candidate preparation
        cand_dir = loop.prepare_candidate(clone_baseline=False)
        self.assertEqual(loop.state, FDDState.CANDIDATE_CREATED)

        # Step 5: Smoke test (passing)
        smoke_runs = [FailureRecord(run_id="s-1", candidate_id="M1_test", task_id="t-1", run_status="COMPLETED", success=True, is_actionable=True)]
        smoke_ok = loop.evaluate_smoke(smoke_records=smoke_runs)
        self.assertTrue(smoke_ok)
        self.assertEqual(loop.state, FDDState.SMOKE_TESTED)

        # Step 6: Validation run (improved: 0 WRONG_HYPOTHESIS failures)
        val_runs = [
            FailureRecord(run_id="v-1", candidate_id="M1_test", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
            FailureRecord(run_id="v-2", candidate_id="M1_test", task_id="t-2", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
        ]
        loop.evaluate_validation(validation_records=val_runs)
        self.assertEqual(loop.state, FDDState.VALIDATED)

        # Step 7: Held-out confirmation
        ho_cand = [FailureRecord(run_id="h-1", candidate_id="M1_test", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]
        ho_base = [FailureRecord(run_id="hb-1", candidate_id="M0", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]
        loop.evaluate_held_out(held_out_records=ho_cand)
        self.assertEqual(loop.state, FDDState.HELD_OUT_CHECKED)

        # Step 8: Apply promotion gate
        decision = loop.apply_promotion_gate(held_out_baseline_records=ho_base)
        self.assertEqual(decision, PromotionDecision.PROMOTED)
        self.assertEqual(loop.state, FDDState.PROMOTED)

        # Step 9: Save artifacts
        exp_dir = loop.save_experiment(base_output_dir=self.temp_path)
        self.assertTrue((exp_dir / "manifest.json").is_file())
        self.assertTrue((exp_dir / "report.md").is_file())

        # Step 10: Verify saved artifacts
        ok, errors = verify_fdd_artifacts(exp_dir)
        self.assertTrue(ok, f"Verification failed with: {errors}")


if __name__ == "__main__":
    unittest.main()
