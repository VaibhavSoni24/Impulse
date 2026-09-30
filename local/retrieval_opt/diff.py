"""Deterministic Retrieval Policy Comparison Engine (Stage 33 Section 29).

Compares two RetrievalPolicy instances to isolate changes, compute parameter deltas,
and verify that policy differences strictly adhere to single-dimension discipline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Dict, List, Tuple

from local.retrieval_opt.models import RetrievalPolicy


@dataclass
class RetrievalPolicyDiff:
    """Structured, deterministic diff between parent and candidate retrieval policies."""

    parent_candidate_id: str
    candidate_id: str
    parent_variant: str
    candidate_variant: str
    parent_policy_hash: str
    candidate_policy_hash: str
    enabled_flags_diff: Dict[str, Tuple[bool, bool]] = field(default_factory=dict)
    budget_diff: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    parameters_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    triggers_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    dynamic_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    fallback_diff: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    is_identical: bool = False
    is_isolated_progression: bool = True
    summary_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_retrieval_policy_diff(
    parent: RetrievalPolicy,
    candidate: RetrievalPolicy,
) -> RetrievalPolicyDiff:
    """Computes a deterministic, auditable diff between two RetrievalPolicy instances."""
    parent_hash = parent.compute_policy_hash()
    cand_hash = candidate.compute_policy_hash()

    diff = RetrievalPolicyDiff(
        parent_candidate_id=parent.candidate_id,
        candidate_id=candidate.candidate_id,
        parent_variant=parent.variant,
        candidate_variant=candidate.variant,
        parent_policy_hash=parent_hash,
        candidate_policy_hash=cand_hash,
        is_identical=(parent_hash == cand_hash),
    )

    if diff.is_identical:
        diff.summary_messages.append("Policies are identical.")
        return diff

    # 1. Enabled flags
    flag_keys = [
        "semantic_retrieval_enabled",
        "neighbor_retrieval_enabled",
        "subgraph_retrieval_enabled",
        "dynamic_depth_enabled",
    ]
    for key in flag_keys:
        p_val = getattr(parent, key)
        c_val = getattr(candidate, key)
        if p_val != c_val:
            diff.enabled_flags_diff[key] = (p_val, c_val)
            diff.summary_messages.append(f"{key}: {p_val} -> {c_val}")

    # 2. Budget limits
    budget_keys = [
        "max_retrieval_calls",
        "max_semantic_calls",
        "max_neighbor_calls",
        "max_subgraph_calls",
        "max_retrieved_items",
    ]
    for key in budget_keys:
        p_val = getattr(parent, key)
        c_val = getattr(candidate, key)
        if p_val != c_val:
            diff.budget_diff[key] = (p_val, c_val)
            diff.summary_messages.append(f"{key}: {p_val} -> {c_val}")

    # 3. Parameters
    param_keys = [
        "semantic_top_k",
        "neighbor_depth",
        "subgraph_depth",
        "subgraph_breadth_k",
        "similarity_threshold",
        "expansion_policy",
    ]
    for key in param_keys:
        p_val = getattr(parent, key)
        c_val = getattr(candidate, key)
        if p_val != c_val:
            diff.parameters_diff[key] = (p_val, c_val)
            diff.summary_messages.append(f"{key}: {p_val} -> {c_val}")

    # 4. Trigger conditions
    all_trigger_keys = sorted(
        list(set(parent.trigger_conditions.keys()).union(set(candidate.trigger_conditions.keys())))
    )
    for t_key in all_trigger_keys:
        p_val = parent.trigger_conditions.get(t_key)
        c_val = candidate.trigger_conditions.get(t_key)
        if p_val != c_val:
            diff.triggers_diff[t_key] = (p_val, c_val)
            diff.summary_messages.append(f"trigger_conditions['{t_key}']: {p_val} -> {c_val}")

    # 5. Dynamic config
    all_dyn_keys = sorted(
        list(set(parent.dynamic_config.keys()).union(set(candidate.dynamic_config.keys())))
    )
    for d_key in all_dyn_keys:
        p_val = parent.dynamic_config.get(d_key)
        c_val = candidate.dynamic_config.get(d_key)
        if p_val != c_val:
            diff.dynamic_diff[d_key] = (p_val, c_val)
            diff.summary_messages.append(f"dynamic_config['{d_key}']: {p_val} -> {c_val}")

    # 6. Fallback behavior
    all_fb_keys = sorted(
        list(set(parent.fallback_behavior.keys()).union(set(candidate.fallback_behavior.keys())))
    )
    for fb_key in all_fb_keys:
        p_val = parent.fallback_behavior.get(fb_key)
        c_val = candidate.fallback_behavior.get(fb_key)
        if p_val != c_val:
            diff.fallback_diff[fb_key] = (p_val, c_val)
            diff.summary_messages.append(f"fallback_behavior['{fb_key}']: {p_val} -> {c_val}")

    return diff


def render_retrieval_policy_diff_md(diff: RetrievalPolicyDiff) -> str:
    """Renders a human-readable markdown representation of the policy diff."""
    lines: List[str] = [
        f"### Policy Diff: `{diff.parent_candidate_id}` ({diff.parent_variant}) -> `{diff.candidate_id}` ({diff.candidate_variant})",
        "",
        f"- **Parent Policy Hash:** `{diff.parent_policy_hash}`",
        f"- **Candidate Policy Hash:** `{diff.candidate_policy_hash}`",
        f"- **Identical:** `{'YES' if diff.is_identical else 'NO'}`",
        "",
    ]

    if diff.is_identical:
        lines.append("No policy parameters were changed.")
        return "\n".join(lines)

    if diff.enabled_flags_diff:
        lines.append("#### Enabled Features")
        for key, (pval, cval) in diff.enabled_flags_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.budget_diff:
        lines.append("#### Budgets & Limits")
        for key, (pval, cval) in diff.budget_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.parameters_diff:
        lines.append("#### Parameters & Depth")
        for key, (pval, cval) in diff.parameters_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.triggers_diff:
        lines.append("#### Trigger Conditions")
        for key, (pval, cval) in diff.triggers_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.dynamic_diff:
        lines.append("#### Dynamic Expansion Config")
        for key, (pval, cval) in diff.dynamic_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    if diff.fallback_diff:
        lines.append("#### Fallback Behavior")
        for key, (pval, cval) in diff.fallback_diff.items():
            lines.append(f"- `{key}`: `{pval}` -> `{cval}`")
        lines.append("")

    return "\n".join(lines)
