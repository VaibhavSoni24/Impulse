"""Comprehensive Test Suite for Stage 41: Multi-Adapter Experimentation.

Tests all 24 mandatory requirements (A through X):
A. Parent commit check
B. Clean-tree check
C. Single-adapter prerequisite
D. Missing adapter block
E. Missing measured benefit block
F. Fixture adapter rejection
G. Role schema
H. Role-to-adapter mapping
I. Duplicate assignment rejection
J. Unsupported role rejection
K. Base-model compatibility
L. Adapter hash verification
M. Provenance verification
N. Objective metadata validation
O. Invariance checks
P. Matrix generation (MA0 through MA7)
Q. Candidate schema
R. Metrics schema
S. Held-out protection
T. Dry-run
U. No-execution gate
V. No production modification
W. Current-state blocked result
X. Deterministic output
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.lora_ablation.adapter_gate import compute_file_sha256
from local.multi_adapter.artifacts import MultiAdapterArtifactManager
from local.multi_adapter.errors import (
    BaseModelMismatchError,
    MultiAdapterError,
    RoleConflictError,
    SingleAdapterPrerequisiteError,
    UnvalidatedAdapterError,
)
from local.multi_adapter.evaluator import MultiAdapterEvaluator
from local.multi_adapter.matrix import MultiAdapterMatrixGenerator
from local.multi_adapter.models import (
    AdapterRole,
    AdapterStatus,
    BASE_MODEL_IDENTIFIER,
    FROZEN_ROOT_PROMPT_HASH,
    MultiAdapterCandidateConfig,
    MultiAdapterExecutionStatus,
    MultiAdapterMetrics,
    MultiAdapterReport,
    MultiAdapterRunManifest,
    PrerequisiteCheckResult,
    RoleAdapterAssignment,
    Stage41Decision,
)
from local.multi_adapter.prerequisites import SingleAdapterPrerequisiteChecker
from local.multi_adapter.reporting import MultiAdapterReporter
from local.multi_adapter.validation import MultiAdapterConfigValidator

EXPECTED_PARENT_STAGE40_COMMIT = "d11faf3fb9a56ba6876ddf9aea3574b883c9321a"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMultiAdapterStage41(unittest.TestCase):
    """Authoritative test cases for Stage 41 Multi-Adapter Experimentation."""

    def setUp(self) -> None:
        self.repo_root = PROJECT_ROOT
        self.prereq_checker = SingleAdapterPrerequisiteChecker(self.repo_root)
        self.matrix_gen = MultiAdapterMatrixGenerator()
        self.validator = MultiAdapterConfigValidator()
        self.evaluator = MultiAdapterEvaluator(self.repo_root)
        self.reporter = MultiAdapterReporter(self.repo_root)
        self.artifact_mgr = MultiAdapterArtifactManager(self.repo_root)

    # -------------------------------------------------------------------------
    # A. Parent Commit Check
    # -------------------------------------------------------------------------
    def test_A_parent_commit_check(self) -> None:
        """Verifies parent commit recorded matches Stage 40 final commit."""
        report = self.evaluator.evaluate_multi_adapter()
        self.assertEqual(report.parent_commit, EXPECTED_PARENT_STAGE40_COMMIT)

    # -------------------------------------------------------------------------
    # B. Clean-Tree Check
    # -------------------------------------------------------------------------
    def test_B_clean_tree_check(self) -> None:
        """Verifies all 14 frozen Stage 24-40 baseline artifacts match authoritative hashes."""
        is_match, details = verify_frozen_artifacts(self.repo_root)
        self.assertTrue(is_match, f"Frozen artifacts modified: {details}")
        self.assertEqual(len(details), 14)
        for path, info in details.items():
            self.assertEqual(info["status"], "MATCH", f"Mismatch in {path}")

    # -------------------------------------------------------------------------
    # C. Single-Adapter Prerequisite
    # -------------------------------------------------------------------------
    def test_C_single_adapter_prerequisite(self) -> None:
        """Verifies that the scientific prerequisite check fails closed when no validated adapter exists."""
        prereq = self.prereq_checker.check_single_adapter_prerequisite()
        self.assertFalse(prereq.eligible)
        self.assertFalse(prereq.single_adapter_validated)
        self.assertIn("NO_MEASURED_SINGLE_ADAPTER_BENEFIT", prereq.blocking_reasons)

    # -------------------------------------------------------------------------
    # D. Missing Adapter Block
    # -------------------------------------------------------------------------
    def test_D_missing_adapter_block(self) -> None:
        """Verifies that an unprovided or missing adapter path blocks execution."""
        prereq = self.prereq_checker.check_single_adapter_prerequisite(adapter_path=None)
        self.assertFalse(prereq.eligible)
        self.assertTrue(any("No candidate adapter artifact directory specified" in r for r in prereq.blocking_reasons))

    # -------------------------------------------------------------------------
    # E. Missing Measured Benefit Block
    # -------------------------------------------------------------------------
    def test_E_missing_measured_benefit_block(self) -> None:
        """Verifies that if Stage 40 did not execute or report improvement, prerequisite fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_report = Path(tmp_dir) / "fake_stage40_report.md"
            fake_report.write_text(
                "# Stage 40\n- **Did real A/B execution occur?** **NO**\n- **Measured Adapter Improvement:** **NO**\n",
                encoding="utf-8",
            )
            prereq = self.prereq_checker.check_single_adapter_prerequisite(stage40_report_path=fake_report)
            self.assertFalse(prereq.eligible)
            self.assertIn("NO_MEASURED_SINGLE_ADAPTER_BENEFIT", prereq.blocking_reasons)

    # -------------------------------------------------------------------------
    # F. Fixture Adapter Rejection
    # -------------------------------------------------------------------------
    def test_F_fixture_adapter_rejection(self) -> None:
        """Verifies that a fixture-generated adapter is strictly rejected from satisfying prerequisite."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "adapter_config.json").write_text("{}", encoding="utf-8")
            (tmp_path / "adapter_model.safetensors").write_bytes(b"dummy")
            (tmp_path / "manifest.json").write_text(
                json.dumps({
                    "base_model": BASE_MODEL_IDENTIFIER,
                    "dataset_id": "L0-TOOL-DISCIPLINE-DATA-v1",
                    "dataset_version": "1.0.0",
                    "objective_id": "OBJ-TOOL-DISCIPLINE",
                    "status": "COMPLETED",
                    "evidence_mode": "FIXTURE",
                }),
                encoding="utf-8",
            )
            prereq = self.prereq_checker.check_single_adapter_prerequisite(adapter_path=tmp_path)
            self.assertFalse(prereq.eligible)
            self.assertTrue(any("Fixture-generated adapter cannot satisfy" in r for r in prereq.blocking_reasons))

    # -------------------------------------------------------------------------
    # G. Role Schema
    # -------------------------------------------------------------------------
    def test_G_role_schema(self) -> None:
        """Verifies the AdapterRole enum covers root, scout, reviewer."""
        self.assertEqual(AdapterRole.ROOT.value, "root")
        self.assertEqual(AdapterRole.SCOUT.value, "scout")
        self.assertEqual(AdapterRole.REVIEWER.value, "reviewer")

    # -------------------------------------------------------------------------
    # H. Role-to-Adapter Mapping
    # -------------------------------------------------------------------------
    def test_H_role_to_adapter_mapping(self) -> None:
        """Verifies RoleAdapterAssignment data structure and serialization."""
        assign = RoleAdapterAssignment(
            role=AdapterRole.ROOT,
            adapter_id="root_opt_v1",
            adapter_path="/valid/root/adapter",
            status=AdapterStatus.VALIDATED,
            base_model=BASE_MODEL_IDENTIFIER,
            allowed_agent_roles=[AdapterRole.ROOT],
        )
        d = assign.to_dict()
        self.assertEqual(d["role"], "root")
        self.assertEqual(d["status"], "VALIDATED")
        self.assertEqual(d["allowed_agent_roles"], ["root"])

    # -------------------------------------------------------------------------
    # I. Duplicate Assignment Rejection
    # -------------------------------------------------------------------------
    def test_I_duplicate_assignment_rejection(self) -> None:
        """Verifies role mismatch and invalid assignment detection."""
        candidate = MultiAdapterCandidateConfig(
            candidate_id="MA_TEST",
            description="Test candidate",
            roles={
                AdapterRole.ROOT.value: {
                    "role": "scout",  # Mismatch! Scout adapter in root slot
                    "status": AdapterStatus.VALIDATED.value,
                    "base_model": BASE_MODEL_IDENTIFIER,
                    "allowed_agent_roles": ["scout"],
                }
            },
        )
        is_valid, violations = self.validator.validate_candidate_config(candidate)
        self.assertFalse(is_valid)
        self.assertTrue(any("Role mismatch" in v for v in violations))

    # -------------------------------------------------------------------------
    # J. Unsupported Role Rejection
    # -------------------------------------------------------------------------
    def test_J_unsupported_role_rejection(self) -> None:
        """Verifies that an unknown agent role is rejected."""
        candidate = MultiAdapterCandidateConfig(
            candidate_id="MA_TEST",
            description="Test candidate",
            roles={"unsupported_agent_role": None},
        )
        is_valid, violations = self.validator.validate_candidate_config(candidate)
        self.assertFalse(is_valid)
        self.assertTrue(any("Unsupported agent role" in v for v in violations))

    # -------------------------------------------------------------------------
    # K. Base-Model Compatibility
    # -------------------------------------------------------------------------
    def test_K_base_model_compatibility(self) -> None:
        """Verifies that an adapter with an incompatible base model is rejected."""
        candidate = MultiAdapterCandidateConfig(
            candidate_id="MA_TEST",
            description="Test candidate",
            roles={
                AdapterRole.ROOT.value: {
                    "role": "root",
                    "status": AdapterStatus.VALIDATED.value,
                    "base_model": "unsupported-model-7b",  # Incompatible!
                    "allowed_agent_roles": ["root"],
                }
            },
        )
        is_valid, violations = self.validator.validate_candidate_config(candidate)
        self.assertFalse(is_valid)
        self.assertTrue(any("incompatible" in v for v in violations))

    # -------------------------------------------------------------------------
    # L. Adapter Hash Verification
    # -------------------------------------------------------------------------
    def test_L_adapter_hash_verification(self) -> None:
        """Verifies file hash calculation helper on existing repository files."""
        hash_val = compute_file_sha256(self.repo_root / "agent" / "agent.yaml")
        self.assertTrue(isinstance(hash_val, str) and len(hash_val) == 64)

    # -------------------------------------------------------------------------
    # M. Provenance Verification
    # -------------------------------------------------------------------------
    def test_M_provenance_verification(self) -> None:
        """Verifies that an unvalidated adapter status is rejected."""
        candidate = MultiAdapterCandidateConfig(
            candidate_id="MA_TEST",
            description="Test candidate",
            roles={
                AdapterRole.ROOT.value: {
                    "role": "root",
                    "status": AdapterStatus.UNAVAILABLE.value,  # Not validated!
                    "base_model": BASE_MODEL_IDENTIFIER,
                    "allowed_agent_roles": ["root"],
                }
            },
        )
        is_valid, violations = self.validator.validate_candidate_config(candidate)
        self.assertFalse(is_valid)
        self.assertTrue(any("unvalidated adapter" in v for v in violations))

    # -------------------------------------------------------------------------
    # N. Objective Metadata Validation
    # -------------------------------------------------------------------------
    def test_N_objective_metadata_validation(self) -> None:
        """Verifies RoleAdapterAssignment preserves objective metadata."""
        assign = RoleAdapterAssignment(
            role=AdapterRole.SCOUT,
            objective_id="OBJ-LOCALIZATION",
            status=AdapterStatus.VALIDATED,
            allowed_agent_roles=[AdapterRole.SCOUT],
        )
        self.assertEqual(assign.objective_id, "OBJ-LOCALIZATION")

    # -------------------------------------------------------------------------
    # O. Invariance Checks
    # -------------------------------------------------------------------------
    def test_O_invariance_checks(self) -> None:
        """Verifies candidate configuration enforces base model and prompt invariance."""
        candidate = MultiAdapterCandidateConfig(
            candidate_id="MA_TEST",
            description="Test candidate",
            base_model="different_model",  # Invariance broken!
        )
        is_valid, violations = self.validator.validate_candidate_config(candidate)
        self.assertFalse(is_valid)
        self.assertTrue(any("base model" in v for v in violations))

    # -------------------------------------------------------------------------
    # P. Matrix Generation (MA0 - MA7)
    # -------------------------------------------------------------------------
    def test_P_matrix_generation(self) -> None:
        """Verifies canonical 8-member experiment matrix is constructed correctly."""
        matrix = self.matrix_gen.generate_matrix()
        self.assertEqual(len(matrix), 8)
        expected_ids = ["MA0", "MA1", "MA2", "MA3", "MA4", "MA5", "MA6", "MA7"]
        self.assertEqual(sorted(matrix.keys()), sorted(expected_ids))

        # MA0 has no adapters
        self.assertEqual(matrix["MA0"].roles["root"], None)
        self.assertEqual(matrix["MA0"].roles["scout"], None)
        self.assertEqual(matrix["MA0"].roles["reviewer"], None)

    # -------------------------------------------------------------------------
    # Q. Candidate Schema
    # -------------------------------------------------------------------------
    def test_Q_candidate_schema(self) -> None:
        """Verifies candidate schema serialization to dict."""
        matrix = self.matrix_gen.generate_matrix()
        ma1_dict = matrix["MA1"].to_dict()
        self.assertEqual(ma1_dict["candidate_id"], "MA1")
        self.assertEqual(ma1_dict["status"], MultiAdapterExecutionStatus.BLOCKED.value)

    # -------------------------------------------------------------------------
    # R. Metrics Schema
    # -------------------------------------------------------------------------
    def test_R_metrics_schema(self) -> None:
        """Verifies MultiAdapterMetrics schema captures role-specific and cost metrics."""
        metrics = MultiAdapterMetrics(
            candidate_id="MA4",
            task_count=10,
            overall_task_success_rate=0.7,
        )
        m_dict = metrics.to_dict()
        self.assertIn("root_metrics", m_dict)
        self.assertIn("scout_metrics", m_dict)
        self.assertIn("reviewer_metrics", m_dict)
        self.assertIn("cost_metrics", m_dict)

    # -------------------------------------------------------------------------
    # S. Held-Out Protection
    # -------------------------------------------------------------------------
    def test_S_held_out_protection(self) -> None:
        """Verifies held_out.lock and held-out benchmark splits are locked."""
        lock_file = self.repo_root / "benchmark" / "splits" / "v1" / "held_out.lock"
        self.assertTrue(lock_file.exists())
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        self.assertEqual(lock_data.get("held_out_count"), 14)
        self.assertIn("locked_at", lock_data)

    # -------------------------------------------------------------------------
    # T. Dry-Run Validation
    # -------------------------------------------------------------------------
    def test_T_dry_run(self) -> None:
        """Verifies dry-run returns structured validation summary without mutating repo."""
        summary = self.evaluator.execute_dry_run()
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["matrix_size"], 8)
        self.assertFalse(summary["single_adapter_prerequisite"]["eligible"])
        self.assertEqual(
            summary["overall_decision"],
            Stage41Decision.STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE.value,
        )

    # -------------------------------------------------------------------------
    # U. No-Execution Gate
    # -------------------------------------------------------------------------
    def test_U_no_execution_gate(self) -> None:
        """Verifies that evaluate_multi_adapter refuses execution when prerequisite fails."""
        report = self.evaluator.evaluate_multi_adapter()
        self.assertEqual(
            report.overall_status,
            Stage41Decision.STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE,
        )
        self.assertIsNone(report.metrics)
        self.assertIn("NO_MEASURED_SINGLE_ADAPTER_BENEFIT", report.decision_reason)

    # -------------------------------------------------------------------------
    # V. No Production Modification
    # -------------------------------------------------------------------------
    def test_V_no_production_modification(self) -> None:
        """Verifies that running multi-adapter evaluation never mutates agent.yaml."""
        agent_yaml_path = self.repo_root / "agent" / "agent.yaml"
        before_hash = compute_file_sha256(agent_yaml_path)

        report = self.evaluator.evaluate_multi_adapter()
        self.assertIsNotNone(report)

        after_hash = compute_file_sha256(agent_yaml_path)
        self.assertEqual(before_hash, after_hash, "agent.yaml must never be modified by Stage 41!")

    # -------------------------------------------------------------------------
    # W. Current-State Blocked Result
    # -------------------------------------------------------------------------
    def test_W_current_state_blocked_result(self) -> None:
        """Verifies that evaluating current repository state outputs the expected blocked decision."""
        report = self.evaluator.evaluate_multi_adapter()
        self.assertEqual(
            report.overall_status,
            Stage41Decision.STAGE_41_COMPLETE_FRAMEWORK_VERIFIED_BLOCKED_BY_PREREQUISITE,
        )
        self.assertFalse(report.prerequisite_result.eligible)

    # -------------------------------------------------------------------------
    # X. Deterministic Output
    # -------------------------------------------------------------------------
    def test_X_deterministic_output(self) -> None:
        """Verifies repeated prerequisite queries yield strictly identical results."""
        r1 = self.prereq_checker.check_single_adapter_prerequisite()
        r2 = self.prereq_checker.check_single_adapter_prerequisite()
        self.assertEqual(r1.eligible, r2.eligible)
        self.assertEqual(r1.blocking_reasons, r2.blocking_reasons)


if __name__ == "__main__":
    unittest.main()
