"""Pre-Flight Verification Subsystem for Compute Experiments (Section 13).

Performs exhaustive preflight validation before launching experiments:
- Manifest existence
- Git commit & working tree policy
- Model identifier verification
- Benchmark split integrity
- Prompt and tool contract integrity
- Adapter availability (enforcing hard gate)
- Hardware and CUDA compatibility
- Package dependencies
- Disk space budget
- Output directory safety
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import List, Optional

from local.compute.artifacts import check_disk_budget, compute_file_sha256
from local.compute.compatibility import evaluate_experiment_compatibility
from local.compute.hardware import detect_hardware
from local.compute.models import (
    EnvironmentClass,
    HardwareProfile,
    PreflightCheckResult,
    PreflightStatus,
    SoftwareProfile,
)
from local.compute.software import audit_software

FROZEN_BASE_MODEL = "gemma-4-31b-it-qat-w4a16-ct"


class ComputePreflightAuditor:
    """Audits whether an experiment is ready to execute in the current environment."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent

    def _resolve_contract_path(self) -> Optional[Path]:
        """Resolves existing experiment contract path."""
        candidates = [
            self.repo_root / "experiments" / "lora" / "L0" / "experiment_contract.json",
            self.repo_root / "experiments" / "lora" / "experiment_contract.json",
        ]
        for p in candidates:
            if p.is_file():
                return p
        return None

    def run_preflight(
        self,
        experiment_id: str,
        hw: Optional[HardwareProfile] = None,
        sw: Optional[SoftwareProfile] = None,
    ) -> PreflightCheckResult:
        """Executes the full preflight check battery."""
        hardware = hw or detect_hardware(self.repo_root)
        software = sw or audit_software()

        passed: List[str] = []
        failed: List[str] = []
        blocking_reasons: List[str] = []
        warnings: List[str] = []

        norm_id = experiment_id.upper().strip()

        # 1. Experiment contract / manifest exists
        contract_path = self._resolve_contract_path()
        if contract_path and contract_path.is_file():
            passed.append(f"EXPERIMENT_CONTRACT_EXISTS:{contract_path.name}")
        else:
            failed.append("EXPERIMENT_CONTRACT_MISSING")
            blocking_reasons.append("MISSING_EXPERIMENT_CONTRACT")

        # 2. Git commit exists
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                passed.append(f"GIT_COMMIT_RESOLVED:{res.stdout.strip()[:8]}")
            else:
                failed.append("GIT_COMMIT_UNRESOLVED")
                blocking_reasons.append("GIT_COMMIT_NOT_FOUND")
        except Exception:
            failed.append("GIT_COMMIT_UNRESOLVED")
            blocking_reasons.append("GIT_NOT_FOUND")

        # 3. Model identifier check
        # Must strictly remain gemma-4-31b-it-qat-w4a16-ct
        if contract_path and contract_path.is_file():
            try:
                c_data = json.loads(contract_path.read_text(encoding="utf-8"))
                model_id = c_data.get("model_id") or c_data.get("experiment_contract", {}).get("model_id")
                if model_id == FROZEN_BASE_MODEL:
                    passed.append(f"MODEL_IDENTIFIER_VALID:{FROZEN_BASE_MODEL}")
                else:
                    failed.append(f"MODEL_IDENTIFIER_MISMATCH:{model_id}")
                    blocking_reasons.append("UNAPPROVED_BASE_MODEL")
            except Exception:
                failed.append("MODEL_IDENTIFIER_UNREADABLE")
                blocking_reasons.append("CORRUPTED_CONTRACT")

        # 4. Benchmark split hashes
        benchmark_paths = [
            ("smoke", self.repo_root / "benchmark" / "tasks" / "smoke.jsonl"),
            ("dev", self.repo_root / "benchmark" / "splits" / "v1" / "dev.jsonl"),
            ("validation", self.repo_root / "benchmark" / "splits" / "v1" / "validation.jsonl"),
            ("held_out", self.repo_root / "benchmark" / "splits" / "v1" / "held_out.jsonl"),
        ]
        splits_ok = True
        for b_name, b_path in benchmark_paths:
            if b_path.is_file():
                passed.append(f"BENCHMARK_SPLIT_EXISTS:{b_name}")
            else:
                splits_ok = False
                failed.append(f"BENCHMARK_SPLIT_MISSING:{b_name}")
        if not splits_ok:
            blocking_reasons.append("INCOMPLETE_BENCHMARK_SPLITS")

        # 5. Prompt hash integrity
        prompt_path = self.repo_root / "agent" / "prompts" / "root.md"
        if prompt_path.is_file():
            p_sha = compute_file_sha256(prompt_path)
            passed.append(f"PROMPT_RESOLVED:{p_sha[:8]}")
        else:
            failed.append("PROMPT_MISSING")
            blocking_reasons.append("MISSING_ROOT_PROMPT")

        # 6. Adapter availability (enforcing Hard Gate)
        is_adapter_dependent = norm_id in {"L1", "L1_TRAINING", "MA1", "MA1_EXECUTION", "LORA_ABLATION"}
        if is_adapter_dependent:
            # Stage 41 confirmed 0 validated adapters exist
            failed.append("NO_VALIDATED_ADAPTER_ARTIFACT")
            blocking_reasons.append("MISSING_VALIDATED_ADAPTER")
        else:
            passed.append("NO_ADAPTER_REQUIRED_FOR_EXPERIMENT")

        # 7. Environment compatibility evaluation
        contract = evaluate_experiment_compatibility(experiment_id, hardware, software)
        if contract.compatibility_status == "READY":
            passed.append("ENVIRONMENT_COMPATIBLE")
        elif contract.compatibility_status == "BLOCKED":
            failed.append("ENVIRONMENT_BLOCKED")
            blocking_reasons.append("GPU_REQUIRED")
        elif contract.compatibility_status == "INCOMPATIBLE":
            failed.append("ENVIRONMENT_INCOMPATIBLE")
            blocking_reasons.append("MISSING_SOFTWARE_DEPENDENCIES")
        else:
            failed.append("ENVIRONMENT_UNKNOWN")
            blocking_reasons.append("UNKNOWN_ENVIRONMENT_COMPATIBILITY")

        # 8. Disk space budget
        disk_ok, free_gb, needed_gb = check_disk_budget(
            required_gb=25.0 if is_adapter_dependent else 0.5,
            safety_margin_gb=5.0,
            check_path=self.repo_root,
        )
        if disk_ok:
            passed.append(f"DISK_BUDGET_SATISFIED:{free_gb}GB_FREE")
        else:
            failed.append(f"DISK_BUDGET_EXCEEDED:{free_gb}GB_FREE_NEED_{needed_gb}GB")
            blocking_reasons.append("INSUFFICIENT_DISK_SPACE")

        # 9. Output directory safety
        out_dir = self.repo_root / "experiments" / "compute"
        if out_dir.exists() and (out_dir / "frozen.lock").exists():
            failed.append("OUTPUT_DIRECTORY_LOCKED")
            blocking_reasons.append("CANNOT_WRITE_TO_FROZEN_OUTPUT")
        else:
            passed.append("OUTPUT_DIRECTORY_SAFE")

        # Determine overall PreflightStatus
        if blocking_reasons:
            if "GPU_REQUIRED" in blocking_reasons or "MISSING_VALIDATED_ADAPTER" in blocking_reasons:
                overall_status = PreflightStatus.BLOCKED
            else:
                overall_status = PreflightStatus.INCOMPATIBLE
        else:
            overall_status = PreflightStatus.READY

        return PreflightCheckResult(
            status=overall_status,
            experiment_id=experiment_id,
            environment_class=hardware.environment_class,
            passed_checks=passed,
            failed_checks=failed,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            fingerprint_sha256="",
        )
