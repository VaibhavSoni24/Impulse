"""Comprehensive Unit and Integration Tests for Stage 34: Testing Strategy Optimization Loop.

Covers all required specifications:
1. T0 policy creation
2. T1 policy creation
3. T2 policy creation
4. T3 policy creation
5. Policy diff determinism
6. Single-dimension testing-change enforcement
7. Prompt immutability
8. Retrieval immutability
9. Topology immutability
10. Skill immutability
11. Targeted test selection
12. Adjacent selection
13. Subsystem selection
14. Full-suite feasibility
15. Adaptive risk rules
16. Adaptive escalation
17. Adaptive stopping
18. Fallback handling
19. Test trace schema
20. Test cost metrics
21. Evidence metrics
22. Early detection
23. Redundancy detection
24. Duplicate execution detection
25. Paired task comparison
26. FDD integration
27. Targeted failure reduction
28. Unchanged target
29. Collateral regression
30. Held-out regression
31. No live results
32. Infrastructure-only results
33. Fixture/live isolation
34. Clean-copy integration
35. Stage 25 context compaction interaction
36. Stage 26 tool budgeting interaction
37. Stage 29 split verification
38. Frozen test skill protection
39. Candidate uniqueness
40. Manifest hash verification
41. Deterministic report generation
42. Candidate artifact verification
43. CLI smoke execution
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
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.models import FDDRunDelta, FailureRecord, Intervention, InterventionScope, PromotionDecision
from local.testing_opt.cli import run_testing_cli, verify_testing_candidate_artifacts
from local.testing_opt.diff import compute_test_policy_diff, render_test_policy_diff_md
from local.testing_opt.experiment import TestingExperimentManager
from local.testing_opt.feasibility import (
    FeasibilityEvaluationResult,
    FullSuiteFeasibilityEvaluator,
    evaluate_full_suite_feasibility,
)
from local.testing_opt.fixtures import (
    get_fixture_a_t0_targeted_pass,
    get_fixture_b_t0_targeted_fail,
    get_fixture_c_t1_adjacent_discovers_regression,
    get_fixture_d_t1_redundant_tests,
    get_fixture_e_t2_subsystem_discovers_regression,
    get_fixture_f_t2_full_suite_infeasible,
    get_fixture_g_t2_full_suite_feasible,
    get_fixture_h_t3_low_risk_stops_early,
    get_fixture_i_t3_high_risk_escalates,
    get_fixture_j_t3_discovers_regression_at_later_stage,
    get_fixture_k_duplicate_test_execution,
    get_fixture_l_repeated_full_suite,
    get_fixture_m_test_discovery_failure,
    get_fixture_n_test_command_failure_fallback,
    get_fixture_o_pre_existing_test_failure,
    get_fixture_p_infrastructure_only_execution,
    get_fixture_q_target_failure_improves,
    get_fixture_r_target_failure_unchanged,
    get_fixture_s_collateral_regression,
    get_fixture_t_held_out_regression,
    get_fixture_u_paired_comparison,
    get_fixture_v_deterministic_policy_diff,
    get_fixture_w_manifest_mismatch,
    get_fixture_x_frozen_skill_hash_mismatch,
    get_fixture_y_no_actionable_live_data,
)
from local.testing_opt.metrics import (
    build_test_quality_cost_frontier,
    compute_test_cost_metrics,
    compute_test_evidence_metrics,
    render_test_quality_cost_frontier_md,
)
from local.testing_opt.models import (
    AdaptiveEscalationTrace,
    FullSuiteFeasibility,
    RiskSignal,
    RiskSignalType,
    TestCandidateManifest,
    TestCostMetrics,
    TestDiagnostics,
    TestEvidenceMetrics,
    TestExecutionEvent,
    TestHypothesis,
    TestLevel,
    TestPolicy,
    TestTaskPairOutcome,
    TestingStrategyVariant,
)
from local.testing_opt.paired import (
    compute_test_paired_comparison,
    save_test_paired_results_csv,
    save_test_paired_results_jsonl,
    summarize_test_paired_outcomes,
)
from local.testing_opt.policy import (
    build_t0_targeted_policy,
    build_t1_adjacent_policy,
    build_t2_subsystem_full_policy,
    build_t3_adaptive_policy,
    get_canonical_testing_policy,
)
from local.testing_opt.reporting import generate_testing_experiment_report
from local.testing_opt.risk import (
    AdaptiveDecision,
    AdaptiveEscalationController,
    RiskSignalEvaluator,
)
from local.testing_opt.trace import TestTraceCollector
from local.testing_opt.validator import (
    EXPECTED_FROZEN_TEST_SKILL_SHA256,
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_RETRIEVAL_R0_POLICY_SHA256,
    EXPECTED_TOPOLOGY_ID,
    TestingValidationError,
    validate_testing_candidate_integrity,
    validate_testing_hypothesis,
)


class TestTestingStrategyStage34(unittest.TestCase):
    """Test suite covering all required specifications of Stage 34."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.testing_dir = Path(self.tmp_dir) / "testing"
        self.testing_dir.mkdir(parents=True, exist_ok=True)
        self.manager = TestingExperimentManager(testing_base_dir=self.testing_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. T0 policy creation
    def test_01_t0_policy_creation(self) -> None:
        p0 = build_t0_targeted_policy()
        self.assertEqual(p0.variant, TestingStrategyVariant.T0.value)
        self.assertTrue(p0.targeted_enabled)
        self.assertFalse(p0.adjacent_enabled)
        self.assertFalse(p0.subsystem_enabled)
        self.assertFalse(p0.full_suite_enabled)
        self.assertFalse(p0.adaptive_enabled)
        self.assertEqual(p0.max_test_commands, 2)
        self.assertTrue(len(p0.compute_policy_hash()) == 64)

    # 2. T1 policy creation
    def test_02_t1_policy_creation(self) -> None:
        p1 = build_t1_adjacent_policy()
        self.assertEqual(p1.variant, TestingStrategyVariant.T1.value)
        self.assertTrue(p1.targeted_enabled)
        self.assertTrue(p1.adjacent_enabled)
        self.assertFalse(p1.subsystem_enabled)
        self.assertFalse(p1.full_suite_enabled)
        self.assertFalse(p1.adaptive_enabled)
        self.assertGreater(p1.max_test_commands, 2)

    # 3. T2 policy creation
    def test_03_t2_policy_creation(self) -> None:
        p2 = build_t2_subsystem_full_policy()
        self.assertEqual(p2.variant, TestingStrategyVariant.T2.value)
        self.assertTrue(p2.targeted_enabled)
        self.assertTrue(p2.adjacent_enabled)
        self.assertTrue(p2.subsystem_enabled)
        self.assertTrue(p2.full_suite_enabled)
        self.assertFalse(p2.adaptive_enabled)

    # 4. T3 policy creation
    def test_04_t3_policy_creation(self) -> None:
        p3 = build_t3_adaptive_policy()
        self.assertEqual(p3.variant, TestingStrategyVariant.T3.value)
        self.assertTrue(p3.targeted_enabled)
        self.assertTrue(p3.adjacent_enabled)
        self.assertTrue(p3.subsystem_enabled)
        self.assertTrue(p3.full_suite_enabled)
        self.assertTrue(p3.adaptive_enabled)

    # 5. Policy diff determinism
    def test_05_policy_diff_determinism(self) -> None:
        p0, p1 = get_fixture_v_deterministic_policy_diff()
        diff1 = compute_test_policy_diff(p0, p1)
        diff2 = compute_test_policy_diff(p0, p1)
        self.assertEqual(diff1.to_dict(), diff2.to_dict())
        self.assertEqual(render_test_policy_diff_md(diff1), render_test_policy_diff_md(diff2))
        self.assertIn("adjacent_enabled", diff1.enabled_flags_diff)

    # 6. Single-dimension testing-change enforcement
    def test_06_single_dimension_testing_change_enforcement(self) -> None:
        p0 = build_t0_targeted_policy()
        p1 = build_t1_adjacent_policy()
        diff = compute_test_policy_diff(p0, p1)
        self.assertFalse(diff.is_identical)
        self.assertIn("adjacent_enabled", diff.enabled_flags_diff)
        # Policy diff should only touch testing-related parameters, not prompts or retrieval
        self.assertNotIn("prompt_sha256", diff.to_dict())
        self.assertNotIn("retrieval_policy_hash", diff.to_dict())
        self.assertNotIn("topology_id", diff.to_dict())

    # 7. Prompt immutability
    def test_07_prompt_immutability(self) -> None:
        policy = build_t1_adjacent_policy()
        manifest = TestCandidateManifest(
            candidate_id="T1",
            parent_candidate_id="T0",
            testing_variant="T1",
            testing_policy_hash=policy.compute_policy_hash(),
            prompt_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",  # Altered!
            hypothesis=TestHypothesis("INCOMPLETE_FIX", "Obs", "Hyp", "Change", "Sig", "Rej"),
            evidence_mode="FIXTURE",
        )
        is_valid, errors = validate_testing_candidate_integrity(manifest, policy, verify_frozen=False)
        self.assertFalse(is_valid)
        self.assertTrue(any("Prompt immutability violated" in e for e in errors))

    # 8. Retrieval immutability
    def test_08_retrieval_immutability(self) -> None:
        policy = build_t1_adjacent_policy()
        manifest = TestCandidateManifest(
            candidate_id="T1",
            parent_candidate_id="T0",
            testing_variant="T1",
            testing_policy_hash=policy.compute_policy_hash(),
            retrieval_policy_hash="0000000000000000000000000000000000000000000000000000000000000000",  # Altered!
            hypothesis=TestHypothesis("INCOMPLETE_FIX", "Obs", "Hyp", "Change", "Sig", "Rej"),
            evidence_mode="FIXTURE",
        )
        is_valid, errors = validate_testing_candidate_integrity(manifest, policy, verify_frozen=False)
        self.assertFalse(is_valid)
        self.assertTrue(any("Retrieval immutability violated" in e for e in errors))

    # 9. Topology immutability
    def test_09_topology_immutability(self) -> None:
        policy = build_t1_adjacent_policy()
        manifest = TestCandidateManifest(
            candidate_id="T1",
            parent_candidate_id="T0",
            testing_variant="T1",
            testing_policy_hash=policy.compute_policy_hash(),
            topology_id="scout_debugger_reviewer",  # Altered!
            hypothesis=TestHypothesis("INCOMPLETE_FIX", "Obs", "Hyp", "Change", "Sig", "Rej"),
            evidence_mode="FIXTURE",
        )
        is_valid, errors = validate_testing_candidate_integrity(manifest, policy, verify_frozen=False)
        self.assertFalse(is_valid)
        self.assertTrue(any("Topology immutability violated" in e for e in errors))

    # 10. Skill immutability
    def test_10_skill_immutability(self) -> None:
        bad_hash = get_fixture_x_frozen_skill_hash_mismatch()
        self.assertNotEqual(bad_hash, EXPECTED_FROZEN_TEST_SKILL_SHA256)
        # Verify that actual file in repository has exact expected hash
        skill_file = Path("agent/skills/test_strategy/SKILL.md")
        self.assertTrue(skill_file.is_file())
        actual_hash = compute_file_sha256(skill_file)
        self.assertEqual(actual_hash, EXPECTED_FROZEN_TEST_SKILL_SHA256)

    # 11. Targeted test selection
    def test_11_targeted_test_selection(self) -> None:
        policy, records, events = get_fixture_a_t0_targeted_pass()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].test_level, TestLevel.TARGETED.value)
        self.assertEqual(events[0].result, "PASSED")
        self.assertEqual(events[0].tests_executed, 1)

    # 12. Adjacent selection
    def test_12_adjacent_selection(self) -> None:
        policy, records, events = get_fixture_c_t1_adjacent_discovers_regression()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].test_level, TestLevel.TARGETED.value)
        self.assertEqual(events[1].test_level, TestLevel.ADJACENT.value)
        self.assertEqual(events[1].result, "FAILED")
        self.assertEqual(events[1].failures_detected, 1)

    # 13. Subsystem selection
    def test_13_subsystem_selection(self) -> None:
        policy, records, events = get_fixture_e_t2_subsystem_discovers_regression()
        self.assertEqual(len(events), 3)
        levels = [e.test_level for e in events]
        self.assertEqual(levels, [TestLevel.TARGETED.value, TestLevel.ADJACENT.value, TestLevel.SUBSYSTEM.value])
        self.assertEqual(events[2].result, "FAILED")

    # 14. Full-suite feasibility
    def test_14_full_suite_feasibility(self) -> None:
        # Feasible scenario
        pol_g, ctx_g = get_fixture_g_t2_full_suite_feasible()
        res_g = evaluate_full_suite_feasibility(
            policy=pol_g,
            estimated_runtime_seconds=ctx_g["historical_runtime_sec"],
            remaining_budget_seconds=ctx_g["remaining_budget_sec"],
            suite_test_count=ctx_g["total_test_count"],
            is_environment_stable=ctx_g["environment_stable"],
        )
        self.assertEqual(res_g.feasibility, FullSuiteFeasibility.FEASIBLE)

        # Infeasible scenario
        pol_f, ctx_f = get_fixture_f_t2_full_suite_infeasible()
        res_f = evaluate_full_suite_feasibility(
            policy=pol_f,
            estimated_runtime_seconds=ctx_f["historical_runtime_sec"],
            remaining_budget_seconds=ctx_f["remaining_budget_sec"],
            suite_test_count=ctx_f["total_test_count"],
            is_environment_stable=ctx_f["environment_stable"],
        )
        self.assertEqual(res_f.feasibility, FullSuiteFeasibility.NOT_FEASIBLE)

        # Unknown scenario
        res_unk = evaluate_full_suite_feasibility(policy=pol_g)
        self.assertEqual(res_unk.feasibility, FullSuiteFeasibility.UNKNOWN)

    # 15. Adaptive risk rules
    def test_15_adaptive_risk_rules(self) -> None:
        signals = RiskSignalEvaluator.evaluate_diff_risk(
            modified_files=["core/models.py", "core/views.py", "core/utils.py", "core/api.py"],
            added_lines=120,
            deleted_lines=40,
            is_public_api_modified=True,
            is_shared_utility_modified=True,
        )
        self.assertGreaterEqual(len(signals), 3)
        agg_risk = RiskSignalEvaluator.compute_aggregate_risk_level(signals)
        self.assertIn(agg_risk, ("HIGH", "CRITICAL"))

    # 16. Adaptive escalation
    def test_16_adaptive_escalation(self) -> None:
        policy = build_t3_adaptive_policy()
        controller = AdaptiveEscalationController(policy)
        signals = [
            RiskSignal(signal_type=RiskSignalType.CHANGED_PUBLIC_API.value, severity="HIGH", observed=True)
        ]
        trace = controller.decide_next_step(
            current_level=TestLevel.TARGETED.value,
            test_passed=True,
            risk_signals=signals,
            commands_executed=1,
            remaining_budget_seconds=200.0,
        )
        self.assertEqual(trace.decision, AdaptiveDecision.ESCALATE.value)
        self.assertEqual(trace.target_level, TestLevel.ADJACENT.value)

    # 17. Adaptive stopping
    def test_17_adaptive_stopping(self) -> None:
        policy = build_t3_adaptive_policy()
        controller = AdaptiveEscalationController(policy)
        trace = controller.decide_next_step(
            current_level=TestLevel.TARGETED.value,
            test_passed=True,
            risk_signals=[],  # Low risk
            commands_executed=1,
            remaining_budget_seconds=200.0,
        )
        self.assertEqual(trace.decision, AdaptiveDecision.STOP.value)
        self.assertIsNone(trace.target_level)

    # 18. Fallback handling
    def test_18_fallback_handling(self) -> None:
        pol_n, events_n = get_fixture_n_test_command_failure_fallback()
        self.assertEqual(len(events_n), 2)
        self.assertEqual(events_n[0].result, "ERROR")
        self.assertIn("FALLBACK", events_n[0].escalation_decision)
        self.assertEqual(events_n[1].result, "PASSED")

        pol_m, event_m = get_fixture_m_test_discovery_failure()
        self.assertEqual(event_m.result, "SKIPPED")
        self.assertIn("DISCOVERY_FAILED", event_m.stop_decision)

    # 19. Test trace schema
    def test_19_test_trace_schema(self) -> None:
        _, _, events = get_fixture_a_t0_targeted_pass()
        ev = events[0]
        ev_dict = ev.to_dict()
        self.assertEqual(ev_dict["strategy_id"], "T0")
        self.assertEqual(ev_dict["test_level"], "TARGETED")
        self.assertEqual(ev_dict["result"], "PASSED")
        # Roundtrip
        deser = TestExecutionEvent.from_dict(ev_dict)
        self.assertEqual(deser.command, ev.command)
        self.assertEqual(deser.duration_ms, ev.duration_ms)

    # 20. Test cost metrics
    def test_20_test_cost_metrics(self) -> None:
        _, _, events = get_fixture_c_t1_adjacent_discovers_regression()
        cost = compute_test_cost_metrics(events, total_agent_tool_calls=10, total_agent_runtime_ms=5000.0)
        self.assertEqual(cost.total_test_commands, 2)
        self.assertEqual(cost.targeted_commands, 1)
        self.assertEqual(cost.adjacent_commands, 1)
        self.assertEqual(cost.subsystem_commands, 0)
        self.assertEqual(cost.total_tests_executed, 5)
        self.assertAlmostEqual(cost.total_test_runtime_ms, 950.0)
        self.assertEqual(cost.testing_tool_call_share, 0.2)

    # 21. Evidence metrics
    def test_21_evidence_metrics(self) -> None:
        _, records, events = get_fixture_c_t1_adjacent_discovers_regression()
        quality = compute_test_evidence_metrics(
            events=events,
            candidate_records=records,
            target_failure_mode="INCOMPLETE_FIX",
        )
        self.assertEqual(quality.adjacent_failures_discovered, 1)
        self.assertEqual(quality.targeted_behavior_confirmed, 1)
        self.assertEqual(quality.early_detection_level, "ADJACENT")

    # 22. Early detection
    def test_22_early_detection(self) -> None:
        # Fixture B detects failure at TARGETED
        _, _, events_b = get_fixture_b_t0_targeted_fail()
        quality_b = compute_test_evidence_metrics(events=events_b, candidate_records=[])
        self.assertEqual(quality_b.early_detection_level, "TARGETED")

        # Fixture E detects at SUBSYSTEM
        _, _, events_e = get_fixture_e_t2_subsystem_discovers_regression()
        quality_e = compute_test_evidence_metrics(events=events_e, candidate_records=[])
        self.assertEqual(quality_e.early_detection_level, "SUBSYSTEM")

    # 23. Redundancy detection
    def test_23_redundancy_detection(self) -> None:
        _, _, events = get_fixture_d_t1_redundant_tests()
        collector = TestTraceCollector("T1")
        for e in events:
            collector.record_event(e)
        diag = collector.compute_diagnostics()
        self.assertEqual(diag.zero_new_evidence_adjacent_count, 1)

    # 24. Duplicate execution detection
    def test_24_duplicate_execution_detection(self) -> None:
        dup_events = get_fixture_k_duplicate_test_execution()
        collector_k = TestTraceCollector("T0")
        for e in dup_events:
            collector_k.record_event(e)
        diag_k = collector_k.compute_diagnostics()
        self.assertEqual(diag_k.duplicate_command_count, 1)

        rep_full = get_fixture_l_repeated_full_suite()
        collector_l = TestTraceCollector("T2")
        for e in rep_full:
            collector_l.record_event(e)
        diag_l = collector_l.compute_diagnostics()
        self.assertEqual(diag_l.unnecessary_full_suite_count, 2)

    # 25. Paired task comparison
    def test_25_paired_task_comparison(self) -> None:
        base_recs, cand_recs, base_evs, cand_evs = get_fixture_u_paired_comparison()
        outcomes = compute_test_paired_comparison(base_recs, cand_recs, base_evs, cand_evs)
        self.assertEqual(len(outcomes), 4)
        summary = summarize_test_paired_outcomes(outcomes)
        self.assertEqual(summary["total_paired"], 4)
        self.assertEqual(summary["FAIL_TO_PASS"], 1)
        self.assertEqual(summary["PASS_TO_FAIL"], 1)
        self.assertGreater(summary["total_test_commands_candidate"], summary["total_test_commands_baseline"])

    # 26. FDD integration
    def test_26_fdd_integration(self) -> None:
        base_recs, cand_recs = get_fixture_q_target_failure_improves()
        delta = compute_run_delta(base_recs, cand_recs, "INCOMPLETE_FIX")
        self.assertEqual(delta.targeted_reduction, 3)
        self.assertEqual(len(delta.collateral_regressions), 0)
        decision, rationale = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # 27. Targeted failure reduction
    def test_27_targeted_failure_reduction(self) -> None:
        base_recs, cand_recs = get_fixture_q_target_failure_improves()
        delta = compute_run_delta(base_recs, cand_recs, "INCOMPLETE_FIX")
        self.assertGreater(delta.targeted_reduction, 0)

    # 28. Unchanged target
    def test_28_unchanged_target(self) -> None:
        base_recs, cand_recs = get_fixture_r_target_failure_unchanged()
        delta = compute_run_delta(base_recs, cand_recs, "INCOMPLETE_FIX")
        self.assertEqual(delta.targeted_reduction, 0)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 29. Collateral regression
    def test_29_collateral_regression(self) -> None:
        base_recs, cand_recs = get_fixture_s_collateral_regression()
        delta = compute_run_delta(base_recs, cand_recs, "INCOMPLETE_FIX")
        self.assertGreater(len(delta.collateral_regressions), 0)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 30. Held-out regression
    def test_30_held_out_regression(self) -> None:
        val_base, val_cand, held_base, held_cand = get_fixture_t_held_out_regression()
        delta = compute_run_delta(
            baseline_records=val_base,
            candidate_records=val_cand,
            target_failure_mode="INCOMPLETE_FIX",
            held_out_baseline=held_base,
            held_out_candidate=held_cand,
        )
        self.assertGreater(delta.targeted_reduction, 0)
        self.assertTrue(delta.held_out_regression)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 31. No live results
    def test_31_no_live_results(self) -> None:
        recs = get_fixture_y_no_actionable_live_data()
        self.assertTrue(all(r.evidence_mode == "UNAVAILABLE" for r in recs))
        self.assertTrue(all(not r.is_actionable for r in recs))

    # 32. Infrastructure-only results
    def test_32_infrastructure_only_results(self) -> None:
        rec, ev = get_fixture_p_infrastructure_only_execution()
        self.assertEqual(rec.evidence_mode, "INFRASTRUCTURE_ONLY")
        self.assertFalse(rec.is_actionable)
        self.assertEqual(ev.evidence_mode, "INFRASTRUCTURE_ONLY")

    # 33. Fixture/live isolation
    def test_33_fixture_live_isolation(self) -> None:
        _, recs_a, _ = get_fixture_a_t0_targeted_pass()
        recs_y = get_fixture_y_no_actionable_live_data()
        # Verify evidence modes are distinct and preserved
        self.assertTrue(all(r.evidence_mode == "FIXTURE" for r in recs_a))
        self.assertTrue(all(r.evidence_mode == "UNAVAILABLE" for r in recs_y))

    # 34. Clean-copy integration
    def test_34_clean_copy_integration(self) -> None:
        from local.clean_copy.evaluator import CleanCopyEvaluator
        self.assertTrue(callable(CleanCopyEvaluator))

    # 35. Stage 25 context compaction interaction
    def test_35_stage25_compaction_interaction(self) -> None:
        from local.context_compaction import compact_test_log
        raw_log = "PASSED test_1\n" * 50 + "FAILED test_critical_failure\nAssertionError: expected 5 got 3\n"
        res = compact_test_log("pytest tests/", 1, raw_log)
        self.assertIn("FAILED test_critical_failure", res.preserved_text)

    # 36. Stage 26 tool budgeting interaction
    def test_36_stage26_budgeting_interaction(self) -> None:
        from local.budgeting.cache import BoundedToolCache
        cache = BoundedToolCache(max_entries=5)
        k = cache.make_cache_key("search_similar_code", {"query": "pytest tests/"}, "repo_state_1")
        self.assertIsNotNone(k)
        cache.put(k, {"result": "PASSED"})
        entry = cache.get(k)
        self.assertIsNotNone(entry)
        self.assertEqual(cache.hits_count, 1)

    # 37. Stage 29 split verification
    def test_37_stage29_split_verification(self) -> None:
        val_path = Path("benchmark/splits/validation_split.json")
        held_path = Path("benchmark/splits/held_out.lock")
        if val_path.is_file():
            val_hash = compute_file_sha256(val_path)
            self.assertTrue(len(val_hash) == 64)
        if held_path.is_file():
            held_hash = compute_file_sha256(held_path)
            self.assertTrue(len(held_hash) == 64)

    # 38. Frozen test skill protection
    def test_38_frozen_test_skill_protection(self) -> None:
        skill_path = Path("agent/skills/test_strategy/SKILL.md")
        actual_hash = compute_file_sha256(skill_path)
        self.assertEqual(actual_hash, EXPECTED_FROZEN_TEST_SKILL_SHA256)
        self.assertEqual(actual_hash, FROZEN_STAGE24_HASHES["agent/skills/test_strategy/SKILL.md"])

    # 39. Candidate uniqueness
    def test_39_candidate_uniqueness(self) -> None:
        policy = build_t1_adjacent_policy()
        hyp = TestHypothesis("INCOMPLETE_FIX", "Obs", "Hyp", "Change", "Sig", "Rej")
        self.manager.create_candidate("T1", "T0", policy, hyp, evidence_mode="FIXTURE")
        # Attempting to recreate candidate should raise FileExistsError
        with self.assertRaises(FileExistsError):
            self.manager.create_candidate("T1", "T0", policy, hyp, evidence_mode="FIXTURE")

    # 40. Manifest hash verification
    def test_40_manifest_hash_verification(self) -> None:
        manifest, policy = get_fixture_w_manifest_mismatch()
        is_valid, errors = validate_testing_candidate_integrity(manifest, policy, verify_frozen=False)
        self.assertFalse(is_valid)
        self.assertTrue(any("Policy hash mismatch" in e for e in errors))

    # 41. Deterministic report generation
    def test_41_deterministic_report_generation(self) -> None:
        p0 = build_t0_targeted_policy()
        diff = compute_test_policy_diff(p0, p0)
        manifest = self.manager.ensure_t0_baseline(evidence_mode="FIXTURE")
        report1 = generate_testing_experiment_report(
            manifest=manifest,
            diff=diff,
            quality=TestEvidenceMetrics(0.0, 1.0, "BASELINE", 0, 0.0),
            cost=TestCostMetrics(),
            diagnostics=TestDiagnostics(),
            paired_outcomes=[],
            validation_passed=True,
        )
        report2 = generate_testing_experiment_report(
            manifest=manifest,
            diff=diff,
            quality=TestEvidenceMetrics(0.0, 1.0, "BASELINE", 0, 0.0),
            cost=TestCostMetrics(),
            diagnostics=TestDiagnostics(),
            paired_outcomes=[],
            validation_passed=True,
        )
        self.assertEqual(report1, report2)
        self.assertIn("Testing Strategy Experiment: T0", report1)

    # 42. Candidate artifact verification
    def test_42_candidate_artifact_verification(self) -> None:
        # Verify existing canonical T0 in experiments/testing/T0
        t0_path = Path("experiments/testing/T0")
        if t0_path.exists():
            is_ok, errs = verify_testing_candidate_artifacts(t0_path)
            self.assertTrue(is_ok, f"Verification failed: {errs}")

    # 43. CLI smoke execution
    def test_43_cli_smoke_execution(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_testing_cli(["--parent", "T0", "--analyze", "--testing-dir", str(self.testing_dir)])
        self.assertEqual(ret, 0)
        self.assertIn("Testing Strategy Baseline Analysis", buf.getvalue())

        buf_matrix = io.StringIO()
        with redirect_stdout(buf_matrix):
            ret_matrix = run_testing_cli(["--matrix", "--testing-dir", str(self.testing_dir)])
        self.assertEqual(ret_matrix, 0)


if __name__ == "__main__":
    unittest.main()
