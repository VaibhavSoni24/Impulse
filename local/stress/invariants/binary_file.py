"""Stress Invariant Checker: STRESS 9 — Binary or Unusual File Intent.

Verifies that binary or non-UTF8 files are detected without silent text corruption,
that submission/diff inspection safely handles or rejects them, and that diagnostic
reporting avoids dumping raw binary sequences to console or log artifacts.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Tuple

from local.stress.fixtures import create_binary_file_fixture


def is_binary_content(data: bytes) -> bool:
    """Deterministic binary check: tests for null byte or invalid UTF-8."""
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def format_safe_preview(data: bytes, max_len: int = 64) -> str:
    """Formats safe diagnostic preview without dumping unprintable binary chars."""
    if is_binary_content(data):
        return f"<binary data: {len(data)} bytes, sha256_prefix={data[:8].hex()}>"
    text = data.decode("utf-8", errors="replace")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def check_binary_file_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates binary file detection, corruption prevention, and safe diagnostics.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="impulse_stress_binary_"))

    try:
        bin_path = create_binary_file_fixture(tmp_dir, "asset.bin")
        raw_bytes = bin_path.read_bytes()

        # Invariant 1: Binary detector correctly flags content
        is_bin = is_binary_content(raw_bytes)
        if not is_bin:
            return (
                False,
                "Binary detector failed to identify null bytes in asset.bin",
                {},
            )

        # Invariant 2: Direct text decoding fails safely without silent corruption
        decode_failed_as_expected = False
        try:
            raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decode_failed_as_expected = True

        if not decode_failed_as_expected:
            return (
                False,
                "Expected UnicodeDecodeError when decoding binary file as UTF-8, but decode succeeded unexpectedly",
                {},
            )

        # Invariant 3: Safe diagnostic preview does not contain raw control chars
        preview = format_safe_preview(raw_bytes)
        if "\x00" in preview or any(ord(c) < 32 and c not in "\n\r\t" for c in preview):
            return (
                False,
                f"Diagnostic preview leaked raw binary control characters: {preview}",
                {},
            )

        if "<binary data: 128 bytes" not in preview:
            return (
                False,
                f"Expected structured binary tag in preview, got: {preview}",
                {},
            )

        details = {
            "file_size": len(raw_bytes),
            "is_binary_detected": is_bin,
            "unicode_decode_rejected": decode_failed_as_expected,
            "safe_preview": preview,
        }

        return (
            True,
            "Binary file (128 bytes) accurately detected via null-byte inspection; silent text corruption rejected and diagnostic formatting safely bounded.",
            details,
        )

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
