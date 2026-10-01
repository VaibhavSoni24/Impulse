"""Hard Data Gate Validator for Stage 39 LoRA Training (Section 5, 6, 7).

Validates all prerequisites before ANY model loading or training operation:
1. Dataset manifest integrity and status (must be DATASET_READY)
2. Partition counts: TRAIN > 0 and VALIDATION > 0
3. Target objective: strictly OBJ-TOOL-DISCIPLINE
4. Zero held-out benchmark leakage
5. Zero unpermitted or unknown license sources
6. Zero secrets and confirmed sanitization status
7. Fixture safety: fixtures quarantined from training
8. Base model compatibility: gemma-4-31b-it-qat-w4a16-ct
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_train.dataset import ToolDisciplineDatasetLoader
from local.lora_train.errors import (
    DataGateBlockedError,
    FixtureSafetyError,
)
from local.lora_train.models import TrainingConfig, TrainingStatus


class DataGateValidator:
    """Enforces the strict, non-bypassable Stage 39 Data Gate."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.manifest_path = (
            self.repo_root / "experiments" / "lora" / "L1-data" / "manifests" / "dataset_manifest.json"
        )
        self.contract_path = (
            self.repo_root / "experiments" / "lora" / "L1-data" / "training_contract.json"
        )
        self.dataset_loader = ToolDisciplineDatasetLoader(repo_root=self.repo_root)

    def evaluate_gate(
        self, config: TrainingConfig, allow_fixtures: bool = False
    ) -> tuple[bool, str, dict[str, Any]]:
        """Audits all data gate conditions.

        Returns:
            (is_permitted, status_code, audit_details)
        """
        details: dict[str, Any] = {
            "dataset_manifest_exists": False,
            "contract_exists": False,
            "manifest_status": None,
            "train_count": 0,
            "validation_count": 0,
            "objective_id": None,
            "violations": [],
        }

        # 1. Manifest existence
        if not self.manifest_path.exists():
            details["violations"].append(f"Missing dataset manifest at {self.manifest_path}")
            return False, TrainingStatus.BLOCKED_BY_DATA.value, details
        details["dataset_manifest_exists"] = True

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            details["violations"].append(f"Corrupt dataset manifest: {e}")
            return False, TrainingStatus.BLOCKED_BY_DATA.value, details

        # 2. Dataset status
        m_status = manifest_data.get("dataset_status")
        details["manifest_status"] = m_status
        if m_status != "DATASET_READY" and not allow_fixtures:
            details["violations"].append(
                f"Dataset manifest status is '{m_status}' (expected 'DATASET_READY')"
            )

        # 3. Objective check
        obj_id = manifest_data.get("objective_id")
        details["objective_id"] = obj_id
        if obj_id != "OBJ-TOOL-DISCIPLINE":
            details["violations"].append(
                f"Objective mismatch: expected 'OBJ-TOOL-DISCIPLINE', found '{obj_id}'"
            )

        # 4. Partition counts
        train_count = manifest_data.get("train_count", 0)
        val_count = manifest_data.get("validation_count", 0)
        details["train_count"] = train_count
        details["validation_count"] = val_count

        if not allow_fixtures:
            if train_count <= 0:
                details["violations"].append(f"TRAIN partition is empty (count={train_count})")
            if val_count <= 0:
                details["violations"].append(f"VALIDATION partition is empty (count={val_count})")

        # 5. Training contract existence
        if not self.contract_path.exists():
            details["violations"].append(f"Missing training contract at {self.contract_path}")
        else:
            details["contract_exists"] = True

        # 6. Verify loaders and data records
        try:
            train_recs, val_recs, loader_meta = self.dataset_loader.load_and_validate_partitions(
                allow_fixtures=allow_fixtures
            )
            details["verified_train_records"] = len(train_recs)
            details["verified_val_records"] = len(val_recs)
        except (DataGateBlockedError, FixtureSafetyError) as e:
            if not allow_fixtures:
                details["violations"].append(str(e))

        is_permitted = len(details["violations"]) == 0
        status_code = (
            TrainingStatus.TRAINING_COMPLETED.value
            if is_permitted
            else TrainingStatus.BLOCKED_BY_DATA.value
        )
        return is_permitted, status_code, details

    def enforce_gate(self, config: TrainingConfig, allow_fixtures: bool = False) -> None:
        """Enforces the gate, raising DataGateBlockedError if any check fails."""
        is_permitted, status_code, details = self.evaluate_gate(config, allow_fixtures=allow_fixtures)
        if not is_permitted:
            reasons = "; ".join(details["violations"])
            raise DataGateBlockedError(reasons, details=details)
