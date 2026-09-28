"""Deterministic final-review trigger evaluation for the Reviewer agent (Stage 23).

Defines:
- ReviewerTriggerContext: Observable context capturing patch state and verification readiness
- is_review_ready: Pure deterministic evaluation of review readiness
- evaluate_reviewer_trigger: Complete trigger decision enforcing loop prevention and policy rules
"""

from __future__ import annotations

from dataclasses import dataclass
from local.reviewer.models import ReviewerPolicy


@dataclass
class ReviewerTriggerContext:
    """Observable context representing current patch readiness and review lifecycle."""

    has_candidate_diff: bool = False  # Non-empty implementation patch exists
    verification_attempted: bool = False  # Targeted verification tests were executed
    has_result_summary: bool = False  # Summary of test outcome exists
    is_final_review_point: bool = True  # Agent is approaching patch finalization/submission
    prior_reviewer_invocations: int = 0  # Reviewer invocations on current patch
    patch_state_version: int = 0  # Monotonic version tracking patch modifications
    last_reviewed_patch_version: int = -1  # Patch version when Reviewer was last invoked
    last_reviewed_patch_hash: str = ""  # Hash of patch from previous review
    current_patch_hash: str = ""  # Hash of current patch candidate


def is_review_ready(context: ReviewerTriggerContext) -> tuple[bool, str]:
    """Evaluates whether the deterministic review readiness condition is met.

    REVIEWER_TRIGGER fires when:
    1. Root has produced a non-empty candidate diff (`has_candidate_diff == True`).
    2. Relevant verification has been attempted (`verification_attempted == True`).
    3. Result summary exists (`has_result_summary == True`).
    4. Root is at final review point approaching submission (`is_final_review_point == True`).
    """
    if not context.has_candidate_diff:
        return False, "Candidate diff is empty; review requires an implemented modification."
    if not context.verification_attempted:
        return False, "Verification has not been attempted; review requires test verification evidence."
    if not context.has_result_summary:
        return False, "Result summary is missing; verification outcome not documented."
    if not context.is_final_review_point:
        return False, "Not at final review point; review occurs prior to patch submission."

    return True, "Patch and verification evidence ready for final review."


def evaluate_reviewer_trigger(
    context: ReviewerTriggerContext,
    policy: ReviewerPolicy = ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW,
) -> tuple[bool, str]:
    """Determines whether Reviewer should be invoked under the specified policy with loop prevention.

    Enforces:
    - Policy differentiation: V0 (UNAVAILABLE) always returns False.
    - Loop prevention: at most 1 invocation per unchanged patch episode.
    - Review readiness evaluation.
    """
    if policy == ReviewerPolicy.UNAVAILABLE:
        return False, "Reviewer unavailable: candidate policy V0 does not configure Reviewer specialist."

    # Loop prevention check: if already invoked and patch version and hash are unchanged
    is_same_patch_version = (
        context.prior_reviewer_invocations > 0
        and context.patch_state_version == context.last_reviewed_patch_version
    )
    is_same_patch_hash = (
        bool(context.last_reviewed_patch_hash)
        and context.current_patch_hash == context.last_reviewed_patch_hash
    )
    if is_same_patch_version and (is_same_patch_hash or not context.current_patch_hash):
        return False, "Reviewer invocation suppressed by loop prevention: already reviewed once for this unchanged patch state."

    ready, reason = is_review_ready(context)
    if not ready:
        return False, f"Reviewer not triggered: {reason}"

    return True, f"Reviewer triggered: {reason}"
