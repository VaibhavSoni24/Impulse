"""Deterministic uncertainty condition and trigger evaluation for the Scout agent (Stage 21).

Defines:
- ScoutTriggerContext: Observable context capturing repository reconnaissance state
- is_localization_uncertain: Pure deterministic evaluation of localization ambiguity
- evaluate_scout_trigger: Complete trigger decision enforcing loop prevention and policy rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from local.scout.models import ScoutPolicy


@dataclass
class ScoutTriggerContext:
    """Observable context representing current localization and reconnaissance state."""

    issue_description: str = ""
    candidate_files: list[str] = field(default_factory=list)
    candidate_symbols: list[str] = field(default_factory=list)
    exact_recon_completed: bool = False  # Cheap direct reconnaissance (triage/exact search) completed
    source_evidence_sufficient: bool = False  # Direct source inspection confirmed defect location
    has_confirmed_defect_location: bool = False  # Specific file + symbol confirmed
    retrieval_conflicting_or_weak: bool = False  # Exact/semantic results ambiguous or contradictory
    has_committed_edit_hypothesis: bool = False  # Root agent already formed edit hypothesis
    prior_scout_invocations: int = 0  # Number of Scout calls in current episode
    repository_state_version: int = 0  # Monotonic version tracking repo modifications
    last_scout_repo_version: int = -1  # Repo version when Scout was last invoked


def is_localization_uncertain(context: ScoutTriggerContext) -> tuple[bool, str]:
    """Evaluates whether the deterministic localization-uncertainty condition is met.

    SCOUT_TRIGGER fires when:
    1. Cheap direct repository reconnaissance has been performed.
    2. Before committing to a code-edit hypothesis.
    3. Localization remains ambiguous:
       - Multiple candidate files or symbols remain unresolved, OR
       - No candidate locations established despite initial reconnaissance, OR
       - Retrieval evidence is weak, contradictory, or insufficient.
    4. Direct source evidence has NOT yet confirmed a specific defect location.
    """
    # Negative condition 1: If defect location is already confirmed and sufficient
    if context.has_confirmed_defect_location or context.source_evidence_sufficient:
        return False, "Defect location is already confirmed and source evidence is sufficient."

    # Negative condition 2: Cheap direct reconnaissance must precede specialist invocation
    if not context.exact_recon_completed:
        return False, "Initial direct repository reconnaissance (triage / exact search) not yet completed."

    # Negative condition 3: If root agent already committed to an edit hypothesis, reconnaissance is done
    if context.has_committed_edit_hypothesis:
        return False, "Root agent has already committed to an edit hypothesis; reconnaissance phase complete."

    # Ambiguity criteria
    has_multiple_candidates = len(context.candidate_files) > 1 or len(context.candidate_symbols) > 1
    has_no_candidates = len(context.candidate_files) == 0 and len(context.candidate_symbols) == 0
    has_weak_retrieval = context.retrieval_conflicting_or_weak

    if has_multiple_candidates:
        return True, f"Localization uncertain: multiple candidate targets remain ({len(context.candidate_files)} files, {len(context.candidate_symbols)} symbols)."
    if has_no_candidates:
        return True, "Localization uncertain: direct reconnaissance yielded zero confirmed candidate targets."
    if has_weak_retrieval:
        return True, "Localization uncertain: retrieval evidence is conflicting or weak."

    # Exactly one clear candidate identified and no weak retrieval
    return False, "Single unambiguous candidate identified; specialist localization not needed."


def evaluate_scout_trigger(
    context: ScoutTriggerContext,
    policy: ScoutPolicy = ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY,
) -> tuple[bool, str]:
    """Determines whether Scout should be invoked under the specified policy with loop prevention.

    Enforces:
    - Loop prevention: at most 1 invocation per unchanged uncertainty episode.
    - Uncertainty condition evaluation.
    - Policy differentiation:
        - MANDATORY_UNDER_UNCERTAINTY (E_S2): Fires whenever condition is met.
        - AVAILABLE (E_S1): Returns eligibility; invocation remains discretionary for root.
    """
    # Loop prevention check
    if context.prior_scout_invocations > 0 and context.repository_state_version == context.last_scout_repo_version:
        return False, "Scout invocation suppressed by loop prevention: already invoked once for this unchanged uncertainty episode."

    uncertain, reason = is_localization_uncertain(context)
    if not uncertain:
        return False, f"Scout not triggered: {reason}"

    if policy == ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY:
        return True, f"Scout mandatory: {reason}"
    else:
        return True, f"Scout available: {reason}"
