"""Held-out dataset protection and locking mechanism (Stage 29 Phase 16).

Enforces:
1. Held-out tasks are immutable and cryptographically bound to the split manifest.
2. Development tools can query `is_held_out_task` to prevent test-set leakage or repeated tuning.
3. Tamper detection: Verifies that held-out split file has not been modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from benchmark.splits.hashing import compute_canonical_task_set_hash, compute_file_sha256
from benchmark.splits.models import SplitLock

DEFAULT_LOCK_FILENAME = "held_out.lock"


class HeldOutViolationError(Exception):
    """Raised when an attempt is made to mutate or improperly use held-out benchmark tasks."""


def create_held_out_lock(
    held_out_tasks: list[dict[str, Any]],
    held_out_file_path: Path | str,
    manifest_sha256: str,
    output_lock_path: Path | str,
) -> SplitLock:
    """Creates a cryptographic lock file protecting the HELD_OUT benchmark split."""
    file_p = Path(held_out_file_path)
    lock_p = Path(output_lock_path)

    task_ids = sorted([str(t.get("instance_id", "")).strip() for t in held_out_tasks])
    file_hash = compute_file_sha256(file_p)
    set_hash = compute_canonical_task_set_hash(held_out_tasks)

    lock = SplitLock(
        held_out_count=len(task_ids),
        held_out_tasks=task_ids,
        held_out_file_sha256=file_hash,
        task_set_sha256=set_hash,
        manifest_sha256=manifest_sha256,
        locked_at=datetime_now_iso(),
    )

    lock_p.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_p, "w", encoding="utf-8") as f:
        json.dump(lock.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")

    return lock


def datetime_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def load_held_out_lock(lock_path: Path | str) -> SplitLock:
    """Loads a SplitLock object from filesystem."""
    p = Path(lock_path)
    if not p.is_file():
        raise FileNotFoundError(f"Held-out lock file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    return SplitLock(
        held_out_count=data["held_out_count"],
        held_out_tasks=data["held_out_tasks"],
        held_out_file_sha256=data["held_out_file_sha256"],
        task_set_sha256=data["task_set_sha256"],
        manifest_sha256=data["manifest_sha256"],
        locked_at=data["locked_at"],
    )


def verify_held_out_lock(
    lock_path: Path | str,
    held_out_file_path: Path | str,
    current_manifest_sha256: str,
) -> tuple[bool, str]:
    """Verifies that the held_out dataset matches its locked hash and bound manifest."""
    try:
        lock = load_held_out_lock(lock_path)
    except Exception as e:
        return False, f"Failed to load held-out lock: {e}"

    # Verify manifest binding
    if lock.manifest_sha256 != current_manifest_sha256:
        return (
            False,
            f"Lock manifest hash mismatch: locked {lock.manifest_sha256[:12]}, current {current_manifest_sha256[:12]}",
        )

    # Verify file SHA-256
    file_p = Path(held_out_file_path)
    if not file_p.is_file():
        return False, f"Held-out split file missing: {file_p}"

    actual_file_hash = compute_file_sha256(file_p)
    if actual_file_hash != lock.held_out_file_sha256:
        return (
            False,
            f"Held-out file SHA-256 tampered: expected {lock.held_out_file_sha256[:12]}, got {actual_file_hash[:12]}",
        )

    return True, "Held-out split locked and verified"


def is_held_out_task(task_id: str, lock_path: Optional[Path | str] = None) -> bool:
    """Checks whether a given task ID belongs to the protected HELD_OUT split."""
    if lock_path is None:
        lock_path = Path("benchmark/splits/v1/held_out.lock")
    p = Path(lock_path)
    if not p.is_file():
        return False

    try:
        lock = load_held_out_lock(p)
        return task_id.strip() in lock.held_out_tasks
    except Exception:
        return False
