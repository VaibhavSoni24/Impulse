"""Recovery policy rules for the five recovery families (Stage 20 / Candidate E11).

Defines bounded recovery sequences and safeguards for:
1. Search Fallback (semantic -> exact -> tree -> graph)
2. Test Failure (classify -> diff -> stack -> revise hypothesis)
3. Bad Edit (diff -> repair/revert -> targeted test)
4. Tool Failure (retry -> alternate tool -> terminate)
5. Budget Pressure (stop exploration -> targeted validation -> final review)
"""

from __future__ import annotations

from local.failures import FailureClass
from local.progress import NoProgressReason, ProgressStatus
from local.recovery.models import (
    RecoveryActionType,
    RecoveryContext,
    RecoveryDecision,
    RecoveryPath,
    RecoveryState,
)

# Compatible tool fallbacks (existing competition tools only)
ALTERNATE_TOOL_MAP: dict[str, str] = {
    "search_similar_code": "run_command",  # Fallback to exact text search / grep
    "get_code_neighbors": "read_file",     # Fallback to direct source inspection
    "get_code_subgraph": "get_code_neighbors",  # Fallback to 1-hop neighbor inspection
    "edit_file": "write_file",             # Fallback to complete file overwrite
}

# Configurable default limits for recovery bounds
MAX_TOOL_RETRIES = 1
MAX_PATH_ATTEMPTS = 2
BUDGET_CALL_THRESHOLD = 10
BUDGET_TIME_THRESHOLD_SECONDS = 300.0


def evaluate_budget_pressure(context: RecoveryContext, attempt: int) -> RecoveryDecision | None:
    """Checks if budget constraints require budget-pressure recovery."""
    is_budget_pressure = (
        context.budget_warning_present
        or (context.remaining_tool_calls is not None and context.remaining_tool_calls <= BUDGET_CALL_THRESHOLD)
        or (context.remaining_time_seconds is not None and context.remaining_time_seconds <= BUDGET_TIME_THRESHOLD_SECONDS)
    )
    if not is_budget_pressure:
        return None

    if attempt == 1:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.BUDGET_PRESSURE,
            action=RecoveryActionType.STOP_EXPLORATION,
            rationale="Budget pressure detected; terminating low-value exploratory queries.",
            attempt_number=attempt,
            evidence_used=[
                f"remaining_tool_calls={context.remaining_tool_calls}",
                f"remaining_time_seconds={context.remaining_time_seconds}",
                f"budget_warning={context.budget_warning_present}",
            ],
        )
    elif attempt == 2:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.BUDGET_PRESSURE,
            action=RecoveryActionType.TARGETED_VALIDATION,
            rationale="Executing final high-value targeted verification before session cutoff.",
            attempt_number=attempt,
            evidence_used=["Budget pressure escalation"],
        )
    else:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXHAUSTED,
            selected_path=RecoveryPath.BUDGET_PRESSURE,
            action=RecoveryActionType.FINAL_REVIEW,
            rationale="Budget pressure limit reached; proceeding to final patch diff inspection.",
            attempt_number=attempt,
            is_exhausted=True,
            evidence_used=["Final review reached under budget pressure"],
        )


def evaluate_tool_failure(context: RecoveryContext, attempt: int) -> RecoveryDecision | None:
    """Evaluates tool invocation failures (harness or tool errors)."""
    if not context.tool_error:
        return None

    # Do NOT retry invalid command syntax (that is a deterministic user error, not transient)
    if context.is_command_syntax_error:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXHAUSTED,
            selected_path=RecoveryPath.TOOL_FAILURE,
            action=RecoveryActionType.TERMINATE_PATH,
            rationale="Command invocation failed due to invalid CLI syntax; retry disallowed.",
            attempt_number=attempt,
            is_exhausted=True,
            evidence_used=[f"syntax_error: {context.tool_error}"],
        )

    tool_name = context.latest_tool_name or ""
    if attempt <= MAX_TOOL_RETRIES:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.TOOL_FAILURE,
            action=RecoveryActionType.RETRY_TOOL,
            target=tool_name,
            rationale=f"Bounded single retry of tool '{tool_name}' after invocation failure.",
            attempt_number=attempt,
            evidence_used=[f"tool_error: {context.tool_error}"],
        )
    elif attempt == MAX_TOOL_RETRIES + 1:
        alt_tool = ALTERNATE_TOOL_MAP.get(tool_name)
        if alt_tool:
            return RecoveryDecision(
                state=RecoveryState.RECOVERY_EXECUTING,
                selected_path=RecoveryPath.TOOL_FAILURE,
                action=RecoveryActionType.USE_ALTERNATE_TOOL,
                target=alt_tool,
                rationale=f"Tool retry exhausted; falling back to compatible alternate tool '{alt_tool}'.",
                attempt_number=attempt,
                evidence_used=[f"primary_tool: {tool_name}", f"alternate_tool: {alt_tool}"],
            )

    return RecoveryDecision(
        state=RecoveryState.RECOVERY_EXHAUSTED,
        selected_path=RecoveryPath.TOOL_FAILURE,
        action=RecoveryActionType.TERMINATE_PATH,
        rationale=f"Tool '{tool_name}' failure recovery exhausted; terminating action path.",
        attempt_number=attempt,
        is_exhausted=True,
        evidence_used=["Tool retries and alternates exhausted"],
    )


def evaluate_bad_edit(context: RecoveryContext, attempt: int) -> RecoveryDecision | None:
    """Evaluates regressions or repeated invalid edits."""
    is_bad_edit = (
        context.failure_classification == FailureClass.REGRESSION.value
        or context.no_progress_reason == NoProgressReason.REPEATED_EDIT.value
    )
    if not is_bad_edit:
        return None

    if not context.diff_inspected:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.BAD_EDIT,
            action=RecoveryActionType.INSPECT_DIFF,
            rationale="Regression or repeated edit detected; inspecting current diff before mutating code.",
            attempt_number=attempt,
            evidence_used=[f"failure_class={context.failure_classification}"],
        )

    # Identify candidate file for repair / revert
    # Must adhere to SAFE CHANGE OWNERSHIP
    candidate_files = context.agent_owned_files or context.modified_files
    target_file = candidate_files[-1] if candidate_files else ""

    # Check ownership safety: NEVER revert pre-existing or ambiguous files
    if target_file and not context.is_safe_to_revert(target_file):
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.BAD_EDIT,
            action=RecoveryActionType.REVISE_HYPOTHESIS,
            target="",
            rationale=(
                f"Modified file '{target_file}' is not safely owned by agent "
                "(pre-existing change detected); destructive revert prohibited. Revising hypothesis instead."
            ),
            attempt_number=attempt,
            evidence_used=["Unrelated pre-existing change preserved"],
        )

    if attempt == 1 and target_file:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.BAD_EDIT,
            action=RecoveryActionType.REPAIR_EDIT,
            target=target_file,
            rationale=f"Attempting bounded in-place repair of recent modification in '{target_file}'.",
            attempt_number=attempt,
            evidence_used=[f"agent_owned_file: {target_file}"],
        )
    elif attempt == 2 and target_file:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.BAD_EDIT,
            action=RecoveryActionType.REVERT_EDIT,
            target=target_file,
            rationale=f"In-place repair ineffective; reverting agent-owned edit in '{target_file}'.",
            attempt_number=attempt,
            evidence_used=[f"agent_owned_file: {target_file}"],
        )

    return RecoveryDecision(
        state=RecoveryState.RECOVERY_EXHAUSTED,
        selected_path=RecoveryPath.BAD_EDIT,
        action=RecoveryActionType.TARGETED_VALIDATION,
        rationale="Bad edit recovery actions complete; re-running targeted verification.",
        attempt_number=attempt,
        is_exhausted=True,
        evidence_used=["Bad edit recovery sequence exhausted"],
    )


def evaluate_test_failure(context: RecoveryContext, attempt: int) -> RecoveryDecision | None:
    """Evaluates test verification failures (classify -> diff -> stack -> revise hypothesis)."""
    is_test_failure = (
        context.test_result == "FAILED"
        or context.failure_classification in [
            FailureClass.INCOMPLETE_FIX.value,
            FailureClass.WRONG_HYPOTHESIS.value,
            FailureClass.NEW_EDGE_CASE.value,
        ]
        or context.no_progress_reason in [
            NoProgressReason.REPEATED_FAILURE.value,
            NoProgressReason.REPEATED_HYPOTHESIS.value,
        ]
    )
    if not is_test_failure:
        return None

    # Step 1: Inspect diff if not already inspected
    if not context.diff_inspected and context.modified_files:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.TEST_FAILURE,
            action=RecoveryActionType.INSPECT_DIFF,
            rationale="Test failure observed; inspecting active diff to align verification with changes.",
            attempt_number=attempt,
            evidence_used=[
                f"test_result={context.test_result}",
                f"failure_class={context.failure_classification}",
            ],
        )

    # Step 2: Inspect stack trace if traceback evidence is present
    if context.has_stack_trace and attempt == 1:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.TEST_FAILURE,
            action=RecoveryActionType.INSPECT_STACK,
            target=context.stack_trace_snippet[:100],
            rationale="Inspecting failure traceback and call path directly in source code.",
            attempt_number=attempt,
            evidence_used=[
                f"failure_class={context.failure_classification}",
                "Stack trace present in test output",
            ],
        )

    # Step 3: Revise hypothesis if wrong hypothesis or repeated hypothesis or attempt 1 without stack
    if (
        attempt == 1
        or context.failure_classification == FailureClass.WRONG_HYPOTHESIS.value
        or context.no_progress_reason == NoProgressReason.REPEATED_HYPOTHESIS.value
        or (attempt == 2 and context.has_stack_trace)
    ):
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.TEST_FAILURE,
            action=RecoveryActionType.REVISE_HYPOTHESIS,
            rationale="Evidence contradicts previous root cause; formulating revised hypothesis.",
            attempt_number=attempt,
            evidence_used=[f"failure_class={context.failure_classification}"],
        )

    return RecoveryDecision(
        state=RecoveryState.RECOVERY_EXHAUSTED,
        selected_path=RecoveryPath.TEST_FAILURE,
        action=RecoveryActionType.TARGETED_VALIDATION,
        rationale="Hypothesis and source review complete; running minimal targeted verification.",
        attempt_number=attempt,
        is_exhausted=True,
        evidence_used=[
            f"failure_class={context.failure_classification}",
            "Minimal targeted verification",
        ],
    )


def evaluate_search_fallback(context: RecoveryContext, attempt: int) -> RecoveryDecision | None:
    """Evaluates search fallback ladder (semantic -> exact -> tree -> graph)."""
    # Triggered when localization is ambiguous or no new evidence appears during reconnaissance
    is_search_needed = (
        context.no_progress_reason == NoProgressReason.NO_NEW_EVIDENCE.value
        or context.failure_classification == FailureClass.UNKNOWN.value
        or (not context.source_evidence_sufficient and not context.failure_classification and context.test_result != "FAILED")
    )
    if not is_search_needed:
        return None

    if context.source_evidence_sufficient:
        return RecoveryDecision(
            state=RecoveryState.NORMAL,
            selected_path=RecoveryPath.SEARCH_FALLBACK,
            action=RecoveryActionType.NONE,
            rationale="Source evidence is already sufficient; search fallback not required.",
            attempt_number=attempt,
            is_exhausted=True,
            evidence_used=["source_evidence_sufficient=True"],
        )

    history = [s.lower() for s in context.retrieval_history]
    if "semantic" not in history:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_SELECTED,
            selected_path=RecoveryPath.SEARCH_FALLBACK,
            action=RecoveryActionType.FALLBACK_SEMANTIC,
            rationale="Step 1 in search fallback ladder: invoking selective semantic search.",
            attempt_number=attempt,
            evidence_used=["semantic not yet in retrieval history"],
        )
    elif "exact" not in history:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.SEARCH_FALLBACK,
            action=RecoveryActionType.FALLBACK_EXACT_SEARCH,
            rationale="Step 2 in search fallback ladder: falling back to exact text / symbol search.",
            attempt_number=attempt,
            evidence_used=["exact not yet in retrieval history"],
        )
    elif "tree" not in history:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.SEARCH_FALLBACK,
            action=RecoveryActionType.FALLBACK_TREE_INSPECTION,
            rationale="Step 3 in search fallback ladder: inspecting directory tree and module layout.",
            attempt_number=attempt,
            evidence_used=["tree not yet in retrieval history"],
        )
    elif "graph" not in history:
        return RecoveryDecision(
            state=RecoveryState.RECOVERY_EXECUTING,
            selected_path=RecoveryPath.SEARCH_FALLBACK,
            action=RecoveryActionType.FALLBACK_GRAPH,
            rationale="Step 4 in search fallback ladder: querying relational graph neighbors.",
            attempt_number=attempt,
            evidence_used=["graph not yet in retrieval history"],
        )

    return RecoveryDecision(
        state=RecoveryState.RECOVERY_EXHAUSTED,
        selected_path=RecoveryPath.SEARCH_FALLBACK,
        action=RecoveryActionType.TERMINATE_PATH,
        rationale="All 4 search fallback levels exhausted; stopping retrieval exploration.",
        attempt_number=attempt,
        is_exhausted=True,
        evidence_used=["search fallback ladder fully exhausted"],
    )
