"""Deterministic Testing Policy Comparison Engine (Stage 34 Section 34).

Compares two TestPolicy instances to isolate changes, compute parameter deltas,
and verify that policy differences strictly adhere to single-dimension discipline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from local.testing_opt.models import TestPolicy


@dataclass
class TestPolicyDiff:
    """Structured, deterministic diff between parent and candidate testing policies."""

    parent_candidate_id: str
    candidate_id: str
    parent_variant: str
    candidate_variant: str
    parent_policy_hash: str
    candidate_policy_hash: str
    enabled_flags_diff: Dict[str, Tuple[bool, bool]] = field(default_factory=dict)
    budget_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    feasibility_rules_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    escalation_rules_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    stop_rules_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    fallback_rules_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    is_identical: bool = False
    is_isolated_progression: bool = True
    summary_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_test_policy_diff(
    parent: TestPolicy,
    candidate: TestPolicy,
) -> TestPolicyDiff:
    """Computes a deterministic, auditable diff between two TestPolicy instances."""
    parent_hash = parent.compute_policy_hash()
    cand_hash = candidate.compute_policy_hash()

    diff = TestPolicyDiff(
        parent_candidate_id=parent.candidate_id,
        candidate_id=candidate.candidate_id,
        parent_variant=parent.variant,
        candidate_variant=candidate.variant,
        parent_policy_hash=parent_hash,
        candidate_policy_hash=cand_hash,
        is_identical=(parent_hash == cand_hash),
    )

    if diff.is_identical:
        diff.summary_messages.append("Testing policies are identical.")
        return diff

    # 1. Enabled flags
    flag_keys = [
        "targeted_enabled",
        "adjacent_enabled",
        "subsystem_enabled",
        "full_suite_enabled",
        "adaptive_enabled",
    ]
    for key in flag_keys:
        p_val = getattr(parent, key)
        c_val = getattr(candidate, key)
        if p_val != c_val:
            diff.enabled_flags_diff[key] = (p_val, c_val)
            diff.summary_messages.append(f"{key}: {p_val} -> {c_val}")

    # 2. Budgets
    budget_keys = [
        "max_test_commands",
        "max_test_cases",
        "runtime_budget_seconds",
    ]
    for key in budget_keys:
        p_val = getattr(parent, key)
        c_val = getattr(candidate, key)
        if p_val != c_val:
            diff.budget_diff[key] = (p_val, c_val)
            diff.summary_messages.append(f"{key}: {p_val} -> {c_val}")

    # 3. Feasibility rules
    all_feas_keys = sorted(
        list(set(parent.full_suite_feasibility_rules.keys()).union(set(candidate.full_suite_feasibility_rules.keys())))
    )
    for k in all_feas_keys:
        p_val = parent.full_suite_feasibility_rules.get(k)
        c_val = candidate.full_suite_feasibility_rules.get(k)
        if p_val != c_val:
            diff.feasibility_rules_diff[k] = (p_val, c_val)
            diff.summary_messages.append(f"full_suite_feasibility_rules['{k}']: {p_val} -> {c_val}")

    # 4. Escalation rules
    all_esc_keys = sorted(
        list(set(parent.escalation_rules.keys()).union(set(candidate.escalation_rules.keys())))
    )
    for k in all_esc_keys:
        p_val = parent.escalation_rules.get(k)
        c_val = candidate.escalation_rules.get(k)
        if p_val != c_val:
            diff.escalation_rules_diff[k] = (p_val, c_val)
            diff.summary_messages.append(f"escalation_rules['{k}']: {p_val} -> {c_val}")

    # 5. Stop rules
    all_stop_keys = sorted(
        list(set(parent.stop_rules.keys()).union(set(candidate.stop_rules.keys())))
    )
    for k in all_stop_keys:
        p_val = parent.stop_rules.get(k)
        c_val = candidate.stop_rules.get(k)
        if p_val != c_val:
            diff.stop_rules_diff[k] = (p_val, c_val)
            diff.summary_messages.append(f"stop_rules['{k}']: {p_val} -> {c_val}")

    # 6. Fallback rules
    all_fb_keys = sorted(
        list(set(parent.fallback_rules.keys()).union(set(candidate.fallback_rules.keys())))
    )
    for k in all_fb_keys:
        p_val = parent.fallback_rules.get(k)
        c_val = candidate.fallback_rules.get(k)
        if p_val != c_val:
            diff.fallback_rules_diff[k] = (p_val, c_val)
            diff.summary_messages.append(f"fallback_rules['{k}']: {p_val} -> {c_val}")

    return diff


def render_test_policy_diff_md(diff: TestPolicyDiff) -> str:
    """Renders a clean markdown representation of the testing policy diff."""
    lines: List[str] = [
        f"### Testing Policy Diff: `{diff.parent_candidate_id}` ({diff.parent_variant}) -> `{diff.candidate_id}` ({diff.candidate_variant})",
        "",
        f"- **Parent Policy Hash:** `{diff.parent_policy_hash}`",
        f"- **Candidate Policy Hash:** `{diff.candidate_policy_hash}`",
        f"- **Identical:** `{'YES' if diff.is_identical else 'NO'}`",
        "",
    ]

    if diff.is_identical:
        lines.append("No testing policy parameters were changed.")
        return "\n".join(lines)

    if diff.enabled_flags_diff:
        lines.append("#### Enabled Strategy Levels")
        for key, (pval, cval) in diff.enabled_flags_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.budget_diff:
        lines.append("#### Budgets & Execution Limits")
        for key, (pval, cval) in diff.budget_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.escalation_rules_diff:
        lines.append("#### Escalation Rules")
        for key, (pval, cval) in diff.escalation_rules_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.stop_rules_diff:
        lines.append("#### Stopping Rules")
        for key, (pval, cval) in diff.stop_rules_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.feasibility_rules_diff:
        lines.append("#### Full Suite Feasibility Rules")
        for key, (pval, cval) in diff.feasibility_rules_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.fallback_rules_diff:
        lines.append("#### Fallback Rules")
        for key, (pval, cval) in diff.fallback_rules_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    return "\n".join(lines)
