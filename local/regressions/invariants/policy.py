"""Invariant checker for POLICY regressions (Stage 45 Phase 5).

Covers:
- REG-POLICY-001: Prohibits edits before reading tests and establishing direct repository evidence.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple
from local.regressions.errors import RegressionExecutionError
from local.scout.trigger import ScoutTriggerContext, is_localization_uncertain


def check_edit_before_evidence_policy() -> Tuple[bool, str, Dict[str, Any]]:
    """Checks REG-POLICY-001: Policy strictly requires reconnaissance and test evidence before code modification."""
    # Scenario A: Attempting action before direct exact reconnaissance is completed
    context_unexplored = ScoutTriggerContext(
        issue_description="Bug in calculation logic",
        candidate_files=[],
        candidate_symbols=[],
        exact_recon_completed=False,  # Recon NOT completed
        source_evidence_sufficient=False,
        has_confirmed_defect_location=False,
    )
    can_trigger, rationale = is_localization_uncertain(context_unexplored)
    if can_trigger:
        raise RegressionExecutionError(
            f"REG-POLICY-001 violation: Reconnaissance bypass allowed when exact_recon_completed is False: {rationale}"
        )
    if "Initial direct repository reconnaissance" not in rationale:
        raise RegressionExecutionError(
            f"REG-POLICY-001 violation: Expected rationale to demand initial direct reconnaissance, got: {rationale}"
        )

    # Scenario B: Committing to edit hypothesis prematurely without source evidence confirmation
    context_premature_hypothesis = ScoutTriggerContext(
        issue_description="Bug in calculation logic",
        candidate_files=["calc.py"],
        candidate_symbols=["compute"],
        exact_recon_completed=True,
        source_evidence_sufficient=False,
        has_confirmed_defect_location=False,
        has_committed_edit_hypothesis=True,  # Premature hypothesis
    )
    can_trigger_hyp, rationale_hyp = is_localization_uncertain(context_premature_hypothesis)
    if can_trigger_hyp:
        raise RegressionExecutionError(
            f"REG-POLICY-001 violation: Premature edit hypothesis allowed to bypass specialist/uncertainty check: {rationale_hyp}"
        )
    if "has already committed to an edit hypothesis" not in rationale_hyp:
        raise RegressionExecutionError(
            f"REG-POLICY-001 violation: Expected hypothesis termination rationale, got: {rationale_hyp}"
        )

    return True, "Reconnaissance discipline and evidence requirements strictly block edits before test/source inspection", {
        "unexplored_rationale": rationale,
        "premature_hypothesis_rationale": rationale_hyp,
    }
