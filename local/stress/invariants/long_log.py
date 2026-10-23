"""Stress Invariant Checker: STRESS 6 — Failing Test with Long Logs.

Verifies that verbose, high-volume test execution output is bounded and compacted,
ensuring that critical error tracebacks and final summary verdicts survive truncation
while preventing unbounded memory or storage growth.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Tuple

from local.failures.models import MAX_OUTPUT_SUMMARY_LENGTH
from local.stress.fixtures import create_long_log_fixture


def compact_test_log(log_content: str, max_length: int = MAX_OUTPUT_SUMMARY_LENGTH) -> tuple[str, bool]:
    """Compacts a long test log while preserving initial failure and final summary."""
    if len(log_content) <= max_length:
        return log_content, False

    lines = log_content.splitlines()
    # Extract failure trace block
    error_lines = []
    in_error = False
    for line in lines:
        if "FAILURE TRACE START" in line:
            in_error = True
        if in_error:
            error_lines.append(line)
        if "FAILURE TRACE END" in line:
            break

    # Extract final summary lines
    summary_lines = []
    in_summary = False
    for line in lines:
        if "TEST SUITE EXECUTION SUMMARY" in line:
            in_summary = True
        if in_summary:
            summary_lines.append(line)

    error_text = "\n".join(error_lines)
    summary_text = "\n".join(summary_lines)

    truncation_banner = f"\n... [TRUNCATED {len(log_content) - len(error_text) - len(summary_text)} BYTES OF VERBOSE OUTPUT] ...\n"
    compacted = error_text + truncation_banner + summary_text

    if len(compacted) > max_length:
        compacted = compacted[:max_length - 20] + "\n... [TRUNCATED]"

    return compacted, True


def check_long_log_stress(total_bytes: int = 50_000) -> tuple[bool, str, dict[str, Any]]:
    """Evaluates bounded compaction and critical error preservation on large logs.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="impulse_stress_long_log_"))
    start_t = time.perf_counter()

    try:
        log_file = create_long_log_fixture(tmp_dir, total_bytes=total_bytes)
        gen_duration_ms = (time.perf_counter() - start_t) * 1000.0

        actual_file_size = log_file.stat().st_size
        raw_text = log_file.read_text(encoding="utf-8")

        compact_start = time.perf_counter()
        compacted_output, is_truncated = compact_test_log(raw_text)
        compact_duration_ms = (time.perf_counter() - compact_start) * 1000.0

        # Invariant 1: Log file was genuinely large (>= total_bytes)
        if actual_file_size < total_bytes:
            return (
                False,
                f"Generated log size {actual_file_size} was less than requested {total_bytes}",
                {"actual_file_size": actual_file_size},
            )

        # Invariant 2: Output was marked truncated
        if not is_truncated:
            return (
                False,
                "Expected is_truncated=True for long log, got False",
                {},
            )

        # Invariant 3: Compacted output is strictly bounded
        if len(compacted_output) > MAX_OUTPUT_SUMMARY_LENGTH:
            return (
                False,
                f"Compacted output exceeded MAX_OUTPUT_SUMMARY_LENGTH ({len(compacted_output)} > {MAX_OUTPUT_SUMMARY_LENGTH})",
                {"compacted_length": len(compacted_output)},
            )

        # Invariant 4: Critical error trace survived truncation
        if "missing_mandatory_batch_header" not in compacted_output:
            return (
                False,
                "Critical error key 'missing_mandatory_batch_header' was lost in compaction",
                {"compacted_output": compacted_output},
            )

        # Invariant 5: Final summary survived truncation
        if "FAILED (failures=1" not in compacted_output:
            return (
                False,
                "Final failure summary 'FAILED (failures=1' was lost in compaction",
                {"compacted_output": compacted_output},
            )

        details = {
            "original_log_bytes": actual_file_size,
            "compacted_chars": len(compacted_output),
            "max_summary_bound": MAX_OUTPUT_SUMMARY_LENGTH,
            "truncation_flag": is_truncated,
            "critical_trace_preserved": True,
            "final_summary_preserved": True,
            "generation_time_ms": gen_duration_ms,
            "compact_time_ms": compact_duration_ms,
        }

        return (
            True,
            f"Successfully compacted {actual_file_size} byte verbose log down to {len(compacted_output)} chars while preserving failure trace and test summary.",
            details,
        )

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
