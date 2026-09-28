"""Deterministic controller for Reviewer agent invocation and loop prevention (Stage 23).

Provides:
- ReviewerControllerV1: Tracks Reviewer invocations per patch episode,
  enforces max 1 invocation per unchanged patch, and integrates results into TaskState.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from local.reviewer.models import ReviewerPolicy, ReviewerResult
from local.reviewer.trigger import ReviewerTriggerContext, evaluate_reviewer_trigger

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class ReviewerControllerV1:
    """Manages Reviewer invocation bounds, episode tracking, and TaskState synchronization."""

    def __init__(self, policy: ReviewerPolicy = ReviewerPolicy.AVAILABLE_AT_FINAL_REVIEW) -> None:
        self.policy = policy
        self.invocation_count = 0
        self.history: list[ReviewerResult] = []
        self.last_reviewed_patch_version = -1
        self.last_reviewed_patch_hash = ""

    def reset(self) -> None:
        """Resets controller state and history."""
        self.invocation_count = 0
        self.history.clear()
        self.last_reviewed_patch_version = -1
        self.last_reviewed_patch_hash = ""

    def get_invocation_count(self) -> int:
        """Returns the total number of Reviewer invocations in the current session."""
        return self.invocation_count

    def should_invoke(self, context: ReviewerTriggerContext) -> tuple[bool, str]:
        """Evaluates whether Reviewer should be invoked according to the configured policy."""
        # Sync context with controller internal state
        context.prior_reviewer_invocations = self.invocation_count
        context.last_reviewed_patch_version = self.last_reviewed_patch_version
        context.last_reviewed_patch_hash = self.last_reviewed_patch_hash
        return evaluate_reviewer_trigger(context, self.policy)

    def record_result(
        self,
        context: ReviewerTriggerContext,
        result: ReviewerResult,
        state: TaskState | None = None,
    ) -> None:
        """Records a completed Reviewer invocation, updates loop prevention markers, and integrates into TaskState."""
        self.invocation_count += 1
        self.last_reviewed_patch_version = context.patch_state_version
        self.last_reviewed_patch_hash = context.current_patch_hash
        self.history.append(result)

        if state is not None:
            result.integrate_into_task_state(state)
