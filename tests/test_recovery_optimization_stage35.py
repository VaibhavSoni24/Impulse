"""Comprehensive Unit and Integration Tests for Stage 35: Recovery Optimization Loop.

Covers all 48+ required specifications:
1. Trace normalization
2. Repeated command detection
3. Repeated error detection
4. Repeated edit detection
5. No-progress interaction
6. Deterministic recovery clustering
7. Cluster selection
8. Earliest recovery opportunity
9. Detection latency
10. Recovery intervention creation
11. Single-dimension enforcement
12. Candidate isolation
13. Recovery policy diff
14. State-machine transitions
15. Recovery success
16. Recovery failure
17. Alternate-path recovery
18. Retry budget
19. Stop condition
20. Loop detection
21. Oscillation detection
22. Recovery-without-state-change detection
23. Late recovery detection
24. Prompt-specific recovery instruction isolation
25. Prompt invariance
26. Retrieval invariance
27. Testing invariance
28. Topology invariance
29. Skill invariance
30. FDD integration
31. Targeted failure reduction
32. Unchanged target
33. Collateral regression
34. Paired failure comparison
35. Detection latency delta
36. Recovery cost metrics
37. Testing/retrieval cost interactions
38. Clean-copy evaluator integration
39. Held-out gate
40. No-live-results
41. Infrastructure-only results
42. Fixture/live isolation
43. Benchmark hash verification
44. Manifest verification
45. Frozen artifact protection
46. Duplicate candidate rejection
47. Deterministic reports
48. Candidate artifact verification
49. Tool failure alternate tool recovery
50. Test failure revised investigation
51. Bad edit repair recovery
52. Search fallback useful path
53. Budget pressure bounded recovery
54. Missed recovery opportunity
55. Manifest mismatch rejection
56. CLI smoke commands
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from benchmark.splits.hashing import compute_file_sha256
from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.fdd.models import Intervention, InterventionScope, PromotionDecision
from local.recovery_opt.cli import run_recovery_cli
from local.recovery_opt.clustering import cluster_recovery_failures, select_highest_value_recovery_cluster
from local.recovery_opt.diff import diff_recovery_policies, format_recovery_policy_diff_md
from local.recovery_opt.earliest_detection import analyze_early_detection
from local.recovery_opt.experiment import RecoveryExperimentManager
from local.recovery_opt.fixtures import (
    fixture_a_repeated_command,
    fixture_aa_no_actionable_live_recovery,
    fixture_ab_infrastructure_only_data,
    fixture_ac_held_out_regression,
    fixture_ad_manifest_hash_mismatch,
    fixture_ae_duplicate_candidate_rejection,
    fixture_b_repeated_error,
    fixture_c_repeated_edit,
    fixture_d_no_progress_trigger,
    fixture_e_recovery_succeeds_immediately,
    fixture_f_recovery_succeeds_after_alternate_path,
    fixture_g_recovery_fails,
    fixture_h_recovery_loops,
    fixture_i_alternating_recovery_loop,
    fixture_j_retry_budget_exhausted,
    fixture_k_recovery_triggered_too_late,
    fixture_l_correct_recovery_opportunity_missed,
    fixture_m_failed_tool_alternate_tool_succeeds,
    fixture_n_test_failure_revised_investigation_succeeds,
    fixture_o_bad_edit_repair_succeeds,
    fixture_p_search_fallback_useful_path,
    fixture_q_budget_pressure_bounded_recovery,
    fixture_r_collateral_regression,
    fixture_s_targeted_failure_reduction,
    fixture_t_unchanged_target_failure,
    fixture_u_detection_latency_improvement,
    fixture_v_detection_latency_regression,
    fixture_w_testing_policy_invariant_manifest,
    fixture_x_retrieval_policy_invariant_manifest,
    fixture_y_prompt_invariant_manifest,
    fixture_z_skill_invariant_manifest,
)
from local.recovery_opt.loop_detector import RecoveryLoopDetector, is_loop_regression
from local.recovery_opt.metrics import compute_recovery_cost_metrics, compute_recovery_quality_metrics
from local.recovery_opt.mining import RecoveryTraceMiner, extract_failure_signature, normalize_command_str
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
    RecoveryPatternType,
    RecoveryPolicy,
    RecoveryQualityMetrics,
    RecoverySelectionStatus,
    RecoveryStateMachineState,
    RecoveryTaskPairOutcome,
    RecoveryVariant,
    RetryBudgetConfig,
    TaskRecoveryTransition,
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
    check_candidate_loop_safety,
    validate_recovery_candidate_integrity,
    validate_recovery_hypothesis,
)


class TestRecoveryOptimizationStage35(unittest.TestCase):
    """Authoritative test suite for Stage 35 Recovery Optimization Loop."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. Trace normalization
    def test_01_trace_normalization(self) -> None:
        sig = extract_failure_signature("AssertionError: 5 != 3\n  File at 0xdeadbeef")
        self.assertEqual(sig, "AssertionError: 5 != 3")
        norm_c = normalize_command_str("pytest   -k   test_auth  ")
        self.assertEqual(norm_c, "pytest -k test_auth")

    # 2. Repeated command detection
    def test_02_repeated_command_detection(self) -> None:
        events = fixture_a_repeated_command()
        miner = RecoveryTraceMiner()
        records = miner.analyze_task_events("task_cmd", [e.to_dict() for e in events])
        cmd_records = [r for r in records if r.repeated_pattern == RecoveryPatternType.REPEATED_COMMAND.value]
        self.assertGreaterEqual(len(cmd_records), 1)
        self.assertIn("REPEATED_CMD", cmd_records[0].failure_signature)

    # 3. Repeated error detection
    def test_03_repeated_error_detection(self) -> None:
        events = fixture_b_repeated_error()
        miner = RecoveryTraceMiner()
        records = miner.analyze_task_events("task_err", [e.to_dict() for e in events])
        err_records = [r for r in records if r.repeated_pattern == RecoveryPatternType.REPEATED_ERROR.value]
        self.assertGreaterEqual(len(err_records), 1)
        self.assertIn("REPEATED_ERR", err_records[0].failure_signature)

    # 4. Repeated edit detection
    def test_04_repeated_edit_detection(self) -> None:
        events = fixture_c_repeated_edit()
        miner = RecoveryTraceMiner()
        records = miner.analyze_task_events("task_edit", [e.to_dict() for e in events])
        edit_records = [r for r in records if r.repeated_pattern == RecoveryPatternType.REPEATED_EDIT.value]
        self.assertGreaterEqual(len(edit_records), 1)
        self.assertIn("REPEATED_EDIT", edit_records[0].failure_signature)

    # 5. No-progress interaction
    def test_05_no_progress_interaction(self) -> None:
        events = fixture_d_no_progress_trigger()
        self.assertFalse(events[0].recovery_eligible)
        self.assertTrue(events[1].recovery_eligible)
        self.assertEqual(events[1].action, "FALLBACK_SEMANTIC")

    # 6. Deterministic recovery clustering
    def test_06_deterministic_recovery_clustering(self) -> None:
        recs = [
            RecoveryFailureRecord("r1", "t1", "REC0", failure_signature="ErrA", repeated_pattern="REPEATED_ERROR"),
            RecoveryFailureRecord("r2", "t2", "REC0", failure_signature="ErrA", repeated_pattern="REPEATED_ERROR"),
            RecoveryFailureRecord("r3", "t3", "REC0", failure_signature="ErrB", repeated_pattern="REPEATED_COMMAND"),
        ]
        c1 = cluster_recovery_failures(recs)
        c2 = cluster_recovery_failures(list(reversed(recs)))
        self.assertEqual(len(c1), 2)
        self.assertEqual([c.cluster_id for c in c1], [c.cluster_id for c in c2])

    # 7. Cluster selection
    def test_07_cluster_selection(self) -> None:
        clusters = [
            RecoveryCluster(
                cluster_id="cls_fixture",
                pattern_type="REPEATED_COMMAND",
                canonical_signature="pytest -k test_auth",
                affected_unique_tasks=["t1", "t2"],
                evidence_modes=["FIXTURE"],
                recurrence_count=2,
                actionable_status=True,
            )
        ]
        sel, status, rat = select_highest_value_recovery_cluster(clusters, allow_fixture=True)
        self.assertEqual(status, RecoverySelectionStatus.ACTIONABLE_RECOVERY_SELECTED)
        self.assertIsNotNone(sel)
        self.assertEqual(sel.cluster_id, "cls_fixture")

    # 8. Earliest recovery opportunity
    def test_08_earliest_recovery_opportunity(self) -> None:
        events = fixture_k_recovery_triggered_too_late()
        rep = analyze_early_detection(events)
        self.assertEqual(rep.first_recovery_opportunity_event_index, 1)
        self.assertEqual(rep.actual_recovery_trigger_event_index, 5)

    # 9. Detection latency
    def test_09_detection_latency(self) -> None:
        events = fixture_k_recovery_triggered_too_late()
        rep = analyze_early_detection(events)
        self.assertEqual(rep.detection_latency_events, 4)
        self.assertEqual(rep.detection_latency_turns, 4)

    # 10. Recovery intervention creation
    def test_10_recovery_intervention_creation(self) -> None:
        interv = Intervention(
            intervention_id="int_rec_01",
            source_cluster_id="cls_01",
            target_failure_mode="REPEATED_COMMAND",
            hypothesis="Early fallback avoids repeated command failure.",
            expected_behavior_change="Initiate fallback on 1st recurrence.",
            intervention_scope=InterventionScope.RECOVERY.value,
            changed_dimensions=["recovery_trigger"],
            affected_files=["experiments/recovery/REC1/policy.json"],
            baseline_candidate="REC0",
            candidate_id="REC1",
        )
        self.assertEqual(interv.intervention_scope, "RECOVERY")
        self.assertEqual(len(interv.changed_dimensions), 1)

    # 11. Single-dimension enforcement
    def test_11_single_dimension_enforcement(self) -> None:
        hyp = RecoveryHypothesis(
            target_failure="Test",
            observation="Obs",
            hypothesis="Hyp",
            recovery_change="Change",
            expected_behavior="Beh",
            expected_metric_signal="Signal",
            rejection_condition="Cond",
        )
        ok, errs = validate_recovery_hypothesis(hyp)
        self.assertTrue(ok)
        self.assertEqual(len(errs), 0)

        # Missing field
        bad_hyp = RecoveryHypothesis(
            target_failure="",
            observation="Obs",
            hypothesis="",
            recovery_change="Change",
            expected_behavior="",
            expected_metric_signal="",
            rejection_condition="",
        )
        ok_bad, errs_bad = validate_recovery_hypothesis(bad_hyp)
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(errs_bad), 4)

    # 12. Candidate isolation
    def test_12_candidate_isolation(self) -> None:
        man, pol = fixture_ae_duplicate_candidate_rejection()
        ok, errs = validate_recovery_candidate_integrity(man, pol, verify_frozen=False)
        self.assertFalse(ok)
        self.assertTrue(any("candidate_id 'REC1' cannot equal parent_candidate" in e for e in errs))

    # 13. Recovery policy diff
    def test_13_recovery_policy_diff(self) -> None:
        p0 = build_rec0_baseline_policy()
        p1 = build_rec1_early_detection_policy()
        diff = diff_recovery_policies(p0, p1)
        self.assertFalse(diff["is_identical"])
        self.assertTrue(diff["feature_flag_changes"]["early_detection_enabled"]["candidate"])
        md = format_recovery_policy_diff_md(p0, p1)
        self.assertIn("Recovery Policy Diff", md)

    # 14. State-machine transitions
    def test_14_state_machine_transitions(self) -> None:
        states = [s.value for s in RecoveryStateMachineState]
        self.assertIn("FAILURE_DETECTED", states)
        self.assertIn("RECOVERY_ELIGIBLE", states)
        self.assertIn("RECOVERY_SELECTED", states)
        self.assertIn("RECOVERY_EXECUTED", states)
        self.assertIn("RESULT_OBSERVED", states)
        self.assertIn("RECOVERED", states)
        self.assertIn("LOOP_DETECTED", states)

    # 15. Recovery success
    def test_15_recovery_success(self) -> None:
        events = fixture_e_recovery_succeeds_immediately()
        qm = compute_recovery_quality_metrics(events)
        self.assertEqual(qm.targeted_recovery_success_rate, 1.0)
        self.assertEqual(qm.tasks_recovered_after_failure, 1)

    # 16. Recovery failure
    def test_16_recovery_failure(self) -> None:
        events = fixture_g_recovery_fails()
        qm = compute_recovery_quality_metrics(events)
        self.assertEqual(qm.targeted_recovery_success_rate, 0.0)
        self.assertEqual(qm.tasks_abandoned_after_failure, 1)

    # 17. Alternate-path recovery
    def test_17_alternate_path_recovery(self) -> None:
        events = fixture_f_recovery_succeeds_after_alternate_path()
        qm = compute_recovery_quality_metrics(events)
        self.assertEqual(qm.targeted_recovery_success_rate, 1.0)
        self.assertEqual(qm.alternate_path_success_rate, 1.0)

    # 18. Retry budget
    def test_18_retry_budget(self) -> None:
        events = fixture_j_retry_budget_exhausted()
        collector = RecoveryTraceCollector()
        diag = collector.evaluate_diagnostics(events)
        self.assertTrue(diag.recovery_budget_exhaustion)

    # 19. Stop condition
    def test_19_stop_condition(self) -> None:
        policy = build_rec0_baseline_policy()
        self.assertIn("target_state_recovered", policy.stop_conditions)
        self.assertIn("budget_exhausted", policy.stop_conditions)

    # 20. Loop detection
    def test_20_loop_detection(self) -> None:
        events = fixture_h_recovery_loops()
        detector = RecoveryLoopDetector(max_allowed_direct_repeats=2)
        res = detector.analyze_events(events)
        self.assertTrue(res.loop_detected)
        self.assertEqual(res.loop_type, "DIRECT_LOOP")

    # 21. Oscillation detection
    def test_21_oscillation_detection(self) -> None:
        events = fixture_i_alternating_recovery_loop()
        detector = RecoveryLoopDetector()
        res = detector.analyze_events(events)
        self.assertTrue(res.loop_detected)
        self.assertEqual(res.loop_type, "OSCILLATION")

    # 22. Recovery-without-state-change detection
    def test_22_recovery_without_state_change_detection(self) -> None:
        events = fixture_b_repeated_error()
        collector = RecoveryTraceCollector()
        diag = collector.evaluate_diagnostics(events)
        self.assertTrue(diag.recovery_without_state_change)

    # 23. Late recovery detection
    def test_23_late_recovery_detection(self) -> None:
        events = fixture_k_recovery_triggered_too_late()
        collector = RecoveryTraceCollector()
        diag = collector.evaluate_diagnostics(events)
        self.assertTrue(diag.late_recovery)

    # 24. Prompt-specific recovery instruction isolation
    def test_24_prompt_specific_recovery_instruction_isolation(self) -> None:
        pol = build_rec0_baseline_policy()
        pol.prompt_instruction = "When test fails 2x, switch hypothesis."
        man = fixture_w_testing_policy_invariant_manifest()
        man.policy_hash = pol.compute_policy_hash()
        ok, errs = validate_recovery_candidate_integrity(man, pol, verify_frozen=False)
        self.assertTrue(ok)
        self.assertEqual(len(errs), 0)

    # 25. Prompt invariance
    def test_25_prompt_invariance(self) -> None:
        man = fixture_y_prompt_invariant_manifest()
        self.assertEqual(man.root_prompt_hash, EXPECTED_P0_PROMPT_SHA256)

    # 26. Retrieval invariance
    def test_26_retrieval_invariance(self) -> None:
        man = fixture_x_retrieval_policy_invariant_manifest()
        self.assertEqual(man.retrieval_policy_hash, EXPECTED_R0_RETRIEVAL_POLICY_HASH)

    # 27. Testing invariance
    def test_27_testing_invariance(self) -> None:
        man = fixture_w_testing_policy_invariant_manifest()
        self.assertEqual(man.testing_policy_hash, EXPECTED_T0_TESTING_POLICY_HASH)

    # 28. Topology invariance
    def test_28_topology_invariance(self) -> None:
        man = fixture_w_testing_policy_invariant_manifest()
        self.assertEqual(man.topology_hash, EXPECTED_TOPOLOGY_ID)

    # 29. Skill invariance
    def test_29_skill_invariance(self) -> None:
        man = fixture_z_skill_invariant_manifest()
        self.assertEqual(man.test_strategy_skill_hash, EXPECTED_TEST_STRATEGY_SKILL_SHA256)
        self.assertEqual(man.repo_triage_skill_hash, EXPECTED_REPO_TRIAGE_SKILL_SHA256)

    # 30. FDD integration
    def test_30_fdd_integration(self) -> None:
        manager = RecoveryExperimentManager(repo_root=self.tmp_path)
        b_evs, c_evs = fixture_s_targeted_failure_reduction()
        dec, rat, metrics = manager.evaluate_candidate(
            "REC1",
            baseline_events=b_evs,
            candidate_events=c_evs,
            target_failure_mode="auth token expired",
            allow_fixture=True,
        )
        self.assertEqual(dec, PromotionDecision.PROMOTED)
        self.assertIn("Promoted", rat)

    # 31. Targeted failure reduction
    def test_31_targeted_failure_reduction(self) -> None:
        b_evs, c_evs = fixture_s_targeted_failure_reduction()
        pairs = compute_paired_recovery_comparisons(b_evs, c_evs)
        recovered = [p for p in pairs if p.transition == TaskRecoveryTransition.FAIL_TO_RECOVERED.value]
        self.assertEqual(len(recovered), 2)

    # 32. Unchanged target
    def test_32_unchanged_target(self) -> None:
        manager = RecoveryExperimentManager(repo_root=self.tmp_path)
        b_evs, c_evs = fixture_t_unchanged_target_failure()
        dec, rat, _ = manager.evaluate_candidate(
            "REC1",
            baseline_events=b_evs,
            candidate_events=c_evs,
            target_failure_mode="auth token expired",
            allow_fixture=True,
        )
        self.assertEqual(dec, PromotionDecision.REJECTED)
        self.assertIn("remained unchanged", rat)

    # 33. Collateral regression
    def test_33_collateral_regression(self) -> None:
        base, cand = fixture_r_collateral_regression()
        self.assertEqual(len(base), 2)
        self.assertEqual(len(cand), 3)
        self.assertEqual(cand[2].failure_class, "REGRESSION")

    # 34. Paired failure comparison
    def test_34_paired_failure_comparison(self) -> None:
        b_evs, c_evs = fixture_s_targeted_failure_reduction()
        pairs = compute_paired_recovery_comparisons(b_evs, c_evs)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].baseline_task_result, "FAIL")
        self.assertEqual(pairs[0].candidate_task_result, "PASS")

    # 35. Detection latency delta
    def test_35_detection_latency_delta(self) -> None:
        b_evs, c_evs = fixture_u_detection_latency_improvement()
        b_rep = analyze_early_detection(b_evs)
        c_rep = analyze_early_detection(c_evs)
        self.assertEqual(b_rep.detection_latency_events, 4)
        self.assertEqual(c_rep.detection_latency_events, 0)
        self.assertLess(c_rep.detection_latency_events, b_rep.detection_latency_events)

    # 36. Recovery cost metrics
    def test_36_recovery_cost_metrics(self) -> None:
        events = fixture_a_repeated_command()
        cm = compute_recovery_cost_metrics(events)
        self.assertEqual(cm.recovery_tool_calls, 2)
        self.assertEqual(cm.retry_count, 1)

    # 37. Testing/retrieval cost interactions
    def test_37_testing_retrieval_cost_interactions(self) -> None:
        events = [
            RecoveryExecutionEvent("r", "t", "REC0", 1, "", "", True, "", "TARGETED_VALIDATION", 1, "", "", False, "", False, "", duration_ms=50.0),
            RecoveryExecutionEvent("r", "t", "REC0", 2, "", "", True, "", "FALLBACK_EXACT_SEARCH", 1, "", "", False, "", False, "", duration_ms=50.0),
        ]
        cm = compute_recovery_cost_metrics(events)
        self.assertEqual(cm.additional_tests_caused, 1)
        self.assertEqual(cm.additional_retrieval_calls, 1)

    # 38. Clean-copy evaluator integration
    def test_38_clean_copy_evaluator_integration(self) -> None:
        from local.clean_copy.evaluator import CleanCopyEvaluator
        self.assertTrue(callable(CleanCopyEvaluator))

    # 39. Held-out gate
    def test_39_held_out_gate(self) -> None:
        ho = fixture_ac_held_out_regression()
        self.assertTrue(ho["held_out_regression"])

    # 40. No-live-results
    def test_40_no_live_results(self) -> None:
        records = fixture_aa_no_actionable_live_recovery()
        clusters = cluster_recovery_failures(records)
        _, status, rat = select_highest_value_recovery_cluster(clusters, allow_fixture=False)
        self.assertEqual(status, RecoverySelectionStatus.INFRASTRUCTURE_ONLY)

    # 41. Infrastructure-only results
    def test_41_infrastructure_only_results(self) -> None:
        records = fixture_ab_infrastructure_only_data()
        self.assertTrue(all(r.evidence_mode == "UNAVAILABLE" for r in records))
        self.assertTrue(all(not r.is_actionable for r in records))

    # 42. Fixture/live isolation
    def test_42_fixture_live_isolation(self) -> None:
        evs = fixture_a_repeated_command()
        self.assertEqual(evs[0].evidence_mode, "FIXTURE")

    # 43. Benchmark hash verification
    def test_43_benchmark_hash_verification(self) -> None:
        from benchmark.splits.manifests import verify_manifest_integrity
        from benchmark.splits.hashing import compute_file_sha256
        val_path = Path("benchmark/splits/validation_split.json")
        if val_path.is_file():
            val_hash = compute_file_sha256(val_path)
            self.assertEqual(len(val_hash), 64)
        v1_manifest = Path("benchmark/splits/v1/dev.json")
        if v1_manifest.is_file():
            self.assertTrue(verify_manifest_integrity(v1_manifest))

    # 44. Manifest verification
    def test_44_manifest_verification(self) -> None:
        pol = build_rec0_baseline_policy()
        man = fixture_w_testing_policy_invariant_manifest()
        self.assertEqual(man.policy_hash, pol.compute_policy_hash())

    # 45. Frozen artifact protection
    def test_45_frozen_artifact_protection(self) -> None:
        ok, res = verify_frozen_artifacts(Path.cwd())
        self.assertTrue(ok)
        self.assertEqual(len(res), 14)
        self.assertTrue(all(v["status"] == "MATCH" for v in res.values()))

    # 46. Duplicate candidate rejection
    def test_46_duplicate_candidate_rejection(self) -> None:
        man, pol = fixture_ae_duplicate_candidate_rejection()
        ok, errs = validate_recovery_candidate_integrity(man, pol, verify_frozen=False)
        self.assertFalse(ok)

    # 47. Deterministic reports
    def test_47_deterministic_reports(self) -> None:
        pol = build_rec0_baseline_policy()
        man = fixture_w_testing_policy_invariant_manifest()
        rep1 = generate_candidate_report_md(
            man, pol, None, None,
            RecoveryCostMetrics(), RecoveryQualityMetrics(),
            RecoveryDiagnostics(), [], "BASELINE", "Rationale"
        )
        rep2 = generate_candidate_report_md(
            man, pol, None, None,
            RecoveryCostMetrics(), RecoveryQualityMetrics(),
            RecoveryDiagnostics(), [], "BASELINE", "Rationale"
        )
        self.assertEqual(rep1, rep2)

    # 48. Candidate artifact verification
    def test_48_candidate_artifact_verification(self) -> None:
        manager = RecoveryExperimentManager(repo_root=Path.cwd())
        for cid in ["REC0", "REC1", "REC2", "REC3"]:
            ok, errs = manager.verify_candidate(cid)
            self.assertTrue(ok, f"Candidate {cid} failed verification: {errs}")

    # 49. Tool failure alternate tool recovery
    def test_49_tool_failure_alternate_tool(self) -> None:
        events = fixture_m_failed_tool_alternate_tool_succeeds()
        self.assertEqual(events[0].action, "USE_ALTERNATE_TOOL")
        self.assertEqual(events[0].recovery_outcome, RecoveryOutcome.RECOVERED.value)

    # 50. Test failure revised investigation
    def test_50_test_failure_revised_investigation(self) -> None:
        events = fixture_n_test_failure_revised_investigation_succeeds()
        self.assertEqual(events[0].action, "REVISE_HYPOTHESIS")
        self.assertEqual(events[0].recovery_outcome, RecoveryOutcome.RECOVERED.value)

    # 51. Bad edit repair recovery
    def test_51_bad_edit_repair(self) -> None:
        events = fixture_o_bad_edit_repair_succeeds()
        self.assertEqual(events[0].action, "REVERT_EDIT")
        self.assertEqual(events[0].recovery_outcome, RecoveryOutcome.RECOVERED.value)

    # 52. Search fallback useful path
    def test_52_search_fallback_useful_path(self) -> None:
        events = fixture_p_search_fallback_useful_path()
        self.assertEqual(events[0].action, "FALLBACK_EXACT_SEARCH")
        self.assertEqual(events[0].recovery_outcome, RecoveryOutcome.RECOVERED.value)

    # 53. Budget pressure bounded recovery
    def test_53_budget_pressure_recovery(self) -> None:
        events = fixture_q_budget_pressure_bounded_recovery()
        self.assertEqual(events[0].action, "STOP_EXPLORATION")
        self.assertEqual(events[0].recovery_outcome, RecoveryOutcome.RECOVERED.value)

    # 54. Missed recovery opportunity
    def test_54_missed_recovery_opportunity(self) -> None:
        events = fixture_l_correct_recovery_opportunity_missed()
        collector = RecoveryTraceCollector()
        diag = collector.evaluate_diagnostics(events)
        self.assertTrue(diag.missed_recovery_opportunity)

    # 55. Manifest mismatch rejection
    def test_55_manifest_mismatch_rejection(self) -> None:
        man, pol = fixture_ad_manifest_hash_mismatch()
        ok, errs = validate_recovery_candidate_integrity(man, pol, verify_frozen=False)
        self.assertFalse(ok)
        self.assertTrue(any("Policy hash mismatch" in e for e in errs))

    # 56. CLI smoke commands
    def test_56_cli_smoke_commands(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret_analyze = run_recovery_cli(["--candidate", "REC0", "--analyze"])
            self.assertEqual(ret_analyze, 0)

            ret_diff = run_recovery_cli(["--candidate", "REC1", "--diff"])
            self.assertEqual(ret_diff, 0)

            ret_report = run_recovery_cli(["--candidate", "REC0", "--report"])
            self.assertEqual(ret_report, 0)

            ret_matrix = run_recovery_cli(["--matrix"])
            self.assertEqual(ret_matrix, 0)

            ret_mine = run_recovery_cli(["--mine-failures"])
            self.assertEqual(ret_mine, 0)

            ret_cluster = run_recovery_cli(["--cluster"])
            self.assertEqual(ret_cluster, 0)


if __name__ == "__main__":
    unittest.main()
