"""Deterministic Recovery Controller implementation (Stage 20 / Candidate E11).

Provides RecoveryControllerV1 to select, execute, and bound recovery actions
across the five canonical recovery families without infinite recursion.
"""

from __future__ import annotations

from typing import Any

from local.recovery.models import (
    RecoveryActionType,
    RecoveryContext,
    RecoveryDecision,
    RecoveryPath,
    RecoveryState,
)
from local.recovery.policy import (
    MAX_PATH_ATTEMPTS,
    evaluate_bad_edit,
    evaluate_budget_pressure,
    evaluate_search_fallback,
    evaluate_test_failure,
    evaluate_tool_failure,
)


class RecoveryControllerV1:
    """Deterministic, bounded recovery controller.

    Evaluates recovery triggers in fixed priority order:
    1. Budget Pressure: Stop low-value exploration -> targeted validation -> final review.
    2. Tool Failure: Bounded retry -> alternate tool -> terminate.
    3. Bad Edit: Inspect diff -> repair/revert (safe ownership only) -> rerun targeted test.
    4. Test Failure: Classify -> inspect diff -> inspect stack -> revise hypothesis.
    5. Search Fallback: Semantic -> exact search -> tree inspection -> graph.

    Loop prevention:
    - Bounded per-path attempts (default: 2).
    - Exhausted paths are not repeated.
    - Transitions cleanly to NORMAL, RECOVERY_EXHAUSTED, or TERMINAL.
    """

    def __init__(self, max_attempts: int = MAX_PATH_ATTEMPTS) -> None:
        self.max_attempts = max_attempts
        self.attempts: dict[str, int] = {}
        self.history: list[RecoveryDecision] = []

    def reset(self) -> None:
        """Resets controller state and attempt counters."""
        self.attempts.clear()
        self.history.clear()

    def get_attempts(self, path: RecoveryPath) -> int:
        """Returns the number of attempts executed for a specific recovery path."""
        return self.attempts.get(path.value, 0)

    def route_recovery(self, context: RecoveryContext) -> RecoveryDecision:
        """Determines the next bounded recovery action based on structured context."""
        # -------------------------------------------------------------
        # 0. Check for Normal State (no failure, no no-progress, no tool error)
        # -------------------------------------------------------------
        has_failure = bool(context.failure_classification or context.test_result == "FAILED")
        has_no_progress = bool(
            context.progress_status == "NO_PROGRESS"
            or (context.no_progress_reason and context.no_progress_reason != "NONE")
        )
        has_tool_error = bool(context.tool_error)
        has_budget_pressure = bool(
            context.budget_warning_present
            or (context.remaining_tool_calls is not None and context.remaining_tool_calls <= 10)
            or (context.remaining_time_seconds is not None and context.remaining_time_seconds <= 300)
        )

        if not (has_failure or has_no_progress or has_tool_error or has_budget_pressure):
            return RecoveryDecision(
                state=RecoveryState.NORMAL,
                selected_path=RecoveryPath.NONE,
                action=RecoveryActionType.NONE,
                rationale="Normal execution state; no failure or no-progress recovery condition active.",
                attempt_number=0,
                is_exhausted=False,
            )

        # -------------------------------------------------------------
        # 1. Budget Pressure Priority
        # -------------------------------------------------------------
        if has_budget_pressure:
            attempt_bp = self.attempts.get(RecoveryPath.BUDGET_PRESSURE.value, 0) + 1
            decision_bp = evaluate_budget_pressure(context, attempt_bp)
            if decision_bp is not None:
                return self._record_and_return(RecoveryPath.BUDGET_PRESSURE, decision_bp)

        # -------------------------------------------------------------
        # 2. Tool Failure Priority
        # -------------------------------------------------------------
        if has_tool_error:
            attempt_tf = self.attempts.get(RecoveryPath.TOOL_FAILURE.value, 0) + 1
            decision_tf = evaluate_tool_failure(context, attempt_tf)
            if decision_tf is not None:
                return self._record_and_return(RecoveryPath.TOOL_FAILURE, decision_tf)

        # -------------------------------------------------------------
        # 3. Bad Edit Priority (Regressions or Repeated Edits)
        # -------------------------------------------------------------
        is_bad_edit = (
            context.failure_classification == "REGRESSION"
            or context.no_progress_reason == "REPEATED_EDIT"
        )
        if is_bad_edit:
            attempt_be = self.attempts.get(RecoveryPath.BAD_EDIT.value, 0) + 1
            if attempt_be <= self.max_attempts:
                decision_be = evaluate_bad_edit(context, attempt_be)
                if decision_be is not None:
                    return self._record_and_return(RecoveryPath.BAD_EDIT, decision_be)

        # -------------------------------------------------------------
        # 4. Test Failure Priority
        # -------------------------------------------------------------
        is_test_failure = (
            context.test_result == "FAILED"
            or context.failure_classification in [
                "INCOMPLETE_FIX",
                "WRONG_HYPOTHESIS",
                "NEW_EDGE_CASE",
            ]
            or context.no_progress_reason in [
                "REPEATED_FAILURE",
                "REPEATED_HYPOTHESIS",
            ]
        )
        if is_test_failure:
            attempt_tfail = self.attempts.get(RecoveryPath.TEST_FAILURE.value, 0) + 1
            if attempt_tfail <= self.max_attempts:
                decision_tfail = evaluate_test_failure(context, attempt_tfail)
                if decision_tfail is not None:
                    return self._record_and_return(RecoveryPath.TEST_FAILURE, decision_tfail)

        # -------------------------------------------------------------
        # 5. Search Fallback Priority
        # -------------------------------------------------------------
        is_search = (
            context.no_progress_reason == "NO_NEW_EVIDENCE"
            or context.failure_classification == "UNKNOWN"
            or (not context.source_evidence_sufficient and not has_failure and not is_bad_edit)
        )
        if is_search:
            attempt_sf = self.attempts.get(RecoveryPath.SEARCH_FALLBACK.value, 0) + 1
            if attempt_sf <= 5:
                decision_sf = evaluate_search_fallback(context, attempt_sf)
                if decision_sf is not None:
                    return self._record_and_return(RecoveryPath.SEARCH_FALLBACK, decision_sf)

        # -------------------------------------------------------------
        # 6. All Applicable Recovery Paths Exhausted -> TERMINAL
        # -------------------------------------------------------------
        return RecoveryDecision(
            state=RecoveryState.TERMINAL,
            selected_path=RecoveryPath.NONE,
            action=RecoveryActionType.TERMINATE_PATH,
            rationale="All applicable recovery paths have been exhausted without progress.",
            attempt_number=0,
            is_exhausted=True,
            evidence_used=["Attempts limit reached across eligible paths"],
        )

    def _record_and_return(self, path: RecoveryPath, decision: RecoveryDecision) -> RecoveryDecision:
        """Records attempt count and history, returning the decision."""
        self.attempts[path.value] = self.attempts.get(path.value, 0) + 1
        self.history.append(decision)
        return decision
