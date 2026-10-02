"""Invariant checker for INFRASTRUCTURE regressions (Stage 45 Phase 8).

Covers:
- REG-BENCHMARK-001: Strict cryptographic held-out task split protection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple
from benchmark.splits.held_out_lock import is_held_out_task, load_held_out_lock
from local.regressions.errors import HeldOutContaminationError, RegressionExecutionError


LOCK_FILE_PATH = Path("benchmark/splits/v1/held_out.lock")


def validate_task_not_held_out(task_id: str) -> None:
    """Validates that a candidate or regression task ID does NOT belong to the held-out split."""
    if is_held_out_task(task_id, lock_path=LOCK_FILE_PATH):
        raise HeldOutContaminationError(
            f"Held-out contamination detected: Task '{task_id}' is locked in the protected test split and cannot be used in regressions."
        )


def check_held_out_protection_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-BENCHMARK-001: Verifies cryptographic held-out lock and ensures zero leakage into regression suites."""
    if not LOCK_FILE_PATH.is_file():
        raise RegressionExecutionError(f"REG-BENCHMARK-001 violation: Held-out lock file missing at {LOCK_FILE_PATH}")

    lock = load_held_out_lock(LOCK_FILE_PATH)
    if lock.held_out_count != 14:
        raise RegressionExecutionError(
            f"REG-BENCHMARK-001 violation: Expected 14 held-out tasks in lock, got {lock.held_out_count}"
        )

    # Invariant 1: All locked tasks are confirmed held-out
    for t_id in lock.held_out_tasks:
        if not is_held_out_task(t_id, lock_path=LOCK_FILE_PATH):
            raise RegressionExecutionError(
                f"REG-BENCHMARK-001 violation: Task '{t_id}' failed is_held_out_task check"
            )

    # Invariant 2: Regression validator must reject held-out task with HeldOutContaminationError
    sample_held_out = lock.held_out_tasks[0]
    rejected = False
    try:
        validate_task_not_held_out(sample_held_out)
    except HeldOutContaminationError:
        rejected = True

    if not rejected:
        raise RegressionExecutionError(
            f"REG-BENCHMARK-001 violation: validate_task_not_held_out failed to reject held-out task '{sample_held_out}'"
        )

    # Invariant 3: Non-held-out development task passes cleanly
    dev_task = "sympy_14024"
    if is_held_out_task(dev_task, lock_path=LOCK_FILE_PATH):
        raise RegressionExecutionError(f"REG-BENCHMARK-001 violation: Non-held-out task '{dev_task}' falsely flagged as held-out")
    validate_task_not_held_out(dev_task)

    return True, "Cryptographic held-out split lock verified; zero contamination permitted in regression corpus", {
        "held_out_count": lock.held_out_count,
        "sample_task_rejected": sample_held_out,
        "manifest_sha256": lock.manifest_sha256[:12],
    }
