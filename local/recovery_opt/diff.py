"""Deterministic Recovery Policy Diffing Engine (Stage 35 Section 39).

Calculates exact, deterministic differences between baseline and candidate recovery policies:
- trigger changes
- action changes
- retry-bound changes
- fallback changes
- stop-condition changes
- prompt-specific recovery instruction changes
- all unchanged recovery settings

Enforces proof that the experiment changed strictly recovery-specific parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from local.recovery_opt.models import RecoveryPolicy, RetryBudgetConfig


def diff_recovery_policies(
    baseline: RecoveryPolicy,
    candidate: RecoveryPolicy,
) -> dict[str, Any]:
    """Computes structured dictionary of differences between two RecoveryPolicy instances."""
    diff: dict[str, Any] = {
        "baseline_variant": baseline.variant,
        "candidate_variant": candidate.variant,
        "baseline_hash": baseline.compute_policy_hash(),
        "candidate_hash": candidate.compute_policy_hash(),
        "is_identical": baseline.compute_policy_hash() == candidate.compute_policy_hash(),
        "trigger_changes": {},
        "action_changes": {},
        "retry_bound_changes": {},
        "fallback_changes": {},
        "stop_condition_changes": {},
        "feature_flag_changes": {},
        "prompt_instruction_change": None,
        "unchanged_settings": {},
    }

    # 1. Feature flags
    ff_keys = [
        "early_detection_enabled",
        "loop_guard_enabled",
        "alternate_path_routing_enabled",
        "no_progress_threshold_turns",
    ]
    for k in ff_keys:
        b_val = getattr(baseline, k)
        c_val = getattr(candidate, k)
        if b_val != c_val:
            diff["feature_flag_changes"][k] = {"baseline": b_val, "candidate": c_val}
        else:
            diff["unchanged_settings"][k] = b_val

    # 2. Retry bounds
    b_rb = baseline.retry_budgets.to_dict() if isinstance(baseline.retry_budgets, RetryBudgetConfig) else dict(baseline.retry_budgets)
    c_rb = candidate.retry_budgets.to_dict() if isinstance(candidate.retry_budgets, RetryBudgetConfig) else dict(candidate.retry_budgets)
    for k in sorted(set(b_rb.keys()).union(c_rb.keys())):
        b_val = b_rb.get(k)
        c_val = c_rb.get(k)
        if b_val != c_val:
            diff["retry_bound_changes"][k] = {"baseline": b_val, "candidate": c_val}
        else:
            diff["unchanged_settings"][f"retry_budget.{k}"] = b_val

    # 3. Triggers
    b_trig = dict(baseline.triggers)
    c_trig = dict(candidate.triggers)
    for k in sorted(set(b_trig.keys()).union(c_trig.keys())):
        b_val = b_trig.get(k)
        c_val = c_trig.get(k)
        if b_val != c_val:
            diff["trigger_changes"][k] = {"baseline": b_val, "candidate": c_val}
        else:
            diff["unchanged_settings"][f"triggers.{k}"] = b_val

    # 4. Actions
    b_act = dict(baseline.actions)
    c_act = dict(candidate.actions)
    for k in sorted(set(b_act.keys()).union(c_act.keys())):
        b_val = b_act.get(k)
        c_val = c_act.get(k)
        if b_val != c_val:
            diff["action_changes"][k] = {"baseline": b_val, "candidate": c_val}
        else:
            diff["unchanged_settings"][f"actions.{k}"] = b_val

    # 5. Fallback rules
    b_fb = dict(baseline.fallback_rules)
    c_fb = dict(candidate.fallback_rules)
    for k in sorted(set(b_fb.keys()).union(c_fb.keys())):
        b_val = b_fb.get(k)
        c_val = c_fb.get(k)
        if b_val != c_val:
            diff["fallback_changes"][k] = {"baseline": b_val, "candidate": c_val}
        else:
            diff["unchanged_settings"][f"fallback_rules.{k}"] = b_val

    # 6. Stop conditions
    b_sc = set(baseline.stop_conditions)
    c_sc = set(candidate.stop_conditions)
    added_sc = sorted(list(c_sc - b_sc))
    removed_sc = sorted(list(b_sc - c_sc))
    common_sc = sorted(list(b_sc.intersection(c_sc)))
    if added_sc or removed_sc:
        diff["stop_condition_changes"] = {
            "added": added_sc,
            "removed": removed_sc,
        }
    if common_sc:
        diff["unchanged_settings"]["stop_conditions"] = common_sc

    # 7. Prompt instruction
    if baseline.prompt_instruction != candidate.prompt_instruction:
        diff["prompt_instruction_change"] = {
            "baseline": baseline.prompt_instruction,
            "candidate": candidate.prompt_instruction,
        }
    else:
        diff["unchanged_settings"]["prompt_instruction"] = baseline.prompt_instruction

    return diff


def format_recovery_policy_diff_md(
    baseline: RecoveryPolicy,
    candidate: RecoveryPolicy,
) -> str:
    """Renders a clean, structured Markdown diff report between two RecoveryPolicy instances."""
    diff = diff_recovery_policies(baseline, candidate)
    lines: list[str] = [
        f"# Recovery Policy Diff: {baseline.variant} vs. {candidate.variant}",
        "",
        f"- **Baseline Variant:** `{baseline.variant}` (hash: `{diff['baseline_hash'][:12]}`)",
        f"- **Candidate Variant:** `{candidate.variant}` (hash: `{diff['candidate_hash'][:12]}`)",
        f"- **Identical:** `{'YES' if diff['is_identical'] else 'NO'}`",
        "",
    ]

    if diff["is_identical"]:
        lines.append("No configuration differences detected between baseline and candidate.")
        return "\n".join(lines)

    lines.append("## Changed Settings")
    lines.append("")

    # Feature flags
    if diff["feature_flag_changes"]:
        lines.append("### Feature Flags & Thresholds")
        lines.append("| Setting | Baseline | Candidate |")
        lines.append("| :--- | :--- | :--- |")
        for k, v in sorted(diff["feature_flag_changes"].items()):
            lines.append(f"| `{k}` | `{v['baseline']}` | `{v['candidate']}` |")
        lines.append("")

    # Retry bounds
    if diff["retry_bound_changes"]:
        lines.append("### Retry Budget Bounds")
        lines.append("| Bound Parameter | Baseline | Candidate |")
        lines.append("| :--- | :--- | :--- |")
        for k, v in sorted(diff["retry_bound_changes"].items()):
            lines.append(f"| `{k}` | `{v['baseline']}` | `{v['candidate']}` |")
        lines.append("")

    # Triggers
    if diff["trigger_changes"]:
        lines.append("### Trigger Thresholds")
        lines.append("| Trigger Key | Baseline | Candidate |")
        lines.append("| :--- | :--- | :--- |")
        for k, v in sorted(diff["trigger_changes"].items()):
            lines.append(f"| `{k}` | `{v['baseline']}` | `{v['candidate']}` |")
        lines.append("")

    # Actions
    if diff["action_changes"]:
        lines.append("### Action Configurations")
        lines.append("| Action Setting | Baseline | Candidate |")
        lines.append("| :--- | :--- | :--- |")
        for k, v in sorted(diff["action_changes"].items()):
            lines.append(f"| `{k}` | `{v['baseline']}` | `{v['candidate']}` |")
        lines.append("")

    # Fallbacks
    if diff["fallback_changes"]:
        lines.append("### Fallback Rules")
        lines.append("| Condition | Baseline Rule | Candidate Rule |")
        lines.append("| :--- | :--- | :--- |")
        for k, v in sorted(diff["fallback_changes"].items()):
            lines.append(f"| `{k}` | `{v['baseline']}` | `{v['candidate']}` |")
        lines.append("")

    # Stop conditions
    if diff["stop_condition_changes"]:
        lines.append("### Stop Conditions")
        if diff["stop_condition_changes"].get("added"):
            lines.append(f"- **Added Conditions:** {', '.join(f'`{c}`' for c in diff['stop_condition_changes']['added'])}")
        if diff["stop_condition_changes"].get("removed"):
            lines.append(f"- **Removed Conditions:** {', '.join(f'`{c}`' for c in diff['stop_condition_changes']['removed'])}")
        lines.append("")

    # Prompt instruction
    if diff["prompt_instruction_change"]:
        lines.append("### Recovery-Specific Prompt Instruction")
        lines.append(f"- **Baseline:** `{diff['prompt_instruction_change']['baseline']}`")
        lines.append(f"- **Candidate:** `{diff['prompt_instruction_change']['candidate']}`")
        lines.append("")

    # Unchanged
    lines.append("## Unchanged Settings")
    lines.append(f"Total unchanged configuration parameters: **{len(diff['unchanged_settings'])}**")
    lines.append("")

    return "\n".join(lines)
