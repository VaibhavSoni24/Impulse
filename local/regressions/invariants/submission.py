"""Invariant checker for SUBMISSION regressions (Stage 45 Phase 5).

Covers:
- REG-SUBMISSION-001: Submitting patch without final diff review and verification evidence.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.reviewer.trigger import ReviewerTriggerContext, is_review_ready


def check_submit_without_final_diff() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-SUBMISSION-001: Final review readiness strictly enforces diff and verification checks before submission."""
    # Scenario A: Attempting submission without verification evidence
    unverified_ctx = ReviewerTriggerContext(
        has_candidate_diff=True,
        verification_attempted=False,  # No verification!
        has_result_summary=False,
        is_final_review_point=True,
    )
    ready, reason = is_review_ready(unverified_ctx)
    if ready:
        raise RegressionExecutionError(
            f"REG-SUBMISSION-001 violation: Review readiness allowed unverified patch: {reason}"
        )
    if "Verification has not been attempted" not in reason:
        raise RegressionExecutionError(
            f"REG-SUBMISSION-001 violation: Expected missing verification reason, got: {reason}"
        )

    # Scenario B: Attempting submission with empty diff
    empty_diff_ctx = ReviewerTriggerContext(
        has_candidate_diff=False,  # No diff
        verification_attempted=True,
        has_result_summary=True,
        is_final_review_point=True,
    )
    ready_diff, reason_diff = is_review_ready(empty_diff_ctx)
    if ready_diff:
        raise RegressionExecutionError(
            f"REG-SUBMISSION-001 violation: Review readiness allowed empty candidate diff: {reason_diff}"
        )

    # Scenario C: Valid final review readiness
    valid_ctx = ReviewerTriggerContext(
        has_candidate_diff=True,
        verification_attempted=True,
        has_result_summary=True,
        is_final_review_point=True,
    )
    ready_valid, reason_valid = is_review_ready(valid_ctx)
    if not ready_valid:
        raise RegressionExecutionError(
            f"REG-SUBMISSION-001 violation: Valid patch and verification rejected: {reason_valid}"
        )

    return True, "Final review readiness structurally required before patch submission", {
        "unverified_reason": reason,
        "empty_diff_reason": reason_diff,
        "valid_ready": ready_valid,
    }
