"""Dataset Loading and Sequence Preparation for Stage 39 LoRA Training (Section 15, 16, 17).

Integrates with Stage 38 dataset loaders and enforces:
1. Strict schema compliance using Stage 38 ToolDisciplineTrainingExample
2. Split disjointness and held-out leakage prevention
3. SFT / PEFT sequence formulation focusing on tool discipline:
   Situation → Evidence → Preferred Tool Action → Validation Signal
4. Token loss masking (conditioning on situation/evidence, calculating loss on preferred action)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_data.dataset_loaders import (
    load_train,
    load_validation,
    verify_dataset_split,
    verify_no_held_out_leakage,
)
from local.lora_data.leakage import HeldOutLeakageChecker
from local.lora_data.models import (
    EvidenceMode,
    SplitType,
    ToolDisciplineTrainingExample,
)
from local.lora_train.errors import DataGateBlockedError, FixtureSafetyError


class ToolDisciplineDatasetLoader:
    """Loads and formats Stage 38 training examples for SFT/PEFT training."""

    def __init__(self, dataset_dir: Optional[Path] = None, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.dataset_dir = Path(
            dataset_dir or (self.repo_root / "experiments" / "lora" / "L1-data" / "curated")
        ).resolve()
        self.manifest_path = self.repo_root / "experiments" / "lora" / "L1-data" / "manifests" / "dataset_manifest.json"

    def load_and_validate_partitions(
        self, allow_fixtures: bool = False
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Loads and strictly audits train and validation splits.

        Returns:
            (train_records, val_records, audit_metadata)

        Raises:
            DataGateBlockedError: If splits fail integrity or data gate checks.
            FixtureSafetyError: If fixture records enter real training.
        """
        # 1. Check dataset manifest
        manifest_meta: dict[str, Any] = {}
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    manifest_meta = json.load(f)
            except Exception as e:
                raise DataGateBlockedError(f"Failed to read dataset manifest: {e}")
        else:
            raise DataGateBlockedError(f"Dataset manifest missing at {self.manifest_path}")

        # 2. Check dataset status
        status = manifest_meta.get("dataset_status", "")
        if status != "DATASET_READY" and not allow_fixtures:
            raise DataGateBlockedError(
                f"Dataset manifest status is '{status}'. Training requires 'DATASET_READY'.",
                details={"manifest_status": status},
            )

        # 3. Load partitions via Stage 38 loaders
        train_records = load_train(self.dataset_dir)
        val_records = load_validation(self.dataset_dir)

        if not allow_fixtures:
            if len(train_records) == 0:
                raise DataGateBlockedError(
                    "TRAIN partition contains 0 examples. Training refused.",
                    details={"train_count": 0, "val_count": len(val_records)},
                )
            if len(val_records) == 0:
                raise DataGateBlockedError(
                    "VALIDATION partition contains 0 examples. Training refused.",
                    details={"train_count": len(train_records), "val_count": 0},
                )

        # 4. Check for fixture contamination
        if not allow_fixtures:
            for rec in train_records + val_records:
                if rec.get("evidence_mode") == EvidenceMode.FIXTURE.value:
                    raise FixtureSafetyError(
                        f"Fixture record '{rec.get('example_id')}' detected in curated training dataset!"
                    )

        # 5. Check split separation
        is_valid_split, split_violations = verify_dataset_split(train_records, val_records)
        if not is_valid_split:
            raise DataGateBlockedError(
                f"Train/Validation split integrity violation: {'; '.join(split_violations)}"
            )

        # 6. Check held-out benchmark leakage
        is_clean_train, t_leaks = verify_no_held_out_leakage(train_records, repo_root=self.repo_root)
        is_clean_val, v_leaks = verify_no_held_out_leakage(val_records, repo_root=self.repo_root)
        if not (is_clean_train and is_clean_val):
            all_leaks = t_leaks + v_leaks
            raise DataGateBlockedError(f"Held-out benchmark leakage detected: {'; '.join(all_leaks)}")

        audit_meta = {
            "dataset_id": manifest_meta.get("dataset_id"),
            "dataset_version": manifest_meta.get("dataset_version"),
            "dataset_sha256": manifest_meta.get("dataset_sha256"),
            "train_count": len(train_records),
            "validation_count": len(val_records),
            "status": "VALIDATED",
        }
        return train_records, val_records, audit_meta

    @staticmethod
    def format_example_for_sft(example: dict[str, Any]) -> dict[str, str]:
        """Formats a training record into SFT conditioning context and target label.

        Focuses loss strictly on the preferred tool invocation behavior:
        - Conditioning Prompt: Situation + Evidence + Prior Tool Context
        - Target Completion: Preferred Action + Arguments + Grounded Rationale
        """
        situation = example.get("situation", "")
        evidence = "\n".join([f"- {ev}" for ev in example.get("evidence", [])])
        tool_seq = json.dumps(example.get("tool_sequence", []), indent=2)

        prompt = (
            f"### SITUATION\n{situation}\n\n"
            f"### OBSERVED EVIDENCE\n{evidence}\n\n"
            f"### PRIOR TOOL TRACE\n{tool_seq}\n\n"
            f"### DECISION OBJECTIVE\n"
            f"Select the next correct action conforming to OBJ-TOOL-DISCIPLINE. "
            f"Avoid repeated failing invocations without new evidence.\n\n"
            f"### PREFERRED ACTION\n"
        )

        pref = example.get("preferred_behavior", {})
        target = json.dumps(pref, indent=2)

        return {
            "prompt": prompt,
            "target": target,
            "full_text": prompt + target,
            "example_id": example.get("example_id", ""),
            "task_id": example.get("task_id", ""),
        }
