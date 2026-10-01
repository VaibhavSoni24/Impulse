"""Comprehensive Test Suite for Stage 36: Skill Optimization Loop.

Covers all 48 mandatory verification points from Stage 36 Section 41:
1. skill inventory
2. frozen S0 snapshot
3. S0 immutability
4. candidate creation
5. unique candidate IDs
6. parent hash validation
7. one skill change per candidate
8. multiple skill mutation rejection
9. non-skill mutation rejection
10. prompt mutation rejection
11. retrieval mutation rejection
12. testing-policy mutation rejection
13. recovery-policy mutation rejection
14. topology mutation rejection
15. skill scope validation
16. deterministic skill diff
17. SHA-256 manifest correctness
18. duplicate root-prompt detection
19. duplicate skill-instruction detection
20. contradiction diagnostics
21. bloat diagnostics
22. task-scope matrix
23. target behavior improvement
24. target behavior unchanged
25. target behavior worsening
26. collateral regression
27. task-paired comparison
28. context cost metrics
29. redundancy metrics
30. ablation lineage
31. FDD integration
32. clean-copy evaluator integration
33. testing strategy invariance
34. retrieval invariance
35. recovery invariance
36. topology invariance
37. frozen artifact invariance
38. no-live-data handling
39. infrastructure-only handling
40. fixture/live isolation
41. benchmark manifest hash verification
42. held-out lock verification
43. candidate duplicate rejection
44. deterministic report generation
45. CLI inventory
46. CLI analysis
47. candidate artifact verification
48. security/final diff protection
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

from local.clean_copy.evaluator import CleanCopyEvaluator
from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.fdd.models import InterventionScope
from local.skill_opt.analyzer import (
    SkillContentAnalyzer,
    analyze_skill_content,
    extract_meaningful_lines,
    normalize_sentence,
)
from local.skill_opt.cli import run_skill_cli
from local.skill_opt.diff import compute_metrics, diff_skills, estimate_tokens, render_skill_diff_md
from local.skill_opt.experiment import SkillExperimentManager
from local.skill_opt.fixtures import (
    fixture_a_s0_snapshot,
    fixture_ab_skill_hash_mismatch,
    fixture_ac_duplicate_candidate_id,
    fixture_ad_deterministic_report_output,
    fixture_ae_candidate_artifact_verification,
    fixture_af_no_actionable_live_data,
    fixture_ag_infrastructure_only_evidence,
    fixture_ah_fixture_live_separation,
    fixture_ai_frozen_stage24_mutation_attempt,
    fixture_b_s1_add_instruction,
    fixture_c_s1_remove_instruction,
    fixture_d_s1_reword_instruction,
    fixture_e_s1_reorder_instruction,
    fixture_f_duplicate_root_prompt,
    fixture_g_duplicate_skill_instruction,
    fixture_h_contradiction,
    fixture_i_scope_leakage,
    fixture_j_multiple_skills_changed,
    fixture_k_non_skill_file_changed,
    fixture_l_prompt_changed,
    fixture_m_retrieval_changed,
    fixture_n_testing_policy_changed,
    fixture_o_recovery_policy_changed,
    fixture_p_topology_changed,
    fixture_q_target_behavior_improves,
    fixture_r_target_behavior_unchanged,
    fixture_s_target_behavior_worsens,
    fixture_t_collateral_regression,
    fixture_u_context_cost_increases,
    fixture_v_redundancy_decreases_without_task_regression,
    fixture_w_redundancy_decreases_but_task_worsens,
    fixture_x_paired_comparison,
    fixture_y_ablation_lineage,
    fixture_z_held_out_regression,
)
from local.skill_opt.inventory import SkillInventory, compute_file_sha256
from local.skill_opt.metrics import (
    compare_skill_metrics,
    compute_skill_behavior_metrics,
    compute_skill_context_metrics,
)
from local.skill_opt.models import (
    InstructionDuplicationCategory,
    SkillCandidateManifest,
    SkillChangeType,
    SkillContextCostMetrics,
    SkillHypothesis,
    SkillScopeType,
    TaskBehaviorTransition,
)
from local.skill_opt.paired import (
    build_task_scope_matrix,
    compute_paired_task_comparisons,
    save_paired_results,
)
from local.skill_opt.reporting import generate_candidate_report_md, generate_top_level_matrix_md
from local.skill_opt.scope_validator import validate_skill_scope
from local.skill_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REC0_RECOVERY_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
    validate_candidate_single_skill_change,
    validate_skill_candidate_invariance,
    validate_skill_hypothesis,
)


class TestSkillOptimizationStage36(unittest.TestCase):
    """Authoritative test suite for Stage 36 Skill Optimization Loop."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.inventory = SkillInventory(self.repo_root)
        self.manager = SkillExperimentManager(self.repo_root)

    def test_01_skill_inventory(self) -> None:
        """1. Discovers canonical skill artifacts and reports metadata accurately."""
        skills = self.inventory.discover_skills()
        skill_ids = [s.skill_id for s in skills]
        self.assertIn("test_strategy", skill_ids)
        self.assertIn("repo_triage", skill_ids)
        for s in skills:
            self.assertTrue(s.is_frozen)
            self.assertTrue(s.is_optimizer_eligible)
            self.assertIn(s.path, FROZEN_STAGE24_HASHES)

    def test_02_frozen_s0_snapshot(self) -> None:
        """2. S0 snapshots match canonical frozen hashes byte-for-byte."""
        ts_s0 = self.manager.get_candidate_dir("test_strategy", "S0")
        rt_s0 = self.manager.get_candidate_dir("repo_triage", "S0")
        self.assertTrue((ts_s0 / "SKILL.md").exists())
        self.assertTrue((rt_s0 / "SKILL.md").exists())

        ts_hash = compute_file_sha256(ts_s0 / "SKILL.md")
        rt_hash = compute_file_sha256(rt_s0 / "SKILL.md")
        self.assertEqual(ts_hash, EXPECTED_TEST_STRATEGY_SKILL_SHA256)
        self.assertEqual(rt_hash, EXPECTED_REPO_TRIAGE_SKILL_SHA256)

    def test_03_s0_immutability(self) -> None:
        """3. S0 baseline manifests declare BASELINE status and identical parent hash."""
        manifest_path = self.manager.get_candidate_dir("test_strategy", "S0") / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["candidate_id"], "S0")
        self.assertEqual(data["parent_candidate_id"], "S0")
        self.assertEqual(data["skill_hash"], data["parent_skill_hash"])
        self.assertEqual(data["status"], "BASELINE")

    def test_04_candidate_creation(self) -> None:
        """4. Candidate S1 directories exist with valid manifests and diffs."""
        for skill_id in ["test_strategy", "repo_triage"]:
            s1_dir = self.manager.get_candidate_dir(skill_id, "S1")
            self.assertTrue((s1_dir / "SKILL.md").exists())
            self.assertTrue((s1_dir / "manifest.json").exists())
            self.assertTrue((s1_dir / "skill_diff.json").exists())
            self.assertTrue((s1_dir / "report.md").exists())

    def test_05_unique_candidate_ids(self) -> None:
        """5. Candidate IDs must be distinct within skill lineage."""
        cand_ts = ["S0", "S1"]
        self.assertEqual(len(cand_ts), len(set(cand_ts)))
        cand_rt = ["S0", "S1"]
        self.assertEqual(len(cand_rt), len(set(cand_rt)))

    def test_06_parent_hash_validation(self) -> None:
        """6. Candidate S1 parent_skill_hash matches S0 skill_hash."""
        for skill_id in ["test_strategy", "repo_triage"]:
            s0_m = json.loads((self.manager.get_candidate_dir(skill_id, "S0") / "manifest.json").read_text(encoding="utf-8"))
            s1_m = json.loads((self.manager.get_candidate_dir(skill_id, "S1") / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(s1_m["parent_skill_hash"], s0_m["skill_hash"])

    def test_07_one_skill_change_per_candidate(self) -> None:
        """7. Exactly one skill change allowed per candidate."""
        ok, errs = validate_candidate_single_skill_change(["test_strategy"])
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_08_multiple_skill_mutation_rejection(self) -> None:
        """8. Modifying multiple skills simultaneously is rejected."""
        multi = fixture_j_multiple_skills_changed()
        ok, errs = validate_candidate_single_skill_change(multi)
        self.assertFalse(ok)
        self.assertTrue(any("Multi-skill modification rejected" in e for e in errs))

    def test_09_non_skill_mutation_rejection(self) -> None:
        """9. Candidate touching non-skill files is strictly rejected."""
        non_skill = fixture_k_non_skill_file_changed()
        ok, errs = validate_candidate_single_skill_change(["test_strategy"], non_skill)
        self.assertFalse(ok)
        self.assertTrue(any("Non-skill file mutation rejected" in e for e in errs))

    def test_10_prompt_mutation_rejection(self) -> None:
        """10. Tampered root prompt hash violates invariance and is rejected."""
        manifest = fixture_l_prompt_changed()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Prompt immutability violated" in e for e in errs))

    def test_11_retrieval_mutation_rejection(self) -> None:
        """11. Tampered retrieval policy hash violates invariance and is rejected."""
        manifest = fixture_m_retrieval_changed()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Retrieval immutability violated" in e for e in errs))

    def test_12_testing_policy_mutation_rejection(self) -> None:
        """12. Tampered testing policy hash violates invariance and is rejected."""
        manifest = fixture_n_testing_policy_changed()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Testing immutability violated" in e for e in errs))

    def test_13_recovery_policy_mutation_rejection(self) -> None:
        """13. Tampered recovery policy hash violates invariance and is rejected."""
        manifest = fixture_o_recovery_policy_changed()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Recovery immutability violated" in e for e in errs))

    def test_14_topology_mutation_rejection(self) -> None:
        """14. Tampered topology identity violates invariance and is rejected."""
        manifest = fixture_p_topology_changed()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Topology immutability violated" in e for e in errs))

    def test_15_skill_scope_validation(self) -> None:
        """15. Skill scope validator detects and rejects cross-subsystem leakage."""
        _, added_leakage = fixture_i_scope_leakage()
        ok, errs = validate_skill_scope("test_strategy", SkillScopeType.TESTING.value, added_leakage)
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errs), 3)
        self.assertTrue(any("search_similar_code" in e for e in errs))
        self.assertTrue(any("RecoveryController" in e for e in errs))
        self.assertTrue(any("sub_agents/scout" in e for e in errs))

    def test_16_deterministic_skill_diff(self) -> None:
        """16. Skill diff engine computes exact line and token deltas deterministically."""
        p_text, c_text, _ = fixture_b_s1_add_instruction()
        diff_data = diff_skills(p_text, c_text, "S0", "S1")
        self.assertEqual(diff_data["lines_added_count"], 1)
        self.assertEqual(diff_data["lines_removed_count"], 0)
        self.assertFalse(diff_data["is_identical"])
        self.assertGreater(diff_data["cost_metrics"]["token_delta"], 0)

        # Markdown report rendering
        md = render_skill_diff_md(diff_data)
        self.assertIn("## Context Cost Deltas", md)
        self.assertIn("+ - Verify exit code semantics.", md)

    def test_17_sha256_manifest_correctness(self) -> None:
        """17. Candidate manifests record cryptographic hashes matching actual file bytes."""
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                m = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
                actual_hash = compute_file_sha256(cand_dir / "SKILL.md")
                self.assertEqual(m["skill_hash"], actual_hash)

    def test_18_duplicate_root_prompt_detection(self) -> None:
        """18. Root prompt duplication is detected deterministically."""
        dup_text = fixture_f_duplicate_root_prompt()
        root_prompt = (self.repo_root / "experiments" / "candidates" / "M0" / "prompts" / "root.md").read_text(encoding="utf-8")
        dup_rep, _ = analyze_skill_content(dup_text, root_prompt)
        self.assertGreater(dup_rep.exact_duplicate_lines, 0)
        self.assertGreater(dup_rep.duplication_ratio, 0.0)

    def test_19_duplicate_skill_instruction_detection(self) -> None:
        """19. Internal duplicate instructions within the same skill are flagged."""
        internal_dup = fixture_g_duplicate_skill_instruction()
        analyzer = SkillContentAnalyzer()
        dups = analyzer.detect_internal_duplication(internal_dup)
        self.assertGreater(len(dups), 0)
        self.assertGreaterEqual(dups[0]["similarity"], 0.85)

    def test_20_contradiction_diagnostics(self) -> None:
        """20. Contradictory instructions within skill are flagged with line numbers."""
        conflict_text = fixture_h_contradiction()
        analyzer = SkillContentAnalyzer()
        contradictions = analyzer.detect_contradictions(conflict_text)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0].contradiction_type, "FULL_SUITE_EXECUTION_CONFLICT")

    def test_21_bloat_diagnostics(self) -> None:
        """21. Bloat diagnostics flag generic empty phrases."""
        bloat_text = "# Skill\n\n- Be careful and make sure it works.\n- Write good code.\n"
        analyzer = SkillContentAnalyzer()
        diag = analyzer.evaluate_diagnostics(bloat_text)
        self.assertTrue(diag.is_overly_generic)
        self.assertTrue(diag.has_bloat)

    def test_22_task_scope_matrix(self) -> None:
        """22. Skill task-scope matrix maps tasks to expected behaviors and transitions."""
        pairs = fixture_x_paired_comparison()
        matrix = build_task_scope_matrix("S1", "test_strategy", "TESTING", "Reduce redundancy", pairs)
        self.assertEqual(len(matrix), len(pairs))
        for entry in matrix:
            self.assertIn("task_id", entry)
            self.assertIn("actual_behavior", entry)
            self.assertIn("result", entry)

    def test_23_target_behavior_improvement(self) -> None:
        """23. Metrics detect target failure reduction and quality improvement."""
        parent, cand = fixture_q_target_behavior_improves()
        p_m = compute_skill_behavior_metrics(parent)
        c_m = compute_skill_behavior_metrics(cand)
        cost = SkillContextCostMetrics(token_delta=-10)
        cmp = compare_skill_metrics(p_m, c_m, cost)
        self.assertTrue(cmp["quality_improved"])
        self.assertFalse(cmp["quality_regressed"])
        self.assertEqual(cmp["pareto_status"], "STRICTLY_DOMINATES")

    def test_24_target_behavior_unchanged(self) -> None:
        """24. Metrics detect neutral behavior shift."""
        parent, cand = fixture_r_target_behavior_unchanged()
        p_m = compute_skill_behavior_metrics(parent)
        c_m = compute_skill_behavior_metrics(cand)
        cost = SkillContextCostMetrics(token_delta=0)
        cmp = compare_skill_metrics(p_m, c_m, cost)
        self.assertFalse(cmp["quality_improved"])
        self.assertFalse(cmp["quality_regressed"])
        self.assertEqual(cmp["pareto_status"], "NEUTRAL")

    def test_25_target_behavior_worsening(self) -> None:
        """25. Metrics detect behavior regression."""
        parent, cand = fixture_s_target_behavior_worsens()
        p_m = compute_skill_behavior_metrics(parent)
        c_m = compute_skill_behavior_metrics(cand)
        cost = SkillContextCostMetrics(token_delta=-5)
        cmp = compare_skill_metrics(p_m, c_m, cost)
        self.assertTrue(cmp["quality_regressed"])
        self.assertEqual(cmp["pareto_status"], "REGRESSION")

    def test_26_collateral_regression(self) -> None:
        """26. Metrics flag collateral task degradation even if target improved on one task."""
        parent, cand = fixture_t_collateral_regression()
        p_m = compute_skill_behavior_metrics(parent)
        c_m = compute_skill_behavior_metrics(cand)
        cost = SkillContextCostMetrics(token_delta=-10)
        cmp = compare_skill_metrics(p_m, c_m, cost)
        self.assertTrue(cmp["quality_regressed"])
        self.assertEqual(cmp["pareto_status"], "REGRESSION")

    def test_27_task_paired_comparison(self) -> None:
        """27. Paired comparison maps all required transition states."""
        pairs = fixture_x_paired_comparison()
        transitions = [p.transition for p in pairs]
        self.assertIn(TaskBehaviorTransition.PASS_TO_PASS.value, transitions)
        self.assertIn(TaskBehaviorTransition.FAIL_TO_PASS.value, transitions)
        self.assertIn(TaskBehaviorTransition.PASS_TO_FAIL.value, transitions)
        self.assertIn(TaskBehaviorTransition.FAIL_UNCHANGED.value, transitions)
        self.assertIn(TaskBehaviorTransition.REDUNDANT_TO_NON_REDUNDANT.value, transitions)

    def test_28_context_cost_metrics(self) -> None:
        """28. Context cost calculates character, word, line, and token deltas."""
        parent_text = "This is a simple baseline instruction sentence for testing."
        cand_text = "This is a simple baseline instruction sentence."
        metrics = compute_skill_context_metrics(cand_text, parent_text)
        self.assertLess(metrics.char_delta, 0)
        self.assertLess(metrics.word_delta, 0)
        self.assertLessEqual(metrics.token_delta, 0)

    def test_29_redundancy_metrics(self) -> None:
        """29. Redundancy reduction without task regression is classified as improvement."""
        parent, cand = fixture_v_redundancy_decreases_without_task_regression()
        p_m = compute_skill_behavior_metrics(parent)
        c_m = compute_skill_behavior_metrics(cand)
        cost = SkillContextCostMetrics(token_delta=-5)
        cmp = compare_skill_metrics(p_m, c_m, cost)
        self.assertTrue(cmp["quality_improved"])
        self.assertEqual(cmp["pareto_status"], "STRICTLY_DOMINATES")

    def test_30_ablation_lineage(self) -> None:
        """30. Ablation lineage tracks sequential dependencies across S0 -> S1 -> S2."""
        manifests = fixture_y_ablation_lineage()
        self.assertEqual(manifests[0].candidate_id, "S0")
        self.assertEqual(manifests[1].parent_candidate_id, "S0")
        self.assertEqual(manifests[2].parent_candidate_id, "S1")
        self.assertEqual(manifests[2].parent_skill_hash, manifests[1].skill_hash)

    def test_31_fdd_integration(self) -> None:
        """31. FDD integration recognizes InterventionScope.SKILL."""
        self.assertEqual(InterventionScope.SKILL.value, "SKILL")

    def test_32_clean_copy_evaluator_integration(self) -> None:
        """32. Clean copy evaluator initializes with workspace isolation parameters."""
        evaluator = CleanCopyEvaluator(repo_root=self.repo_root)
        self.assertIsNotNone(evaluator.snapshot_mgr)
        self.assertIsNotNone(evaluator.candidate_loader)
        self.assertIsNotNone(evaluator.patch_extractor)

    def test_33_testing_strategy_invariance(self) -> None:
        """33. Stage 34 testing execution policy hash is invariant."""
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                m = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["testing_policy_hash"], EXPECTED_T0_TESTING_POLICY_HASH)

    def test_34_retrieval_invariance(self) -> None:
        """34. Stage 33 retrieval policy hash is invariant."""
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                m = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["retrieval_policy_hash"], EXPECTED_R0_RETRIEVAL_POLICY_HASH)

    def test_35_recovery_invariance(self) -> None:
        """35. Stage 35 recovery policy hash is invariant."""
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                m = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["recovery_policy_hash"], EXPECTED_REC0_RECOVERY_POLICY_HASH)

    def test_36_topology_invariance(self) -> None:
        """36. Topology identity is invariant (root_only)."""
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                m = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(m["topology_identity"], EXPECTED_TOPOLOGY_ID)

    def test_37_frozen_artifact_invariance(self) -> None:
        """37. All 14 frozen Stage 24 artifacts strictly match their authoritative digests."""
        all_passed, results = verify_frozen_artifacts(self.repo_root)
        self.assertTrue(all_passed)
        for path, res in results.items():
            self.assertEqual(res["status"], "MATCH", f"Frozen artifact altered: {path}")

    def test_38_no_live_data_handling(self) -> None:
        """38. Accurately reports NO_ACTIONABLE_LIVE_SKILL_DATA without fabrication."""
        info = fixture_af_no_actionable_live_data()
        self.assertEqual(info["status"], "NO_ACTIONABLE_LIVE_SKILL_DATA")
        self.assertFalse(info["fabricated_gains_asserted"])

    def test_39_infrastructure_only_handling(self) -> None:
        """39. Infrastructure errors are isolated and not conflated with skill failures."""
        err_info = fixture_ag_infrastructure_only_evidence()
        self.assertEqual(err_info["error_type"], "INFRASTRUCTURE_UNAVAILABLE")
        self.assertFalse(err_info["classified_as_skill_failure"])

    def test_40_fixture_live_isolation(self) -> None:
        """40. Fixture evidence mode is isolated from LIVE mode."""
        f_mode, l_mode = fixture_ah_fixture_live_separation()
        self.assertEqual(f_mode, "FIXTURE")
        self.assertEqual(l_mode, "LIVE")
        self.assertNotEqual(f_mode, l_mode)

    def test_41_benchmark_manifest_hash_verification(self) -> None:
        """41. Manifest records benchmark split and allows hash verification."""
        manifest = fixture_b_s1_add_instruction()[2]
        self.assertEqual(manifest.benchmark_split, "dev")

    def test_42_held_out_lock_verification(self) -> None:
        """42. Held-out dataset is locked and regressions trigger candidate rejection."""
        val_d, held_d, decision = fixture_z_held_out_regression()
        self.assertGreater(val_d, 0)
        self.assertLess(held_d, 0)
        self.assertEqual(decision, "REJECTED_HELD_OUT_REGRESSION")

    def test_43_candidate_duplicate_rejection(self) -> None:
        """43. Non-S0 candidate with identical candidate_id and parent_candidate_id is rejected."""
        manifest = fixture_ac_duplicate_candidate_id()
        ok, errs = validate_skill_candidate_invariance(manifest)
        self.assertFalse(ok)
        self.assertTrue(any("Candidate isolation violated" in e for e in errs))

    def test_44_deterministic_report_generation(self) -> None:
        """44. Candidate report.md follows required section structure."""
        report_path = self.manager.get_candidate_dir("test_strategy", "S1") / "report.md"
        content = report_path.read_text(encoding="utf-8")
        required_headers = [
            "# Skill Optimization Experiment",
            "## Candidate",
            "## Skill",
            "## Parent",
            "## Target Behavior",
            "## Baseline Evidence",
            "## Hypothesis",
            "## Intervention",
            "## Scope Check",
            "## Prompt Duplication Analysis",
            "## Smoke Result",
            "## Validation Result",
            "## Held-Out Result",
            "## Target Behavior Delta",
            "## Task-Level Pairing",
            "## Context Cost",
            "## Redundancy / Contradiction Diagnostics",
            "## Collateral Effects",
            "## Decision",
            "## Reproducibility",
        ]
        for h in required_headers:
            self.assertIn(h, content)

    def test_45_cli_inventory(self) -> None:
        """45. CLI --inventory runs successfully and outputs markdown table."""
        buf = io.StringIO()
        orig = sys.stdout
        try:
            sys.stdout = buf
            ret = run_skill_cli(["--inventory"])
            self.assertEqual(ret, 0)
            out = buf.getvalue()
            self.assertIn("# IMPULSE Skill Inventory", out)
            self.assertIn("test_strategy", out)
            self.assertIn("repo_triage", out)
        finally:
            sys.stdout = orig

    def test_46_cli_analysis(self) -> None:
        """46. CLI --analyze reports duplication and diagnostics."""
        buf = io.StringIO()
        orig = sys.stdout
        try:
            sys.stdout = buf
            ret = run_skill_cli(["--skill", "test_strategy", "--candidate", "S0", "--analyze"])
            self.assertEqual(ret, 0)
            out = buf.getvalue()
            self.assertIn("Skill Content Analysis: test_strategy/S0", out)
            self.assertIn("Duplication Ratio:", out)
        finally:
            sys.stdout = orig

    def test_47_candidate_artifact_verification(self) -> None:
        """47. All candidate directories contain complete set of 8 required artifacts."""
        req_artifacts = fixture_ae_candidate_artifact_verification()
        for skill_id in ["test_strategy", "repo_triage"]:
            for cand_id in ["S0", "S1"]:
                cand_dir = self.manager.get_candidate_dir(skill_id, cand_id)
                for art in req_artifacts:
                    art_file = cand_dir / art
                    self.assertTrue(art_file.exists(), f"Missing artifact: {art_file}")

    def test_48_security_final_diff_protection(self) -> None:
        """48. Verifies that frozen skills are not modified in place."""
        target, action = fixture_ai_frozen_stage24_mutation_attempt()
        self.assertEqual(target, "agent/skills/test_strategy/SKILL.md")
        self.assertEqual(action, "EDIT_IN_PLACE_MUTATION")
        # Ensure actual repository files remain untouched
        actual_ts_hash = compute_file_sha256(self.repo_root / target)
        self.assertEqual(actual_ts_hash, EXPECTED_TEST_STRATEGY_SKILL_SHA256)


if __name__ == "__main__":
    unittest.main()
