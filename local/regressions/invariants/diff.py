"""Invariant checker for DIFF_DISCIPLINE regressions (Stage 45 Phase 5).

Covers:
- REG-DIFF-001: Unrelated file modified outside defect scope detected and rejected.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.reviewer.models import ReviewerInput, ReviewerStatus
from local.reviewer.rules import evaluate_review_findings


def check_unrelated_file_diff_invariant() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-DIFF-001: Unrelated modifications outside defect scope trigger blocking findings."""
    # Scenario 1: Clean intended change strictly touching defect files
    clean_input = ReviewerInput(
        issue="Fix integer division error in calculator",
        diff_summary="diff --git a/src/calculator.py b/src/calculator.py\n+    return a // b",
        modified_files=["src/calculator.py"],
        relevant_tests=["tests/test_calculator.py"],
        verification_status="PASSED",
    )
    clean_res = evaluate_review_findings(clean_input)
    if clean_res.status != ReviewerStatus.APPROVE:
        raise RegressionExecutionError(
            f"REG-DIFF-001 violation: Properly scoped clean diff was rejected: {clean_res.summary}"
        )

    # Scenario 2: Diff includes unintended / unrelated modifications (e.g. CI workflow or unrelated infra)
    unrelated_input = ReviewerInput(
        issue="Fix integer division error in calculator",
        diff_summary="diff --git a/src/calculator.py b/src/calculator.py\n+    return a // b\n"
                     "diff --git a/.github/workflows/release.yml b/.github/workflows/release.yml\n+    echo 'test'",
        modified_files=["src/calculator.py", ".github/workflows/release.yml"],
        relevant_tests=["tests/test_calculator.py"],
        verification_status="PASSED",
    )
    unrelated_res = evaluate_review_findings(unrelated_input)
    if unrelated_res.status != ReviewerStatus.CHANGES_REQUESTED:
        raise RegressionExecutionError(
            f"REG-DIFF-001 violation: Unrelated file modification was not blocked: {unrelated_res.status}"
        )

    blocking = [f for f in unrelated_res.blocking_findings if "Scope violation" in f]
    if not blocking:
        raise RegressionExecutionError(
            f"REG-DIFF-001 violation: Scope violation missing from blocking findings: {unrelated_res.blocking_findings}"
        )

    return True, "Modifications to unrelated files outside defect scope are strictly blocked", {
        "clean_status": clean_res.status.value,
        "unrelated_status": unrelated_res.status.value,
        "blocking_findings": blocking,
    }
