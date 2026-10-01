"""Deterministic Skill Content, Redundancy, and Contradiction Analyzer (Stage 36 Sections 9, 10, 23, 24).

Performs lexical and structural analysis of skill content against:
- The frozen Root Agent Prompt baseline (P0)
- Sibling instructions within the same skill (internal duplication)
- Known behavioral contradiction heuristics
- Bloat and generic instruction patterns

Classifies each instruction as:
- DUPLICATE
- POSSIBLE_DUPLICATE
- UNIQUE
- CONTRADICTORY
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from local.skill_opt.models import (
    InstructionDuplicationCategory,
    SkillContradiction,
    SkillDiagnostics,
    SkillDuplicationReport,
)

GENERIC_BLOAT_PATTERNS = [
    r"be careful\b",
    r"make sure it works\b",
    r"write good code\b",
    r"think step by step\b",
    r"do your best\b",
    r"ensure high quality\b",
]

CONTRADICTION_PAIRS = [
    (
        r"\balways run (the )?full( repository)? suite\b",
        r"\b(avoid|never|do not run) (executing )?(the )?(full( repository)?|broad( test)?) suite(s)?\b",
        "FULL_SUITE_EXECUTION_CONFLICT",
    ),
    (
        r"\brevert all( modified)? files\b",
        r"\bnever revert( unrelated)?\b",
        "REVERT_BOUNDARY_CONFLICT",
    ),
    (
        r"\brun broad test(s)?\b",
        r"\bavoid (executing )?broad (test )?suite(s)?\b",
        "BROAD_TESTING_CONFLICT",
    ),
    (
        r"\brecursively dump (entire )?directory\b",
        r"\bnever (recursively )?dump\b",
        "DIRECTORY_DUMP_CONFLICT",
    ),
]


def normalize_sentence(text: str) -> str:
    """Normalizes text for deterministic duplication detection."""
    clean = text.strip().lower()
    clean = re.sub(r"[`*_#>-]+", " ", clean)
    clean = re.sub(r"[^\w\s]", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def extract_meaningful_lines(markdown_text: str) -> List[tuple[int, str]]:
    """Extracts non-empty, non-header content lines with 1-indexed line numbers."""
    lines = markdown_text.splitlines()
    meaningful: list[tuple[int, str]] = []
    in_code_fence = False

    for idx, raw in enumerate(lines, start=1):
        s = raw.strip()
        if s.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if not s or s.startswith("#") or s == "---":
            continue
        # Strip list markers
        s_clean = re.sub(r"^[-*+]\s+", "", s)
        s_clean = re.sub(r"^\d+\.\s+", "", s_clean)
        if len(normalize_sentence(s_clean)) >= 10:
            meaningful.append((idx, s_clean))

    return meaningful


def compute_token_jaccard(a: str, b: str) -> float:
    """Computes Jaccard similarity between two normalized strings based on word tokens."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


class SkillContentAnalyzer:
    """Deterministic analyzer for skill duplication, bloat, and contradictions."""

    def __init__(self, root_prompt_text: str = "") -> None:
        self.root_prompt_text = root_prompt_text
        self.root_lines = [
            normalize_sentence(line)
            for _, line in extract_meaningful_lines(root_prompt_text)
        ]

    def analyze_root_duplication(self, skill_text: str) -> SkillDuplicationReport:
        """Analyzes skill lines against root prompt to detect redundant instructions."""
        skill_lines = extract_meaningful_lines(skill_text)
        if not skill_lines:
            return SkillDuplicationReport()

        exact_dups = 0
        near_dups = 0
        unique_cnt = 0
        items: list[dict[str, Any]] = []

        for line_no, raw_line in skill_lines:
            norm_skill = normalize_sentence(raw_line)
            category = InstructionDuplicationCategory.UNIQUE.value
            matched_root = ""
            best_sim = 0.0

            # 1. Exact match
            if norm_skill in self.root_lines:
                category = InstructionDuplicationCategory.DUPLICATE.value
                exact_dups += 1
                matched_root = norm_skill
            else:
                # 2. Near match via Jaccard
                for r_line in self.root_lines:
                    sim = compute_token_jaccard(norm_skill, r_line)
                    if sim > best_sim:
                        best_sim = sim
                        matched_root = r_line

                if best_sim >= 0.80:
                    category = InstructionDuplicationCategory.DUPLICATE.value
                    exact_dups += 1
                elif best_sim >= 0.60:
                    category = InstructionDuplicationCategory.POSSIBLE_DUPLICATE.value
                    near_dups += 1
                else:
                    unique_cnt += 1

            if category != InstructionDuplicationCategory.UNIQUE.value:
                items.append({
                    "line_number": line_no,
                    "skill_instruction": raw_line,
                    "category": category,
                    "matched_root_line": matched_root,
                    "similarity": round(best_sim if category != InstructionDuplicationCategory.DUPLICATE.value else 1.0, 3),
                })

        total = len(skill_lines)
        ratio = ((exact_dups + near_dups) / total) if total > 0 else 0.0

        return SkillDuplicationReport(
            total_skill_lines=total,
            exact_duplicate_lines=exact_dups,
            near_duplicate_lines=near_dups,
            unique_lines=unique_cnt,
            duplication_ratio=round(ratio, 4),
            duplicate_items=items,
        )

    def detect_contradictions(self, skill_text: str) -> List[SkillContradiction]:
        """Detects conflicting instruction pairs within the skill text."""
        skill_lines = extract_meaningful_lines(skill_text)
        contradictions: list[SkillContradiction] = []

        for rule_a_pat, rule_b_pat, c_type in CONTRADICTION_PAIRS:
            match_a: Optional[tuple[int, str]] = None
            match_b: Optional[tuple[int, str]] = None

            for line_no, raw_line in skill_lines:
                clean = raw_line.lower()
                if re.search(rule_a_pat, clean) and match_a is None:
                    match_a = (line_no, raw_line)
                if re.search(rule_b_pat, clean) and match_b is None:
                    match_b = (line_no, raw_line)

            if match_a and match_b and match_a[0] != match_b[0]:
                contradictions.append(
                    SkillContradiction(
                        line_number_a=match_a[0],
                        line_number_b=match_b[0],
                        instruction_a=match_a[1],
                        instruction_b=match_b[1],
                        contradiction_type=c_type,
                        rationale=f"Contradictory directives detected on lines {match_a[0]} and {match_b[0]}.",
                    )
                )

        return contradictions

    def detect_internal_duplication(self, skill_text: str) -> List[dict[str, Any]]:
        """Detects repeated instructions within the skill itself."""
        skill_lines = extract_meaningful_lines(skill_text)
        internal_dups: list[dict[str, Any]] = []

        for i in range(len(skill_lines)):
            lno_a, text_a = skill_lines[i]
            norm_a = normalize_sentence(text_a)
            for j in range(i + 1, len(skill_lines)):
                lno_b, text_b = skill_lines[j]
                norm_b = normalize_sentence(text_b)

                sim = compute_token_jaccard(norm_a, norm_b)
                if sim >= 0.85:
                    internal_dups.append({
                        "line_a": lno_a,
                        "line_b": lno_b,
                        "text_a": text_a,
                        "text_b": text_b,
                        "similarity": round(sim, 3),
                    })

        return internal_dups

    def evaluate_diagnostics(self, skill_text: str) -> SkillDiagnostics:
        """Runs full audit and returns structured SkillDiagnostics."""
        dup_rep = self.analyze_root_duplication(skill_text)
        contradictions = self.detect_contradictions(skill_text)
        internal_dups = self.detect_internal_duplication(skill_text)

        notes: list[str] = []
        has_generic = False

        for lno, text in extract_meaningful_lines(skill_text):
            for pat in GENERIC_BLOAT_PATTERNS:
                if re.search(pat, text.lower()):
                    has_generic = True
                    notes.append(f"Generic bloat detected on line {lno}: '{text}'.")

        if dup_rep.exact_duplicate_lines > 0:
            notes.append(f"Root prompt duplication: {dup_rep.exact_duplicate_lines} lines duplicate root instructions.")

        if internal_dups:
            notes.append(f"Internal duplication: {len(internal_dups)} repeated instruction pairs found.")

        if contradictions:
            notes.append(f"Contradictions: {len(contradictions)} conflicting directive pairs detected.")

        return SkillDiagnostics(
            has_root_duplication=dup_rep.exact_duplicate_lines > 0,
            has_internal_duplication=len(internal_dups) > 0,
            has_contradictions=len(contradictions) > 0,
            has_scope_leakage=False,
            has_bloat=has_generic or dup_rep.duplication_ratio >= 0.25,
            is_overly_generic=has_generic,
            diagnostic_notes=notes,
            contradictions=contradictions,
        )


def analyze_skill_content(
    skill_text: str,
    root_prompt_text: str = "",
    scope: str = "",
) -> Tuple[SkillDuplicationReport, SkillDiagnostics]:
    """Convenience helper to analyze duplication, contradictions, and diagnostics."""
    analyzer = SkillContentAnalyzer(root_prompt_text=root_prompt_text)
    dup_report = analyzer.analyze_root_duplication(skill_text)
    diagnostics = analyzer.evaluate_diagnostics(skill_text)
    return dup_report, diagnostics
