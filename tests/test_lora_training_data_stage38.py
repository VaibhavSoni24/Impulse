"""Authoritative Unit and Regression Suite for Stage 38: Construct LoRA Training Data.

Systematically verifies:
A. Parent commit check (0d66dd9cf6b8e23289c3a92bda4d12268d2b8920)
B. Clean tree check (no modifications to frozen Stage 24-37 artifacts)
C. Schema validation
D. Required field validation
E. Source provenance validation
F. Permission-status validation
G. Secret detection
H. Redaction behavior
I. Duplicate detection
J. Near-duplicate detection
K. Train / validation separation
L. Held-out leakage rejection
M. Task-ID leakage rejection
N. Repository/base-commit leakage checks
O. Patch/test-patch fingerprint leakage checks
P. Objective alignment (strictly OBJ-TOOL-DISCIPLINE)
Q. Positive-example validation
R. Negative-example validation
S. Contrastive-example validation
T. Unpaired-example labeling
U. Deterministic split
V. Deterministic dataset hash
W. Quality rejection rules
X. Fixture isolation
Y. No-fabrication rule
Z. Manifest generation
AA. Training-contract validation
AB. No-training enforcement
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.lora_data.cli import run_cli
from local.lora_data.contracts import build_stage39_training_contract
from local.lora_data.dataset_loaders import (
    load_train,
    load_validation,
    verify_dataset_split,
    verify_no_held_out_leakage,
)
from local.lora_data.duplicates import (
    DuplicateDetector,
    compute_example_hash,
    compute_sequence_signature,
)
from local.lora_data.leakage import HeldOutLeakageChecker
from local.lora_data.manifests import compute_file_sha256, write_manifests
from local.lora_data.models import (
    ContrastiveType,
    DatasetManifest,
    DatasetStatus,
    EvidenceMode,
    LicenseStatus,
    QualityStatus,
    QualityVector,
    RejectionReason,
    SplitType,
    Stage39TrainingContract,
    ToolDisciplineTrainingExample,
)
from local.lora_data.pipeline import LoRADataPipeline
from local.lora_data.quality import QualityFilter
from local.lora_data.sanitizer import SecretSanitizer


class TestLoRATrainingDataStage38(unittest.TestCase):
    """Authoritative test cases for Stage 38 LoRA training data pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.pipeline = LoRADataPipeline(repo_root=cls.repo_root)

    def test_A_parent_commit_check(self):
        """A. Verifies that the parent commit recorded in the manifest is the Stage 37 final commit."""
        expected_parent = "0d66dd9cf6b8e23289c3a92bda4d12268d2b8920"
        manifest = DatasetManifest()
        self.assertEqual(manifest.parent_git_commit, expected_parent)

    def test_B_clean_tree_check(self):
        """B. Verifies that all frozen Stage 24-37 artifacts match their authoritative checksums."""
        is_match, results = verify_frozen_artifacts(self.repo_root)
        self.assertTrue(is_match, f"Frozen artifacts modified: {results}")
        self.assertEqual(len(results), 14)

    def test_C_schema_validation(self):
        """C. Verifies full serialization and deserialization of training examples."""
        ex = ToolDisciplineTrainingExample(
            example_id="ex_schema_01",
            task_id="task_test_01",
            repo="org/repo",
            base_commit="abc12345",
            situation="Agent faced test error.",
            evidence=["Test failed with code 1"],
            tool_sequence=[{"tool_name": "run_command", "arguments": {"command": "pytest"}, "result_summary": "fail", "exit_code": 1}],
            preferred_behavior={"action": "read_file", "arguments": {"path": "a.py"}},
            negative_behavior={"action": "run_command", "arguments": {"command": "pytest"}},
            contrastive_type=ContrastiveType.PAIRED_CONTRASTIVE.value,
            validation_signal="Resolved after inspection",
        )
        d = ex.to_dict()
        self.assertEqual(d["example_id"], "ex_schema_01")
        self.assertEqual(d["objective_id"], "OBJ-TOOL-DISCIPLINE")
        reconstructed = ToolDisciplineTrainingExample.from_dict(d)
        self.assertEqual(reconstructed.example_id, ex.example_id)

    def test_D_required_field_validation(self):
        """D. Verifies required fields in training examples."""
        ex = ToolDisciplineTrainingExample(
            example_id="ex_req_01",
            task_id="t1",
            repo="r1",
            situation="Situation",
            evidence=["e1"],
            preferred_behavior={"action": "run_command"},
        )
        d = ex.to_dict()
        required_fields = [
            "example_id",
            "dataset_id",
            "split",
            "task_id",
            "repo",
            "objective_id",
            "situation",
            "evidence",
            "tool_sequence",
            "preferred_behavior",
            "contrastive_type",
            "provenance",
            "quality",
            "evidence_mode",
        ]
        for field in required_fields:
            self.assertIn(field, d)

    def test_E_source_provenance_validation(self):
        """E. Verifies provenance structure and metadata completeness."""
        qfilter = QualityFilter()
        ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "provenance": {
                "source_name": "impulse_eval_traces",
                "source_location": "experiments/lora/L1-data/fixtures",
                "source_type": "fixture",
                "license": "Apache-2.0",
                "license_evidence": "LICENSE file",
                "allowed_for_training": True,
                "attribution_required": False,
                "redistribution_allowed": True,
                "license_status": LicenseStatus.PERMITTED.value,
            },
            "preferred_behavior": {"action": "run_command"},
            "evidence": ["Evidence 1"],
            "tool_sequence": [{"tool_name": "run_command", "arguments": {}, "result_summary": "ok"}],
            "validation_signal": "verified",
        }
        is_acc, _, reasons = qfilter.evaluate_example(ex, is_fixture_allowed=True)
        self.assertTrue(is_acc, f"Rejection reasons: {reasons}")

    def test_F_permission_status_validation(self):
        """F. Negative test: Verifies rejection of UNKNOWN or NOT_PERMITTED licenses."""
        qfilter = QualityFilter()
        ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "provenance": {
                "source_name": "proprietary_repo",
                "license": "Proprietary",
                "allowed_for_training": False,
                "license_status": LicenseStatus.NOT_PERMITTED.value,
            },
            "preferred_behavior": {"action": "run_command"},
            "evidence": ["Evidence"],
            "tool_sequence": [{"tool_name": "run_command", "arguments": {}, "result_summary": "ok"}],
            "validation_signal": "verified",
        }
        is_acc, _, reasons = qfilter.evaluate_example(ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_NOT_PERMITTED.value, reasons)

    def test_G_secret_detection(self):
        """G. Negative test: Verifies detection and rejection of credentials."""
        sanitizer = SecretSanitizer()
        sample = {
            "situation": "Authentication token glpat-abcdef12345678901234 was used.",
            "evidence": ["Output was ok"],
        }
        data, is_clean, redactions, reasons = sanitizer.sanitize_example(sample)
        self.assertFalse(is_clean)
        self.assertTrue(any("GITLAB_TOKEN" in r for r in reasons))

    def test_H_redaction_behavior(self):
        """H. Verifies deterministic redaction of host-specific file paths."""
        sanitizer = SecretSanitizer()
        text = r"File located at C:\Users\developer\impulse\local\file.py"
        clean, count = sanitizer.sanitize_paths(text)
        self.assertNotIn("developer", clean)
        self.assertIn("[WORKSPACE_ROOT]/impulse/local/file.py", clean)
        self.assertEqual(count, 1)

    def test_I_duplicate_detection(self):
        """I. Negative test: Verifies exact duplicate detection via SHA-256 collision."""
        detector = DuplicateDetector()
        ex1 = {
            "example_id": "ex_dup_01",
            "task_id": "t1",
            "repo": "r1",
            "situation": "Test situation",
            "tool_sequence": [{"tool_name": "get_status", "arguments": {}}],
            "preferred_behavior": {"action": "run_command"},
            "negative_behavior": {},
            "objective_id": "OBJ-TOOL-DISCIPLINE",
        }
        ex2 = dict(ex1)
        ex2["example_id"] = "ex_dup_02"

        unique, dups, stats = detector.deduplicate([ex1, ex2])
        self.assertEqual(len(unique), 1)
        self.assertEqual(len(dups), 1)
        self.assertEqual(stats["duplicates_removed"], 1)

    def test_J_near_duplicate_detection(self):
        """J. Verifies near-duplicate tool sequence collision detection."""
        detector = DuplicateDetector()
        ex1 = {
            "example_id": "ex_near_01",
            "task_id": "t1",
            "situation": "Situation A",
            "tool_sequence": [{"tool_name": "run_command", "arguments": {"command": "pytest -v"}}],
            "preferred_behavior": {"action": "read_file"},
            "objective_id": "OBJ-TOOL-DISCIPLINE",
        }
        ex2 = {
            "example_id": "ex_near_02",
            "task_id": "t2",
            "situation": "Situation B different wording",
            "tool_sequence": [{"tool_name": "run_command", "arguments": {"command": "pytest -v"}}],
            "preferred_behavior": {"action": "read_file"},
            "objective_id": "OBJ-TOOL-DISCIPLINE",
        }
        unique, dups, stats = detector.deduplicate([ex1, ex2])
        self.assertEqual(len(unique), 1)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["duplicate_reason"], "IDENTICAL_NORMALIZED_TOOL_SEQUENCE")

    def test_K_train_validation_separation(self):
        """K. Negative test: Verifies detection of overlapping tasks between train and validation."""
        train_data = [{"example_id": "t1", "task_id": "task_common", "split": "TRAIN", "tool_sequence": []}]
        val_data = [{"example_id": "v1", "task_id": "task_common", "split": "VALIDATION", "tool_sequence": []}]
        is_valid, violations = verify_dataset_split(train_data, val_data)
        self.assertFalse(is_valid)
        self.assertTrue(any("SPLIT_TASK_OVERLAP" in v for v in violations))

    def test_L_held_out_leakage_rejection(self):
        """L. Negative test: Verifies that any held-out benchmark task is rejected."""
        checker = HeldOutLeakageChecker(repo_root=self.repo_root)
        ex = {"task_id": "requests_6589", "repo": "psf/requests"}
        leaked, reasons = checker.check_example(ex)
        self.assertTrue(leaked)
        self.assertTrue(any("LEAKAGE_TASK_ID" in r for r in reasons))

    def test_M_task_id_leakage_rejection(self):
        """M. Negative test: Verifies rejection for all 14 held-out task IDs."""
        checker = HeldOutLeakageChecker(repo_root=self.repo_root)
        self.assertEqual(len(checker.held_out_tasks), 14)
        for tid in checker.held_out_tasks:
            leaked, reasons = checker.check_example({"task_id": tid})
            self.assertTrue(leaked, f"Failed to catch held-out task {tid}")

    def test_N_repo_base_commit_leakage_checks(self):
        """N. Negative test: Verifies rejection when repo and base commit match a held-out instance."""
        checker = HeldOutLeakageChecker(repo_root=self.repo_root)
        ex = {
            "task_id": "anonymized_alias_999",
            "repo": "encode/httpx",
            "base_commit": "4acf5c2c37714cc63b5cf71b3e284fca83c90311",
        }
        leaked, reasons = checker.check_example(ex)
        self.assertTrue(leaked)
        self.assertTrue(any("LEAKAGE_REPO_COMMIT" in r for r in reasons))

    def test_O_patch_fingerprint_leakage_checks(self):
        """O. Negative test: Verifies rejection if held-out patch fingerprint appears in text."""
        checker = HeldOutLeakageChecker(repo_root=self.repo_root)
        if checker.held_out_patch_hashes:
            sample_hash = next(iter(checker.held_out_patch_hashes))
            ex = {
                "task_id": "dev_task_1",
                "situation": f"Applied patch with fingerprint {sample_hash} to resolve issue.",
            }
            leaked, reasons = checker.check_example(ex)
            self.assertTrue(leaked)
            self.assertTrue(any("LEAKAGE_PATCH_HASH" in r for r in reasons))

    def test_P_objective_alignment(self):
        """P. Negative test: Verifies that examples outside OBJ-TOOL-DISCIPLINE are rejected."""
        qfilter = QualityFilter()
        ex = {
            "objective_id": "OBJ-CODE-GENERATION",
            "provenance": {"source_name": "s", "license": "MIT", "allowed_for_training": True, "license_status": "PERMITTED"},
            "preferred_behavior": {"action": "write_file"},
            "evidence": ["e"],
            "tool_sequence": [{"tool_name": "write_file", "arguments": {}, "result_summary": "ok"}],
            "validation_signal": "done",
        }
        is_acc, _, reasons = qfilter.evaluate_example(ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_OBJECTIVE_MISMATCH.value, reasons)

    def test_Q_positive_example_validation(self):
        """Q. Verifies positive pattern behavior representation (Pattern A-D)."""
        fixtures = self.pipeline.generate_fixture_dataset()
        pos_patterns = [f for f in fixtures if f.get("preferred_behavior", {}).get("action")]
        self.assertGreaterEqual(len(pos_patterns), 4)
        for p in pos_patterns:
            self.assertIn("rationale", p["preferred_behavior"])
            self.assertTrue(len(p["evidence"]) >= 1)

    def test_R_negative_example_validation(self):
        """R. Verifies negative behavior and failure rationales."""
        fixtures = self.pipeline.generate_fixture_dataset()
        neg_patterns = [f for f in fixtures if f.get("negative_behavior", {}).get("action")]
        self.assertGreaterEqual(len(neg_patterns), 4)
        for n in neg_patterns:
            self.assertIn("rationale", n["negative_behavior"])

    def test_S_contrastive_example_validation(self):
        """S. Verifies paired contrastive examples having both positive and negative actions."""
        fixtures = self.pipeline.generate_fixture_dataset()
        paired = [f for f in fixtures if f.get("contrastive_type") == ContrastiveType.PAIRED_CONTRASTIVE.value]
        self.assertGreaterEqual(len(paired), 4)
        for p in paired:
            self.assertTrue(p["preferred_behavior"].get("action"))
            self.assertTrue(p["negative_behavior"].get("action"))

    def test_T_unpaired_example_labeling(self):
        """T. Verifies unpaired negative examples are explicitly marked UNPAIRED."""
        fixtures = self.pipeline.generate_fixture_dataset()
        unpaired = [f for f in fixtures if f.get("contrastive_type") == ContrastiveType.UNPAIRED.value]
        self.assertGreaterEqual(len(unpaired), 1)
        for u in unpaired:
            self.assertEqual(u["preferred_behavior"], {})
            self.assertTrue(u["negative_behavior"].get("action"))

    def test_U_deterministic_split(self):
        """U. Verifies deterministic task-disjoint partition repeatability with seed 42."""
        pipeline_1 = LoRADataPipeline(repo_root=self.repo_root, seed=42)
        pipeline_2 = LoRADataPipeline(repo_root=self.repo_root, seed=42)
        # Verify both pipelines produce identical manifests
        m1 = pipeline_1.run_pipeline(dry_run=True)
        m2 = pipeline_2.run_pipeline(dry_run=True)
        self.assertEqual(m1.dataset_sha256, m2.dataset_sha256)
        self.assertEqual(m1.train_count, m2.train_count)
        self.assertEqual(m1.validation_count, m2.validation_count)

    def test_V_deterministic_dataset_hash(self):
        """V. Verifies deterministic SHA-256 computation on real bytes."""
        h1 = compute_file_sha256(self.pipeline.output_root / "training_contract.json")
        h2 = compute_file_sha256(self.pipeline.output_root / "training_contract.json")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_W_quality_rejection_rules(self):
        """W. Verifies explicit rejection categories for infrastructure-only and ambiguous records."""
        qfilter = QualityFilter()
        infra_ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "evidence_mode": EvidenceMode.INFRASTRUCTURE_ONLY.value,
            "provenance": {"source_name": "s", "license": "MIT", "allowed_for_training": True, "license_status": "PERMITTED"},
            "preferred_behavior": {"action": "run_command"},
        }
        is_acc, _, reasons = qfilter.evaluate_example(infra_ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_INFRASTRUCTURE_ONLY.value, reasons)

    def test_X_fixture_isolation(self):
        """X. Negative test: Verifies that fixture examples cannot enter curated train partition."""
        qfilter = QualityFilter()
        fix_ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "evidence_mode": EvidenceMode.FIXTURE.value,
            "provenance": {"source_name": "s", "license": "MIT", "allowed_for_training": True, "license_status": "PERMITTED"},
            "preferred_behavior": {"action": "run_command"},
        }
        is_acc, _, reasons = qfilter.evaluate_example(fix_ex, is_fixture_allowed=False)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_FIXTURE_ISOLATION.value, reasons)

    def test_Y_no_fabrication_rule(self):
        """Y. Verifies zero fabrication rule: curated train and validation remain count 0 when no live data exists."""
        manifest = self.pipeline.run_pipeline(dry_run=False)
        self.assertEqual(manifest.train_count, 0)
        self.assertEqual(manifest.validation_count, 0)
        self.assertEqual(manifest.dataset_status, DatasetStatus.BLOCKED_BY_DATA.value)

    def test_Z_manifest_generation(self):
        """Z. Verifies dataset_manifest.json and file_manifest.json generation and byte hashes."""
        manifest_path = self.pipeline.manifests_dir / "dataset_manifest.json"
        file_manifest_path = self.pipeline.manifests_dir / "file_manifest.json"
        self.assertTrue(manifest_path.exists())
        self.assertTrue(file_manifest_path.exists())

        with open(file_manifest_path, "r", encoding="utf-8") as f:
            f_map = json.load(f)
            self.assertIn("training_contract.json", f_map)
            self.assertEqual(len(f_map["training_contract.json"]), 64)

    def test_AA_training_contract_validation(self):
        """AA. Verifies training contract links to Stage 39 without guessing hyperparameters."""
        contract = build_stage39_training_contract(repo_root=self.repo_root)
        self.assertEqual(contract.base_model, "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(contract.objective_id, "OBJ-TOOL-DISCIPLINE")
        self.assertEqual(contract.control_candidate, "M0")
        self.assertEqual(contract.candidate_identifier, "L1")
        self.assertEqual(contract.prompt_hash, "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e")
        self.assertEqual(len(contract.tool_contract_hashes), 9)

        d = contract.to_dict()
        self.assertNotIn("learning_rate", d)
        self.assertNotIn("lora_rank", d)
        self.assertNotIn("lora_alpha", d)
        self.assertNotIn("batch_size", d)

    def test_AB_no_training_enforcement(self):
        """AB. Negative test: Verifies that CLI refuses any training command flag."""
        # Suppress stderr during argparse failure test
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with self.assertRaises(SystemExit):
                run_cli(["--train"])
        finally:
            sys.stderr = old_stderr

    def test_neg_01_held_out_rejection(self):
        """Negative test 1: A HELD_OUT example is strictly rejected."""
        checker = HeldOutLeakageChecker(repo_root=self.repo_root)
        leaked, reasons = checker.check_example({"task_id": "requests_6629"})
        self.assertTrue(leaked)
        self.assertTrue(any("LEAKAGE_TASK_ID" in r for r in reasons))

    def test_neg_02_unknown_license_rejection(self):
        """Negative test 2: An unknown-license example is strictly rejected."""
        qfilter = QualityFilter()
        ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "provenance": {
                "source_name": "unknown_src",
                "license": "Custom",
                "allowed_for_training": True,
                "license_status": LicenseStatus.UNKNOWN.value,
            },
            "preferred_behavior": {"action": "run_command"},
            "evidence": ["e1"],
        }
        is_acc, _, reasons = qfilter.evaluate_example(ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_NOT_PERMITTED.value, reasons)

    def test_neg_03_secret_containing_rejection(self):
        """Negative test 3: A secret-containing example is strictly rejected."""
        sanitizer = SecretSanitizer()
        sample = {"situation": "Using secret token sk-abc12345678901234567890 to test."}
        data, is_clean, redactions, reasons = sanitizer.sanitize_example(sample)
        self.assertFalse(is_clean)
        self.assertGreater(len(reasons), 0)

    def test_neg_04_fabricated_trajectory_rejection(self):
        """Negative test 4: A fabricated trajectory without provenance is strictly rejected."""
        qfilter = QualityFilter()
        fab_ex = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "provenance": {},  # Missing provenance
            "preferred_behavior": {"action": "run_command"},
            "evidence": ["e1"],
        }
        is_acc, _, reasons = qfilter.evaluate_example(fab_ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_NO_PROVENANCE.value, reasons)

    def test_neg_05_objective_irrelevant_rejection(self):
        """Negative test 5: An objective-irrelevant example is strictly rejected."""
        qfilter = QualityFilter()
        irrel_ex = {
            "objective_id": "OBJ-PROMPT-OBEDIENCE",
            "provenance": {"source_name": "s", "license": "MIT", "allowed_for_training": True, "license_status": "PERMITTED"},
            "preferred_behavior": {"action": "run_command"},
            "evidence": ["e1"],
        }
        is_acc, _, reasons = qfilter.evaluate_example(irrel_ex)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_OBJECTIVE_MISMATCH.value, reasons)

    def test_neg_06_fixture_in_train_rejection(self):
        """Negative test 6: A fixture example cannot enter TRAIN."""
        qfilter = QualityFilter()
        fix_candidate = {
            "objective_id": "OBJ-TOOL-DISCIPLINE",
            "evidence_mode": EvidenceMode.FIXTURE.value,
            "provenance": {"source_name": "s", "license": "MIT", "allowed_for_training": True, "license_status": "PERMITTED"},
            "preferred_behavior": {"action": "run_command"},
        }
        is_acc, _, reasons = qfilter.evaluate_example(fix_candidate, is_fixture_allowed=False)
        self.assertFalse(is_acc)
        self.assertIn(RejectionReason.REJECT_FIXTURE_ISOLATION.value, reasons)

    def test_neg_07_train_val_silent_overlap_rejection(self):
        """Negative test 7: TRAIN and VALIDATION cannot silently overlap."""
        train_records = [{"example_id": "tr1", "task_id": "shared_task", "split": "TRAIN", "tool_sequence": []}]
        val_records = [{"example_id": "va1", "task_id": "shared_task", "split": "VALIDATION", "tool_sequence": []}]
        is_valid, violations = verify_dataset_split(train_records, val_records)
        self.assertFalse(is_valid)
        self.assertTrue(any("SPLIT_TASK_OVERLAP" in v for v in violations))

    def test_neg_08_cli_training_invocation_rejected(self):
        """Negative test 8: A training command cannot be invoked by the Stage 38 CLI."""
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with self.assertRaises(SystemExit):
                run_cli(["--peft-train"])
        finally:
            sys.stderr = old_stderr


if __name__ == "__main__":
    unittest.main()
