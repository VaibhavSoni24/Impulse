"""Focused unit and integration test suite for Stage 44 Candidate Promotion Gate.

Covers:
- Requirements A through Z from Stage 44 specification
- Negative validation checks and fail-closed promotion enforcement
- Non-collapsing decision logic (PROMOTE, REJECT, BLOCKED)
- Task-paired contingency tracking, held-out regression, runtime budgets
- Zero-bypass guarantees (--force rejection)
- Current-best pointer validation and append-only audit trail
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from local.promotion import (
    CurrentBestValidationResult,
    EvidenceMode,
    ForbiddenBypassError,
    GateDecision,
    GateDimensionStatus,
    MetricDirection,
    PromotionGate,
    PromotionGateFailureError,
    TaskPairOutcome,
    compare_held_out,
    compare_validation,
    evaluate_configuration,
    evaluate_promotion,
    evaluate_reproducibility,
    evaluate_runtime,
    promote_candidate,
    reject_candidate,
)
from local.promotion.errors import CandidateNotFoundError
from local.versioning.hashing import compute_canonical_dict_hash
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    CurrentBestPointer,
    PromotionStatus,
)
from local.versioning.registry import CandidateRegistry


class TestCandidatePromotionStage44(unittest.TestCase):
    """Authoritative test suite for Stage 44 Candidate Promotion Gate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)
        self.candidates_dir = self.root / "experiments" / "candidates"
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.registry = CandidateRegistry(candidates_dir=self.candidates_dir, repo_root=self.root)
        self.gate = PromotionGate(candidates_dir=self.candidates_dir, repo_root=self.root)

        # Create dummy baseline candidate B0
        self.b0_manifest = self._make_manifest(
            candidate_id="B0",
            primary_dimension="baseline",
            parent_id=None,
            prompt_hash="1111111111111111111111111111111111111111111111111111111111111111",
        )
        self.registry.register_candidate(self.b0_manifest, overwrite_finalized=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_manifest(
        self,
        candidate_id: str,
        primary_dimension: str = "prompt",
        parent_id: str | None = "B0",
        prompt_hash: str = "2222222222222222222222222222222222222222222222222222222222222222",
        experiment_type: str = "prompt_optimization",
        status: str = "VALIDATED",
        promotion_status: str = "NOT_PROMOTED",
        base_model: str = "gemma-4-31b-it-qat-w4a16-ct",
        adapter_id: str | None = None,
        git_commit: str = "abcdef0123456789abcdef0123456789abcdef01",
        evidence_mode: str = "LIVE",
    ) -> CandidateManifest:
        m = CandidateManifest(
            candidate_id=candidate_id,
            candidate_version="1.0.0",
            status=status,
            parent_candidate_id=parent_id,
            git_commit=git_commit,
            created_at="2026-10-02T10:00:00+00:00",
            description=f"Candidate {candidate_id} test manifest",
            experiment_type=experiment_type,
            primary_dimension=primary_dimension,
            change_summary={
                "primary_dimension": primary_dimension,
                "changed_components": [primary_dimension],
                "unchanged_components": ["retrieval"],
                "rationale": "Test candidate",
            },
            base_model=base_model,
            model_revision=None,
            root_prompt_hash=prompt_hash,
            skill_hashes={"repo_triage": "3333333333333333333333333333333333333333333333333333333333333333"},
            sub_agent_hashes={},
            tool_contract_hashes={"run_command": "4444444444444444444444444444444444444444444444444444444444444444"},
            retrieval_version="R0",
            testing_version="T0",
            recovery_version="REC0",
            topology="root_only",
            adapter_id=adapter_id,
            adapter_sha256=None,
            benchmark_manifest_hash="5555555555555555555555555555555555555555555555555555555555555555",
            dev_split_hash="6666666666666666666666666666666666666666666666666666666666666666",
            validation_split_hash="7777777777777777777777777777777777777777777777777777777777777777",
            held_out_split_hash="8888888888888888888888888888888888888888888888888888888888888888",
            runtime_settings={"timeout_seconds": 600},
            sampling_settings={"temperature": 0.2, "top_p": 0.95, "max_output_tokens": 16384},
            compute_environment_id="LOCAL_CPU",
            evidence_mode=evidence_mode,
            result_status="VALIDATED",
            promotion_status=promotion_status,
        )
        m.manifest_hash = compute_canonical_dict_hash(m.to_dict(), exclude_keys=["manifest_hash"])
        return m

    # A. Gate schema
    def test_A_gate_schema(self) -> None:
        rec = self.gate.evaluate("B0")
        d = rec.to_dict()
        required_keys = {
            "candidate_id", "baseline_candidate_id", "decision", "timestamp",
            "gate_version", "primary_metric", "validation_result", "held_out_result",
            "runtime_result", "configuration_result", "reproducibility_result",
            "overall_result", "evidence_mode", "reasons", "source_manifests", "source_hashes",
        }
        self.assertTrue(required_keys.issubset(d.keys()))
        json_str = json.dumps(d)
        self.assertIn("B0", json_str)

    # B. Validation comparison
    def test_B_validation_comparison(self) -> None:
        cand = self._make_manifest("C_test", parent_id="B0")
        base = self.b0_manifest
        b_runs = [{"task_id": "t1", "success": False, "split_name": "validation"}]
        c_runs = [{"task_id": "t1", "success": True, "split_name": "validation"}]
        res = compare_validation(cand, c_runs, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.PASS.value)
        self.assertGreater(res.delta, 0)

    # C. Task-paired comparison
    def test_C_task_paired_comparison(self) -> None:
        cand = self._make_manifest("C_test", parent_id="B0")
        base = self.b0_manifest
        b_runs = [
            {"task_id": "t1", "success": True, "split_name": "validation"},
            {"task_id": "t2", "success": False, "split_name": "validation"},
        ]
        c_runs = [
            {"task_id": "t1", "success": True, "split_name": "validation"},
            {"task_id": "t2", "success": True, "split_name": "validation"},
        ]
        res = compare_validation(cand, c_runs, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertIsNotNone(res.task_pairs)
        self.assertEqual(res.task_pairs.baseline_pass_candidate_pass, 1)
        self.assertEqual(res.task_pairs.baseline_fail_candidate_pass, 1)
        self.assertEqual(res.task_pairs.baseline_pass_candidate_fail, 0)

    # D. Held-out comparison
    def test_D_held_out_comparison(self) -> None:
        cand = self._make_manifest("C_test", parent_id="B0")
        base = self.b0_manifest
        b_runs = [{"task_id": "h1", "success": True, "split_name": "held_out"}]
        c_runs_pass = [{"task_id": "h1", "success": True, "split_name": "held_out"}]
        c_runs_fail = [{"task_id": "h1", "success": False, "split_name": "held_out"}]

        res_pass = compare_held_out(cand, c_runs_pass, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res_pass.dimension_status, GateDimensionStatus.PASS.value)
        self.assertEqual(res_pass.regression_count, 0)

        res_fail = compare_held_out(cand, c_runs_fail, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res_fail.dimension_status, GateDimensionStatus.FAIL.value)
        self.assertEqual(res_fail.regression_count, 1)

    # E. Runtime evaluation
    def test_E_runtime_evaluation(self) -> None:
        cand = self._make_manifest("C_test")
        runs_ok = [{"elapsed_seconds": 120.0, "tool_calls": 5}]
        runs_slow = [{"elapsed_seconds": 950.0, "tool_calls": 20}]

        res_ok = evaluate_runtime(cand, runs_ok, evidence_mode=EvidenceMode.LIVE.value, budget_limit_ms_override=600_000.0)
        self.assertEqual(res_ok.dimension_status, GateDimensionStatus.PASS.value)
        self.assertFalse(res_ok.budget_violated)

        res_slow = evaluate_runtime(cand, runs_slow, evidence_mode=EvidenceMode.LIVE.value, budget_limit_ms_override=600_000.0)
        self.assertEqual(res_slow.dimension_status, GateDimensionStatus.FAIL.value)
        self.assertTrue(res_slow.budget_violated)

    # F. Configuration evaluation
    def test_F_configuration_evaluation(self) -> None:
        cand = self._make_manifest("C_test", parent_id="B0")
        res = evaluate_configuration(cand, self.b0_manifest, repo_root=self.root)
        self.assertEqual(res.dimension_status, GateDimensionStatus.PASS.value)
        self.assertTrue(res.model_permitted)
        self.assertFalse(res.secrets_found)

    # G. Reproducibility evaluation
    def test_G_reproducibility_evaluation(self) -> None:
        cand = self._make_manifest("C_test")
        runs = [{"task_id": "t1", "success": True}]
        res = evaluate_reproducibility(cand, runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.PASS.value)
        self.assertTrue(res.git_commit_verified)
        self.assertTrue(res.manifest_hash_verified)

    # H. Combined-dimension detection
    def test_H_combined_dimension_detection(self) -> None:
        cand = self._make_manifest(
            candidate_id="A1",
            primary_dimension="combined_ablation",
            experiment_type="combined_ablation",
            parent_id="B0",
            prompt_hash="9999999999999999999999999999999999999999999999999999999999999999",
        )
        # Also modify retrieval version to simulate multi-dimension
        cand.retrieval_version = "R1"
        cand.manifest_hash = compute_canonical_dict_hash(cand.to_dict(), exclude_keys=["manifest_hash"])
        res = evaluate_configuration(cand, self.b0_manifest, repo_root=self.root)
        self.assertEqual(res.dimension_status, GateDimensionStatus.PASS.value)
        self.assertTrue(res.multi_dimension_allowed)

    # I. PASS/FAIL/UNKNOWN semantics
    def test_I_pass_fail_unknown_semantics(self) -> None:
        cand = self._make_manifest("C_test")
        # Missing evidence must return UNKNOWN, not PASS
        res = compare_validation(cand, [], self.b0_manifest, [], evidence_mode=EvidenceMode.UNAVAILABLE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.UNKNOWN.value)
        self.assertNotEqual(res.dimension_status, GateDimensionStatus.PASS.value)

    # J. PROMOTE/REJECT/BLOCKED semantics
    def test_J_promote_reject_blocked_semantics(self) -> None:
        # A candidate with UNKNOWN dimension evaluates to BLOCKED
        rec = self.gate.evaluate("B0")
        self.assertEqual(rec.decision, GateDecision.BLOCKED.value)

    # K. Blocked-vs-rejected distinction
    def test_K_blocked_vs_rejected_distinction(self) -> None:
        # Candidate with missing evidence is BLOCKED
        rec_blocked = self.gate.evaluate("B0")
        self.assertEqual(rec_blocked.decision, GateDecision.BLOCKED.value)

        # Candidate with failed configuration is REJECTED
        cand_bad = self._make_manifest("C_bad", parent_id="B0", primary_dimension="prompt")
        cand_bad.retrieval_version = "R9"
        cand_bad.manifest_hash = compute_canonical_dict_hash(cand_bad.to_dict(), exclude_keys=["manifest_hash"])
        self.registry.register_candidate(cand_bad, overwrite_finalized=True)
        rec_reject = self.gate.evaluate("C_bad")
        self.assertEqual(rec_reject.decision, GateDecision.REJECT.value)

    # L. Current-best consistency
    def test_L_current_best_consistency(self) -> None:
        self.registry.set_current_best("B0", rationale="Baseline current best")
        val = self.gate.validate_current_best()
        self.assertTrue(val.valid)
        self.assertEqual(val.current_best_candidate_id, "B0")

        # Inconsistency: pointing to non-existent candidate
        bad_pointer = CurrentBestPointer(
            candidate_id="NON_EXISTENT",
            candidate_version="1.0.0",
            status="VALIDATED",
            updated_at="2026-10-02T10:00:00+00:00",
            git_commit="abcdef0123456789abcdef0123456789abcdef01",
            manifest_hash="dummy",
            rationale="corrupted pointer",
        )
        self.registry.current_best_file.write_text(json.dumps(bad_pointer.to_dict()), encoding="utf-8")
        val_bad = self.gate.validate_current_best()
        self.assertFalse(val_bad.valid)
        self.assertIn("not registered", val_bad.issues[0])

    # M. L1 blocked state
    def test_M_L1_blocked_state(self) -> None:
        l1 = self._make_manifest(
            candidate_id="L1",
            primary_dimension="adapter",
            experiment_type="lora_adaptation",
            status="BLOCKED",
            promotion_status="BLOCKED",
            adapter_id="experiments/lora/L1/adapter.safetensors",
            evidence_mode="UNAVAILABLE",
        )
        self.registry.register_candidate(l1, overwrite_finalized=True)
        rec = self.gate.evaluate("L1")
        self.assertEqual(rec.decision, GateDecision.BLOCKED.value)
        self.assertIn("adapter", rec.reasons[0].lower())

    # N. RC1 reserved state
    def test_N_RC1_reserved_state(self) -> None:
        rc1 = self._make_manifest(
            candidate_id="RC1",
            primary_dimension="packaging",
            experiment_type="release_candidate",
            status="RESERVED",
            promotion_status="RESERVED",
        )
        self.registry.register_candidate(rc1, overwrite_finalized=True)
        rec = self.gate.evaluate("RC1")
        self.assertEqual(rec.decision, GateDecision.BLOCKED.value)
        self.assertIn("NO_RELEASE_CANDIDATE_CONFIGURATION", rec.reasons[0])

    # O. M0-M5 structural vs scientific distinction
    def test_O_M0_M5_structural_vs_scientific_distinction(self) -> None:
        m0 = self._make_manifest(
            candidate_id="M0",
            primary_dimension="topology",
            experiment_type="competition_candidate",
        )
        m0.evidence_mode = "INFRASTRUCTURE_ONLY"
        self.registry.register_candidate(m0, overwrite_finalized=True)
        rec = self.gate.evaluate("M0")
        self.assertEqual(rec.decision, GateDecision.BLOCKED.value)
        self.assertIn("structural submission validation", rec.reasons[0])

    # P. Promotion record generation
    def test_P_promotion_record_generation(self) -> None:
        rec = self.gate.evaluate("B0")
        saved_path = self.gate.save_promotion_record(rec, self.b0_manifest)
        self.assertTrue(saved_path.is_file())
        md_path = saved_path.with_suffix(".md")
        self.assertTrue(md_path.is_file())
        content = md_path.read_text(encoding="utf-8")
        self.assertIn("## 1. Candidate", content)
        self.assertIn("## 12. Gate Decision", content)

    # Q. Rejection record generation
    def test_Q_rejection_record_generation(self) -> None:
        cand = self._make_manifest("C_fail", parent_id="B0")
        self.registry.register_candidate(cand, overwrite_finalized=True)
        rec = self.gate.reject_candidate("C_fail", reason="Failed targeted validation benchmark")
        self.assertEqual(rec.decision, GateDecision.REJECT.value)
        rej_file = self.gate.promotions_dir / "C_fail.json"
        self.assertTrue(rej_file.is_file())

    # R. History append-only behavior
    def test_R_history_append_only_behavior(self) -> None:
        rec = self.gate.evaluate("B0")
        self.gate.save_promotion_record(rec, self.b0_manifest, record_event=True)
        lines_before = self.registry.history_file.read_text(encoding="utf-8").strip().splitlines()

        self.gate.save_promotion_record(rec, self.b0_manifest, record_event=True)
        lines_after = self.registry.history_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines_after), len(lines_before) + 1)

    # S. Immutable candidate enforcement
    def test_S_immutable_candidate_enforcement(self) -> None:
        cand = self._make_manifest("C_imm")
        self.registry.register_candidate(cand, overwrite_finalized=True)
        # Verify gate evaluation does not mutate manifest hash
        cand_before = self.registry.get_candidate("C_imm")
        _ = self.gate.evaluate("C_imm")
        cand_after = self.registry.get_candidate("C_imm")
        self.assertEqual(cand_before.manifest_hash, cand_after.manifest_hash)

    # T. No force bypass
    def test_T_no_force_bypass(self) -> None:
        # Verify attempting promotion on non-promoting candidate raises PromotionGateFailureError
        with self.assertRaises(PromotionGateFailureError):
            self.gate.promote_candidate("B0")

    # U. Fixture promotion rejection
    def test_U_fixture_promotion_rejection(self) -> None:
        cand = self._make_manifest("C_fix")
        runs = [{"task_id": "t1", "success": True, "split_name": "validation"}]
        res = compare_validation(cand, runs, self.b0_manifest, runs, evidence_mode=EvidenceMode.FIXTURE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.UNKNOWN.value)

    # V. Infrastructure-only promotion rejection
    def test_V_infrastructure_only_promotion_rejection(self) -> None:
        cand = self._make_manifest("C_infra")
        runs = [{"task_id": "t1", "success": None, "split_name": "validation"}]
        res = compare_validation(cand, runs, self.b0_manifest, runs, evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.UNKNOWN.value)

    # W. Missing evidence handling
    def test_W_missing_evidence_handling(self) -> None:
        cand = self._make_manifest("C_none")
        res = compare_validation(cand, [], self.b0_manifest, [], evidence_mode=EvidenceMode.UNAVAILABLE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.UNKNOWN.value)
        self.assertIsNone(res.delta)

    # X. Deterministic gate output
    def test_X_deterministic_gate_output(self) -> None:
        rec1 = self.gate.evaluate("B0")
        rec2 = self.gate.evaluate("B0")
        self.assertEqual(rec1.decision, rec2.decision)
        self.assertEqual(rec1.validation_result, rec2.validation_result)
        self.assertEqual(rec1.reproducibility_result, rec2.reproducibility_result)

    # Y. Reproducibility metadata validation
    def test_Y_reproducibility_metadata_validation(self) -> None:
        cand_corrupt = self._make_manifest("C_corrupt", git_commit="not-a-valid-sha")
        res = evaluate_reproducibility(cand_corrupt, [], evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)
        self.assertFalse(res.git_commit_verified)

    # Z. Multi-dimensional change detection
    def test_Z_multi_dimensional_change_detection(self) -> None:
        cand_multi = self._make_manifest("C_multi", parent_id="B0", primary_dimension="prompt")
        # Change both prompt and retrieval without declaring combined_ablation
        cand_multi.retrieval_version = "R9"
        cand_multi.manifest_hash = compute_canonical_dict_hash(cand_multi.to_dict(), exclude_keys=["manifest_hash"])
        res = evaluate_configuration(cand_multi, self.b0_manifest, repo_root=self.root)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)
        self.assertTrue(res.is_multi_dimension)
        self.assertFalse(res.multi_dimension_allowed)

    # NEGATIVE TESTS
    def test_negative_worse_validation_cannot_promote(self) -> None:
        cand = self._make_manifest("C_worse", parent_id="B0")
        base = self.b0_manifest
        b_runs = [{"task_id": "t1", "success": True, "split_name": "validation"}]
        c_runs = [{"task_id": "t1", "success": False, "split_name": "validation"}]
        res = compare_validation(cand, c_runs, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)

    def test_negative_held_out_regression_cannot_promote(self) -> None:
        cand = self._make_manifest("C_reg", parent_id="B0")
        base = self.b0_manifest
        b_runs = [{"task_id": "h1", "success": True, "split_name": "held_out"}]
        c_runs = [{"task_id": "h1", "success": False, "split_name": "held_out"}]
        res = compare_held_out(cand, c_runs, base, b_runs, evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)

    def test_negative_runtime_violation_cannot_promote(self) -> None:
        cand = self._make_manifest("C_time")
        runs = [{"elapsed_seconds": 1500.0, "status": "timeout"}]
        res = evaluate_runtime(cand, runs, evidence_mode=EvidenceMode.LIVE.value, budget_limit_ms_override=600_000.0)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)

    def test_negative_invalid_config_cannot_promote(self) -> None:
        cand = self._make_manifest("C_bad_model", base_model="unapproved-model")
        res = evaluate_configuration(cand, self.b0_manifest, repo_root=self.root)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)

    def test_negative_missing_repro_cannot_promote(self) -> None:
        cand = self._make_manifest("C_bad_git", git_commit="invalid")
        res = evaluate_reproducibility(cand, [], evidence_mode=EvidenceMode.LIVE.value)
        self.assertEqual(res.dimension_status, GateDimensionStatus.FAIL.value)

    def test_negative_blocked_cannot_be_promoted(self) -> None:
        with self.assertRaises(PromotionGateFailureError):
            self.gate.promote_candidate("B0")

    def test_negative_rejected_cannot_be_directly_promoted(self) -> None:
        cand = self._make_manifest("C_rej", status="REJECTED", promotion_status="REJECTED")
        self.registry.register_candidate(cand, overwrite_finalized=True)
        with self.assertRaises(PromotionGateFailureError):
            self.gate.promote_candidate("C_rej")

    def test_negative_nonexistent_candidate_cannot_be_evaluated(self) -> None:
        with self.assertRaises(CandidateNotFoundError):
            self.gate.evaluate("DOES_NOT_EXIST")


if __name__ == "__main__":
    unittest.main()
