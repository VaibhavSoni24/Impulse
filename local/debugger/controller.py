"""Deterministic controller for Debugger agent invocation and loop prevention (Stage 22).

Provides:
- DebuggerControllerV1: Tracks Debugger invocations per difficult-failure episode,
  enforces max 1 invocation per episode, and integrates results into TaskState.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from local.debugger.models import DebuggerPolicy, DebuggerResult
from local.debugger.trigger import DebuggerTriggerContext, evaluate_debugger_trigger

if TYPE_CHECKING:
    from local.task_state.models import TaskState


class DebuggerControllerV1:
    """Manages Debugger invocation bounds, episode tracking, and TaskState synchronization."""

    def __init__(self, policy: DebuggerPolicy = DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE) -> None:
        self.policy = policy
        self.invocation_count = 0
        self.history: list[DebuggerResult] = []
        self.last_invoked_repo_version = -1
        self.last_invoked_failure_signature = ""

    def reset(self) -> None:
        """Resets controller state and history."""
        self.invocation_count = 0
        self.history.clear()
        self.last_invoked_repo_version = -1
        self.last_invoked_failure_signature = ""

    def get_invocation_count(self) -> int:
        """Returns the total number of Debugger invocations in the current session."""
        return self.invocation_count

    def should_invoke(self, context: DebuggerTriggerContext) -> tuple[bool, str]:
        """Evaluates whether Debugger should be invoked according to the configured policy."""
        # Sync context with controller internal state
        context.prior_debugger_invocations = self.invocation_count
        context.last_debugger_repo_version = self.last_invoked_repo_version
        context.last_failure_signature = self.last_invoked_failure_signature
        return evaluate_debugger_trigger(context, self.policy)

    def record_result(
        self,
        context: DebuggerTriggerContext,
        result: DebuggerResult,
        state: TaskState | None = None,
    ) -> None:
        """Records a completed Debugger invocation, updates loop prevention markers, and integrates into TaskState."""
        self.invocation_count += 1
        self.last_invoked_repo_version = context.repository_state_version
        self.last_invoked_failure_signature = context.current_failure_signature
        self.history.append(result)

        if state is not None:
            result.integrate_into_task_state(state)
