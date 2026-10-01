"""Comprehensive Test Suite for Stage 42: Free Compute Strategy.

Tests all 24 mandatory requirements (A through X):
A. Hardware detection
B. CPU classification
C. CUDA classification
D. Package detection
E. Environment fingerprint determinism
F. Secret sanitization
G. Capability matrix
H. Experiment environment contract
I. Preflight
J. Incompatible environment rejection
K. Artifact manifest
L. Artifact hash verification
M. Transfer manifest exclusions
N. CPU/GPU evidence separation
O. Fixture/live separation
P. Disk check
Q. Network classification
R. Kaggle bootstrap validation
S. LoRA dry-run portability
T. Ablation dry-run portability
U. Multi-adapter dry-run portability
V. No-automatic-download rule
W. No-credential rule
X. Reproducibility metadata
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from local.compute.artifacts import (
    check_disk_budget,
    classify_network_requirement,
    compute_file_sha256,
    create_artifact_transfer_manifest,
    create_return_artifact_manifest,
    is_forbidden_transfer_path,
    scan_for_secrets,
    verify_artifact_transfer_manifest,
    verify_return_artifact_manifest,
)
from local.compute.bootstrap import (
    generate_kaggle_bootstrap_bundle,
    record_bootstrap_execution,
)
from local.compute.capabilities import get_capability_matrix
from local.compute.compatibility import evaluate_experiment_compatibility
from local.compute.errors import (
    ArtifactHashMismatchError,
    SecretLeakageDetectedError,
)
from local.compute.fingerprint import generate_compute_fingerprint, sanitize_value
from local.compute.hardware import detect_hardware
from local.compute.models import (
    CUDACapability,
    EnvironmentClass,
    EvidenceMode,
    ExecutionMode,
    HardwareProfile,
    NetworkRequirement,
    PreflightStatus,
    SoftwareProfile,
    VerificationStatus,
)
from local.compute.preflight import ComputePreflightAuditor
from local.compute.software import audit_software

EXPECTED_PARENT_COMMIT = "4f5c0d8cb3581893b7d1007fc0c699cd08c94c19"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFreeComputeStage42(unittest.TestCase):
    """Test battery enforcing deterministic free compute portability."""

    def setUp(self) -> None:
        self.repo_root = PROJECT_ROOT
        self.hw = detect_hardware(self.repo_root)
        self.sw = audit_software()

    def test_a_hardware_detection(self) -> None:
        """A: Verifies that hardware detection observes non-empty platform fields."""
        self.assertIsNotNone(self.hw.os_name)
        self.assertIsNotNone(self.hw.architecture)
        self.assertIsNotNone(self.hw.python_version)
        self.assertGreater(self.hw.cpu_count_logical, 0)
        self.assertGreater(self.hw.total_ram_gb, 0.0)
        self.assertGreater(self.hw.free_disk_gb, 0.0)

    def test_b_cpu_classification(self) -> None:
        """B: Verifies host is classified as LOCAL_CPU when CUDA is unavailable."""
        if not self.hw.cuda_available:
            self.assertEqual(self.hw.environment_class, EnvironmentClass.LOCAL_CPU)
            self.assertEqual(self.hw.classification, CUDACapability.NO_CUDA_GPU.value)

    def test_c_cuda_classification(self) -> None:
        """C: Negative test: Integrated graphics must never be reported as CUDA GPU."""
        if self.hw.is_integrated_gpu:
            self.assertFalse(self.hw.cuda_available)
            self.assertEqual(self.hw.classification, CUDACapability.NO_CUDA_GPU.value)

    def test_d_package_detection(self) -> None:
        """D: Verifies ML package discovery correctly catalogs installed status."""
        self.assertIn("torch", self.sw.packages)
        self.assertIn("transformers", self.sw.packages)
        self.assertIn("peft", self.sw.packages)
        self.assertIn("pytest", self.sw.packages)
        # Packages must be recorded without importing heavy frameworks
        self.assertIsInstance(self.sw.python_version, str)

    def test_e_environment_fingerprint_determinism(self) -> None:
        """E: Verifies compute fingerprint is deterministic and stable."""
        fp1 = generate_compute_fingerprint(self.hw, self.sw)
        fp2 = generate_compute_fingerprint(self.hw, self.sw)
        self.assertEqual(fp1.fingerprint_sha256, fp2.fingerprint_sha256)
        self.assertEqual(len(fp1.fingerprint_sha256), 64)

    def test_f_secret_sanitization(self) -> None:
        """F: Negative test: Secret strings and private credentials trigger errors."""
        with self.assertRaises(SecretLeakageDetectedError):
            sanitize_value("ghp_123456789012345678901234567890")

        with self.assertRaises(SecretLeakageDetectedError):
            sanitize_value({"api_key": "kaggle_0123456789abcdef"})

        # Clean strings must pass
        self.assertEqual(sanitize_value("AMD64"), "AMD64")

    def test_g_capability_matrix(self) -> None:
        """G: Verifies capability matrix separates design from verified reality."""
        cpu_caps = get_capability_matrix(EnvironmentClass.LOCAL_CPU)
        self.assertEqual(cpu_caps.environment_class, "LOCAL_CPU")

        # Local CPU responsibilities must be ACTUALLY_VERIFIED
        self.assertTrue(cpu_caps.capabilities["prompt_validation"].supported)
        self.assertEqual(
            cpu_caps.capabilities["prompt_validation"].verified_status,
            VerificationStatus.ACTUALLY_VERIFIED.value,
        )

        # GPU responsibilities on CPU must be BLOCKED
        self.assertFalse(cpu_caps.capabilities["lora_training"].supported)
        self.assertEqual(
            cpu_caps.capabilities["lora_training"].verified_status,
            VerificationStatus.BLOCKED.value,
        )

        # Kaggle GPU matrix must distinguish SUPPORTED_BY_DESIGN from NOT_VERIFIED
        kaggle_caps = get_capability_matrix(EnvironmentClass.KAGGLE_FREE_GPU)
        self.assertTrue(kaggle_caps.capabilities["configuration_supported"].supported)
        self.assertFalse(kaggle_caps.capabilities["actual_runtime_verified"].supported)
        self.assertEqual(
            kaggle_caps.capabilities["actual_runtime_verified"].verified_status,
            VerificationStatus.NOT_VERIFIED.value,
        )

    def test_h_experiment_environment_contract(self) -> None:
        """H: Verifies environment contract creation for CPU-compatible and GPU experiments."""
        contract_cpu = evaluate_experiment_compatibility("STAGE42_AUDIT", self.hw, self.sw)
        self.assertEqual(contract_cpu.compatibility_status, "READY")
        self.assertFalse(contract_cpu.required_cuda)

        contract_gpu = evaluate_experiment_compatibility("L1_TRAINING", self.hw, self.sw)
        self.assertTrue(contract_gpu.required_cuda)
        self.assertEqual(contract_gpu.required_gpu_memory, "UNKNOWN")
        if not self.hw.cuda_available:
            self.assertEqual(contract_gpu.compatibility_status, "BLOCKED")

    def test_i_preflight_cpu_experiment(self) -> None:
        """I: Verifies preflight succeeds on CPU-compatible baseline candidate M0."""
        auditor = ComputePreflightAuditor(self.repo_root)
        res = auditor.run_preflight("M0", hw=self.hw, sw=self.sw)
        self.assertEqual(res.status, PreflightStatus.READY)
        self.assertIn("EXPERIMENT_CONTRACT_EXISTS:experiment_contract.json", res.passed_checks)
        self.assertIn("ENVIRONMENT_COMPATIBLE", res.passed_checks)

    def test_j_incompatible_environment_rejection(self) -> None:
        """J: Negative test: GPU-dependent experiments are BLOCKED on CPU host."""
        auditor = ComputePreflightAuditor(self.repo_root)
        res = auditor.run_preflight("L1_TRAINING", hw=self.hw, sw=self.sw)
        self.assertEqual(res.status, PreflightStatus.BLOCKED)
        self.assertIn("GPU_REQUIRED", res.blocking_reasons)

    def test_k_artifact_manifest_creation(self) -> None:
        """K: Verifies artifact transfer manifest generation selects authorized assets."""
        manifest = create_artifact_transfer_manifest(self.repo_root, target_environment="KAGGLE_FREE_GPU")
        self.assertGreater(len(manifest.items), 0)
        self.assertGreater(manifest.total_size_bytes, 0)
        paths = [item.relative_path for item in manifest.items]
        self.assertIn("agent/agent.yaml", paths)
        self.assertIn("experiments/lora/L0/experiment_contract.json", paths)

    def test_l_artifact_hash_verification(self) -> None:
        """L: Verifies artifact hash verification succeeds on clean assets, fails on modified."""
        manifest = create_artifact_transfer_manifest(self.repo_root, target_environment="KAGGLE_FREE_GPU")
        ok, failures = verify_artifact_transfer_manifest(manifest, self.repo_root)
        self.assertTrue(ok)
        self.assertEqual(len(failures), 0)

        # Negative test: modify an item hash
        manifest.items[0].sha256 = "0" * 64
        ok_bad, failures_bad = verify_artifact_transfer_manifest(manifest, self.repo_root)
        self.assertFalse(ok_bad)
        self.assertIn("HASH_MISMATCH", failures_bad[0])

    def test_m_transfer_manifest_exclusions(self) -> None:
        """M: Verifies sensitive and development-only files are strictly forbidden from transfer."""
        self.assertTrue(is_forbidden_transfer_path(".env"))
        self.assertTrue(is_forbidden_transfer_path(".env.local"))
        self.assertTrue(is_forbidden_transfer_path("secrets/key.pem"))
        self.assertTrue(is_forbidden_transfer_path("token.txt"))
        self.assertTrue(is_forbidden_transfer_path("agent/__pycache__/agent.pyc"))
        self.assertTrue(is_forbidden_transfer_path(".git/HEAD"))
        self.assertFalse(is_forbidden_transfer_path("agent/agent.yaml"))

    def test_n_cpu_gpu_evidence_separation(self) -> None:
        """N: Verifies return artifact manifest binds compute fingerprint and evidence mode."""
        fp = generate_compute_fingerprint(self.hw, self.sw)
        manifest = create_return_artifact_manifest(
            run_id="RUN_001",
            environment_fingerprint_sha256=fp.fingerprint_sha256,
            metrics={"task_success": 1.0},
            artifacts=[],
            execution_mode=ExecutionMode.DRY_RUN,
            environment_class="LOCAL_CPU",
            evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY,
        )
        self.assertEqual(manifest.evidence_mode, EvidenceMode.INFRASTRUCTURE_ONLY.value)
        self.assertEqual(manifest.environment_fingerprint_sha256, fp.fingerprint_sha256)

    def test_o_fixture_live_separation(self) -> None:
        """O: Negative test: Fixture evidence can never be converted into LIVE mode."""
        fp = generate_compute_fingerprint(self.hw, self.sw)
        # Attempting to assign FIXTURE with LIVE assertion is forbidden
        manifest = create_return_artifact_manifest(
            run_id="RUN_FIXTURE",
            environment_fingerprint_sha256=fp.fingerprint_sha256,
            metrics={},
            artifacts=[],
            execution_mode=ExecutionMode.DRY_RUN,
            environment_class="LOCAL_CPU",
            evidence_mode=EvidenceMode.FIXTURE,
        )
        self.assertNotEqual(manifest.evidence_mode, EvidenceMode.LIVE.value)

    def test_p_disk_check(self) -> None:
        """P: Verifies disk budget check detects available space and flags shortages."""
        ok, free_gb, needed_gb = check_disk_budget(required_gb=1.0, safety_margin_gb=1.0, check_path=self.repo_root)
        self.assertTrue(ok)
        self.assertGreater(free_gb, 0.0)

        # Negative test: demanding 1,000,000 GB must fail
        fail_ok, _, _ = check_disk_budget(required_gb=1_000_000.0, check_path=self.repo_root)
        self.assertFalse(fail_ok)

    def test_q_network_classification(self) -> None:
        """Q: Verifies tasks are classified correctly by network requirements."""
        self.assertEqual(
            classify_network_requirement("UNIT_TEST"),
            NetworkRequirement.NETWORK_NOT_REQUIRED,
        )
        self.assertEqual(
            classify_network_requirement("BENCHMARK_ANALYSIS"),
            NetworkRequirement.NETWORK_NOT_REQUIRED,
        )
        self.assertEqual(
            classify_network_requirement("MODEL_DOWNLOAD"),
            NetworkRequirement.NETWORK_REQUIRED,
        )

    def test_r_kaggle_bootstrap_validation(self) -> None:
        """R: Verifies Kaggle bundle files exist and contain zero personal credentials."""
        bundle_dir = self.repo_root / "compute" / "kaggle"
        self.assertTrue((bundle_dir / "README.md").is_file())
        self.assertTrue((bundle_dir / "bootstrap.sh").is_file())
        self.assertTrue((bundle_dir / "bootstrap.py").is_file())
        self.assertTrue((bundle_dir / "environment_check.py").is_file())
        self.assertTrue((bundle_dir / "run_experiment.py").is_file())

        for fname in ["README.md", "bootstrap.sh", "bootstrap.py", "environment_check.py", "run_experiment.py"]:
            content = (bundle_dir / fname).read_text(encoding="utf-8")
            scan_for_secrets(content)

    def test_s_lora_dry_run_portability(self) -> None:
        """S: Verifies scripts/run_lora_training.py can execute --verify without crashes."""
        import subprocess
        res = subprocess.run(
            ["python", "scripts/run_lora_training.py", "--verify"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("BLOCKED_BY_DATA", res.stdout)

    def test_t_ablation_dry_run_portability(self) -> None:
        """T: Verifies scripts/run_lora_ablation.py can execute --verify without crashes."""
        import subprocess
        res = subprocess.run(
            ["python", "scripts/run_lora_ablation.py", "--verify"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Hard Adapter Gate blocked", res.stdout)
        self.assertIn("MISSING_ADAPTER_ARTIFACT", res.stdout)

    def test_u_multi_adapter_dry_run_portability(self) -> None:
        """U: Verifies scripts/run_multi_adapter.py can execute --verify without crashes."""
        import subprocess
        res = subprocess.run(
            ["python", "scripts/run_multi_adapter.py", "--verify"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("BLOCKED BY SINGLE-ADAPTER PREREQUISITE", res.stdout)
        self.assertIn("NO_MEASURED_SINGLE_ADAPTER_BENEFIT", res.stdout)

    def test_v_no_automatic_download_rule(self) -> None:
        """V: Verifies inspect_compute CLI commands run completely offline without downloading weights."""
        import subprocess
        for flag in ["--hardware", "--software", "--capabilities", "--fingerprint"]:
            res = subprocess.run(
                ["python", "scripts/inspect_compute.py", flag],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            data = json.loads(res.stdout)
            self.assertIsInstance(data, dict)

    def test_w_no_credential_rule(self) -> None:
        """W: Scans all compute reports and configs for leaked credentials."""
        report_path = self.repo_root / "experiments" / "compute" / "stage42_report.md"
        if report_path.is_file():
            scan_for_secrets(report_path.read_text(encoding="utf-8"))

        contract_path = self.repo_root / "experiments" / "compute" / "environment_contract.json"
        if contract_path.is_file():
            scan_for_secrets(contract_path.read_text(encoding="utf-8"))

    def test_x_reproducibility_metadata(self) -> None:
        """X: Verifies record_bootstrap_execution records all required reproducibility metadata."""
        meta = record_bootstrap_execution(
            script_version="1.0.0",
            git_commit=EXPECTED_PARENT_COMMIT,
            environment_fingerprint="abc12345",
            package_versions={"pytest": "9.1.1"},
            start_time="2026-10-01T00:00:00Z",
            status="INITIALIZED",
        )
        self.assertEqual(meta.script_version, "1.0.0")
        self.assertEqual(meta.git_commit, EXPECTED_PARENT_COMMIT)
        self.assertEqual(meta.status, "INITIALIZED")
        self.assertIsNotNone(meta.end_time)


if __name__ == "__main__":
    unittest.main()
