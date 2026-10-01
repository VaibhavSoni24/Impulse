"""Dataset Loading and Split Verification Utilities (Stage 38 Section 25).

Provides strict loading functions and integrity verification:
- load_train()
- load_validation()
- verify_dataset_split()
- verify_no_held_out_leakage()

Guarantees that VALIDATION cannot accidentally be treated as TRAIN,
and that HELD_OUT is never touched or mixed into training splits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_data.leakage import HeldOutLeakageChecker
from local.lora_data.models import SplitType


def get_default_dataset_dir(repo_root: Optional[Path] = None) -> Path:
    """Returns the default curated dataset directory path."""
    root = Path(repo_root or Path(".")).resolve()
    return root / "experiments" / "lora" / "L1-data" / "curated"


def load_train(dataset_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    """Loads and verifies the TRAIN partition from the curated dataset.

    Raises:
        ValueError: If any loaded record has split != 'TRAIN'.
    """
    curated_dir = Path(dataset_dir or get_default_dataset_dir())
    train_file = curated_dir / "train.jsonl"
    records: list[dict[str, Any]] = []

    if not train_file.exists():
        return records

    with open(train_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            split = rec.get("split")
            if split != SplitType.TRAIN.value:
                raise ValueError(
                    f"Integrity violation in {train_file} at line {idx + 1}: expected split '{SplitType.TRAIN.value}', found '{split}'"
                )
            records.append(rec)

    return records


def load_validation(dataset_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    """Loads and verifies the VALIDATION partition from the curated dataset.

    Raises:
        ValueError: If any loaded record has split != 'VALIDATION'.
    """
    curated_dir = Path(dataset_dir or get_default_dataset_dir())
    val_file = curated_dir / "validation.jsonl"
    records: list[dict[str, Any]] = []

    if not val_file.exists():
        return records

    with open(val_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            split = rec.get("split")
            if split != SplitType.VALIDATION.value:
                raise ValueError(
                    f"Integrity violation in {val_file} at line {idx + 1}: expected split '{SplitType.VALIDATION.value}', found '{split}'"
                )
            records.append(rec)

    return records


def verify_dataset_split(
    train_records: list[dict[str, Any]], val_records: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Verifies that TRAIN and VALIDATION records are strictly disjoint and correctly labeled.

    Returns:
        (is_valid, list_of_violations)
    """
    violations: list[str] = []

    for r in train_records:
        if r.get("split") != SplitType.TRAIN.value:
            violations.append(f"Train record {r.get('example_id')} has incorrect split '{r.get('split')}'")

    for r in val_records:
        if r.get("split") != SplitType.VALIDATION.value:
            violations.append(f"Validation record {r.get('example_id')} has incorrect split '{r.get('split')}'")

    leakage_checker = HeldOutLeakageChecker()
    clean_sep, sep_violations = leakage_checker.check_split_separation(train_records, val_records)
    if not clean_sep:
        violations.extend(sep_violations)

    return len(violations) == 0, violations


def verify_no_held_out_leakage(
    records: list[dict[str, Any]], repo_root: Optional[Path] = None
) -> tuple[bool, list[str]]:
    """Verifies that no record in the provided dataset leaks into the HELD_OUT benchmark.

    Returns:
        (is_clean, list_of_violations)
    """
    checker = HeldOutLeakageChecker(repo_root=repo_root)
    violations: list[str] = []

    for rec in records:
        leaked, rec_violations = checker.check_example(rec)
        if leaked:
            violations.extend([f"[{rec.get('example_id')}] {v}" for v in rec_violations])

    return len(violations) == 0, violations
