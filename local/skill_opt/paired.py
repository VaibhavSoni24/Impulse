"""Paired Task Comparison and Task-Scope Matrix Engine (Stage 36 Sections 21, 25).

Evaluates parent skill vs candidate skill on the exact same task set:
- Task success transitions:
  - PASS_TO_PASS
  - PASS_TO_FAIL
  - FAIL_TO_PASS
  - FAIL_TO_OTHER_FAIL
  - FAIL_UNCHANGED
- Behavioral shifts:
  - REDUNDANT_TO_NON_REDUNDANT
  - MISSING_DISCOVERY_TO_CORRECT_DISCOVERY
  - LATE_DISCOVERY_TO_EARLY_DISCOVERY
- Outputs:
  - paired_results.jsonl
  - paired_results.csv
  - task-scope matrix representation
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.skill_opt.models import (
    SkillTaskPairOutcome,
    TaskBehaviorTransition,
)


def compute_paired_task_comparisons(
    parent_results: List[Dict[str, Any]],
    candidate_results: List[Dict[str, Any]],
    skill_id: str,
    parent_id: str = "S0",
    candidate_id: str = "S1",
    benchmark_tasks: Optional[List[str]] = None,
) -> List[SkillTaskPairOutcome]:
    """Generates deterministic paired per-task comparisons across identical task sets."""
    parent_by_task = {r.get("task_id", ""): r for r in parent_results if r.get("task_id")}
    cand_by_task = {r.get("task_id", ""): r for r in candidate_results if r.get("task_id")}

    all_tasks = sorted(set(benchmark_tasks or list(parent_by_task.keys()) + list(cand_by_task.keys())))
    pairs: list[SkillTaskPairOutcome] = []

    for tid in all_tasks:
        p_res = parent_by_task.get(tid)
        c_res = cand_by_task.get(tid)

        if not p_res and not c_res:
            continue

        p_pass = bool(p_res.get("success", False)) if p_res else False
        c_pass = bool(c_res.get("success", False)) if c_res else False
        p_status = "PASS" if p_pass else "FAIL"
        c_status = "PASS" if c_pass else "FAIL"

        p_metric = float(p_res.get("behavior_metric", 0.0)) if p_res else 0.0
        c_metric = float(c_res.get("behavior_metric", 0.0)) if c_res else 0.0

        p_redundant = bool(p_res.get("has_redundancy", False)) if p_res else False
        c_redundant = bool(c_res.get("has_redundancy", False)) if c_res else False

        p_missing_disc = bool(p_res.get("missing_discovery", False)) if p_res else False
        c_missing_disc = bool(c_res.get("missing_discovery", False)) if c_res else False

        p_late_disc = bool(p_res.get("late_discovery", False)) if p_res else False
        c_late_disc = bool(c_res.get("late_discovery", False)) if c_res else False

        notes: list[str] = []

        if not p_res or not c_res:
            transition = TaskBehaviorTransition.UNPAIRED.value
            behavior_trans = "UNPAIRED"
        elif not p_pass and c_pass:
            transition = TaskBehaviorTransition.FAIL_TO_PASS.value
            behavior_trans = "RESOLVED"
            notes.append("Task resolved successfully under candidate skill.")
        elif p_pass and not c_pass:
            transition = TaskBehaviorTransition.PASS_TO_FAIL.value
            behavior_trans = "REGRESSED"
            notes.append("Task regressed under candidate skill.")
        elif p_redundant and not c_redundant and c_pass >= p_pass:
            transition = TaskBehaviorTransition.REDUNDANT_TO_NON_REDUNDANT.value
            behavior_trans = "REDUNDANCY_ELIMINATED"
            notes.append("Redundant operations eliminated without degrading task resolution.")
        elif p_missing_disc and not c_missing_disc:
            transition = TaskBehaviorTransition.MISSING_DISCOVERY_TO_CORRECT_DISCOVERY.value
            behavior_trans = "DISCOVERY_ACQUIRED"
            notes.append("Target discovery successfully acquired.")
        elif p_late_disc and not c_late_disc:
            transition = TaskBehaviorTransition.LATE_DISCOVERY_TO_EARLY_DISCOVERY.value
            behavior_trans = "DISCOVERY_ACCELERATED"
            notes.append("Target discovery executed earlier in trajectory.")
        elif not p_pass and not c_pass:
            p_fail_mode = p_res.get("failure_mode", "")
            c_fail_mode = c_res.get("failure_mode", "")
            if p_fail_mode and c_fail_mode and p_fail_mode != c_fail_mode:
                transition = TaskBehaviorTransition.FAIL_TO_OTHER_FAIL.value
                behavior_trans = "FAILURE_SHIFTED"
                notes.append(f"Failure mode shifted from '{p_fail_mode}' to '{c_fail_mode}'.")
            else:
                transition = TaskBehaviorTransition.FAIL_UNCHANGED.value
                behavior_trans = "UNCHANGED"
                notes.append("Failure remained unchanged.")
        else:
            transition = TaskBehaviorTransition.PASS_TO_PASS.value
            behavior_trans = "UNCHANGED"
            notes.append("Task remained passing.")

        pair = SkillTaskPairOutcome(
            task_id=tid,
            skill_id=skill_id,
            parent_candidate=parent_id,
            candidate_id=candidate_id,
            parent_result=p_status,
            candidate_result=c_status,
            transition=transition,
            parent_behavior_metric=p_metric,
            candidate_behavior_metric=c_metric,
            behavior_transition=behavior_trans,
            diff_notes=notes,
        )
        pairs.append(pair)

    return pairs


def save_paired_results(
    pairs: List[SkillTaskPairOutcome],
    jsonl_path: Path | str,
    csv_path: Path | str,
) -> None:
    """Saves paired results to both JSONL and CSV formats."""
    j_p = Path(jsonl_path)
    j_p.parent.mkdir(parents=True, exist_ok=True)
    with j_p.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_dict()) + "\n")

    c_p = Path(csv_path)
    c_p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_id",
        "skill_id",
        "parent_candidate",
        "candidate_id",
        "parent_result",
        "candidate_result",
        "transition",
        "parent_behavior_metric",
        "candidate_behavior_metric",
        "behavior_transition",
    ]
    with c_p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in pairs:
            d = p.to_dict()
            writer.writerow({k: d.get(k) for k in fieldnames})


def build_task_scope_matrix(
    candidate_id: str,
    skill_id: str,
    scope: str,
    expected_behavior: str,
    paired_outcomes: List[SkillTaskPairOutcome],
) -> List[Dict[str, Any]]:
    """Builds structured Skill-Task matrix (Stage 36 Section 25)."""
    matrix: list[dict[str, Any]] = []
    for p in paired_outcomes:
        matrix.append({
            "task_id": p.task_id,
            "skill_id": skill_id,
            "candidate_id": candidate_id,
            "scope": scope,
            "expected_behavior": expected_behavior,
            "actual_behavior": p.behavior_transition,
            "result": p.candidate_result,
            "transition": p.transition,
        })
    return matrix
