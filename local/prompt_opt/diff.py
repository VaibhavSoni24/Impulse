"""Prompt Diff Engine and Bloat Diagnostics for Stage 32 (Sections 8, 16, 17).

Provides:
- Deterministic unified and semantic prompt diffing
- Quantitative prompt cost metrics (lines, characters, estimated tokens)
- Prompt bloat detection (duplicates, filler language, contradictions)
- Markdown and JSON serialization
"""

from __future__ import annotations

import difflib
import hashlib
import re
from typing import List, Optional, Tuple

from local.prompt_opt.models import PromptBloatReport, PromptCostMetrics, PromptDiff


GENERIC_FILLER_PHRASES = [
    "do your best",
    "you are a genius",
    "you are an expert genius",
    "think really hard",
    "take a deep breath",
    "give 110%",
    "as an ai language model",
    "strive for perfection",
    "believe in yourself",
    "you are brilliant",
]


def _compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_prompt_cost(
    content: str,
    parent_content: Optional[str] = None,
) -> PromptCostMetrics:
    """Computes quantitative length and token estimates for prompt content."""
    chars = len(content)
    lines = len(content.splitlines())
    words = len(content.split())
    # Canonical token estimation without adding third-party tokenizer dependencies: ~4 chars per token
    est_tokens = max(1, chars // 4)

    char_delta = None
    line_delta = None
    token_delta = None

    if parent_content is not None:
        p_chars = len(parent_content)
        p_lines = len(parent_content.splitlines())
        p_tokens = max(1, p_chars // 4)
        char_delta = chars - p_chars
        line_delta = lines - p_lines
        token_delta = est_tokens - p_tokens

    return PromptCostMetrics(
        char_count=chars,
        line_count=lines,
        word_count=words,
        estimated_tokens=est_tokens,
        char_delta=char_delta,
        line_delta=line_delta,
        estimated_token_delta=token_delta,
    )


def detect_prompt_bloat(content: str) -> PromptBloatReport:
    """Scans prompt content for duplicates, generic motivational filler, and contradictions."""
    diagnostics: List[str] = []
    duplicate_lines: List[str] = []
    filler_found: List[str] = []
    contradictions: List[str] = []

    # 1. Check duplicate non-trivial lines
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    seen_lines: set[str] = set()
    for l in lines:
        if len(l) > 20 and not l.startswith("#") and not l.startswith("```"):
            if l in seen_lines:
                duplicate_lines.append(l)
            else:
                seen_lines.add(l)

    if duplicate_lines:
        diagnostics.append(f"Found {len(duplicate_lines)} repeated non-trivial line(s).")

    # 2. Check generic filler phrases
    lower_content = content.lower()
    for phrase in GENERIC_FILLER_PHRASES:
        if phrase in lower_content:
            filler_found.append(phrase)
            diagnostics.append(f"Found generic non-operational filler phrase: '{phrase}'.")

    # 3. Check obvious contradictory instructions
    has_always_all_tests = "always execute all tests" in lower_content or "run all tests always" in lower_content
    has_never_all_tests = "never run all tests" in lower_content or "avoid full-repository test sweeps" in lower_content
    if has_always_all_tests and has_never_all_tests:
        contradictions.append("Contradiction detected: instructions mention both always running all tests and avoiding full sweeps.")
        diagnostics.append("Contradictory test execution constraints identified.")

    is_bloated = bool(duplicate_lines or filler_found or contradictions)

    return PromptBloatReport(
        is_bloated=is_bloated,
        duplicate_lines=duplicate_lines,
        filler_phrases_found=filler_found,
        potential_contradictions=contradictions,
        diagnostics=diagnostics,
    )


def extract_sections_from_markdown(content: str) -> List[Tuple[str, int]]:
    """Extracts markdown section headers with line numbers."""
    sections: List[Tuple[str, int]] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        if line.startswith("#"):
            heading = line.strip("#").strip()
            sections.append((heading, idx))
    return sections


def compute_prompt_diff(
    parent_id: str,
    candidate_id: str,
    parent_content: str,
    candidate_content: str,
    prompt_filename: str = "root.md",
) -> PromptDiff:
    """Computes a structured, deterministic diff between two prompt versions."""
    parent_lines = parent_content.splitlines(keepends=True)
    candidate_lines = candidate_content.splitlines(keepends=True)

    parent_hash = _compute_sha256(parent_content)
    candidate_hash = _compute_sha256(candidate_content)

    udiff = list(difflib.unified_diff(
        parent_lines,
        candidate_lines,
        fromfile=f"{parent_id}/{prompt_filename}",
        tofile=f"{candidate_id}/{prompt_filename}",
    ))
    diff_text = "".join(udiff)

    added_snippets: List[str] = []
    removed_snippets: List[str] = []
    added_count = 0
    removed_count = 0

    for line in udiff:
        if line.startswith("+") and not line.startswith("+++"):
            added_count += 1
            added_snippets.append(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            removed_count += 1
            removed_snippets.append(line[1:].strip())

    changed_count = max(added_count, removed_count)

    # Detect affected sections
    sections = extract_sections_from_markdown(candidate_content)
    changed_sections_set: set[str] = set()

    for snippet in added_snippets:
        if snippet:
            # Match to nearest section
            for h, _ in sections:
                if h.lower() in snippet.lower() or snippet.lower() in h.lower():
                    changed_sections_set.add(h)

    if not changed_sections_set and sections:
        # Fallback to general changed location
        changed_sections_set.add("Operational Workflow")

    cost = compute_prompt_cost(candidate_content, parent_content=parent_content)

    return PromptDiff(
        parent_candidate_id=parent_id,
        candidate_id=candidate_id,
        parent_prompt_hash=parent_hash,
        candidate_prompt_hash=candidate_hash,
        changed_files=[prompt_filename],
        added_lines_count=added_count,
        removed_lines_count=removed_count,
        changed_lines_count=changed_count,
        added_text_snippets=added_snippets[:20],  # Bound length
        removed_text_snippets=removed_snippets[:20],
        changed_sections=sorted(list(changed_sections_set)),
        unified_diff=diff_text,
        cost_metrics=cost,
    )


def render_prompt_diff_md(diff: PromptDiff) -> str:
    """Renders human-readable markdown for prompt diff."""
    lines: List[str] = [
        f"# Prompt Diff: `{diff.parent_candidate_id}` → `{diff.candidate_id}`",
        "",
        "## Summary",
        f"- **Files Changed:** `{', '.join(diff.changed_files)}`",
        f"- **Lines Added:** +{diff.added_lines_count}",
        f"- **Lines Removed:** -{diff.removed_lines_count}",
        f"- **Character Delta:** {f'{diff.cost_metrics.char_delta:+}' if diff.cost_metrics.char_delta is not None else '0'}",
        f"- **Estimated Token Delta:** {f'{diff.cost_metrics.estimated_token_delta:+}' if diff.cost_metrics.estimated_token_delta is not None else '0'}",
        f"- **Sections Affected:** {', '.join(diff.changed_sections) if diff.changed_sections else 'None'}",
        f"- **Parent SHA-256:** `{diff.parent_prompt_hash}`",
        f"- **Candidate SHA-256:** `{diff.candidate_prompt_hash}`",
        "",
        "## Unified Diff",
        "```diff",
        diff.unified_diff.strip() if diff.unified_diff else "No differences found.",
        "```",
        "",
        "## Quantitative Cost",
        "| Metric | Parent | Candidate | Delta |",
        "|---|---|---|---|",
        f"| Characters | {diff.cost_metrics.char_count - (diff.cost_metrics.char_delta or 0)} | {diff.cost_metrics.char_count} | {f'{diff.cost_metrics.char_delta:+}' if diff.cost_metrics.char_delta is not None else '0'} |",
        f"| Lines | {diff.cost_metrics.line_count - (diff.cost_metrics.line_delta or 0)} | {diff.cost_metrics.line_count} | {f'{diff.cost_metrics.line_delta:+}' if diff.cost_metrics.line_delta is not None else '0'} |",
        f"| Estimated Tokens | {diff.cost_metrics.estimated_tokens - (diff.cost_metrics.estimated_token_delta or 0)} | {diff.cost_metrics.estimated_tokens} | {f'{diff.cost_metrics.estimated_token_delta:+}' if diff.cost_metrics.estimated_token_delta is not None else '0'} |",
        "",
    ]
    return "\n".join(lines)
