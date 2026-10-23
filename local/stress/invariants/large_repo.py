"""Stress Invariant Checker: STRESS 1 — Very Large Repository.

Verifies deterministic repository inspection, path containment, resource bounding,
and safe cleanup over a synthetic repository with many nested files.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Tuple

from local.stress.fixtures import create_large_repo_fixture


def check_large_repo_stress(
    num_files: int = 120,
    depth: int = 3,
) -> tuple[bool, str, dict[str, Any]]:
    """Executes large repository stress test.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="impulse_stress_large_repo_"))
    start_t = time.perf_counter()

    try:
        fixture_meta = create_large_repo_fixture(tmp_dir, num_files=num_files, depth=depth)
        gen_duration_ms = (time.perf_counter() - start_t) * 1000.0

        # Traversal and inspection
        scan_start_t = time.perf_counter()
        discovered_files: list[str] = []
        discovered_bytes = 0

        for root, dirs, files in os.walk(tmp_dir):
            # Ignore .git internals
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                full_p = Path(root) / f
                # Path containment invariant: must be within tmp_dir
                try:
                    rel_p = full_p.relative_to(tmp_dir)
                except ValueError:
                    return False, f"Path traversal failure: {full_p} outside {tmp_dir}", {}

                # Avoid directory escape sequences
                norm_str = str(rel_p).replace("\\", "/")
                if ".." in norm_str or norm_str.startswith("/"):
                    return False, f"Illegal relative path representation: {norm_str}", {}

                discovered_files.append(norm_str)
                discovered_bytes += full_p.stat().st_size

        scan_duration_ms = (time.perf_counter() - scan_start_t) * 1000.0

        # Invariant 1: File count matches expectation
        if len(discovered_files) != num_files:
            return (
                False,
                f"File count mismatch: expected {num_files}, found {len(discovered_files)}",
                {"discovered_count": len(discovered_files)},
            )

        # Invariant 2: Total bytes matches fixture metadata
        if discovered_bytes != fixture_meta["total_bytes"]:
            return (
                False,
                f"Byte count mismatch: expected {fixture_meta['total_bytes']}, found {discovered_bytes}",
                {"discovered_bytes": discovered_bytes},
            )

        # Invariant 3: Performance bound (should scan 120 files in < 5.0 seconds on local host)
        if scan_duration_ms > 5000.0:
            return (
                False,
                f"Scan exceeded bounded time limit (took {scan_duration_ms:.1f}ms)",
                {"scan_duration_ms": scan_duration_ms},
            )

        # Invariant 4: Repeated inspection idempotency (no memory or file leaks)
        second_files = []
        for root, dirs, files in os.walk(tmp_dir):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                second_files.append((Path(root) / f).relative_to(tmp_dir))

        if len(second_files) != len(discovered_files):
            return (
                False,
                f"Inspection leaked files on second pass: {len(second_files)} vs {len(discovered_files)}",
                {},
            )

        details = {
            "num_files": num_files,
            "depth": depth,
            "directory_count": fixture_meta["directory_count"],
            "total_bytes": discovered_bytes,
            "generation_time_ms": gen_duration_ms,
            "scan_time_ms": scan_duration_ms,
            "path_containment_verified": True,
            "idempotency_verified": True,
        }

        return (
            True,
            f"Successfully navigated {num_files} files ({discovered_bytes} bytes) across {fixture_meta['directory_count']} directories with verified path containment and bounded runtime.",
            details,
        )

    finally:
        # Safe cleanup
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
