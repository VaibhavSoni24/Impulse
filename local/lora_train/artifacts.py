"""Artifact and Run Manifest Management for Stage 39 LoRA Training (Section 18, 19, 20).

Handles:
1. Real run artifact emission under `experiments/lora/runs/<run_id>/`:
   - manifest.json
   - config.json
   - dataset_manifest.json
   - environment.json
   - metrics.json
   - checkpoints/
   - logs/
   - report.md
2. Blocked run reporting (prevents creating fake run directories when training is blocked)
3. Cryptographic checksums (SHA-256) of adapter weights and checkpoints
4. Security sanitization: strips credentials, .env values, and host user tokens
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.lora_train.models import (
    BlockedRunRecord,
    HardwareAuditReport,
    RunManifest,
    TrainingConfig,
    TrainingMetrics,
    TrainingStatus,
)


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file's raw bytes."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_directory_manifest(dir_path: Path) -> dict[str, str]:
    """Generates relative path to SHA-256 map for all files within dir_path."""
    manifest: dict[str, str] = {}
    if not dir_path.exists():
        return manifest

    for p in sorted(dir_path.rglob("*")):
        if p.is_file():
            rel_path = p.relative_to(dir_path).as_posix()
            manifest[rel_path] = compute_file_sha256(p)

    return manifest


class ArtifactManager:
    """Manages training checkpoints, adapter configurations, and run manifests."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.runs_root = self.repo_root / "experiments" / "lora" / "runs"

    def write_blocked_feasibility_record(
        self, blocked_record: BlockedRunRecord, output_path: Optional[Path] = None
    ) -> Path:
        """Writes a blocked execution record without creating a false run directory."""
        dest = output_path or (
            self.repo_root / "experiments" / "lora" / "blocked_run_record.json"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(blocked_record.to_dict(), f, indent=2, sort_keys=True)
        return dest

    def emit_real_run_artifacts(
        self,
        run_manifest: RunManifest,
        config: TrainingConfig,
        metrics: TrainingMetrics,
        hardware_report: HardwareAuditReport,
        dataset_manifest_path: Optional[Path] = None,
    ) -> Path:
        """Emits the complete artifact package for an actual training run under experiments/lora/runs/<run_id>/."""
        run_dir = self.runs_root / run_manifest.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = run_dir / "checkpoints"
        logs_dir = run_dir / "logs"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        # 1. config.json
        with open(run_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, sort_keys=True)

        # 2. environment.json (sanitized package & host metadata, no secrets)
        env_sanitized = {
            "os_name": hardware_report.os_name,
            "os_release": hardware_report.os_release,
            "python_version": hardware_report.python_version,
            "cuda_available": hardware_report.cuda_available,
            "gpu_model": hardware_report.gpu_model,
            "gpu_count": hardware_report.gpu_count,
            "per_gpu_vram_gb": hardware_report.per_gpu_vram_gb,
            "total_ram_gb": hardware_report.total_ram_gb,
            "software_versions": {
                "torch": hardware_report.torch_version,
                "transformers": hardware_report.transformers_version,
                "peft": hardware_report.peft_version,
            },
            "classification": hardware_report.classification,
        }
        with open(run_dir / "environment.json", "w", encoding="utf-8") as f:
            json.dump(env_sanitized, f, indent=2, sort_keys=True)

        # 3. dataset_manifest.json copy if provided
        if dataset_manifest_path and dataset_manifest_path.exists():
            with open(dataset_manifest_path, "r", encoding="utf-8") as f:
                d_meta = json.load(f)
            with open(run_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
                json.dump(d_meta, f, indent=2, sort_keys=True)

        # 4. metrics.json
        with open(run_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics.to_dict(), f, indent=2, sort_keys=True)

        # 5. manifest.json
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(run_manifest.to_dict(), f, indent=2, sort_keys=True)

        # 6. report.md
        report_content = f"""# LoRA Training Run Report: `{run_manifest.run_id}`
- **Candidate:** `{run_manifest.candidate_id}`
- **Base Model:** `{run_manifest.base_model}`
- **Objective:** `{run_manifest.objective_id}`
- **Dataset ID:** `{run_manifest.dataset_id}` (v{run_manifest.dataset_version})
- **Status:** `{run_manifest.status}`
- **Steps:** {metrics.steps_completed} / {metrics.total_steps}
- **Runtime:** {metrics.runtime_ms} ms
- **Adapter SHA-256:** `{run_manifest.adapter_sha256 or 'N/A'}`
"""
        with open(run_dir / "report.md", "w", encoding="utf-8") as f:
            f.write(report_content)

        return run_dir
