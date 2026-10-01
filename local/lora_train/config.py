"""Configuration Management Subsystem for Stage 39 LoRA Training (Section 11, 12).

Defines default configurations and validation routines:
- Candidate: L1 (Stage 37 frozen control + Stage 38 OBJ-TOOL-DISCIPLINE data + 1 LoRA adapter)
- Base model: gemma-4-31b-it-qat-w4a16-ct
- Hyperparameter policy: Explicit UNSELECTED sentinel for unresolved variables
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.lora_train.errors import UnresolvedHyperparameterError
from local.lora_train.models import TrainingConfig, UNSELECTED


def get_default_training_config(repo_root: Optional[Path] = None) -> TrainingConfig:
    """Returns the canonical baseline training configuration for candidate L1."""
    root = Path(repo_root or Path(".")).resolve()
    contract_path = root / "experiments" / "lora" / "L1-data" / "training_contract.json"

    tool_contract_hashes: dict[str, str] = {}
    train_hash = ""
    val_hash = ""

    if contract_path.exists():
        try:
            with open(contract_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
                tool_contract_hashes = c_data.get("tool_contract_hashes", {})
                train_hash = c_data.get("train_manifest_hash", "")
                val_hash = c_data.get("validation_manifest_hash", "")
        except Exception:
            pass

    return TrainingConfig(
        candidate_id="L1",
        base_model="gemma-4-31b-it-qat-w4a16-ct",
        objective_id="OBJ-TOOL-DISCIPLINE",
        dataset_id="L0-TOOL-DISCIPLINE-DATA-v1",
        dataset_version="1.0.0",
        train_manifest_hash=train_hash,
        validation_manifest_hash=val_hash,
        prompt_hash="2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
        tool_contract_hashes=tool_contract_hashes,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        rank=UNSELECTED,
        alpha=UNSELECTED,
        dropout=UNSELECTED,
        learning_rate=UNSELECTED,
        batch_size=UNSELECTED,
        gradient_accumulation_steps=UNSELECTED,
        epochs=UNSELECTED,
        sequence_length=UNSELECTED,
        seed=42,
        precision="bf16",
        gradient_checkpointing=True,
        output_dir="experiments/lora/runs/L1",
    )


def load_training_config(config_path: Path) -> TrainingConfig:
    """Loads a TrainingConfig from disk with JSON deserialization."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TrainingConfig.from_dict(data)


def save_training_config(config: TrainingConfig, output_path: Path) -> None:
    """Saves a TrainingConfig to disk formatted as indented JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, sort_keys=True)


def validate_hyperparameters_for_execution(config: TrainingConfig) -> None:
    """Enforces that all mandatory training hyperparameters are resolved and valid before execution.

    Raises:
        UnresolvedHyperparameterError: If any mandatory parameter is UNSELECTED or None.
        ValueError: If hyperparameter values fall outside valid bounds.
    """
    unresolved = config.get_unresolved_hyperparameters()
    if unresolved:
        raise UnresolvedHyperparameterError(unresolved)

    # Value bound checks
    if config.rank <= 0 or not isinstance(config.rank, int):
        raise ValueError(f"LoRA rank must be a positive integer, got {config.rank}")
    if config.alpha <= 0:
        raise ValueError(f"LoRA alpha must be positive, got {config.alpha}")
    if not (0.0 <= config.dropout < 1.0):
        raise ValueError(f"LoRA dropout must be in [0.0, 1.0), got {config.dropout}")
    if config.learning_rate <= 0:
        raise ValueError(f"Learning rate must be positive, got {config.learning_rate}")
    if config.batch_size <= 0:
        raise ValueError(f"Batch size must be a positive integer, got {config.batch_size}")
    if config.sequence_length <= 0:
        raise ValueError(f"Sequence length must be positive, got {config.sequence_length}")
