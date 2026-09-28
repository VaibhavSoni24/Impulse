"""Deterministic controller for Scout agent invocation and loop prevention (Stage 21).

Provides:
- ScoutControllerV1: Tracks Scout invocations per uncertainty episode,
  enforces max 1 invocation per episode, and integrates results into TaskState.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from local.scout.models import ScoutPolicy, ScoutResult, ScoutStatus
from local.scout.trigger import ScoutTriggerContext, evaluate_scout_trigger

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class ScoutControllerV1:
    """Manages Scout invocation bounds, episode tracking, and TaskState synchronization."""

    def __init__(self, policy: ScoutPolicy = ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY) -> None:
        self.policy = policy
        self.invocation_count = 0
        self.history: list[ScoutResult] = []
        self.last_invoked_repo_version = -1

    def reset(self) -> None:
        """Resets controller state and history."""
        self.invocation_count = 0
        self.history.clear()
        self.last_invoked_repo_version = -1

    def get_invocation_count(self) -> int:
        """Returns the total number of Scout invocations in the current session."""
        return self.invocation_count

    def should_invoke(self, context: ScoutTriggerContext) -> tuple[bool, str]:
        """Evaluates whether Scout should be invoked according to the configured policy."""
        # Sync context with controller internal state
        context.prior_scout_invocations = self.invocation_count
        context.last_scout_repo_version = self.last_invoked_repo_version
        return evaluate_scout_trigger(context, self.policy)

    def record_result(self, context: ScoutTriggerContext, result: ScoutResult, state: TaskState | None = None) -> None:
        """Records a completed Scout invocation, updates loop prevention markers, and integrates into TaskState."""
        self.invocation_count += 1
        self.last_invoked_repo_version = context.repository_state_version
        self.history.append(result)

        if state is not None:
            result.integrate_into_task_state(state)
