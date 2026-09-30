"""Task-Level Paired Comparison Engine for Retrieval Optimization (Stage 33 Section 17).

Computes granular per-task behavioral transitions between baseline and candidate retrieval runs:
- FAIL -> PASS (Direct fix)
- PASS -> FAIL (Direct regression)
- FAIL_A -> FAIL_B (Failure mode shift)
- FAIL -> FAIL (Unchanged failure)
- PASS -> PASS (Retained pass)

Tracks per-task retrieval behavior differences (calls, queries, entities).
Serializes to machine-readable JSONL and CSV formats.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.fdd.models import FailureRecord
from local.retrieval_opt.models import (
    RetrievalEvent,
    RetrievalTaskPairOutcome,
    TaskTransition,
)


def compute_retrieval_paired_comparison(
    baseline_records: List[FailureRecord],
    candidate_records: List[FailureRecord],
    baseline_events: Optional[List[RetrievalEvent]] = None,
    candidate_events: Optional[List[RetrievalEvent]] = None,
) -> List[RetrievalTaskPairOutcome]:
    """Computes task-level paired outcomes between baseline and candidate records."""
    base_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in baseline_records if r.task_id
    }
    cand_map: Dict[str, FailureRecord] = {
        r.task_id: r for r in candidate_records if r.task_id
    }

    # Map retrieval events by task_id
    b_ev_map: Dict[str, List[RetrievalEvent]] = {}
    if baseline_events:
        for ev in baseline_events:
            b_ev_map.setdefault(ev.task_id, []).append(ev)

    c_ev_map: Dict[str, List[RetrievalEvent]] = {}
    if candidate_events:
        for ev in candidate_events:
            c_ev_map.setdefault(ev.task_id, []).append(ev)

    # Only evaluate tasks present in both sets
    common_tasks = sorted(list(set(base_map.keys()).intersection(set(cand_map.keys()))))
    outcomes: List[RetrievalTaskPairOutcome] = []

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

        b_calls = len(b_ev_map.get(tid, []))
        c_calls = len(c_ev_map.get(tid, []))
        call_delta = c_calls - b_calls

        diff_parts = []
        if b_calls != c_calls:
            diff_parts.append(f"calls: {b_calls} -> {c_calls} ({call_delta:+})")
        else:
            diff_parts.append(f"calls: {c_calls} (unchanged)")

        c_types = [ev.retrieval_type for ev in c_ev_map.get(tid, [])]
        if c_types:
            diff_parts.append(f"types: {', '.join(sorted(set(c_types)))}")

        behavior_diff = "; ".join(diff_parts)

        outcomes.append(
            RetrievalTaskPairOutcome(
                task_id=tid,
                baseline_success=b_succ,
                candidate_success=c_succ,
                baseline_failure_category=b_cat,
                candidate_failure_category=c_cat,
                transition=trans,
                baseline_retrieval_calls=b_calls,
                candidate_retrieval_calls=c_calls,
                retrieval_call_delta=call_delta,
                retrieval_behavior_diff=behavior_diff,
            )
        )

    return outcomes


def save_paired_results_jsonl(
    outcomes: List[RetrievalTaskPairOutcome],
    file_path: Path | str,
) -> None:
    """Saves paired comparison outcomes to JSONL."""
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for out in outcomes:
            f.write(json.dumps(out.to_dict(), sort_keys=True) + "\n")


def save_paired_results_csv(
    outcomes: List[RetrievalTaskPairOutcome],
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
        "baseline_retrieval_calls",
        "candidate_retrieval_calls",
        "retrieval_call_delta",
        "retrieval_behavior_diff",
    ]
    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for out in outcomes:
            d = out.to_dict()
            writer.writerow({k: d.get(k, "") for k in fieldnames})


def summarize_paired_outcomes(
    outcomes: List[RetrievalTaskPairOutcome],
) -> Dict[str, Any]:
    """Generates aggregate transition counts from paired comparison outcomes."""
    counts = {
        "FAIL_TO_PASS": 0,
        "PASS_TO_FAIL": 0,
        "FAIL_TO_OTHER_FAIL": 0,
        "FAIL_UNCHANGED": 0,
        "PASS_UNCHANGED": 0,
        "UNPAIRED": 0,
        "total_paired": len(outcomes),
        "total_retrieval_calls_baseline": sum(o.baseline_retrieval_calls for o in outcomes),
        "total_retrieval_calls_candidate": sum(o.candidate_retrieval_calls for o in outcomes),
    }
    for out in outcomes:
        t_key = out.transition.value if isinstance(out.transition, TaskTransition) else str(out.transition)
        if t_key in counts:
            counts[t_key] += 1
    return counts
