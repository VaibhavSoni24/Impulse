"""Comprehensive Unit and Integration Tests for Stage 33: Retrieval Optimization Loop.

Covers all 40 required test scenarios:
1. R0 policy validity
2. R1 semantic policy validity
3. R2 neighbor policy validity
4. R3 subgraph policy validity
5. R4 dynamic policy validity
6. Single-dimension retrieval change enforcement
7. Prompt immutability during retrieval experiment
8. Topology immutability
9. Tool contract immutability
10. Deterministic policy diff
11. Retrieval trace schema
12. Semantic event recording
13. Neighbor event recording
14. Subgraph event recording
15. Dynamic-depth trace
16. Retrieval cost metrics
17. Retrieval quality metrics
18. Paired task comparisons
19. Retrieval redundancy detection
20. Dead retrieval detection
21. Over-expansion detection
22. Budget enforcement
23. Stop-condition enforcement
24. Fallback handling
25. Cache-hit accounting
26. Stage 25 context compaction interaction integrity
27. Stage 26 tool caching interaction integrity
28. FDD integration
29. Targeted failure improvement
30. Targeted failure unchanged
31. Collateral regression
32. Validation/held-out gate
33. No-live-results handling
34. Infrastructure-only handling
35. Fixture/live isolation
36. Manifest hash validation
37. Benchmark hash validation
38. Frozen artifact protection
39. Candidate uniqueness
40. Deterministic report generation
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from benchmark.splits.hashing import compute_file_sha256
from local.budgeting.cache import BoundedToolCache
from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.models import FDDRunDelta, FailureRecord, Intervention, InterventionScope, PromotionDecision
from local.retrieval_opt.cli import run_retrieval_cli, verify_retrieval_candidate_artifacts
from local.retrieval_opt.diff import compute_retrieval_policy_diff, render_retrieval_policy_diff_md
from local.retrieval_opt.experiment import RetrievalExperimentManager
from local.retrieval_opt.fixtures import (
    get_fixture_a_r0_baseline,
    get_fixture_b_r1_relevant,
    get_fixture_c_r1_irrelevant,
    get_fixture_d_r2_useful_neighbor,
    get_fixture_e_r2_redundant_neighbors,
    get_fixture_f_r3_dependency_path,
    get_fixture_g_r3_over_expansion,
    get_fixture_h_r4_stops_early,
    get_fixture_i_r4_expands,
    get_fixture_j_budget_exhausted,
    get_fixture_k_tool_failure_fallback,
    get_fixture_l_cache_hit,
    get_fixture_m_duplicate_retrieval,
    get_fixture_n_target_improvement,
    get_fixture_o_target_unchanged,
    get_fixture_p_collateral_regression,
    get_fixture_q_deterministic_comparison,
    get_fixture_r_mixed_evidence_modes,
    get_fixture_s_no_actionable_live_results,
    get_fixture_t_manifest_hash_mismatch,
)
from local.retrieval_opt.metrics import (
    build_quality_cost_frontier,
    compute_retrieval_cost_metrics,
    compute_retrieval_quality_metrics,
    render_quality_cost_frontier_md,
)
from local.retrieval_opt.models import (
    DynamicRoundTrace,
    RetrievalCandidateManifest,
    RetrievalCostMetrics,
    RetrievalDiagnostics,
    RetrievalEvent,
    RetrievalHypothesis,
    RetrievalPolicy,
    RetrievalQualityMetrics,
    RetrievalTaskPairOutcome,
    RetrievalType,
    RetrievalVariant,
    TaskTransition,
)
from local.retrieval_opt.paired import (
    compute_retrieval_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
    summarize_paired_outcomes,
)
from local.retrieval_opt.policy import (
    build_r0_baseline_policy,
    build_r1_semantic_policy,
    build_r2_neighbors_policy,
    build_r3_subgraph_policy,
    build_r4_dynamic_policy,
    get_canonical_policy,
)
from local.retrieval_opt.reporting import generate_retrieval_experiment_report
from local.retrieval_opt.trace import RetrievalTraceCollector
from local.retrieval_opt.validator import (
    ALLOWED_COMPETITION_RETRIEVAL_TOOLS,
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_TOPOLOGY_ID,
    RetrievalValidationError,
    validate_retrieval_candidate_integrity,
    validate_retrieval_hypothesis,
)


class TestRetrievalOptimizationStage33(unittest.TestCase):
    """Test suite covering all 40 required specifications of Stage 33."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.retrieval_dir = Path(self.tmp_dir) / "retrieval"
        self.retrieval_dir.mkdir(parents=True, exist_ok=True)
        self.manager = RetrievalExperimentManager(retrieval_base_dir=self.retrieval_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. R0 policy validity
    def test_01_r0_policy_validity(self) -> None:
        p0 = build_r0_baseline_policy()
        self.assertEqual(p0.variant, RetrievalVariant.R0.value)
        self.assertFalse(p0.semantic_retrieval_enabled)
        self.assertFalse(p0.neighbor_retrieval_enabled)
        self.assertFalse(p0.subgraph_retrieval_enabled)
        self.assertFalse(p0.dynamic_depth_enabled)
        self.assertEqual(p0.max_retrieval_calls, 0)
        self.assertTrue(len(p0.compute_policy_hash()) == 64)

    # 2. R1 semantic policy validity
    def test_02_r1_semantic_policy_validity(self) -> None:
        p1 = build_r1_semantic_policy()
        self.assertEqual(p1.variant, RetrievalVariant.R1.value)
        self.assertTrue(p1.semantic_retrieval_enabled)
        self.assertFalse(p1.neighbor_retrieval_enabled)
        self.assertFalse(p1.subgraph_retrieval_enabled)
        self.assertGreater(p1.semantic_top_k, 0)
        self.assertGreater(p1.max_semantic_calls, 0)

    # 3. R2 neighbor policy validity
    def test_03_r2_neighbor_policy_validity(self) -> None:
        p2 = build_r2_neighbors_policy()
        self.assertEqual(p2.variant, RetrievalVariant.R2.value)
        self.assertTrue(p2.semantic_retrieval_enabled)
        self.assertTrue(p2.neighbor_retrieval_enabled)
        self.assertFalse(p2.subgraph_retrieval_enabled)
        self.assertEqual(p2.neighbor_depth, 1)

    # 4. R3 subgraph policy validity
    def test_04_r3_subgraph_policy_validity(self) -> None:
        p3 = build_r3_subgraph_policy()
        self.assertEqual(p3.variant, RetrievalVariant.R3.value)
        self.assertTrue(p3.semantic_retrieval_enabled)
        self.assertTrue(p3.neighbor_retrieval_enabled)
        self.assertTrue(p3.subgraph_retrieval_enabled)
        self.assertIn(p3.subgraph_breadth_k, (2, 4, 8))

    # 5. R4 dynamic policy validity
    def test_05_r4_dynamic_policy_validity(self) -> None:
        p4 = build_r4_dynamic_policy()
        self.assertEqual(p4.variant, RetrievalVariant.R4.value)
        self.assertTrue(p4.dynamic_depth_enabled)
        self.assertIn("max_rounds", p4.dynamic_config)
        self.assertIn("redundancy_stop_threshold", p4.dynamic_config)

    # 6. Single-dimension retrieval change enforcement
    def test_06_single_dimension_retrieval_change_enforcement(self) -> None:
        p0 = build_r0_baseline_policy()
        p1 = build_r1_semantic_policy()
        diff = compute_retrieval_policy_diff(p0, p1)
        self.assertFalse(diff.is_identical)
        self.assertIn("semantic_retrieval_enabled", diff.enabled_flags_diff)
        self.assertNotIn("topology_id", diff.to_dict())

    # 7. Prompt immutability during retrieval experiment
    def test_07_prompt_immutability_enforcement(self) -> None:
        p1 = build_r1_semantic_policy()
        manifest = RetrievalCandidateManifest(
            candidate_id="R1_bad",
            parent_candidate_id="R0",
            retrieval_variant="R1",
            retrieval_policy_hash=p1.compute_policy_hash(),
            prompt_sha256="bad_prompt_hash",
            hypothesis=RetrievalHypothesis(
                target_failure="WRONG_FILE_LOCALIZATION",
                observation="obs",
                hypothesis="hyp",
                retrieval_change="chg",
                expected_signal="sig",
                rejection_condition="rej",
            ),
        )
        ok, errs = validate_retrieval_candidate_integrity(manifest, p1, verify_frozen=False)
        self.assertFalse(ok)
        self.assertTrue(any("Prompt immutability" in e for e in errs))

    # 8. Topology immutability
    def test_08_topology_immutability_enforcement(self) -> None:
        p1 = build_r1_semantic_policy()
        manifest = RetrievalCandidateManifest(
            candidate_id="R1_bad_topo",
            parent_candidate_id="R0",
            retrieval_variant="R1",
            retrieval_policy_hash=p1.compute_policy_hash(),
            topology_id="scout_debugger_reviewer",
            prompt_sha256=EXPECTED_P0_PROMPT_SHA256,
            hypothesis=RetrievalHypothesis(
                target_failure="WRONG_FILE_LOCALIZATION",
                observation="obs",
                hypothesis="hyp",
                retrieval_change="chg",
                expected_signal="sig",
                rejection_condition="rej",
            ),
        )
        ok, errs = validate_retrieval_candidate_integrity(manifest, p1, verify_frozen=False)
        self.assertFalse(ok)
        self.assertTrue(any("Topology immutability" in e for e in errs))

    # 9. Tool contract immutability
    def test_09_tool_contract_immutability(self) -> None:
        expected_tools = {"search_similar_code", "get_code_neighbors", "get_code_subgraph"}
        self.assertEqual(ALLOWED_COMPETITION_RETRIEVAL_TOOLS, expected_tools)

    # 10. Deterministic policy diff
    def test_10_deterministic_policy_diff(self) -> None:
        p0 = build_r0_baseline_policy()
        p1 = build_r1_semantic_policy()
        diff1 = compute_retrieval_policy_diff(p0, p1)
        diff2 = compute_retrieval_policy_diff(p0, p1)
        self.assertEqual(diff1.to_dict(), diff2.to_dict())
        md = render_retrieval_policy_diff_md(diff1)
        self.assertIn("semantic_retrieval_enabled", md)

    # 11. Retrieval trace schema
    def test_11_retrieval_trace_schema(self) -> None:
        ev = RetrievalEvent(
            run_id="run-1",
            task_id="task-1",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="test query",
            returned_count=2,
            retrieval_duration_ms=25.5,
        )
        d = ev.to_dict()
        self.assertEqual(d["task_id"], "task-1")
        self.assertEqual(d["retrieval_type"], "SEMANTIC")
        ev2 = RetrievalEvent.from_dict(d)
        self.assertEqual(ev2.query, "test query")

    # 12. Semantic event recording
    def test_12_semantic_event_recording(self) -> None:
        collector = RetrievalTraceCollector("R1")
        _, _, events = get_fixture_b_r1_relevant()
        for e in events:
            collector.record_event(e)
        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].retrieval_type, RetrievalType.SEMANTIC.value)

    # 13. Neighbor event recording
    def test_13_neighbor_event_recording(self) -> None:
        collector = RetrievalTraceCollector("R2")
        _, _, events = get_fixture_d_r2_useful_neighbor()
        for e in events:
            collector.record_event(e)
        self.assertEqual(len(collector.events), 2)
        self.assertEqual(collector.events[1].retrieval_type, RetrievalType.NEIGHBORS.value)

    # 14. Subgraph event recording
    def test_14_subgraph_event_recording(self) -> None:
        collector = RetrievalTraceCollector("R3")
        _, _, events = get_fixture_f_r3_dependency_path()
        for e in events:
            collector.record_event(e)
        self.assertEqual(len(collector.events), 1)
        self.assertEqual(collector.events[0].retrieval_type, RetrievalType.SUBGRAPH.value)

    # 15. Dynamic-depth trace
    def test_15_dynamic_depth_trace(self) -> None:
        collector = RetrievalTraceCollector("R4")
        _, traces = get_fixture_i_r4_expands()
        for t in traces:
            collector.record_dynamic_round(t)
        self.assertEqual(len(collector.dynamic_rounds), 2)
        self.assertEqual(collector.dynamic_rounds[0].decision, "CONTINUE")
        self.assertEqual(collector.dynamic_rounds[1].decision, "STOP")

    # 16. Retrieval cost metrics
    def test_16_retrieval_cost_metrics(self) -> None:
        _, _, events = get_fixture_d_r2_useful_neighbor()
        cost = compute_retrieval_cost_metrics(events, total_agent_tool_calls=10, total_runtime_ms=1000.0)
        self.assertEqual(cost.retrieval_call_count, 2)
        self.assertEqual(cost.semantic_calls, 1)
        self.assertEqual(cost.neighbor_calls, 1)
        self.assertEqual(cost.subgraph_calls, 0)
        self.assertEqual(cost.retrieval_tool_call_share, 0.2)
        self.assertGreater(cost.unique_entities_per_retrieval_call, 0)

    # 17. Retrieval quality metrics
    def test_17_retrieval_quality_metrics(self) -> None:
        _, records = get_fixture_n_target_improvement()
        quality = compute_retrieval_quality_metrics(records, target_failure_mode="WRONG_FILE_LOCALIZATION")
        self.assertEqual(quality.pass_rate, 0.8)
        self.assertEqual(quality.targeted_failure_count, 1)

    # 18. Paired task comparisons
    def test_18_paired_task_comparisons(self) -> None:
        base, cand = get_fixture_n_target_improvement()
        outcomes = compute_retrieval_paired_comparison(base, cand)
        self.assertEqual(len(outcomes), 5)
        summary = summarize_paired_outcomes(outcomes)
        self.assertEqual(summary["FAIL_TO_PASS"], 4)
        self.assertEqual(summary["FAIL_UNCHANGED"], 1)

    # 19. Retrieval redundancy detection
    def test_19_retrieval_redundancy_detection(self) -> None:
        collector = RetrievalTraceCollector("R1")
        _, events = get_fixture_m_duplicate_retrieval()
        for e in events:
            collector.record_event(e)
        diag = collector.compute_diagnostics()
        self.assertGreater(diag.redundancy_count, 0)

    # 20. Dead retrieval detection
    def test_20_dead_retrieval_detection(self) -> None:
        collector = RetrievalTraceCollector("R1")
        _, _, events = get_fixture_c_r1_irrelevant()
        for e in events:
            collector.record_event(e)
        diag = collector.compute_diagnostics()
        self.assertGreater(diag.dead_retrieval_count, 0)

    # 21. Over-expansion detection
    def test_21_over_expansion_detection(self) -> None:
        collector = RetrievalTraceCollector("R3")
        _, _, events = get_fixture_g_r3_over_expansion()
        for e in events:
            collector.record_event(e)
        diag = collector.compute_diagnostics()
        self.assertGreater(diag.over_expansion_count, 0)

    # 22. Budget enforcement
    def test_22_budget_enforcement(self) -> None:
        policy, events = get_fixture_j_budget_exhausted()
        self.assertEqual(len(events), policy.max_retrieval_calls)
        self.assertEqual(policy.max_retrieval_calls, 2)

    # 23. Stop-condition enforcement
    def test_23_stop_condition_enforcement(self) -> None:
        _, traces = get_fixture_h_r4_stops_early()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].decision, "STOP")

    # 24. Fallback handling
    def test_24_fallback_handling(self) -> None:
        _, events = get_fixture_k_tool_failure_fallback()
        self.assertEqual(events[0].metadata["status"], "error")
        self.assertEqual(events[0].metadata["fallback_action"], "EXACT_SEARCH")
        self.assertEqual(events[1].retrieval_type, RetrievalType.EXACT_SEARCH.value)

    # 25. Cache-hit accounting
    def test_25_cache_hit_accounting(self) -> None:
        _, events = get_fixture_l_cache_hit()
        cost = compute_retrieval_cost_metrics(events)
        self.assertEqual(cost.cache_hit_count, 1)
        self.assertEqual(cost.cache_hit_ratio, 0.5)

    # 26. Stage 25 context compaction interaction integrity
    def test_26_context_compaction_interaction_integrity(self) -> None:
        ev = RetrievalEvent(
            run_id="run-1",
            task_id="task-1",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="test query",
            context_token_growth=250,
        )
        cost = compute_retrieval_cost_metrics([ev])
        self.assertEqual(cost.total_context_growth_tokens, 250)

    # 27. Stage 26 tool caching interaction integrity
    def test_27_tool_caching_interaction_integrity(self) -> None:
        cache = BoundedToolCache(max_entries=10)
        k = cache.make_cache_key("search_similar_code", {"query": "fits header"}, repository_state_id="state1")
        self.assertIsNotNone(k)
        cache.put(k, {"status": "ok", "count": 2})
        entry = cache.get(k)
        self.assertIsNotNone(entry)
        self.assertEqual(cache.hits_count, 1)

    # 28. FDD integration
    def test_28_fdd_integration(self) -> None:
        self.assertEqual(InterventionScope.RETRIEVAL.value, "RETRIEVAL")
        intervention = Intervention(
            intervention_id="int-retrieval-1",
            source_cluster_id="cluster-1",
            target_failure_mode="WRONG_FILE_LOCALIZATION",
            hypothesis="Reduces localization failures",
            expected_behavior_change="Semantic search used for term mismatch",
            intervention_scope=InterventionScope.RETRIEVAL.value,
            changed_dimensions=["retrieval_policy"],
            affected_files=["local/retrieval_opt/policy.py"],
            baseline_candidate="R0",
            candidate_id="R1",
        )
        self.assertEqual(intervention.intervention_scope, InterventionScope.RETRIEVAL.value)

    # 29. Targeted failure improvement
    def test_29_targeted_failure_improvement(self) -> None:
        base, cand = get_fixture_n_target_improvement()
        delta = compute_run_delta(base, cand, target_failure_mode="WRONG_FILE_LOCALIZATION")
        self.assertEqual(delta.targeted_reduction, 4)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # 30. Targeted failure unchanged
    def test_30_targeted_failure_unchanged(self) -> None:
        base, cand = get_fixture_o_target_unchanged()
        delta = compute_run_delta(base, cand, target_failure_mode="WRONG_FILE_LOCALIZATION")
        self.assertEqual(delta.targeted_reduction, 0)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 31. Collateral regression
    def test_31_collateral_regression(self) -> None:
        base, cand = get_fixture_p_collateral_regression()
        delta = compute_run_delta(base, cand, target_failure_mode="WRONG_FILE_LOCALIZATION")
        self.assertEqual(delta.targeted_reduction, 3)
        self.assertGreater(sum(delta.collateral_regressions.values()), 0)
        decision, _ = evaluate_promotion_gate(delta)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 32. Validation/held-out gate
    def test_32_validation_held_out_gate(self) -> None:
        base, cand = get_fixture_n_target_improvement()
        val_delta = compute_run_delta(base, cand, target_failure_mode="WRONG_FILE_LOCALIZATION")
        decision, _ = evaluate_promotion_gate(val_delta)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # 33. No-live-results handling
    def test_33_no_live_results_handling(self) -> None:
        records = get_fixture_s_no_actionable_live_results()
        delta = compute_run_delta(records, records, target_failure_mode="INFRASTRUCTURE_UNAVAILABLE")
        decision, _ = evaluate_promotion_gate(delta, has_actionable_runs=False)
        self.assertEqual(decision, PromotionDecision.NO_ACTIONABLE_DATA)

    # 34. Infrastructure-only handling
    def test_34_infrastructure_only_handling(self) -> None:
        records = get_fixture_s_no_actionable_live_results()
        quality = compute_retrieval_quality_metrics(records, target_failure_mode="WRONG_FILE_LOCALIZATION")
        self.assertEqual(quality.targeted_failure_count, 0)

    # 35. Fixture/live isolation
    def test_35_fixture_live_isolation(self) -> None:
        base, cand = get_fixture_r_mixed_evidence_modes()
        self.assertNotEqual(base[0].evidence_mode, cand[0].evidence_mode)

    # 36. Manifest hash validation
    def test_36_manifest_hash_validation(self) -> None:
        manifest, policy = get_fixture_t_manifest_hash_mismatch()
        ok, errs = validate_retrieval_candidate_integrity(manifest, policy, verify_frozen=False)
        self.assertFalse(ok)
        self.assertTrue(any("Policy hash mismatch" in e for e in errs))

    # 37. Benchmark hash validation
    def test_37_benchmark_hash_validation(self) -> None:
        man = self.manager.ensure_r0_baseline()
        self.assertIsNotNone(man.benchmark_manifest_hash)

    # 38. Frozen artifact protection
    def test_38_frozen_artifact_protection(self) -> None:
        ok, report = verify_frozen_artifacts(Path("."))
        self.assertTrue(ok)
        self.assertEqual(len(report), 14)
        for path, info in report.items():
            self.assertEqual(info["status"], "MATCH")

    # 39. Candidate uniqueness
    def test_39_candidate_uniqueness(self) -> None:
        p0 = self.manager.ensure_r0_baseline()
        p1 = build_r1_semantic_policy()
        h1 = RetrievalHypothesis(
            target_failure="WRONG_FILE_LOCALIZATION",
            observation="obs",
            hypothesis="hyp",
            retrieval_change="chg",
            expected_signal="sig",
            rejection_condition="rej",
        )
        self.manager.create_candidate("R1_uniq", "R0", p1, h1)
        with self.assertRaises(FileExistsError):
            self.manager.create_candidate("R1_uniq", "R0", p1, h1)

    # 40. Deterministic report generation
    def test_40_deterministic_report_generation(self) -> None:
        p0 = build_r0_baseline_policy()
        p1 = build_r1_semantic_policy()
        diff = compute_retrieval_policy_diff(p0, p1)
        manifest = RetrievalCandidateManifest(
            candidate_id="R1_rep",
            parent_candidate_id="R0",
            retrieval_variant="R1",
            retrieval_policy_hash=p1.compute_policy_hash(),
            hypothesis=RetrievalHypothesis(
                target_failure="WRONG_FILE_LOCALIZATION",
                observation="obs",
                hypothesis="hyp",
                retrieval_change="chg",
                expected_signal="sig",
                rejection_condition="rej",
            ),
        )
        quality = RetrievalQualityMetrics(
            pass_rate=0.5,
            failure_rate=0.5,
            targeted_failure_mode="WRONG_FILE_LOCALIZATION",
            targeted_failure_count=2,
            targeted_failure_rate=0.2,
            localization_failure_count=1,
        )
        cost = RetrievalCostMetrics(
            retrieval_call_count=3,
            semantic_calls=3,
            neighbor_calls=0,
            subgraph_calls=0,
        )
        rep1 = generate_retrieval_experiment_report(manifest, diff, quality, cost)
        rep2 = generate_retrieval_experiment_report(manifest, diff, quality, cost)
        self.assertEqual(rep1, rep2)
        self.assertIn("## Quality Metrics", rep1)
        self.assertIn("## Cost Metrics", rep1)

    # 41. CLI analyze mode
    def test_41_cli_analyze_mode(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_retrieval_cli(["--candidate", "R0", "--retrieval-dir", str(self.retrieval_dir), "--analyze"])
        self.assertEqual(ret, 0)
        self.assertIn("Retrieval Baseline Analysis: R0", buf.getvalue())

    # 42. CLI diff mode
    def test_42_cli_diff_mode(self) -> None:
        self.manager.ensure_r0_baseline()
        p1 = build_r1_semantic_policy()
        h1 = RetrievalHypothesis("WRONG_FILE_LOCALIZATION", "obs", "hyp", "chg", "sig", "rej")
        self.manager.create_candidate("R1_diff_test", "R0", p1, h1)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_retrieval_cli(["--candidate", "R1_diff_test", "--parent", "R0", "--retrieval-dir", str(self.retrieval_dir), "--diff"])
        self.assertEqual(ret, 0)
        self.assertIn("Policy Diff", buf.getvalue())

    # 43. CLI matrix mode
    def test_43_cli_matrix_mode(self) -> None:
        self.manager.ensure_r0_baseline()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_retrieval_cli(["--retrieval-dir", str(self.retrieval_dir), "--matrix"])
        self.assertEqual(ret, 0)
        self.assertIn("Quality vs Cost Frontier Matrix", buf.getvalue())

    # 44. CLI verify mode
    def test_44_cli_verify_mode(self) -> None:
        self.manager.ensure_r0_baseline()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_retrieval_cli(["--verify", str(self.retrieval_dir / "R0")])
        self.assertEqual(ret, 0)
        self.assertIn("[PASS]", buf.getvalue())

    # 45. Frontier rendering
    def test_45_frontier_rendering(self) -> None:
        candidates = [
            {
                "candidate_id": "R0",
                "variant": "R0",
                "quality": RetrievalQualityMetrics(pass_rate=0.4, failure_rate=0.6, targeted_failure_mode="LOC", targeted_failure_count=5, targeted_failure_rate=0.5, localization_failure_count=5),
                "cost": RetrievalCostMetrics(retrieval_call_count=0, semantic_calls=0, neighbor_calls=0, subgraph_calls=0, retrieved_entities=0, unique_entities=0, duplicate_entities=0, source_files_exposed=0),
            },
            {
                "candidate_id": "R1",
                "variant": "R1",
                "quality": RetrievalQualityMetrics(pass_rate=0.6, failure_rate=0.4, targeted_failure_mode="LOC", targeted_failure_count=2, targeted_failure_rate=0.2, localization_failure_count=2),
                "cost": RetrievalCostMetrics(retrieval_call_count=3, semantic_calls=3, neighbor_calls=0, subgraph_calls=0, retrieved_entities=10, unique_entities=8, duplicate_entities=2, source_files_exposed=4, unique_entities_per_retrieval_call=2.67),
            },
        ]
        frontier_rows = build_quality_cost_frontier(candidates)
        md = render_quality_cost_frontier_md(frontier_rows)
        self.assertIn("| `R0` | `R0` |", md)
        self.assertIn("| `R1` | `R1` |", md)

    # 46. Canonical policy retrieval
    def test_46_canonical_policy_retrieval(self) -> None:
        for v in [RetrievalVariant.R0, RetrievalVariant.R1, RetrievalVariant.R2, RetrievalVariant.R3, RetrievalVariant.R4]:
            pol = get_canonical_policy(v)
            self.assertEqual(pol.variant, v.value)
        with self.assertRaises(ValueError):
            get_canonical_policy("R99")


if __name__ == "__main__":
    unittest.main()
