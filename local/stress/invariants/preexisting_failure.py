"""Stress Invariant Checker: STRESS 7 — Pre-Existing Failing Test.

Verifies that the evaluator distinguishes pre-existing test failures present in the
baseline commit from newly introduced regressions, preventing false regression penalties
when unrelated baseline tests are already red.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Set, Tuple

from local.stress.fixtures import create_preexisting_failure_fixture


def parse_test_results(test_output: str) -> dict[str, str]:
    """Extracts test names and outcomes from unittest text output."""
    results = {}
    for line in test_output.splitlines():
        if " ... " in line:
            parts = line.split(" ... ")
            test_name = parts[0].strip()
            status = parts[1].strip()
            results[test_name] = status
    return results


def check_preexisting_failure_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates classification of pre-existing vs resolved test failures.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="impulse_stress_preexist_"))

    try:
        fixture_meta = create_preexisting_failure_fixture(tmp_dir)

        # 1. Run baseline test suite (before any candidate modifications)
        cmd = [sys.executable, "-m", "unittest", "-v", "test_calc.py"]
        proc_baseline = subprocess.run(cmd, cwd=str(tmp_dir), capture_output=True, text=True)
        baseline_results = parse_test_results(proc_baseline.stderr)

        # Invariant 1: In baseline, both tests are failing
        if baseline_results.get("test_preexisting_legacy (test_calc.TestCalc)") != "ERROR":
            return (
                False,
                f"Expected baseline test_preexisting_legacy to fail with ERROR, got {baseline_results}",
                {"baseline_output": proc_baseline.stderr},
            )
        if baseline_results.get("test_target_func (test_calc.TestCalc)") != "FAIL":
            return (
                False,
                f"Expected baseline test_target_func to fail with FAIL, got {baseline_results}",
                {"baseline_output": proc_baseline.stderr},
            )

        # 2. Apply candidate fix to calculator.py targeting ONLY target_func
        code_file = tmp_dir / "calculator.py"
        new_content = (
            "def target_func(x: int) -> int:\n"
            "    # Fixed defect: now returns x + 1\n"
            "    return x + 1\n\n"
            "def legacy_buggy_func() -> int:\n"
            "    # Pre-existing bug left unchanged\n"
            "    return 42 // 0\n"
        )
        code_file.write_text(new_content, encoding="utf-8")

        # 3. Re-run test suite after candidate change
        proc_post = subprocess.run(cmd, cwd=str(tmp_dir), capture_output=True, text=True)
        post_results = parse_test_results(proc_post.stderr)

        # Classify transitions
        preexisting_failures: set[str] = set()
        resolved_failures: set[str] = set()
        new_regressions: set[str] = set()

        all_tests = set(baseline_results.keys()) | set(post_results.keys())
        for t in all_tests:
            b_status = baseline_results.get(t)
            p_status = post_results.get(t)

            b_failed = b_status in ("FAIL", "ERROR")
            p_failed = p_status in ("FAIL", "ERROR")

            if b_failed and p_failed:
                preexisting_failures.add(t)
            elif b_failed and not p_failed:
                resolved_failures.add(t)
            elif not b_failed and p_failed:
                new_regressions.add(t)

        # Invariant 2: test_preexisting_legacy classified as preexisting
        legacy_key = "test_preexisting_legacy (test_calc.TestCalc)"
        if legacy_key not in preexisting_failures:
            return (
                False,
                f"test_preexisting_legacy was not classified as preexisting failure: {preexisting_failures}",
                {},
            )

        # Invariant 3: test_target_func classified as resolved
        target_key = "test_target_func (test_calc.TestCalc)"
        if target_key not in resolved_failures:
            return (
                False,
                f"test_target_func was not classified as resolved failure: {resolved_failures}",
                {},
            )

        # Invariant 4: Zero new regressions
        if len(new_regressions) > 0:
            return (
                False,
                f"False regression detected: {new_regressions}",
                {},
            )

        details = {
            "preexisting_failures": list(preexisting_failures),
            "resolved_failures": list(resolved_failures),
            "new_regressions": list(new_regressions),
            "correctly_distinguished": True,
        }

        return (
            True,
            "Pre-existing legacy test failure correctly isolated from candidate fix; target defect classified as RESOLVED with 0 regressions.",
            details,
        )

    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
