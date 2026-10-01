"""Deterministic Skill Scope Validator (Stage 36 Section 15, 26, 27).

Enforces strict domain boundaries on candidate skill modifications:
- TESTING skill:
  - Allowed: test discovery, test selection, validation sequencing, test result interpretation
  - Forbidden: semantic retrieval implementation, recovery controller loops, topology control
- REPOSITORY_TRIAGE skill:
  - Allowed: repository structure, framework/package identification, entry points, build conventions
  - Forbidden: detailed testing escalation, recovery loop policies, semantic retrieval implementation

Rejects cross-scope mutations and prevents skills from usurping root prompt or specialist responsibilities.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from local.skill_opt.models import SkillScopeType

FORBIDDEN_KEYWORDS_BY_SCOPE: dict[str, list[tuple[str, str]]] = {
    SkillScopeType.TESTING.value: [
        ("search_similar_code", "Semantic retrieval tools belong to retrieval subsystem, not testing skill."),
        ("get_code_neighbors", "Graph neighbor tools belong to retrieval subsystem, not testing skill."),
        ("get_code_subgraph", "Subgraph tools belong to retrieval subsystem, not testing skill."),
        ("RecoveryController", "Recovery controller policies belong to recovery subsystem, not testing skill."),
        ("max_same_action_retries", "Recovery retry bounds belong to recovery subsystem, not testing skill."),
        ("sub_agents/scout", "Specialist topology configuration belongs to topology subsystem, not testing skill."),
        ("sub_agents/reviewer", "Specialist topology configuration belongs to topology subsystem, not testing skill."),
    ],
    SkillScopeType.REPOSITORY_TRIAGE.value: [
        ("search_similar_code", "Semantic retrieval tools belong to retrieval subsystem, not repo triage skill."),
        ("get_code_neighbors", "Graph neighbor tools belong to retrieval subsystem, not repo triage skill."),
        ("RecoveryController", "Recovery controller policies belong to recovery subsystem, not repo triage skill."),
        ("max_same_action_retries", "Recovery retry bounds belong to recovery subsystem, not repo triage skill."),
        ("sub_agents/scout", "Specialist topology configuration belongs to topology subsystem, not repo triage skill."),
        ("adaptive_escalation_ladder", "Test escalation policies belong to testing execution subsystem, not repo triage skill."),
        ("patch_extraction", "Patch extraction mechanics belong to evaluation subsystem, not repo triage skill."),
    ],
}


def validate_skill_scope(
    skill_id: str,
    scope: str,
    added_lines: List[str],
) -> Tuple[bool, List[str]]:
    """Validates that newly introduced instruction lines remain strictly within declared skill scope."""
    errors: List[str] = []
    scope_key = scope.upper()

    forbidden_rules = FORBIDDEN_KEYWORDS_BY_SCOPE.get(scope_key, [])
    # Also check if skill_id has specific mapped scope
    if not forbidden_rules:
        if "test" in skill_id.lower():
            forbidden_rules = FORBIDDEN_KEYWORDS_BY_SCOPE.get(SkillScopeType.TESTING.value, [])
        elif "triage" in skill_id.lower() or "repo" in skill_id.lower():
            forbidden_rules = FORBIDDEN_KEYWORDS_BY_SCOPE.get(SkillScopeType.REPOSITORY_TRIAGE.value, [])

    for idx, line in enumerate(added_lines, start=1):
        clean = line.strip().lower()
        if not clean or clean.startswith("#"):
            continue

        for token, rationale in forbidden_rules:
            if token.lower() in clean:
                errors.append(
                    f"Scope leakage detected at added line {idx} ('{clean[:60]}...'): "
                    f"Forbidden token '{token}'. {rationale}"
                )

    return len(errors) == 0, errors
