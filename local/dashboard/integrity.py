"""Split integrity verification and held-out safety guard for Dashboard (Stage 30).

Enforces:
- Verification of Stage 29 split manifests before dashboard report generation (Phase 15).
- Protection of HELD_OUT locks against tampering or silent modification (Phase 16).
- Aborts dashboard generation if split verification fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from benchmark.splits.held_out_lock import verify_held_out_lock
from benchmark.splits.manifests import load_manifest, verify_manifest_integrity
from benchmark.splits.models import SplitManifest


class SplitIntegrityError(Exception):
    """Raised when split manifest or held-out lock verification fails."""


def verify_split_before_dashboard(
    split_name: str,
    split_version: str = "v1",
    splits_root: Path | str = Path("benchmark/splits"),
) -> Tuple[SplitManifest, Path]:
    """Verifies that the requested split is structurally sound, hashed, and untampered.

    Args:
        split_name: The name of the split ('dev', 'validation', 'held_out', or 'all').
        split_version: The version subdirectory (default: 'v1').
        splits_root: Path to the benchmark/splits directory.

    Returns:
        A tuple of (SplitManifest, split_dir_path).

    Raises:
        SplitIntegrityError: If manifest is missing, hashes do not match,
                             or held-out lock verification fails.
    """
    splits_base = Path(splits_root)
    split_dir = splits_base / split_version
    manifest_path = split_dir / "manifest.json"

    if not manifest_path.is_file():
        raise SplitIntegrityError(
            f"Split manifest not found at {manifest_path}. "
            "Stage 29 splits must exist before generating dashboard reports."
        )

    # 1. Verify manifest integrity (hashes, file presence, counts)
    try:
        valid, errors = verify_manifest_integrity(manifest_path, split_dir)
        if not valid:
            error_details = "; ".join(errors)
            raise SplitIntegrityError(
                f"Split manifest integrity verification FAILED for {split_version}: {error_details}"
            )
        manifest = load_manifest(manifest_path)
    except SplitIntegrityError:
        raise
    except Exception as e:
        raise SplitIntegrityError(
            f"Split manifest verification FAILED for {split_version}: {e}"
        ) from e

    # Check split existence if a specific split was requested
    normalized_split = split_name.lower().strip()
    if normalized_split not in ["all", ""]:
        if normalized_split not in manifest.splits:
            raise SplitIntegrityError(
                f"Split '{split_name}' does not exist in manifest {manifest_path}. "
                f"Available splits: {list(manifest.splits.keys())}"
            )

    # 2. If held_out is involved, strictly verify held_out.lock
    if normalized_split in ["held_out", "all", ""]:
        lock_path = split_dir / "held_out.lock"
        held_out_file = split_dir / "held_out.jsonl"
        if not lock_path.is_file():
            raise SplitIntegrityError(
                f"Held-out lock missing at {lock_path}. Held-out tasks must be cryptographically locked."
            )

        lock_valid, lock_msg = verify_held_out_lock(
            lock_path=lock_path,
            held_out_file_path=held_out_file,
            current_manifest_sha256=manifest.manifest_sha256,
        )
        if not lock_valid:
            raise SplitIntegrityError(
                f"Held-out lock integrity check FAILED: {lock_msg}. "
                "Held-out dataset must not be modified or tampered with."
            )

    return manifest, split_dir
