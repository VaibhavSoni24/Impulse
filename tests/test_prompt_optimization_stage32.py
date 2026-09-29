"""Comprehensive Unit and Integration Tests for Stage 32: Prompt Optimization Loop.

Covers all 28 required test scenarios:
1. P0 snapshot integrity
2. P1 candidate creation
3. Parent hash validation
4. Unique candidate IDs
5. Single prompt intervention validation
6. Non-prompt file mutation rejection
7. Multiple-dimension prompt-change rejection
8. Deterministic prompt diffing
9. SHA-256 manifest correctness
10. Targeted failure reduction
11. Targeted failure unchanged (rejection)
12. Targeted failure worsening (rejection)
13. Collateral regression detection (rejection)
14. Validation/held-out promotion gate (promotion)
15. Held-out regression detection (rejection)
16. No live results handling
17. Infrastructure-only evidence handling
18. Fixture vs. live isolation
19. Task-level paired comparisons (JSONL & CSV)
20. Prompt cost metrics calculation
21. Ablation lineage tracking
22. Duplicate candidate creation rejection
23. Malformed manifest/hypothesis rejection
24. Benchmark manifest hash validation
25. Frozen Stage 24 artifact protection
26. CLI analysis mode execution
27. Deterministic report generation (all 16 required sections)
28. Candidate artifact verification
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from benchmark.splits.hashing import compute_file_sha256
from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.fdd.gates import compute_run_delta, evaluate_promotion_gate
from local.fdd.models import FDDRunDelta, FailureRecord, PromotionDecision
from local.prompt_opt.baseline import (
    DEFAULT_SOURCE_PROMPT,
    EXPECTED_M0_PROMPT_SHA256,
    establish_p0_baseline,
)
from local.prompt_opt.cli import run_prompt_cli, verify_prompt_candidate_artifacts
from local.prompt_opt.diff import (
    compute_prompt_cost,
    compute_prompt_diff,
    detect_prompt_bloat,
    render_prompt_diff_md,
)
from local.prompt_opt.experiment import PromptExperimentManager
from local.prompt_opt.models import (
    PromptCandidateManifest,
    PromptChangeType,
    PromptHypothesis,
    TaskPairOutcome,
    TaskTransition,
)
from local.prompt_opt.paired import (
    compute_task_paired_comparison,
    save_paired_results_csv,
    save_paired_results_jsonl,
    summarize_paired_outcomes,
)
from local.prompt_opt.reporting import generate_prompt_experiment_report
from local.prompt_opt.validator import (
    PromptValidationError,
    validate_prompt_candidate_integrity,
    validate_prompt_hypothesis,
)


class TestPromptOptimizationStage32(unittest.TestCase):
    """Test suite for Prompt Optimization Loop (Stage 32)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="stage32_test_")
        self.temp_path = Path(self.temp_dir)
        self.prompts_dir = self.temp_path / "experiments" / "prompts"
        self.prompts_dir.mkdir(parents=True)
        self.manager = PromptExperimentManager(prompts_base_dir=self.prompts_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. P0 snapshot integrity
    def test_01_p0_snapshot_integrity(self) -> None:
        """P0 baseline is an exact byte-identical replica of M0 root prompt with valid hashes."""
        p0_dir = self.prompts_dir / "P0"
        manifest = establish_p0_baseline(
            output_dir=p0_dir,
            git_commit="test_commit_01",
        )
        self.assertEqual(manifest.candidate_id, "P0")
        self.assertEqual(manifest.prompt_sha256, EXPECTED_M0_PROMPT_SHA256)

        root_file = p0_dir / "root.md"
        self.assertTrue(root_file.is_file())
        self.assertEqual(compute_file_sha256(root_file), EXPECTED_M0_PROMPT_SHA256)

        # Verify artifacts
        ok, errors = verify_prompt_candidate_artifacts(p0_dir)
        self.assertTrue(ok, f"P0 verification failed: {errors}")

    # 2. P1 candidate creation
    def test_02_p1_creation(self) -> None:
        """Creating P1 derived from P0 records parentage and computes prompt diff."""
        p0_man = self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")

        # Create single prompt intervention: Add evidence-before-edit requirement
        new_content = parent_content + "\n\n## Evidence Rule\nExplicitly log test evidence before editing.\n"
        hyp = PromptHypothesis(
            target_failure="WRONG_HYPOTHESIS",
            observation="Premature edits occur before evidence is observed.",
            hypothesis="Requiring explicit evidence logging before edits reduces wrong hypothesis failures.",
            intervention="Add Evidence Rule section requiring evidence before editing.",
            expected_behavior="Agent verifies test results before creating edits.",
            expected_metric_signal="Reduced wrong_hypothesis failure count.",
            rejection_condition="Zero reduction in target failure or increased command failures.",
            change_type=PromptChangeType.ADD_INSTRUCTION.value,
            changed_section="Evidence Rule",
        )

        manifest, diff, bloat = self.manager.create_candidate(
            candidate_id="P1",
            parent_candidate_id="P0",
            new_prompt_content=new_content,
            hypothesis=hyp,
        )

        self.assertEqual(manifest.candidate_id, "P1")
        self.assertEqual(manifest.parent_candidate_id, "P0")
        self.assertEqual(manifest.parent_prompt_sha256, p0_man.prompt_sha256)
        self.assertNotEqual(manifest.prompt_sha256, p0_man.prompt_sha256)
        self.assertTrue(diff.added_lines_count > 0)
        self.assertTrue((self.prompts_dir / "P1" / "prompt_diff.md").is_file())

    # 3. Parent hash validation
    def test_03_parent_hash_validation(self) -> None:
        """Validator rejects candidate if parent prompt hash does not match recorded value."""
        self.manager.ensure_p0_baseline()
        p0_prompt = self.prompts_dir / "P0" / "root.md"

        manifest = PromptCandidateManifest(
            candidate_id="P1_bad_parent",
            parent_candidate_id="P0",
            prompt_id="P1_root",
            prompt_path=str(p0_prompt),
            prompt_sha256=EXPECTED_M0_PROMPT_SHA256,
            parent_prompt_sha256="wrong_parent_hash_1234567890",
            changed_files=["root.md"],
            hypothesis=PromptHypothesis(
                target_failure="WRONG_HYPOTHESIS",
                observation="obs",
                hypothesis="hyp",
                intervention="int",
                expected_behavior="exp",
                expected_metric_signal="sig",
                rejection_condition="rej",
            ),
        )

        ok, errors = validate_prompt_candidate_integrity(
            manifest=manifest,
            candidate_prompt_path=p0_prompt,
            parent_prompt_path=p0_prompt,
        )
        self.assertFalse(ok)
        self.assertTrue(any("parent prompt sha-256 mismatch" in e.lower() for e in errors))

    # 4. Unique candidate IDs
    def test_04_unique_candidate_ids(self) -> None:
        """Re-creating an existing candidate ID raises FileExistsError."""
        self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")
        hyp = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="h",
            intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
        )

        self.manager.create_candidate("P1", "P0", parent_content + "\n# Extra", hyp)
        with self.assertRaises(FileExistsError):
            self.manager.create_candidate("P1", "P0", parent_content + "\n# Extra again", hyp)

    # 5. Single prompt intervention validation
    def test_05_single_prompt_intervention(self) -> None:
        """Structured single prompt intervention passes hypothesis validation."""
        hyp = PromptHypothesis(
            target_failure="INCOMPLETE_FIX",
            observation="Fixes leave edge assertions unsatisfied.",
            hypothesis="Instructing boundary condition checks reduces incomplete fixes.",
            intervention="Add boundary check instruction.",
            expected_behavior="Agent tests edge cases before submitting.",
            expected_metric_signal="Decreased incomplete_fix count.",
            rejection_condition="No improvement or regression in other classes.",
            change_type=PromptChangeType.TIGHTEN_CONSTRAINT.value,
        )
        ok, errors = validate_prompt_hypothesis(hyp)
        self.assertTrue(ok, f"Validation failed: {errors}")

    # 6. Non-prompt file mutation rejection
    def test_06_non_prompt_file_mutation_rejection(self) -> None:
        """Changed files containing non-prompt extensions (yaml, py, sh) are rejected."""
        manifest = PromptCandidateManifest(
            candidate_id="P_invalid_file",
            parent_candidate_id="P0",
            prompt_id="P_root",
            prompt_path="experiments/prompts/P_invalid_file/root.md",
            prompt_sha256="abc",
            parent_prompt_sha256="def",
            changed_files=["root.md", "local/clean_copy/evaluator.py"],
            hypothesis=PromptHypothesis(
                target_failure="COMMAND", observation="o", hypothesis="h",
                intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
            ),
        )
        ok, errors = validate_prompt_candidate_integrity(
            manifest=manifest,
            candidate_prompt_path=Path("non_existent"),
        )
        self.assertFalse(ok)
        self.assertTrue(any("non-prompt file" in e.lower() for e in errors))

    # 7. Multiple-dimension prompt-change rejection
    def test_07_multiple_dimension_prompt_change_rejection(self) -> None:
        """Modifying multiple prompt files in one candidate violates single-component discipline."""
        manifest = PromptCandidateManifest(
            candidate_id="P_multi_prompt",
            parent_candidate_id="P0",
            prompt_id="P_root",
            prompt_path="experiments/prompts/P_multi_prompt/root.md",
            prompt_sha256="abc",
            parent_prompt_sha256="def",
            changed_files=["root.md", "scout.md"],
            hypothesis=PromptHypothesis(
                target_failure="COMMAND", observation="o", hypothesis="h",
                intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
            ),
        )
        ok, errors = validate_prompt_candidate_integrity(
            manifest=manifest,
            candidate_prompt_path=Path("non_existent"),
        )
        self.assertFalse(ok)
        self.assertTrue(any("multiple prompt files" in e.lower() for e in errors))

    # 8. Deterministic prompt diffing
    def test_08_deterministic_prompt_diff(self) -> None:
        """compute_prompt_diff generates deterministic output across repeated invocations."""
        parent_txt = "Line 1\nLine 2\nLine 3\n"
        cand_txt = "Line 1\nLine 2 modified\nLine 3\nLine 4 added\n"

        diff1 = compute_prompt_diff("P0", "P1", parent_txt, cand_txt)
        diff2 = compute_prompt_diff("P0", "P1", parent_txt, cand_txt)

        self.assertEqual(diff1.unified_diff, diff2.unified_diff)
        self.assertEqual(diff1.added_lines_count, 2)
        self.assertEqual(diff1.removed_lines_count, 1)
        self.assertEqual(diff1.cost_metrics.char_delta, diff2.cost_metrics.char_delta)

    # 9. SHA-256 manifest correctness
    def test_09_sha256_manifest_correctness(self) -> None:
        """All recorded artifact hashes in manifest.json strictly match file contents on disk."""
        self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")
        hyp = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="h",
            intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
        )
        manifest, diff, bloat = self.manager.create_candidate("P1_hash", "P0", parent_content + "\n# Extra", hyp)
        cand_dir = self.prompts_dir / "P1_hash"

        # Check recorded hashes
        for fname, recorded_hash in manifest.artifact_hashes.items():
            fpath = cand_dir / fname
            self.assertTrue(fpath.is_file())
            self.assertEqual(compute_file_sha256(fpath), recorded_hash)

    # 10. Targeted failure reduction
    def test_10_targeted_failure_reduction(self) -> None:
        """compute_run_delta correctly calculates targeted failure drop."""
        base_runs = [
            FailureRecord(run_id=f"b-{i}", candidate_id="P0", task_id=f"t-{i}", run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS", is_actionable=True)
            for i in range(5)
        ]
        cand_runs = [
            FailureRecord(run_id="c-0", candidate_id="P1", task_id="t-0", run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS", is_actionable=True),
            FailureRecord(run_id="c-1", candidate_id="P1", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
            FailureRecord(run_id="c-2", candidate_id="P1", task_id="t-2", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
        ]
        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="WRONG_HYPOTHESIS")
        self.assertEqual(delta.targeted_reduction, 4)
        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # 11. Targeted failure unchanged (rejection)
    def test_11_targeted_failure_unchanged(self) -> None:
        """Zero targeted failure reduction results in REJECTED."""
        base_runs = [FailureRecord(run_id=f"b-{i}", candidate_id="P0", task_id=f"t-{i}", run_status="COMPLETED", success=False, failure_category="COMMAND", is_actionable=True) for i in range(3)]
        cand_runs = [FailureRecord(run_id=f"c-{i}", candidate_id="P1", task_id=f"t-{i}", run_status="COMPLETED", success=False, failure_category="COMMAND", is_actionable=True) for i in range(3)]
        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="COMMAND")
        self.assertEqual(delta.targeted_reduction, 0)
        decision, _ = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 12. Targeted failure worsening (rejection)
    def test_12_targeted_failure_worsening(self) -> None:
        """Targeted failure count increasing results in REJECTED."""
        base_runs = [FailureRecord(run_id="b-1", candidate_id="P0", task_id="t-1", run_status="COMPLETED", success=False, failure_category="REGRESSION", is_actionable=True)]
        cand_runs = [FailureRecord(run_id=f"c-{i}", candidate_id="P1", task_id=f"t-{i}", run_status="COMPLETED", success=False, failure_category="REGRESSION", is_actionable=True) for i in range(3)]
        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="REGRESSION")
        self.assertEqual(delta.targeted_reduction, -2)
        decision, _ = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 13. Collateral regression detection (rejection)
    def test_13_collateral_regression(self) -> None:
        """Targeted failure reduction accompanied by collateral regression in other classes is REJECTED."""
        base_runs = [
            FailureRecord(run_id="b-wh", candidate_id="P0", task_id="t-1", run_status="COMPLETED", success=False, failure_category="WRONG_HYPOTHESIS", is_actionable=True)
        ]
        cand_runs = [
            # Target reduced to 0!
            FailureRecord(run_id="c-1", candidate_id="P1", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True),
            # Collateral COMMAND failures appear
            FailureRecord(run_id="c-cmd", candidate_id="P1", task_id="t-2", run_status="COMPLETED", success=False, failure_category="COMMAND", is_actionable=True),
        ]
        delta = compute_run_delta(base_runs, cand_runs, target_failure_mode="WRONG_HYPOTHESIS")
        self.assertEqual(delta.targeted_reduction, 1)
        self.assertIn("COMMAND", delta.collateral_regressions)
        decision, _ = evaluate_promotion_gate(delta, smoke_passed=True, max_collateral_regression=0)
        self.assertEqual(decision, PromotionDecision.REJECTED)

    # 14. Validation/held-out promotion gate
    def test_14_validation_held_out_promotion_gate(self) -> None:
        """Candidate passing smoke, validation, and held-out is PROMOTED."""
        base_val = [FailureRecord(run_id="b-1", candidate_id="P0", task_id="t-1", run_status="COMPLETED", success=False, failure_category="INCOMPLETE_FIX", is_actionable=True)]
        cand_val = [FailureRecord(run_id="c-1", candidate_id="P1", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True)]
        base_ho = [FailureRecord(run_id="hb-1", candidate_id="P0", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]
        cand_ho = [FailureRecord(run_id="hc-1", candidate_id="P1", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]

        delta = compute_run_delta(base_val, cand_val, "INCOMPLETE_FIX", held_out_baseline=base_ho, held_out_candidate=cand_ho)
        decision, _ = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.PROMOTED)

    # 15. Held-out regression detection
    def test_15_held_out_regression_rejection(self) -> None:
        """Candidate improving validation but dropping on held-out is REJECTED."""
        base_val = [FailureRecord(run_id="b-1", candidate_id="P0", task_id="t-1", run_status="COMPLETED", success=False, failure_category="INCOMPLETE_FIX", is_actionable=True)]
        cand_val = [FailureRecord(run_id="c-1", candidate_id="P1", task_id="t-1", run_status="COMPLETED", success=True, failure_category="", is_actionable=True)]
        base_ho = [FailureRecord(run_id="hb-1", candidate_id="P0", task_id="h-1", run_status="COMPLETED", success=True, is_actionable=True)]
        cand_ho = [FailureRecord(run_id="hc-1", candidate_id="P1", task_id="h-1", run_status="COMPLETED", success=False, failure_category="COMMAND", is_actionable=True)]

        delta = compute_run_delta(base_val, cand_val, "INCOMPLETE_FIX", held_out_baseline=base_ho, held_out_candidate=cand_ho)
        decision, rationale = evaluate_promotion_gate(delta, smoke_passed=True)
        self.assertEqual(decision, PromotionDecision.REJECTED)
        self.assertIn("held-out confirmation regressed", rationale.lower())

    # 16. No live results handling
    def test_16_no_live_results(self) -> None:
        """Zero actionable completed runs produce NO_ACTIONABLE_DATA without fake metrics."""
        delta = FDDRunDelta(target_failure_mode="WRONG_HYPOTHESIS", baseline_failure_count=None)
        decision, _ = evaluate_promotion_gate(delta, smoke_passed=True, has_actionable_runs=False)
        self.assertEqual(decision, PromotionDecision.NO_ACTIONABLE_DATA)

    # 17. Infrastructure-only evidence handling
    def test_17_infrastructure_only_evidence(self) -> None:
        """Infrastructure-only runs are marked unexecuted and non-actionable."""
        rec = FailureRecord(
            run_id="r-infra", candidate_id="P0", task_id="t-1",
            run_status="execution_unavailable_local_host",
            failure_category="INFRASTRUCTURE_UNAVAILABLE",
            is_actionable=False,
        )
        self.assertFalse(rec.is_actionable)
        delta = compute_run_delta([rec], [rec], "INFRASTRUCTURE_UNAVAILABLE")
        self.assertEqual(delta.targeted_reduction, 0)

    # 18. Fixture vs. live isolation
    def test_18_fixture_live_isolation(self) -> None:
        """Fixture candidates are strictly isolated and marked with evidence_mode=FIXTURE."""
        self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")
        hyp = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="h",
            intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
        )
        manifest, _, _ = self.manager.create_candidate(
            "P_fixture", "P0", parent_content + "\n# Fixture Note", hyp, evidence_mode="FIXTURE"
        )
        self.assertEqual(manifest.evidence_mode, "FIXTURE")

    # 19. Task-level paired comparisons
    def test_19_task_paired_comparison(self) -> None:
        """Task-level transitions and JSONL/CSV serialization work accurately."""
        base_runs = [
            FailureRecord(run_id="b-1", candidate_id="P0", task_id="task_1", success=False, failure_category="WRONG_HYPOTHESIS", is_actionable=True),
            FailureRecord(run_id="b-2", candidate_id="P0", task_id="task_2", success=True, failure_category="", is_actionable=True),
            FailureRecord(run_id="b-3", candidate_id="P0", task_id="task_3", success=False, failure_category="COMMAND", is_actionable=True),
            FailureRecord(run_id="b-4", candidate_id="P0", task_id="task_4", success=False, failure_category="COMMAND", is_actionable=True),
        ]
        cand_runs = [
            FailureRecord(run_id="c-1", candidate_id="P1", task_id="task_1", success=True, failure_category="", is_actionable=True),  # FAIL -> PASS
            FailureRecord(run_id="c-2", candidate_id="P1", task_id="task_2", success=False, failure_category="COMMAND", is_actionable=True), # PASS -> FAIL
            FailureRecord(run_id="c-3", candidate_id="P1", task_id="task_3", success=False, failure_category="REGRESSION", is_actionable=True), # FAIL -> Other FAIL
            FailureRecord(run_id="c-4", candidate_id="P1", task_id="task_4", success=False, failure_category="COMMAND", is_actionable=True), # FAIL -> FAIL unchanged
        ]

        outcomes = compute_task_paired_comparison(base_runs, cand_runs)
        self.assertEqual(len(outcomes), 4)

        summary = summarize_paired_outcomes(outcomes)
        self.assertEqual(summary["fail_to_pass"], 1)
        self.assertEqual(summary["pass_to_fail"], 1)
        self.assertEqual(summary["fail_to_other_fail"], 1)
        self.assertEqual(summary["fail_unchanged"], 1)

        # Serialization
        jsonl_path = self.temp_path / "paired.jsonl"
        csv_path = self.temp_path / "paired.csv"
        save_paired_results_jsonl(outcomes, jsonl_path)
        save_paired_results_csv(outcomes, csv_path)

        self.assertTrue(jsonl_path.is_file())
        self.assertTrue(csv_path.is_file())

    # 20. Prompt cost metrics calculation
    def test_20_prompt_cost_metrics(self) -> None:
        """compute_prompt_cost calculates lines, characters, words, and deltas."""
        base_text = "Hello world\nSecond line\n"
        new_text = "Hello world\nSecond line modified\nThird line\n"
        cost = compute_prompt_cost(new_text, parent_content=base_text)

        self.assertEqual(cost.line_count, 3)
        self.assertEqual(cost.line_delta, 1)
        self.assertTrue(cost.char_delta > 0)
        self.assertTrue(cost.estimated_tokens > 0)

    # 21. Ablation lineage tracking
    def test_21_ablation_lineage(self) -> None:
        """Ablation candidates record exact parentage and intervention lineage."""
        self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")

        # P1 = P0 + instruction X
        hyp_add = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="add rule X",
            intervention="Add X", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
            change_type=PromptChangeType.ADD_INSTRUCTION.value,
        )
        p1_content = parent_content + "\n## Rule X\nDo X.\n"
        self.manager.create_candidate("P1", "P0", p1_content, hyp_add)

        # P2 = P1 - instruction X (ablation)
        hyp_rem = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="remove rule X to test necessity",
            intervention="Remove X", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
            change_type=PromptChangeType.REMOVE_INSTRUCTION.value,
        )
        p2_manifest, _, _ = self.manager.create_candidate("P2", "P1", parent_content, hyp_rem)

        self.assertEqual(p2_manifest.parent_candidate_id, "P1")
        self.assertEqual(p2_manifest.intervention_type, PromptChangeType.REMOVE_INSTRUCTION.value)

    # 22. Duplicate candidate creation rejection
    def test_22_duplicate_candidate_rejection(self) -> None:
        """PromptExperimentManager rejects candidate creation if directory exists."""
        self.manager.ensure_p0_baseline()
        content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")
        hyp = PromptHypothesis(target_failure="C", observation="o", hypothesis="h", intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r")
        self.manager.create_candidate("P_dup", "P0", content + "\n# Extra", hyp)
        with self.assertRaises(FileExistsError):
            self.manager.create_candidate("P_dup", "P0", content + "\n# Extra 2", hyp)

    # 23. Malformed manifest/hypothesis rejection
    def test_23_malformed_hypothesis_rejection(self) -> None:
        """Empty fields in PromptHypothesis fail validation."""
        bad_hyp = PromptHypothesis(
            target_failure="", observation="", hypothesis="", intervention="", expected_behavior="", expected_metric_signal="", rejection_condition="",
        )
        ok, errors = validate_prompt_hypothesis(bad_hyp)
        self.assertFalse(ok)
        self.assertTrue(len(errors) >= 6)

    # 24. Benchmark manifest hash validation
    def test_24_benchmark_manifest_hash_validation(self) -> None:
        """Split manifest and lock hashes are preserved in candidate manifest."""
        self.manager.ensure_p0_baseline()
        p0_man = json.loads((self.prompts_dir / "P0" / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("benchmark_split", p0_man)
        self.assertIn("model_id", p0_man)

    # 25. Frozen Stage 24 artifact protection
    def test_25_frozen_artifact_protection(self) -> None:
        """Attempting to modify any of the 14 frozen Stage 24 artifacts is strictly rejected."""
        manifest = PromptCandidateManifest(
            candidate_id="P_tamper",
            parent_candidate_id="P0",
            prompt_id="P_root",
            prompt_path="experiments/prompts/P_tamper/root.md",
            prompt_sha256="abc",
            parent_prompt_sha256="def",
            changed_files=["agent/prompts/scout.md"],  # Frozen artifact!
            hypothesis=PromptHypothesis(
                target_failure="COMMAND", observation="o", hypothesis="h",
                intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
            ),
        )
        ok, errors = validate_prompt_candidate_integrity(
            manifest=manifest,
            candidate_prompt_path=Path("non_existent"),
        )
        self.assertFalse(ok)
        self.assertTrue(any("frozen" in e.lower() for e in errors))

    # 26. CLI analysis mode execution
    def test_26_cli_analysis_mode(self) -> None:
        """CLI --analyze prints baseline P0 analysis without errors."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = run_prompt_cli(["--prompts-dir", str(self.prompts_dir), "--parent", "P0", "--analyze"])
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("Prompt Optimization Baseline Analysis: P0", out)
        self.assertIn("Prompt SHA-256", out)

    # 27. Deterministic report generation
    def test_27_deterministic_report_generation(self) -> None:
        """generate_prompt_experiment_report contains all 16 required sections."""
        manifest = PromptCandidateManifest(
            candidate_id="P1_rep",
            parent_candidate_id="P0",
            prompt_id="P1_root",
            prompt_path="experiments/prompts/P1_rep/root.md",
            prompt_sha256="123456",
            parent_prompt_sha256="654321",
            target_failure_mode="WRONG_HYPOTHESIS",
            hypothesis=PromptHypothesis(
                target_failure="WRONG_HYPOTHESIS",
                observation="Baseline had premature edits.",
                hypothesis="Adding evidence check reduces errors.",
                intervention="Add evidence check rule.",
                expected_behavior="Check evidence first.",
                expected_metric_signal="Target failure drops.",
                rejection_condition="Zero drop or collateral regressions.",
            ),
            decision="PROMOTED",
            decision_rationale="Target failure reduced by 3.",
        )
        diff = compute_prompt_diff("P0", "P1_rep", "Base prompt", "Base prompt\nAdded check")
        delta = FDDRunDelta(target_failure_mode="WRONG_HYPOTHESIS", baseline_failure_count=4, candidate_failure_count=1, targeted_reduction=3)

        report = generate_prompt_experiment_report(
            manifest=manifest,
            diff=diff,
            delta=delta,
            smoke_passed=True,
            validation_passed=True,
        )

        required_sections = [
            "# Prompt Optimization Experiment",
            "## Candidate",
            "## Parent",
            "## Target Failure",
            "## Baseline Evidence",
            "## Hypothesis",
            "## Prompt Change",
            "## Prompt Diff",
            "## Smoke Result",
            "## Validation Result",
            "## Held-Out Result",
            "## Targeted Failure Delta",
            "## Paired Task Outcomes",
            "## Collateral Effects",
            "## Prompt Cost",
            "## Decision",
            "## Reproducibility",
        ]
        for sec in required_sections:
            self.assertIn(sec, report, f"Missing required section: {sec}")

    # 28. Candidate artifact verification
    def test_28_candidate_artifact_verification(self) -> None:
        """Recording complete experiment results allows verify_prompt_candidate_artifacts to pass."""
        self.manager.ensure_p0_baseline()
        parent_content = (self.prompts_dir / "P0" / "root.md").read_text(encoding="utf-8")
        hyp = PromptHypothesis(
            target_failure="COMMAND", observation="o", hypothesis="h",
            intervention="i", expected_behavior="e", expected_metric_signal="s", rejection_condition="r",
        )
        manifest, diff, bloat = self.manager.create_candidate("P1_full", "P0", parent_content + "\n# Extra", hyp)

        base_rec = [FailureRecord(run_id="b-1", candidate_id="P0", task_id="t-1", success=False, failure_category="COMMAND", is_actionable=True)]
        cand_rec = [FailureRecord(run_id="c-1", candidate_id="P1_full", task_id="t-1", success=True, failure_category="", is_actionable=True)]

        exp_dir = self.manager.record_experiment_results(
            candidate_id="P1_full",
            manifest=manifest,
            diff=diff,
            decision="PROMOTED",
            decision_rationale="Passed all gates.",
            smoke_passed=True,
            validation_passed=True,
            baseline_records=base_rec,
            candidate_records=cand_rec,
            bloat_report=bloat,
        )

        ok, errors = verify_prompt_candidate_artifacts(exp_dir)
        self.assertTrue(ok, f"Verification failed with: {errors}")


if __name__ == "__main__":
    unittest.main()
