"""Concise, deterministic model-facing state rendering for turn continuity."""

from __future__ import annotations

from local.task_state.models import TaskState


def render_model_context(state: TaskState, max_items: int = 5) -> str:
    """Renders a concise, bounded markdown block of task state for model context.

    Prevents raw unbounded state dumps while ensuring turn continuity.
    """
    lines: list[str] = ["## Active Task State\n"]

    # 1. Summary
    summary_text = state.summary.strip() if state.summary else "Not yet established."
    lines.append(f"### Summary\n{summary_text}\n")

    # 2. Hypothesis
    hypo_text = state.hypothesis.strip() if state.hypothesis else "None formulated yet."
    lines.append(f"### Current Working Hypothesis\n{hypo_text}\n")

    # 3. Key Evidence (most recent items bounded by max_items)
    lines.append("### Key Evidence")
    if state.evidence:
        for ev in state.evidence[-max_items:]:
            status_tag = ""
            if ev.supports_hypothesis is True:
                status_tag = " [Supports]"
            elif ev.supports_hypothesis is False:
                status_tag = " [Refutes]"
            src = f" (via `{ev.source_command_or_file}`)" if ev.source_command_or_file else ""
            lines.append(f"- {ev.observation}{status_tag}{src}")
    else:
        lines.append("- No evidence recorded yet.")
    lines.append("")

    # 4. Tactical Plan
    lines.append("### Tactical Plan")
    if state.plan:
        for i, step in enumerate(state.plan[:max_items], 1):
            lines.append(f"{i}. {step}")
    else:
        lines.append("1. Inspect repository state and formulate hypothesis.")
    lines.append("")

    # 5. Recent Actions (Edits & Tests)
    lines.append("### Recent Actions & Outcomes")
    if state.edits:
        recent_edits = [f"`{ed.path}` ({ed.description})" for ed in state.edits[-max_items:]]
        lines.append(f"- Edits Made: {'; '.join(recent_edits)}")
    else:
        lines.append("- Edits Made: None yet.")

    if state.tests:
        recent_tests = [f"`{t.command}` -> {t.outcome}" for t in state.tests[-max_items:]]
        lines.append(f"- Recent Tests: {'; '.join(recent_tests)}")
    else:
        lines.append("- Recent Tests: None executed yet.")

    unresolved_failures = [f"{f.failure_type}: {f.description}" for f in state.failures if not f.resolved][-max_items:]
    if unresolved_failures:
        lines.append(f"- Active Failures: {'; '.join(unresolved_failures)}")
    else:
        lines.append("- Active Failures: None active.")
    lines.append("")

    # 6. Progress and Verification
    lines.append("### Continuity Status")
    lines.append(f"- No-Progress Count: {state.no_progress_count}")
    rev = state.final_review
    review_status = "Complete" if (rev.diff_inspected and rev.intended_files_only) else "Pending"
    lines.append(f"- Final Review: {review_status}")

    return "\n".join(lines).strip()
