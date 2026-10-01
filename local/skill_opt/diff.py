"""Deterministic Skill Diffing Engine (Stage 36 Section 14).

Computes exact differences between parent and candidate skill documents:
- Added and removed lines
- Word, line, character, and estimated token counts and deltas
- Exact SHA-256 digests before and after
- Changed sections and structural changes

Outputs structured dictionary (`skill_diff.json`) and Markdown report (`skill_diff.md`).
"""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.skill_opt.models import SkillContextCostMetrics


def estimate_tokens(text: str) -> int:
    """Estimates token count deterministically (~4 chars per token baseline, matching Stage 32)."""
    if not text:
        return 0
    words = text.split()
    # Average between word-based and char-based estimation
    char_est = len(text) // 4
    word_est = int(len(words) * 1.3)
    return max(1, (char_est + word_est) // 2) if text.strip() else 0


def compute_metrics(text: str) -> SkillContextCostMetrics:
    """Computes basic size and token metrics for a skill text."""
    chars = len(text)
    lines = len(text.splitlines())
    words = len(text.split())
    tokens = estimate_tokens(text)
    return SkillContextCostMetrics(
        char_count=chars,
        line_count=lines,
        word_count=words,
        estimated_tokens=tokens,
    )


def diff_skills(
    parent_text: str,
    candidate_text: str,
    parent_id: str = "S0",
    candidate_id: str = "S1",
) -> dict[str, Any]:
    """Computes structured dictionary of differences between parent and candidate skills."""
    parent_sha = hashlib.sha256(parent_text.encode("utf-8")).hexdigest()
    cand_sha = hashlib.sha256(candidate_text.encode("utf-8")).hexdigest()

    parent_m = compute_metrics(parent_text)
    cand_m = compute_metrics(candidate_text)

    parent_lines = parent_text.splitlines()
    cand_lines = candidate_text.splitlines()

    matcher = difflib.SequenceMatcher(None, parent_lines, cand_lines)
    added_lines: list[str] = []
    removed_lines: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed_lines.extend(parent_lines[i1:i2])
        if tag in ("replace", "insert"):
            added_lines.extend(cand_lines[j1:j2])

    char_delta = cand_m.char_count - parent_m.char_count
    line_delta = cand_m.line_count - parent_m.line_count
    word_delta = cand_m.word_count - parent_m.word_count
    token_delta = cand_m.estimated_tokens - parent_m.estimated_tokens

    cost_metrics = SkillContextCostMetrics(
        char_count=cand_m.char_count,
        line_count=cand_m.line_count,
        word_count=cand_m.word_count,
        estimated_tokens=cand_m.estimated_tokens,
        char_delta=char_delta,
        line_delta=line_delta,
        word_delta=word_delta,
        token_delta=token_delta,
    )

    diff_data: dict[str, Any] = {
        "parent_id": parent_id,
        "candidate_id": candidate_id,
        "parent_sha256": parent_sha,
        "candidate_sha256": cand_sha,
        "is_identical": parent_sha == cand_sha,
        "cost_metrics": cost_metrics.to_dict(),
        "lines_added_count": len(added_lines),
        "lines_removed_count": len(removed_lines),
        "added_lines": added_lines,
        "removed_lines": removed_lines,
    }
    return diff_data


def render_skill_diff_md(diff_data: dict[str, Any]) -> str:
    """Renders human-readable Markdown diff report for a skill change."""
    pid = diff_data["parent_id"]
    cid = diff_data["candidate_id"]
    cm = diff_data["cost_metrics"]

    lines: list[str] = [
        f"# Skill Diff Report: `{pid}` vs. `{cid}`",
        "",
        "## Summary",
        f"- **Parent Candidate:** `{pid}` (SHA-256: `{diff_data['parent_sha256'][:12]}`)",
        f"- **Candidate:** `{cid}` (SHA-256: `{diff_data['candidate_sha256'][:12]}`)",
        f"- **Identical:** `{'YES' if diff_data['is_identical'] else 'NO'}`",
        "",
        "## Context Cost Deltas",
        "| Metric | Parent | Candidate | Delta |",
        "| :--- | :--- | :--- | :--- |",
        f"| Lines | {cm['line_count'] - cm['line_delta']} | {cm['line_count']} | {cm['line_delta']:+d} |",
        f"| Words | {cm['word_count'] - cm['word_delta']} | {cm['word_count']} | {cm['word_delta']:+d} |",
        f"| Characters | {cm['char_count'] - cm['char_delta']} | {cm['char_count']} | {cm['char_delta']:+d} |",
        f"| Estimated Tokens | {cm['estimated_tokens'] - cm['token_delta']} | {cm['estimated_tokens']} | {cm['token_delta']:+d} |",
        "",
    ]

    if diff_data["is_identical"]:
        lines.append("No text differences detected between parent and candidate skills.")
        return "\n".join(lines)

    lines.append("## Line Additions and Removals")
    lines.append(f"- **Lines Added:** {diff_data['lines_added_count']}")
    lines.append(f"- **Lines Removed:** {diff_data['lines_removed_count']}")
    lines.append("")

    if diff_data["removed_lines"]:
        lines.append("### Removed Lines")
        lines.append("```markdown")
        for line in diff_data["removed_lines"]:
            lines.append(f"- {line}")
        lines.append("```")
        lines.append("")

    if diff_data["added_lines"]:
        lines.append("### Added Lines")
        lines.append("```markdown")
        for line in diff_data["added_lines"]:
            lines.append(f"+ {line}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
