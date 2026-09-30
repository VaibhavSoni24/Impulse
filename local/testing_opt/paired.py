"""Task-Level Paired Comparison Engine for Testing Strategy Experiments (Stage 34 Section 28).

Computes granular per-task behavioral transitions between baseline and candidate testing runs:
- FAIL -> PASS (Direct fix confirmed by testing)
- PASS -> FAIL (Direct regression detected by broader testing)
- FAIL_A -> FAIL_B (Failure mode shift)
- FAIL -> FAIL (Unchanged failure)
- PASS -> PASS (Retained pass)

Tracks per-task testing behavior differences (commands executed, test level reached).
Serializes to machine-readable JSONL and CSV formats.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.fdd.models import FailureRecord
from local.testing_opt.models import (
    TaskTransition,
    TestExecutionEvent,
    TestLevel,
    TestTaskPairOutcome,
)


def compute_test_paired_comparison(
    baseline_records: List[FailureRecord],
    candidate_records: List[FailureRecord],
    baseline_events: Optional[List[TestExecutionEvent]] = None,
    candidate_events: Optional[List[TestExecutionEvent]] = None,
) -> List[TestTaskPairOutcome]:
    """Computes task-level paired outcomes between baseline and candidate test execution records."""
    base_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in baseline_records if r.task_id
    }
    cand_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in candidate_records if r.task_id
    }

    b_ev_map: Dict[str, List[TestExecutionEvent]] = {}
    if baseline_events:
        for ev in baseline_events:
            b_ev_map.setdefault(ev.task_id, []).append(ev)

    c_ev_map: Dict[str, List[TestExecutionEvent]] = {}
    if candidate_events:
        for ev in candidate_events:
            c_ev_map.setdefault(ev.task_id, []).append(ev)

    common_tasks = sorted(list(set(base_map.keys()).intersection(set(cand_map.keys()))))
    outcomes: List[TestTaskPairOutcome] = []

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

        b_cmds = len(b_ev_map.get(tid, []))
        c_cmds = len(c_ev_map.get(tid, []))
        cmd_delta = c_cmds - b_cmds

        def _highest_level(evs: List[TestExecutionEvent]) -> str:
            levels = {e.test_level for e in evs}
            for lvl in [TestLevel.FULL.value, TestLevel.SUBSYSTEM.value, TestLevel.ADJACENT.value, TestLevel.TARGETED.value]:
                if lvl in levels:
                    return lvl
            return TestLevel.TARGETED.value

        b_lvl = _highest_level(b_ev_map.get(tid, []))
        c_lvl = _highest_level(c_ev_map.get(tid, []))

        diff_desc = f"commands: {b_cmds} -> {c_cmds} ({cmd_delta:+}); level: {b_lvl} -> {c_lvl}"

        outcomes.append(
            TestTaskPairOutcome(
                task_id=tid,
                baseline_success=b_succ,
                candidate_success=c_succ,
                baseline_failure_category=b_cat,
                candidate_failure_category=c_cat,
                transition=trans,
                baseline_test_commands=b_cmds,
                candidate_test_commands=c_cmds,
                test_command_delta=cmd_delta,
                baseline_test_level_reached=b_lvl,
                candidate_test_level_reached=c_lvl,
                testing_behavior_diff=diff_desc,
            )
        )

    return outcomes


def save_paired_results_jsonl(
    outcomes: List[TestTaskPairOutcome],
    file_path: Path | str,
) -> None:
    """Saves paired comparison outcomes to JSONL."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for out in outcomes:
            f.write(json.dumps(out.to_dict(), sort_keys=True) + "\n")


def save_paired_results_csv(
    outcomes: List[TestTaskPairOutcome],
    file_path: Path | str,
) -> None:
    """Saves paired comparison outcomes to CSV."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_id",
        "baseline_success",
        "candidate_success",
        "baseline_failure_category",
        "candidate_failure_category",
        "transition",
        "baseline_test_commands",
        "candidate_test_commands",
        "test_command_delta",
        "baseline_test_level_reached",
        "candidate_test_level_reached",
        "testing_behavior_diff",
    ]
    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for out in outcomes:
            d = out.to_dict()
            writer.writerow({k: d.get(k, "") for k in fieldnames})


def summarize_paired_outcomes(
    outcomes: List[TestTaskPairOutcome],
) -> Dict[str, Any]:
    """Summarizes transition counts and command deltas from paired test outcomes."""
    counts = {
        "FAIL_TO_PASS": 0,
        "PASS_TO_FAIL": 0,
        "FAIL_TO_OTHER_FAIL": 0,
        "FAIL_UNCHANGED": 0,
        "PASS_UNCHANGED": 0,
        "UNPAIRED": 0,
        "total_paired": len(outcomes),
        "total_test_commands_baseline": sum(o.baseline_test_commands for o in outcomes),
        "total_test_commands_candidate": sum(o.candidate_test_commands for o in outcomes),
    }
    for out in outcomes:
        t_key = out.transition.value if isinstance(out.transition, TaskTransition) else str(out.transition)
        if t_key in counts:
            counts[t_key] += 1
    return counts


save_test_paired_results_jsonl = save_paired_results_jsonl
save_test_paired_results_csv = save_paired_results_csv
summarize_test_paired_outcomes = summarize_paired_outcomes
