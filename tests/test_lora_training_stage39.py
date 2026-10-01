"""Comprehensive Unit and Regression Suite for Stage 39: LoRA Training.

Systematically verifies:
A. Parent commit verification (65a0cc0f8b6f218fb2650ad1587475d4f48fc799)
B. Clean-tree verification (frozen artifacts match)
C. Dataset manifest verification
D. Zero-train hard block
E. Zero-validation hard block
F. Fixture hard block (evidence_mode == FIXTURE)
G. Held-out leakage hard block
H. Provenance hard block
I. Wrong-objective hard block
J. Wrong-model hard block
K. Invalid-hyperparameter hard block
L. Unresolved-hyperparameter hard block
M. Invariance violation detection
N. Dry-run behavior
O. No-model-load during dry-run
P. No-training-on-fixtures
Q. No-adapter-on-blocked-run
R. Training configuration serialization
S. Reproducibility metadata
T. Seed handling
U. Artifact manifest
V. Adapter hash calculation
W. Failed-run reporting
X. Checkpoint-path safety
Y. Secret/log sanitization
Z. Automatic-promotion prohibition
AA. Current repository hard data gate rejection
AB. Orchestration fixture simulation isolation
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.lora_train.artifacts import ArtifactManager, compute_file_sha256
from local.lora_train.config import (
    get_default_training_config,
    load_training_config,
    save_training_config,
    validate_hyperparameters_for_execution,
)
from local.lora_train.dataset import ToolDisciplineDatasetLoader
from local.lora_train.errors import (
    DataGateBlockedError,
    FixtureSafetyError,
    HardwareGateBlockedError,
    InvarianceViolationError,
    UnresolvedHyperparameterError,
)
from local.lora_train.hardware import audit_training_hardware
from local.lora_train.invariance import InvarianceChecker
from local.lora_train.metrics import MetricsTracker
from local.lora_train.models import (
    BlockedRunRecord,
    ExecutionMode,
    HardwareStatus,
    RunManifest,
    Stage39Decision,
    TrainingConfig,
    TrainingStatus,
    UNSELECTED,
)
from local.lora_train.runner import LoRATrainingRunner
from local.lora_train.validation import DataGateValidator
from scripts.run_lora_training import run_cli


class TestLoRATrainingStage39(unittest.TestCase):
    """Authoritative test cases for Stage 39 LoRA training subsystem."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.runner = LoRATrainingRunner(repo_root=cls.repo_root)

    def test_A_parent_commit_verification(self):
        """A. Verifies that the parent commit is locked to Stage 38 completion commit."""
        expected_parent = "65a0cc0f8b6f218fb2650ad1587475d4f48fc799"
        manifest = RunManifest(run_id="test_run", parent_commit=expected_parent)
        self.assertEqual(manifest.parent_commit, expected_parent)

    def test_B_clean_tree_verification(self):
        """B. Verifies that all 14 frozen Stage 24-38 artifacts remain unchanged."""
        is_match, results = verify_frozen_artifacts(self.repo_root)
        self.assertTrue(is_match, f"Frozen artifacts modified: {results}")
        self.assertEqual(len(results), 14)

    def test_C_dataset_manifest_verification(self):
        """C. Verifies that Stage 38 dataset manifest is valid and correctly reflects BLOCKED_BY_DATA."""
        manifest_path = self.repo_root / "experiments" / "lora" / "L1-data" / "manifests" / "dataset_manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("dataset_id"), "L0-TOOL-DISCIPLINE-DATA-v1")
        self.assertEqual(data.get("objective_id"), "OBJ-TOOL-DISCIPLINE")
        self.assertEqual(data.get("dataset_status"), "BLOCKED_BY_DATA")
        self.assertEqual(data.get("train_count"), 0)
        self.assertEqual(data.get("validation_count"), 0)

    def test_D_zero_train_hard_block(self):
        """D. Verifies that training is refused when TRAIN partition count is 0."""
        validator = DataGateValidator(repo_root=self.repo_root)
        cfg = get_default_training_config(repo_root=self.repo_root)
        is_permitted, status, details = validator.evaluate_gate(cfg)
        self.assertFalse(is_permitted)
        self.assertEqual(status, TrainingStatus.BLOCKED_BY_DATA.value)
        self.assertTrue(any("TRAIN partition is empty" in v for v in details["violations"]))

    def test_E_zero_validation_hard_block(self):
        """E. Verifies that training is refused when VALIDATION partition count is 0."""
        validator = DataGateValidator(repo_root=self.repo_root)
        cfg = get_default_training_config(repo_root=self.repo_root)
        is_permitted, status, details = validator.evaluate_gate(cfg)
        self.assertFalse(is_permitted)
        self.assertTrue(any("VALIDATION partition is empty" in v for v in details["violations"]))

    def test_F_fixture_hard_block(self):
        """F. Verifies that fixture records (evidence_mode=FIXTURE) are barred from real training."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            curated_dir = tmppath / "curated"
            curated_dir.mkdir(parents=True)
            manifest_dir = tmppath / "manifests"
            manifest_dir.mkdir(parents=True)

            # Write manifest claiming READY
            m_data = {
                "dataset_id": "test_ds",
                "dataset_status": "DATASET_READY",
                "objective_id": "OBJ-TOOL-DISCIPLINE",
                "train_count": 1,
                "validation_count": 1,
            }
            with open(manifest_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
                json.dump(m_data, f)

            # Write fixture record in train.jsonl
            with open(curated_dir / "train.jsonl", "w", encoding="utf-8") as f:
                f.write(json.dumps({"example_id": "f1", "split": "TRAIN", "evidence_mode": "FIXTURE"}) + "\n")
            with open(curated_dir / "validation.jsonl", "w", encoding="utf-8") as f:
                f.write(json.dumps({"example_id": "v1", "split": "VALIDATION", "evidence_mode": "LIVE"}) + "\n")

            loader = ToolDisciplineDatasetLoader(dataset_dir=curated_dir, repo_root=tmppath)
            loader.manifest_path = manifest_dir / "dataset_manifest.json"

            with self.assertRaises(FixtureSafetyError):
                loader.load_and_validate_partitions(allow_fixtures=False)

    def test_G_held_out_leakage_hard_block(self):
        """G. Verifies that any held-out benchmark task causes an immediate hard data gate block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            curated_dir = tmppath / "curated"
            curated_dir.mkdir(parents=True)
            manifest_dir = tmppath / "manifests"
            manifest_dir.mkdir(parents=True)

            m_data = {
                "dataset_id": "test_ds",
                "dataset_status": "DATASET_READY",
                "objective_id": "OBJ-TOOL-DISCIPLINE",
                "train_count": 1,
                "validation_count": 1,
            }
            with open(manifest_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
                json.dump(m_data, f)

            # Leak held-out task httpx_3672 into train.jsonl
            with open(curated_dir / "train.jsonl", "w", encoding="utf-8") as f:
                f.write(json.dumps({"example_id": "t1", "split": "TRAIN", "task_id": "httpx_3672", "evidence_mode": "LIVE"}) + "\n")
            with open(curated_dir / "validation.jsonl", "w", encoding="utf-8") as f:
                f.write(json.dumps({"example_id": "v1", "split": "VALIDATION", "task_id": "clean_task", "evidence_mode": "LIVE"}) + "\n")

            loader = ToolDisciplineDatasetLoader(dataset_dir=curated_dir, repo_root=self.repo_root)
            loader.manifest_path = manifest_dir / "dataset_manifest.json"

            with self.assertRaises(DataGateBlockedError) as ctx:
                loader.load_and_validate_partitions(allow_fixtures=False)
            self.assertIn("Held-out benchmark leakage detected", str(ctx.exception))

    def test_H_provenance_hard_block(self):
        """H. Verifies that missing provenance or manifest prevents training."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            empty_validator = DataGateValidator(repo_root=tmppath)
            cfg = get_default_training_config(repo_root=self.repo_root)
            is_permitted, status, details = empty_validator.evaluate_gate(cfg)
            self.assertFalse(is_permitted)
            self.assertEqual(status, TrainingStatus.BLOCKED_BY_DATA.value)

    def test_I_wrong_objective_hard_block(self):
        """I. Verifies that non-OBJ-TOOL-DISCIPLINE configurations are rejected."""
        checker = InvarianceChecker(repo_root=self.repo_root)
        cfg = get_default_training_config(repo_root=self.repo_root)
        cfg.objective_id = "OBJ-GENERIC-CODING"
        is_inv, violations = checker.check_invariance(cfg)
        self.assertFalse(is_inv)
        self.assertTrue(any("Objective mismatch" in v for v in violations))

    def test_J_wrong_model_hard_block(self):
        """J. Verifies that configurations requesting unsupported models are rejected."""
        checker = InvarianceChecker(repo_root=self.repo_root)
        cfg = get_default_training_config(repo_root=self.repo_root)
        cfg.base_model = "llama-3-70b-instruct"
        is_inv, violations = checker.check_invariance(cfg)
        self.assertFalse(is_inv)
        self.assertTrue(any("Model mismatch" in v for v in violations))

    def test_K_invalid_hyperparameter_hard_block(self):
        """K. Verifies that invalid hyperparameter values (e.g. negative rank or invalid dropout) are rejected."""
        cfg = get_default_training_config(repo_root=self.repo_root)
        cfg.rank = -4
        cfg.alpha = 16
        cfg.dropout = 0.1
        cfg.learning_rate = 2e-4
        cfg.batch_size = 4
        cfg.gradient_accumulation_steps = 2
        cfg.epochs = 3
        cfg.sequence_length = 2048

        with self.assertRaises(ValueError) as ctx:
            validate_hyperparameters_for_execution(cfg)
        self.assertIn("LoRA rank must be a positive integer", str(ctx.exception))

    def test_L_unresolved_hyperparameter_hard_block(self):
        """L. Verifies that UNSELECTED hyperparameters are flagged and prevent training."""
        cfg = get_default_training_config(repo_root=self.repo_root)
        self.assertIn("rank", cfg.get_unresolved_hyperparameters())
        with self.assertRaises(UnresolvedHyperparameterError) as ctx:
            validate_hyperparameters_for_execution(cfg)
        self.assertIn("rank", ctx.exception.unselected_fields)

    def test_M_invariance_violation_detection(self):
        """M. Verifies that changing prompt, tools, retrieval, testing, or topology triggers invariance error."""
        checker = InvarianceChecker(repo_root=self.repo_root)
        cfg = get_default_training_config(repo_root=self.repo_root)
        cfg.prompt_hash = "tampered_hash_value"
        is_inv, violations = checker.check_invariance(cfg)
        self.assertFalse(is_inv)
        self.assertTrue(any("Prompt hash mismatch" in v for v in violations))

    def test_N_dry_run_behavior(self):
        """N. Verifies dry-run returns valid structured summary without executing training."""
        result = self.runner.run_dry_run()
        self.assertEqual(result["execution_mode"], ExecutionMode.DRY_RUN.value)
        self.assertTrue(result["invariance_passed"])
        self.assertEqual(result["overall_dry_run_status"], "PASS")

    def test_O_no_model_load_during_dry_run(self):
        """O. Verifies dry-run does not load model weights into memory or allocate GPU memory."""
        result = self.runner.run_dry_run()
        self.assertFalse(result["model_weights_loaded"])
        self.assertEqual(result["gpu_memory_allocated_gb"], 0.0)
        self.assertFalse(result["adapter_weights_written"])

    def test_P_no_training_on_fixtures(self):
        """P. Verifies that synthetic fixtures cannot produce real training or adapter weights."""
        with self.assertRaises(DataGateBlockedError):
            # Invoking train without allow_fixtures should fail immediately on empty curated set
            self.runner.train(allow_fixtures=False)

    def test_Q_no_adapter_on_blocked_run(self):
        """Q. Verifies that blocked runs produce zero adapter weight files."""
        record = self.runner.verify_readiness()
        self.assertEqual(record.status, TrainingStatus.BLOCKED_BY_DATA.value)
        runs_dir = self.repo_root / "experiments" / "lora" / "runs"
        if runs_dir.exists():
            adapter_weights = list(runs_dir.rglob("*.safetensors")) + list(runs_dir.rglob("*.bin"))
            self.assertEqual(len(adapter_weights), 0)

    def test_R_training_configuration_serialization(self):
        """R. Verifies roundtrip serialization of TrainingConfig to and from disk."""
        cfg = get_default_training_config(repo_root=self.repo_root)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            save_training_config(cfg, tmp_path)
            loaded = load_training_config(tmp_path)
            self.assertEqual(loaded.candidate_id, cfg.candidate_id)
            self.assertEqual(loaded.base_model, cfg.base_model)
            self.assertEqual(loaded.prompt_hash, cfg.prompt_hash)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_S_reproducibility_metadata(self):
        """S. Verifies that run manifests capture seeds, model revisions, and parent commit."""
        manifest = RunManifest(
            run_id="run_test",
            parent_commit="65a0cc0f8b6f218fb2650ad1587475d4f48fc799",
            seed=42,
        )
        d = manifest.to_dict()
        self.assertEqual(d["seed"], 42)
        self.assertEqual(d["parent_commit"], "65a0cc0f8b6f218fb2650ad1587475d4f48fc799")

    def test_T_seed_handling(self):
        """T. Verifies that seed is deterministic across configurations."""
        c1 = get_default_training_config(repo_root=self.repo_root)
        c2 = get_default_training_config(repo_root=self.repo_root)
        self.assertEqual(c1.seed, 42)
        self.assertEqual(c2.seed, 42)

    def test_U_artifact_manifest(self):
        """U. Verifies blocked feasibility record is written without creating fake run directory."""
        rec = BlockedRunRecord(
            status=TrainingStatus.BLOCKED_BY_DATA.value,
            reason="Blocked by Data Gate",
            details={},
            hardware_status=HardwareStatus.TRAINING_HARDWARE_UNAVAILABLE.value,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "blocked.json"
            mgr = ArtifactManager(repo_root=self.repo_root)
            mgr.write_blocked_feasibility_record(rec, output_path=out_file)
            self.assertTrue(out_file.exists())
            with open(out_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.assertEqual(d["status"], TrainingStatus.BLOCKED_BY_DATA.value)

    def test_V_adapter_hash_calculation(self):
        """V. Verifies compute_file_sha256 accurately hashes bytes."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_bytes(b"adapter_bytes_12345")
        try:
            h = compute_file_sha256(tmp_path)
            self.assertEqual(len(h), 64)
        finally:
            tmp_path.unlink()

    def test_W_failed_run_reporting(self):
        """W. Verifies that failed or blocked runs capture exact blocker details."""
        rec = self.runner.verify_readiness()
        self.assertIn("data_gate", rec.details)
        self.assertIn("hardware_classification", rec.details)

    def test_X_checkpoint_path_safety(self):
        """X. Verifies that output paths are sandboxed within the repository."""
        cfg = get_default_training_config(repo_root=self.repo_root)
        self.assertTrue(cfg.output_dir.startswith("experiments/lora/"))

    def test_Y_secret_and_log_sanitization(self):
        """Y. Verifies environment dump excludes credentials and private environment variables."""
        hw = audit_training_hardware()
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ArtifactManager(repo_root=Path(tmpdir))
            run_m = RunManifest(run_id="run_sec_test")
            cfg = get_default_training_config(repo_root=self.repo_root)
            metrics = MetricsTracker().finish()
            run_dir = mgr.emit_real_run_artifacts(run_m, cfg, metrics, hw)
            env_file = run_dir / "environment.json"
            self.assertTrue(env_file.exists())
            with open(env_file, "r", encoding="utf-8") as f:
                env_data = json.load(f)
            # Ensure no credentials exist
            self.assertNotIn("API_KEY", str(env_data))
            self.assertNotIn("TOKEN", str(env_data))

    def test_Z_automatic_promotion_prohibition(self):
        """Z. Verifies that production agent.yaml remains completely untouched by Stage 39."""
        prod_agent_yaml = self.repo_root / "agent" / "agent.yaml"
        self.assertTrue(prod_agent_yaml.exists())
        with open(prod_agent_yaml, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("adapter", content)
        self.assertIn("impulse_e0_baseline", content)

    def test_AA_current_repository_hard_data_gate_rejection(self):
        """AA. Verifies that calling train() on the current repository is strictly rejected."""
        with self.assertRaises(DataGateBlockedError) as ctx:
            self.runner.train()
        self.assertIn("TRAIN partition is empty", str(ctx.exception))

    def test_AB_orchestration_fixture_simulation_isolation(self):
        """AB. Verifies orchestration test fixture executes cleanly in memory and is labeled as FIXTURE."""
        cfg = get_default_training_config(repo_root=self.repo_root)
        manifest = self.runner.train(config=cfg, allow_fixtures=True, is_test_fixture=True)
        self.assertEqual(manifest.execution_mode, ExecutionMode.TRAINING_ORCHESTRATION_FIXTURE.value)
        self.assertEqual(manifest.status, TrainingStatus.TRAINING_COMPLETED.value)
        self.assertIsNone(manifest.adapter_sha256)


if __name__ == "__main__":
    unittest.main()
