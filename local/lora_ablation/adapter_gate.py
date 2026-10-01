"""Hard Adapter Gate for Stage 40 LoRA Ablation (Section 4, 19).

Enforces strict verification of LoRA adapter artifacts before allowing any
ablation execution or A/B comparison. Refuses fake, fixture-generated,
incompatible, or unverified adapters.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_ablation.errors import InvalidAdapterError, MissingAdapterError
from local.lora_ablation.models import (
    AdapterArtifactMetadata,
    AdapterGateStatus,
    FROZEN_BASELINE_DIMENSIONS,
)

EXPECTED_BASE_MODEL = FROZEN_BASELINE_DIMENSIONS["base_model"]
EXPECTED_DATASET_ID = "L0-TOOL-DISCIPLINE-DATA-v1"
EXPECTED_DATASET_VERSION = "1.0.0"
EXPECTED_OBJECTIVE_ID = FROZEN_BASELINE_DIMENSIONS["objective_id"]


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hex digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class AdapterGateValidator:
    """Validates that a LoRA adapter artifact meets all strict scientific and provenance requirements."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()

    def validate_adapter(
        self,
        adapter_path: Optional[str | Path] = None,
        expected_base_model: str = EXPECTED_BASE_MODEL,
        expected_dataset_id: str = EXPECTED_DATASET_ID,
        expected_dataset_version: str = EXPECTED_DATASET_VERSION,
        expected_objective: str = EXPECTED_OBJECTIVE_ID,
    ) -> Tuple[bool, AdapterGateStatus, str, Optional[AdapterArtifactMetadata]]:
        """Performs comprehensive validation of candidate adapter artifact.

        Returns:
            (is_valid, status, reason, metadata)
        """
        # 1. Check path provided and directory existence
        if adapter_path is None:
            return (
                False,
                AdapterGateStatus.MISSING_ADAPTER_ARTIFACT,
                "No adapter path specified. Repository currently has no trained adapter.",
                None,
            )

        adapter_dir = Path(adapter_path)
        if not adapter_dir.is_absolute():
            adapter_dir = (self.repo_root / adapter_dir).resolve()

        if not adapter_dir.exists() or not adapter_dir.is_dir():
            return (
                False,
                AdapterGateStatus.MISSING_ADAPTER_ARTIFACT,
                f"Adapter directory does not exist: {adapter_dir}",
                None,
            )

        # 2. Check required files
        config_path = adapter_dir / "adapter_config.json"
        manifest_path = adapter_dir / "manifest.json"

        # Check weights file (.safetensors or .bin)
        weights_path = adapter_dir / "adapter_model.safetensors"
        if not weights_path.exists():
            weights_bin = adapter_dir / "adapter_model.bin"
            if weights_bin.exists():
                weights_path = weights_bin
            else:
                return (
                    False,
                    AdapterGateStatus.MISSING_ADAPTER_FILES,
                    f"Missing adapter weights file in {adapter_dir} (expected adapter_model.safetensors or adapter_model.bin)",
                    None,
                )

        if not config_path.exists():
            return (
                False,
                AdapterGateStatus.MISSING_ADAPTER_FILES,
                f"Missing adapter_config.json in {adapter_dir}",
                None,
            )

        if not manifest_path.exists():
            return (
                False,
                AdapterGateStatus.MISSING_ADAPTER_FILES,
                f"Missing manifest.json in {adapter_dir}",
                None,
            )

        # 3. Parse and validate adapter_config.json
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                adapter_config = json.load(f)
        except Exception as e:
            return (
                False,
                AdapterGateStatus.INVALID_ADAPTER_CONFIG,
                f"Failed to parse adapter_config.json: {e}",
                None,
            )

        if not isinstance(adapter_config, dict):
            return (
                False,
                AdapterGateStatus.INVALID_ADAPTER_CONFIG,
                "adapter_config.json must contain a JSON object",
                None,
            )

        # 4. Parse and validate manifest.json
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            return (
                False,
                AdapterGateStatus.PROVENANCE_INVALID,
                f"Failed to parse manifest.json: {e}",
                None,
            )

        # 5. Check training run status and evidence mode
        training_status = manifest_data.get("status", "")
        if training_status in ("BLOCKED_BY_DATA", "FAILED"):
            return (
                False,
                AdapterGateStatus.TRAINING_STATUS_BLOCKED,
                f"Adapter manifest records non-successful status: '{training_status}'",
                None,
            )

        evidence_mode = manifest_data.get("evidence_mode", "REAL")
        if evidence_mode == "FIXTURE" or manifest_data.get("is_fixture", False):
            return (
                False,
                AdapterGateStatus.FIXTURE_ADAPTER_REJECTED,
                "Fixture-generated adapter cannot be used for ablation evaluation (evidence_mode == FIXTURE).",
                None,
            )

        # 6. Check base model compatibility
        base_model = manifest_data.get("base_model", "")
        if not base_model:
            base_model = adapter_config.get("base_model_name_or_path", "")

        if base_model != expected_base_model:
            return (
                False,
                AdapterGateStatus.INCOMPATIBLE_BASE_MODEL,
                f"Adapter base model '{base_model}' does not match expected '{expected_base_model}'.",
                None,
            )

        # 7. Check dataset ID and version
        dataset_id = manifest_data.get("dataset_id", "")
        dataset_version = manifest_data.get("dataset_version", "")
        if dataset_id != expected_dataset_id or dataset_version != expected_dataset_version:
            return (
                False,
                AdapterGateStatus.INCOMPATIBLE_DATASET,
                f"Adapter trained on dataset '{dataset_id}:{dataset_version}', expected '{expected_dataset_id}:{expected_dataset_version}'.",
                None,
            )

        # 8. Check training objective
        objective_id = manifest_data.get("objective_id", "")
        if objective_id != expected_objective:
            return (
                False,
                AdapterGateStatus.WRONG_OBJECTIVE,
                f"Adapter trained for objective '{objective_id}', expected '{expected_objective}'.",
                None,
            )

        # 9. Verify weights hash integrity
        weights_sha256 = compute_file_sha256(weights_path)
        recorded_sha256 = manifest_data.get("adapter_sha256", "")
        if recorded_sha256 and weights_sha256 != recorded_sha256:
            return (
                False,
                AdapterGateStatus.HASH_MISMATCH,
                f"Adapter weights SHA-256 '{weights_sha256}' does not match manifest '{recorded_sha256}'.",
                None,
            )

        # 10. Compute total size and assemble metadata
        total_size = sum(p.stat().st_size for p in adapter_dir.glob("*") if p.is_file())
        file_hashes = {
            p.name: compute_file_sha256(p) for p in adapter_dir.glob("*") if p.is_file()
        }

        metadata = AdapterArtifactMetadata(
            adapter_dir=str(adapter_dir),
            adapter_config_path=str(config_path),
            adapter_weights_path=str(weights_path),
            manifest_path=str(manifest_path),
            adapter_sha256=weights_sha256,
            base_model=base_model,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            dataset_sha256=manifest_data.get("dataset_sha256", ""),
            objective_id=objective_id,
            training_run_status=training_status,
            evidence_mode=evidence_mode,
            rank=adapter_config.get("r"),
            alpha=adapter_config.get("lora_alpha"),
            dropout=adapter_config.get("lora_dropout"),
            file_hashes=file_hashes,
            total_size_bytes=total_size,
        )

        return (True, AdapterGateStatus.READY, "Adapter artifact verified and ready.", metadata)
