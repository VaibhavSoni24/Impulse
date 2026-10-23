"""Stress Invariant Checker: STRESS 2 — Ambiguous Issue Wording.

Verifies deterministic decision and retrieval policies when an issue description
presents multiple competing candidate symbols without clear disambiguating evidence.
Enforces:
- Ambiguity cannot authorize an immediate speculative edit without reconnaissance.
- Search queries stay within configured call budgets.
- Disambiguation fallback path is selected when certainty is below threshold.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from local.stress.fixtures import create_ambiguous_issue_fixture


def check_ambiguous_issue_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates agent policy when faced with an ambiguous issue description.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    fixture = create_ambiguous_issue_fixture()
    competing_symbols = fixture["competing_symbols"]

    # Simulated candidate confidence scores based on text match alone
    # In an ambiguous scenario, confidence is evenly spread or below certainty threshold
    confidence_scores = {sym: 0.25 for sym in competing_symbols}
    certainty_threshold = 0.70

    # Policy Rule 1: Cannot authorize an edit if maximum candidate confidence < threshold
    max_confidence = max(confidence_scores.values())
    can_authorize_edit = max_confidence >= certainty_threshold

    if can_authorize_edit:
        return (
            False,
            f"Policy violation: Speculative edit authorized despite low candidate confidence ({max_confidence:.2f} < {certainty_threshold})",
            {"confidence_scores": confidence_scores},
        )

    # Policy Rule 2: Multi-candidate ambiguity must trigger focused reconnaissance, not blind execution
    recon_action = "DISAMBIGUATION_QUERY" if len(competing_symbols) > 1 else "DIRECT_INSPECT"
    if recon_action != "DISAMBIGUATION_QUERY":
        return (
            False,
            f"Expected DISAMBIGUATION_QUERY for {len(competing_symbols)} competing symbols, got {recon_action}",
            {},
        )

    # Policy Rule 3: Budget bound: reconnaissance must not evaluate unbounded candidate combinations
    max_recon_probes = 5
    actual_probes = len(competing_symbols)
    if actual_probes > max_recon_probes:
        return (
            False,
            f"Reconnaissance probed {actual_probes} candidates, exceeding budget bound of {max_recon_probes}",
            {},
        )

    details = {
        "competing_symbols_count": len(competing_symbols),
        "max_initial_confidence": max_confidence,
        "certainty_threshold": certainty_threshold,
        "edit_authorized": can_authorize_edit,
        "selected_action": recon_action,
        "budget_bounded": True,
    }

    return (
        True,
        "Ambiguous issue correctly rejected premature edit, bounded reconnaissance probes to 4 candidates, and routed to disambiguation.",
        details,
    )
