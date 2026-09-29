"""Task-Level Paired Comparison Engine (Stage 32 Section 14).

Computes granular per-task behavioral transitions between baseline and candidate runs:
- FAIL -> PASS (Direct fix)
- PASS -> FAIL (Direct regression)
- FAIL_A -> FAIL_B (Failure mode shift)
- FAIL -> FAIL (Unchanged failure)
- PASS -> PASS (Retained pass)

Serializes to machine-readable JSONL and CSV formats.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.fdd.models import FailureRecord
from local.prompt_opt.models import TaskPairOutcome, TaskTransition


def compute_task_paired_comparison(
    baseline_records: List[FailureRecord],
    candidate_records: List[FailureRecord],
) -> List[TaskPairOutcome]:
    """Computes task-level paired outcomes between baseline and candidate records."""
    base_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in baseline_records if r.task_id
    }
    cand_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in candidate_records if r.task_id
    }

    # Only evaluate tasks present in both sets
    common_tasks = sorted(list(set(base_map.keys()).intersection(set(cand_map.keys()))))
    outcomes: List[TaskPairOutcome] = []

    for tid in common_tasks:
        b_rec = base_map[tid]
        c_rec = cand_map[tid]

        b_succ = b_rec.success
        c_succ = c_rec.success
        b_cat = b_rec.failure_category or "NONE"
        c_cat = c_rec.failure_category or "NONE"

        if b_succ is None or c_succ is None:
            trans = TaskTransition.UNPAIRED
        elif b_succ is False and c_succ is True:
            trans = TaskTransition.FAIL_TO_PASS
        elif b_succ is True and c_succ is False:
            trans = TaskTransition.PASS_TO_FAIL
        elif b_succ is True and c_succ is True:
            trans = TaskTransition.PASS_UNCHANGED
        elif b_succ is False and c_succ is False:
            if b_cat == c_cat:
                trans = TaskTransition.FAIL_UNCHANGED
            else:
                trans = TaskTransition.FAIL_TO_OTHER_FAIL
        else:
            trans = TaskTransition.UNPAIRED

        outcomes.append(
            TaskPairOutcome(
                task_id=tid,
                baseline_success=b_succ,
                candidate_success=c_succ,
                baseline_failure_category=b_cat,
                candidate_failure_category=c_cat,
                transition=trans,
            )
        )

    return outcomes


def summarize_paired_outcomes(outcomes: List[TaskPairOutcome]) -> Dict[str, int]:
    """Summarizes transition counts across paired tasks."""
    summary = {
        "total_paired": len(outcomes),
        "fail_to_pass": 0,
        "pass_to_fail": 0,
        "fail_to_other_fail": 0,
        "fail_unchanged": 0,
        "pass_unchanged": 0,
        "unpaired": 0,
    }
    for o in outcomes:
        if o.transition == TaskTransition.FAIL_TO_PASS:
            summary["fail_to_pass"] += 1
        elif o.transition == TaskTransition.PASS_TO_FAIL:
            summary["pass_to_fail"] += 1
        elif o.transition == TaskTransition.FAIL_TO_OTHER_FAIL:
            summary["fail_to_other_fail"] += 1
        elif o.transition == TaskTransition.FAIL_UNCHANGED:
            summary["fail_unchanged"] += 1
        elif o.transition == TaskTransition.PASS_UNCHANGED:
            summary["pass_unchanged"] += 1
        else:
            summary["unpaired"] += 1

    return summary


def save_paired_results_jsonl(outcomes: List[TaskPairOutcome], output_path: Path | str) -> Path:
    """Serializes paired comparison outcomes to JSONL."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for o in outcomes:
            f.write(json.dumps(o.to_dict(), sort_keys=True) + "\n")
    return p


def save_paired_results_csv(outcomes: List[TaskPairOutcome], output_path: Path | str) -> Path:
    """Serializes paired comparison outcomes to standard CSV."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id",
            "baseline_success",
            "candidate_success",
            "baseline_failure_category",
            "candidate_failure_category",
            "transition",
        ])
        for o in outcomes:
            writer.writerow([
                o.task_id,
                "" if o.baseline_success is None else str(o.baseline_success),
                "" if o.candidate_success is None else str(o.candidate_success),
                o.baseline_failure_category,
                o.candidate_failure_category,
                o.transition.value,
            ])
    return p
