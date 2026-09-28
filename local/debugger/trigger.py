"""Deterministic difficult-failure trigger evaluation for the Debugger agent (Stage 22).

Defines:
- DebuggerTriggerContext: Observable context capturing verification outcome and failure signals
- is_difficult_failure: Pure deterministic evaluation of diagnostic difficulty
- evaluate_debugger_trigger: Complete trigger decision enforcing loop prevention and policy rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from local.debugger.models import DebuggerPolicy
from local.failures.models import FailureClass


@dataclass
class DebuggerTriggerContext:
    """Observable context representing current test failure and diagnostic state."""

    test_result: str = ""  # "PASSED", "FAILED", or ""
    failure_class: str = FailureClass.UNKNOWN.value  # One of the 8 canonical FailureClass values
    stack_trace_ambiguous: bool = False  # Stack trace missing frames or pointing to generic wrapper
    has_clear_single_targeted_fix: bool = False  # Obvious failure with clear single fix (root handles alone)
    initial_investigation_bounded: bool = True  # Direct initial check completed
    causal_edit_unclear: bool = False  # For regressions, is the causal modification ambiguous
    repeated_failure_count: int = 0  # Number of repeated failures on same test
    no_progress_signal: str = ""  # E10 no-progress reason if detected
    hypothesis_contradicted: bool = False  # Previous hypothesis contradicted by test outcome
    multiple_causal_locations: bool = False  # Multiple plausible fault origins
    prior_debugger_invocations: int = 0  # Number of Debugger calls in current episode
    repository_state_version: int = 0  # Monotonic version tracking repo modifications
    last_debugger_repo_version: int = -1  # Repo version when Debugger was last invoked
    last_failure_signature: str = ""  # Signature from previous Debugger invocation
    current_failure_signature: str = ""  # Signature of current failure


def is_difficult_failure(context: DebuggerTriggerContext) -> tuple[bool, str]:
    """Evaluates whether the deterministic difficult-failure condition is met.

    DEBUGGER_TRIGGER fires when:
    1. Meaningful verification has failed (`test_result == 'FAILED'`).
    2. Initial direct failure investigation has been completed (`initial_investigation_bounded == True`).
    3. Ordinary failure evidence is insufficient for an immediate confident fix (`has_clear_single_targeted_fix == False`).
    4. At least one difficult failure condition is present:
       - Failure class is UNKNOWN, WRONG_HYPOTHESIS, or INCOMPLETE_FIX
       - Failure class is REGRESSION with an unclear causal edit
       - Stack/call path is ambiguous or uninformative
       - Previous hypothesis is contradicted by new evidence
       - Multiple plausible causal locations remain
       - Repeated failure or no-progress detected
    """
    # Negative condition 1: Meaningful test failure required
    if context.test_result.upper() != "FAILED":
        return False, "Test result is not FAILED; Debugger is only invoked on meaningful verification failures."

    # Negative condition 2: Ordinary single failure with clear targeted fix is manageable by Root alone
    if context.has_clear_single_targeted_fix:
        return False, "Ordinary targeted test failure with a clear single fix; manageable by root agent alone."

    # Negative condition 3: Initial direct investigation must precede specialist invocation
    if not context.initial_investigation_bounded:
        return False, "Initial direct failure investigation not yet completed."

    # Difficult failure criteria
    fc = context.failure_class.upper() if isinstance(context.failure_class, str) else context.failure_class.value

    if fc == FailureClass.UNKNOWN.value:
        return True, "Difficult failure: failure classification is UNKNOWN and causal origin is unresolved."
    if fc == FailureClass.WRONG_HYPOTHESIS.value:
        return True, "Difficult failure: failure class is WRONG_HYPOTHESIS; causal explanation contradicted."
    if fc == FailureClass.INCOMPLETE_FIX.value:
        return True, "Difficult failure: failure class is INCOMPLETE_FIX; unfulfilled assertions or unhandled branches."
    if fc == FailureClass.REGRESSION.value and context.causal_edit_unclear:
        return True, "Difficult failure: REGRESSION observed with unclear causal edit."
    if context.stack_trace_ambiguous:
        return True, "Difficult failure: call path / stack trace is ambiguous or uninformative."
    if context.hypothesis_contradicted:
        return True, "Difficult failure: previous hypothesis contradicted by new failure evidence."
    if context.multiple_causal_locations:
        return True, "Difficult failure: multiple plausible causal locations remain unresolved."
    if context.repeated_failure_count >= 1 or bool(context.no_progress_signal):
        reason = f"signal '{context.no_progress_signal}'" if context.no_progress_signal else f"repeat count {context.repeated_failure_count}"
        return True, f"Difficult failure: repeated failure / no-progress detected ({reason})."

    return False, "Failure does not satisfy difficult-failure conditions; root agent continues normal triage."


def evaluate_debugger_trigger(
    context: DebuggerTriggerContext,
    policy: DebuggerPolicy = DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE,
) -> tuple[bool, str]:
    """Determines whether Debugger should be invoked under the specified policy with loop prevention.

    Enforces:
    - Policy differentiation: D1 (UNAVAILABLE) always returns False.
    - Loop prevention: at most 1 invocation per unchanged difficult-failure episode.
    - Difficult-failure evaluation.
    """
    if policy == DebuggerPolicy.UNAVAILABLE:
        return False, "Debugger unavailable: candidate policy D1 does not configure Debugger specialist."

    # Loop prevention check: if already invoked and repository version and failure signature are unchanged
    is_same_repo_version = (
        context.prior_debugger_invocations > 0
        and context.repository_state_version == context.last_debugger_repo_version
    )
    is_same_failure = (
        bool(context.last_failure_signature)
        and context.current_failure_signature == context.last_failure_signature
    )
    if is_same_repo_version and (is_same_failure or not context.current_failure_signature):
        return False, "Debugger invocation suppressed by loop prevention: already invoked once for this unchanged difficult-failure episode."

    is_difficult, reason = is_difficult_failure(context)
    if not is_difficult:
        return False, f"Debugger not triggered: {reason}"

    return True, f"Debugger triggered: {reason}"
