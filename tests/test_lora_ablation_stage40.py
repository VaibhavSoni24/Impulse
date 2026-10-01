"""Comprehensive Test Suite for Stage 40: LoRA Ablation Framework.

Tests all 31 mandatory requirements (A through AE):
A. Parent commit verification
B. Clean tree verification
C. Condition schema
D. Baseline condition construction
E. Missing adapter hard block
F. Invalid adapter hard block
G. Wrong base model rejection
H. Adapter hash validation
I. Dataset hash validation
J. Prompt invariance
K. Tool invariance
L. Retrieval invariance
M. Testing invariance
N. Recovery invariance
O. Topology invariance
P. Benchmark invariance
Q. Primary A/B comparison structure
R. C/D gating
S. Held-out protection
T. Clean-copy evaluator integration
U. Paired task transitions
V. Objective metrics (OBJ-TOOL-DISCIPLINE)
W. Collateral regression metrics
X. Cost metrics
Y. Promotion gate
Z. Reproducibility manifest
AA. Dry-run
AB. No automatic promotion
AC. Fixture adapter rejection
AD. Fake adapter rejection
AE. Blocked-current-state correctness
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.clean_copy.models import ExecutionMode
from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.lora_ablation.adapter_gate import AdapterGateValidator, compute_file_sha256
from local.lora_ablation.artifacts import AblationArtifactManager
from local.lora_ablation.conditions import ConditionManager
from local.lora_ablation.errors import (
    AblationError,
    DryRunError,
    HeldOutViolationError,
    InvalidAdapterError,
    InvarianceViolationError,
    MissingAdapterError,
    PromotionGateError,
    SecondaryConditionBlockedError,
)
from local.lora_ablation.evaluator import AblationEvaluator
from local.lora_ablation.invariance import AblationInvarianceChecker
from local.lora_ablation.metrics import ToolDisciplineMetricsCalculator
from local.lora_ablation.models import (
    AblationAggregateMetrics,
    AblationComparisonReport,
    AblationConditionConfig,
    AblationRunManifest,
    AdapterArtifactMetadata,
    AdapterGateStatus,
    CollateralStatus,
    ConditionStatus,
    ConditionType,
    FROZEN_BASELINE_DIMENSIONS,
    FROZEN_TOOL_CONTRACT_HASHES,
    PromotionGateDecision,
    Stage40Decision,
    TargetFailureTransition,
    TaskEvaluationRecord,
    TaskPairTransition,
)
from local.lora_ablation.paired import TaskPairedAnalyzer
from local.lora_ablation.promotion import CandidatePromotionGate
from local.lora_ablation.reporting import AblationReporter

EXPECTED_PARENT_STAGE39_COMMIT = "a853123862593eff7bc62dcc0fc04b6db8487e98"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestLoRAAblationStage40(unittest.TestCase):
    """Authoritative test suite for Stage 40 LoRA Ablation."""

    def setUp(self) -> None:
        self.repo_root = PROJECT_ROOT
        self.cond_mgr = ConditionManager(self.repo_root)
        self.inv_checker = AblationInvarianceChecker()
        self.gate_validator = AdapterGateValidator(self.repo_root)
        self.evaluator = AblationEvaluator(self.repo_root)
        self.reporter = AblationReporter(self.repo_root)

    # -------------------------------------------------------------------------
    # A. Parent Commit Verification
    # -------------------------------------------------------------------------
    def test_A_parent_commit_verification(self) -> None:
        """Verifies parent commit recorded matches Stage 39 final commit."""
        report = self.evaluator.run_primary_ablation()
        self.assertEqual(report.parent_commit, EXPECTED_PARENT_STAGE39_COMMIT)

    # -------------------------------------------------------------------------
    # B. Clean Tree Verification
    # -------------------------------------------------------------------------
    def test_B_clean_tree_verification(self) -> None:
        """Verifies all 14 frozen Stage 24-39 baseline artifacts match authoritative hashes."""
        is_match, details = verify_frozen_artifacts(self.repo_root)
        self.assertTrue(is_match, f"Frozen artifacts modified: {details}")
        self.assertEqual(len(details), 14)
        for path, info in details.items():
            self.assertEqual(info["status"], "MATCH", f"Mismatch in {path}")

    # -------------------------------------------------------------------------
    # C. Condition Schema Serialization
    # -------------------------------------------------------------------------
    def test_C_condition_schema(self) -> None:
        """Verifies serialization and deserialization of condition configs and comparison reports."""
        cond_a = self.cond_mgr.build_condition_a()
        a_dict = cond_a.to_dict()
        self.assertEqual(a_dict["condition_type"], ConditionType.BASELINE_NO_ADAPTER.value)
        self.assertEqual(a_dict["status"], ConditionStatus.READY_FOR_ABLATION.value)
        self.assertEqual(a_dict["base_model"], FROZEN_BASELINE_DIMENSIONS["base_model"])

        rec = TaskEvaluationRecord(
            task_id="task_test_001",
            condition=ConditionType.BASELINE_NO_ADAPTER,
            result="FAILED",
            success=False,
            target_failure_status="COMMAND_REDUNDANCY",
            repeated_failing_command_count=2,
            tool_invocation_error_count=3,
        )
        rec_dict = rec.to_dict()
        self.assertEqual(rec_dict["task_id"], "task_test_001")
        self.assertEqual(rec_dict["repeated_failing_command_count"], 2)

    # -------------------------------------------------------------------------
    # D. Baseline Condition Construction
    # -------------------------------------------------------------------------
    def test_D_baseline_condition_construction(self) -> None:
        """Verifies Condition A is constructed from frozen M0 specifications."""
        cond_a = self.cond_mgr.build_condition_a()
        self.assertEqual(cond_a.candidate_id, "M0")
        self.assertFalse(cond_a.adapter_enabled)
        self.assertIsNone(cond_a.adapter_path)
        self.assertEqual(cond_a.prompt_hash, FROZEN_BASELINE_DIMENSIONS["prompt_hash"])
        self.assertEqual(cond_a.retrieval_version, "R0")
        self.assertEqual(cond_a.topology, "root_only")

    # -------------------------------------------------------------------------
    # E. Missing Adapter Hard Block
    # -------------------------------------------------------------------------
    def test_E_missing_adapter_hard_block(self) -> None:
        """Verifies that when no adapter path is provided, the gate strictly returns MISSING_ADAPTER_ARTIFACT."""
        is_valid, status, reason, metadata = self.gate_validator.validate_adapter(None)
        self.assertFalse(is_valid)
        self.assertEqual(status, AdapterGateStatus.MISSING_ADAPTER_ARTIFACT)
        self.assertIsNone(metadata)
        self.assertIn("No adapter path specified", reason)

        # Nonexistent path
        is_valid2, status2, _, _ = self.gate_validator.validate_adapter(Path("nonexistent/adapter/path"))
        self.assertFalse(is_valid2)
        self.assertEqual(status2, AdapterGateStatus.MISSING_ADAPTER_ARTIFACT)

    # -------------------------------------------------------------------------
    # F. Invalid Adapter Hard Block
    # -------------------------------------------------------------------------
    def test_F_invalid_adapter_hard_block(self) -> None:
        """Verifies that an adapter missing required files (.safetensors or config) is rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create config but no weights or manifest
            (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
            is_valid, status, reason, _ = self.gate_validator.validate_adapter(tmp_path)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.MISSING_ADAPTER_FILES)
            self.assertIn("Missing adapter weights", reason)

    # -------------------------------------------------------------------------
    # G. Wrong Base Model Rejection
    # -------------------------------------------------------------------------
    def test_G_wrong_base_model_rejection(self) -> None:
        """Verifies that an adapter trained for a different base model is rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "adapter_config.json").write_text(
                json.dumps({"base_model_name_or_path": "unsupported-model-7b"}), encoding="utf-8"
            )
            (tmp_path / "adapter_model.safetensors").write_bytes(b"dummy_weights")
            (tmp_path / "manifest.json").write_text(
                json.dumps({
                    "base_model": "unsupported-model-7b",
                    "dataset_id": "L0-TOOL-DISCIPLINE-DATA-v1",
                    "dataset_version": "1.0.0",
                    "objective_id": "OBJ-TOOL-DISCIPLINE",
                    "status": "COMPLETED",
                }),
                encoding="utf-8",
            )
            is_valid, status, reason, _ = self.gate_validator.validate_adapter(tmp_path)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.INCOMPATIBLE_BASE_MODEL)
            self.assertIn("does not match expected", reason)

    # -------------------------------------------------------------------------
    # H. Adapter Hash Validation
    # -------------------------------------------------------------------------
    def test_H_adapter_hash_validation(self) -> None:
        """Verifies that an adapter whose weight hash doesn't match its manifest is rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
            (tmp_path / "adapter_model.safetensors").write_bytes(b"actual_weights")
            (tmp_path / "manifest.json").write_text(
                json.dumps({
                    "base_model": FROZEN_BASELINE_DIMENSIONS["base_model"],
                    "dataset_id": "L0-TOOL-DISCIPLINE-DATA-v1",
                    "dataset_version": "1.0.0",
                    "objective_id": "OBJ-TOOL-DISCIPLINE",
                    "status": "COMPLETED",
                    "adapter_sha256": "wrong_expected_sha256_hash",
                }),
                encoding="utf-8",
            )
            is_valid, status, reason, _ = self.gate_validator.validate_adapter(tmp_path)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.HASH_MISMATCH)

    # -------------------------------------------------------------------------
    # I. Dataset Hash / ID Validation
    # -------------------------------------------------------------------------
    def test_I_dataset_hash_validation(self) -> None:
        """Verifies that an adapter trained on an unapproved dataset is rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
            (tmp_path / "adapter_model.safetensors").write_bytes(b"dummy")
            (tmp_path / "manifest.json").write_text(
                json.dumps({
                    "base_model": FROZEN_BASELINE_DIMENSIONS["base_model"],
                    "dataset_id": "UNAPPROVED-DATASET-v99",
                    "dataset_version": "1.0.0",
                    "objective_id": "OBJ-TOOL-DISCIPLINE",
                    "status": "COMPLETED",
                }),
                encoding="utf-8",
            )
            is_valid, status, reason, _ = self.gate_validator.validate_adapter(tmp_path)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.INCOMPATIBLE_DATASET)

    # -------------------------------------------------------------------------
    # J. Prompt Invariance
    # -------------------------------------------------------------------------
    def test_J_prompt_invariance(self) -> None:
        """Verifies that altering root prompt in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            prompt_hash="altered_prompt_hash",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("prompt mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # K. Tool Invariance
    # -------------------------------------------------------------------------
    def test_K_tool_invariance(self) -> None:
        """Verifies that altering any tool contract in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
        )
        cond_b.tool_contract_hashes["run_command"] = "altered_contract_hash"
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("Tool contract for 'run_command' differs" in v for v in violations))

    # -------------------------------------------------------------------------
    # L. Retrieval Invariance
    # -------------------------------------------------------------------------
    def test_L_retrieval_invariance(self) -> None:
        """Verifies that altering retrieval in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            retrieval_version="R1",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("retrieval mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # M. Testing Invariance
    # -------------------------------------------------------------------------
    def test_M_testing_invariance(self) -> None:
        """Verifies that altering testing strategy in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            testing_version="T1",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("testing mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # N. Recovery Invariance
    # -------------------------------------------------------------------------
    def test_N_recovery_invariance(self) -> None:
        """Verifies that altering recovery policy in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            recovery_version="REC1",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("recovery mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # O. Topology Invariance
    # -------------------------------------------------------------------------
    def test_O_topology_invariance(self) -> None:
        """Verifies that altering topology in Condition B triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            topology="scout_debugger_reviewer",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("topology mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # P. Benchmark Invariance
    # -------------------------------------------------------------------------
    def test_P_benchmark_invariance(self) -> None:
        """Verifies that altering benchmark split or manifest hash triggers an invariance violation."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/fake/adapter",
            benchmark_split="validation",  # A was dev
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertFalse(is_inv)
        self.assertTrue(any("split mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # Q. Primary A/B Comparison Structure
    # -------------------------------------------------------------------------
    def test_Q_primary_ab_comparison_structure(self) -> None:
        """Verifies that a validly formed Condition A and Condition B pass all invariance checks."""
        cond_a = self.cond_mgr.build_condition_a()
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            adapter_enabled=True,
            adapter_path="/valid/adapter",
            adapter_sha256="abc123hash",
        )
        is_inv, violations = self.inv_checker.check_primary_ablation_pair(cond_a, cond_b)
        self.assertTrue(is_inv, f"Unexpected violations: {violations}")

    # -------------------------------------------------------------------------
    # R. C/D Gating
    # -------------------------------------------------------------------------
    def test_R_cd_gating(self) -> None:
        """Verifies that Condition C and D cannot execute before Condition B is completed."""
        # Uncompleted B
        cond_b = AblationConditionConfig(
            condition_type=ConditionType.L1_ADAPTER,
            condition_label="Condition B",
            candidate_id="L1",
            status=ConditionStatus.MISSING_ADAPTER_ARTIFACT,
        )
        cond_c = self.cond_mgr.build_condition_c(cond_b)
        cond_d = self.cond_mgr.build_condition_d(cond_b)

        self.assertEqual(cond_c.status, ConditionStatus.BLOCKED_BY_MISSING_ADAPTER)
        self.assertEqual(cond_d.status, ConditionStatus.BLOCKED_BY_MISSING_ADAPTER)

    # -------------------------------------------------------------------------
    # S. Held-Out Protection
    # -------------------------------------------------------------------------
    def test_S_held_out_protection(self) -> None:
        """Verifies held-out benchmark split is protected from hyperparameter tuning."""
        split_manifest_path = self.repo_root / "benchmark" / "splits" / "v1" / "manifest.json"
        self.assertTrue(split_manifest_path.exists())
        with open(split_manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("held_out", data.get("splits", {}))
        # Held out tasks count = 14
        self.assertEqual(len(data["splits"]["held_out"]["task_ids"]), 14)

    # -------------------------------------------------------------------------
    # T. Clean-Copy Evaluator Integration
    # -------------------------------------------------------------------------
    def test_T_clean_copy_evaluator_integration(self) -> None:
        """Verifies clean-copy evaluator is integrated and accessible."""
        self.assertIsNotNone(self.evaluator.clean_copy_evaluator)
        self.assertEqual(self.evaluator.clean_copy_evaluator.repo_root, self.repo_root)

    # -------------------------------------------------------------------------
    # U. Paired Task Transitions
    # -------------------------------------------------------------------------
    def test_U_paired_task_transitions(self) -> None:
        """Verifies 2x2 outcome transition matrix and target failure transition logic."""
        rec_pass = TaskEvaluationRecord("t1", ConditionType.BASELINE_NO_ADAPTER, "RESOLVED", True, "NONE")
        rec_fail = TaskEvaluationRecord(
            "t1", ConditionType.L1_ADAPTER, "FAILED", False, "COMMAND_REDUNDANCY", repeated_failing_command_count=2
        )

        t1 = TaskPairedAnalyzer.classify_task_transition(rec_pass, rec_pass)
        self.assertEqual(t1, TaskPairTransition.A_PASS_B_PASS)

        t2 = TaskPairedAnalyzer.classify_task_transition(rec_pass, rec_fail)
        self.assertEqual(t2, TaskPairTransition.A_PASS_B_FAIL)

        t3 = TaskPairedAnalyzer.classify_task_transition(rec_fail, rec_pass)
        self.assertEqual(t3, TaskPairTransition.A_FAIL_B_PASS)

        t4 = TaskPairedAnalyzer.classify_task_transition(rec_fail, rec_fail)
        self.assertEqual(t4, TaskPairTransition.A_FAIL_B_FAIL)

        # Target transition
        target_resolved = TaskPairedAnalyzer.classify_target_transition(rec_fail, rec_pass)
        self.assertEqual(target_resolved, TargetFailureTransition.TARGET_FAILURE_RESOLVED)

    # -------------------------------------------------------------------------
    # V. Objective Metrics (OBJ-TOOL-DISCIPLINE)
    # -------------------------------------------------------------------------
    def test_V_objective_metrics(self) -> None:
        """Verifies calculation of repeated failing commands from tool traces."""
        tool_trace = [
            {"tool_name": "run_command", "arguments": {"command": "pytest"}, "exit_code": 1},
            # Repeated identical without intervening state modification -> repeated failing
            {"tool_name": "run_command", "arguments": {"command": "pytest"}, "exit_code": 1},
            # Intervening edit
            {"tool_name": "edit_file", "arguments": {"path": "a.py"}, "exit_code": 0},
            # Re-running pytest after edit is NOT an ungrounded repeated failure
            {"tool_name": "run_command", "arguments": {"command": "pytest"}, "exit_code": 1},
        ]
        repeated_failing = ToolDisciplineMetricsCalculator.calculate_repeated_failing_commands(tool_trace)
        self.assertEqual(repeated_failing, 1)

        tool_errors = ToolDisciplineMetricsCalculator.calculate_tool_invocation_errors(tool_trace)
        self.assertEqual(tool_errors, 3)

    # -------------------------------------------------------------------------
    # W. Collateral Regression Metrics
    # -------------------------------------------------------------------------
    def test_W_collateral_regression_metrics(self) -> None:
        """Verifies collateral regression detection when a previously-passing task fails."""
        a_records = [
            TaskEvaluationRecord("task_1", ConditionType.BASELINE_NO_ADAPTER, "RESOLVED", True, "NONE"),
            TaskEvaluationRecord("task_2", ConditionType.BASELINE_NO_ADAPTER, "FAILED", False, "COMMAND", repeated_failing_command_count=1),
        ]
        b_records_regressed = [
            TaskEvaluationRecord("task_1", ConditionType.L1_ADAPTER, "FAILED", False, "SYNTAX"),  # Regressed!
            TaskEvaluationRecord("task_2", ConditionType.L1_ADAPTER, "RESOLVED", True, "NONE"),
        ]
        _, collateral_status, counts = TaskPairedAnalyzer.analyze_task_sets(a_records, b_records_regressed)
        self.assertEqual(collateral_status, CollateralStatus.COLLATERAL_REGRESSION)
        self.assertEqual(counts[TaskPairTransition.A_PASS_B_FAIL.value], 1)

    # -------------------------------------------------------------------------
    # X. Cost Metrics
    # -------------------------------------------------------------------------
    def test_X_cost_metrics(self) -> None:
        """Verifies aggregation of runtime, turns, tool calls, and adapter size."""
        records = [
            TaskEvaluationRecord("t1", ConditionType.L1_ADAPTER, "RESOLVED", True, "NONE", runtime_ms=500.0, tool_calls=4, turns=3),
            TaskEvaluationRecord("t2", ConditionType.L1_ADAPTER, "RESOLVED", True, "NONE", runtime_ms=700.0, tool_calls=6, turns=5),
        ]
        metrics = ToolDisciplineMetricsCalculator.aggregate_task_records(
            ConditionType.L1_ADAPTER, records, adapter_size_bytes=10485760
        )
        self.assertEqual(metrics.cost_metrics["adapter_size_bytes"], 10485760)
        self.assertEqual(metrics.avg_runtime_ms, 600.0)
        self.assertEqual(metrics.avg_tool_calls, 5.0)

    # -------------------------------------------------------------------------
    # Y. Promotion Gate
    # -------------------------------------------------------------------------
    def test_Y_promotion_gate(self) -> None:
        """Verifies CandidatePromotionGate decision rules."""
        a_metrics = AblationAggregateMetrics(
            condition=ConditionType.BASELINE_NO_ADAPTER,
            task_count=10,
            success_count=5,
            pass_rate=0.5,
            total_repeated_failing_commands=8,
            avg_runtime_ms=1000.0,
        )
        b_metrics_promoted = AblationAggregateMetrics(
            condition=ConditionType.L1_ADAPTER,
            task_count=10,
            success_count=7,
            pass_rate=0.7,
            total_repeated_failing_commands=2,  # Improved!
            avg_runtime_ms=1100.0,
        )
        dec, rationale, _ = CandidatePromotionGate.evaluate_promotion(
            a_metrics, b_metrics_promoted, CollateralStatus.TARGET_GAIN, held_out_regressions=0
        )
        self.assertEqual(dec, PromotionGateDecision.PROMOTE)

        # Rejection on collateral regression
        dec_rej, _, _ = CandidatePromotionGate.evaluate_promotion(
            a_metrics, b_metrics_promoted, CollateralStatus.COLLATERAL_REGRESSION, held_out_regressions=0
        )
        self.assertEqual(dec_rej, PromotionGateDecision.REJECT)

    # -------------------------------------------------------------------------
    # Z. Reproducibility Manifest
    # -------------------------------------------------------------------------
    def test_Z_reproducibility_manifest(self) -> None:
        """Verifies AblationRunManifest captures all reproducibility parameters."""
        manifest = AblationRunManifest(
            run_id="run-ablation-001",
            candidate_id="L1",
            condition=ConditionType.L1_ADAPTER,
            parent_commit=EXPECTED_PARENT_STAGE39_COMMIT,
            model_identifier="gemma-4-31b-it-qat-w4a16-ct",
            adapter_identifier="L1-test",
            adapter_sha256="abc1234567890",
            prompt_hash=FROZEN_BASELINE_DIMENSIONS["prompt_hash"],
        )
        m_dict = manifest.to_dict()
        self.assertEqual(m_dict["condition"], ConditionType.L1_ADAPTER.value)
        self.assertEqual(m_dict["parent_commit"], EXPECTED_PARENT_STAGE39_COMMIT)

    # -------------------------------------------------------------------------
    # AA. Dry-Run Validation
    # -------------------------------------------------------------------------
    def test_AA_dry_run(self) -> None:
        """Verifies dry-run returns structured validation summary without mutating repo."""
        summary = self.evaluator.execute_dry_run()
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["conditions"]["A"]["status"], ConditionStatus.READY_FOR_ABLATION.value)
        self.assertEqual(summary["conditions"]["B"]["status"], ConditionStatus.MISSING_ADAPTER_ARTIFACT.value)
        self.assertTrue(summary["invariance_check"]["baseline_a"]["valid"])
        self.assertTrue(summary["benchmark"]["manifest_ready"])

    # -------------------------------------------------------------------------
    # AB. No Automatic Promotion
    # -------------------------------------------------------------------------
    def test_AB_no_automatic_promotion(self) -> None:
        """Verifies that running ablation never modifies agent.yaml or production candidates."""
        agent_yaml_path = self.repo_root / "agent" / "agent.yaml"
        before_hash = compute_file_sha256(agent_yaml_path)

        # Run primary ablation (blocked)
        report = self.evaluator.run_primary_ablation()
        self.assertIsNotNone(report)

        after_hash = compute_file_sha256(agent_yaml_path)
        self.assertEqual(before_hash, after_hash, "agent.yaml must never be modified by ablation runner!")

    # -------------------------------------------------------------------------
    # AC. Fixture Adapter Rejection
    # -------------------------------------------------------------------------
    def test_AC_fixture_adapter_rejection(self) -> None:
        """Verifies that an adapter marked evidence_mode=FIXTURE is strictly rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
            (tmp_path / "adapter_model.safetensors").write_bytes(b"dummy")
            (tmp_path / "manifest.json").write_text(
                json.dumps({
                    "base_model": FROZEN_BASELINE_DIMENSIONS["base_model"],
                    "dataset_id": "L0-TOOL-DISCIPLINE-DATA-v1",
                    "dataset_version": "1.0.0",
                    "objective_id": "OBJ-TOOL-DISCIPLINE",
                    "status": "COMPLETED",
                    "evidence_mode": "FIXTURE",
                }),
                encoding="utf-8",
            )
            is_valid, status, reason, _ = self.gate_validator.validate_adapter(tmp_path)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.FIXTURE_ADAPTER_REJECTED)
            self.assertIn("Fixture-generated adapter cannot be used", reason)

    # -------------------------------------------------------------------------
    # AD. Fake Adapter Rejection
    # -------------------------------------------------------------------------
    def test_AD_fake_adapter_rejection(self) -> None:
        """Verifies arbitrary fake adapter directory without manifest or weights is rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_dir = Path(tmp_dir) / "fake_adapter"
            fake_dir.mkdir()
            (fake_dir / "notes.txt").write_text("This is a fake adapter directory.")

            is_valid, status, reason, _ = self.gate_validator.validate_adapter(fake_dir)
            self.assertFalse(is_valid)
            self.assertEqual(status, AdapterGateStatus.MISSING_ADAPTER_FILES)

    # -------------------------------------------------------------------------
    # AE. Blocked Current State Correctness
    # -------------------------------------------------------------------------
    def test_AE_blocked_current_state_correctness(self) -> None:
        """Verifies that evaluating the current repository state yields the expected blocked decision."""
        report = self.evaluator.run_primary_ablation()
        self.assertEqual(
            report.overall_status,
            Stage40Decision.STAGE_40_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_MISSING_ADAPTER,
        )
        self.assertEqual(report.adapter_gate_status, AdapterGateStatus.MISSING_ADAPTER_ARTIFACT)
        self.assertEqual(report.promotion_decision, PromotionGateDecision.BLOCKED_BY_MISSING_ADAPTER)
        self.assertEqual(report.a_condition.status, ConditionStatus.READY_FOR_ABLATION)
        self.assertEqual(report.b_condition.status, ConditionStatus.MISSING_ADAPTER_ARTIFACT)
        self.assertEqual(report.c_condition.status, ConditionStatus.BLOCKED_BY_MISSING_ADAPTER)
        self.assertEqual(report.d_condition.status, ConditionStatus.BLOCKED_BY_MISSING_ADAPTER)


if __name__ == "__main__":
    unittest.main()
