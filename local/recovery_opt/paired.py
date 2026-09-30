"""Paired Failure Comparison on the Same Failure Set (Stage 35 Sections 30, 31).

Evaluates baseline vs candidate on the EXACT SAME failure set:
- baseline failure pattern vs candidate failure pattern
- recovery triggered?
- recovery action
- recovery outcome
- detection latency
- attempts count
- loops count
- task final result

Transitions:
- FAIL_TO_RECOVERED
- FAIL_TO_STILL_FAILING
- FAIL_TO_DIFFERENT_FAIL
- FAIL_TO_LOOP
- FAIL_TO_BUDGET_EXHAUSTED
- PASS_UNCHANGED
- UNPAIRED
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.recovery_opt.models import (
    RecoveryExecutionEvent,
    RecoveryOutcome,
    RecoveryTaskPairOutcome,
    TaskRecoveryTransition,
)


def compute_paired_recovery_comparisons(
    baseline_events: List[RecoveryExecutionEvent],
    candidate_events: List[RecoveryExecutionEvent],
    same_failure_task_ids: Optional[List[str]] = None,
) -> List[RecoveryTaskPairOutcome]:
    """Generates paired per-task comparisons across the same failure task set."""
    base_by_task: dict[str, list[RecoveryExecutionEvent]] = {}
    for e in baseline_events:
        base_by_task.setdefault(e.task_id, []).append(e)

    cand_by_task: dict[str, list[RecoveryExecutionEvent]] = {}
    for e in candidate_events:
        cand_by_task.setdefault(e.task_id, []).append(e)

    all_task_ids = sorted(
        set(same_failure_task_ids or list(base_by_task.keys()) + list(cand_by_task.keys()))
    )

    pairs: list[RecoveryTaskPairOutcome] = []

    for tid in all_task_ids:
        b_evs = base_by_task.get(tid, [])
        c_evs = cand_by_task.get(tid, [])

        if not b_evs and not c_evs:
            continue

        b_trig = any(e.trigger and e.action != "NONE" for e in b_evs)
        c_trig = any(e.trigger and e.action != "NONE" for e in c_evs)

        b_act = next((e.action for e in b_evs if e.action and e.action != "NONE"), "NONE")
        c_act = next((e.action for e in c_evs if e.action and e.action != "NONE"), "NONE")

        b_pat = next((e.failure_signature for e in b_evs if e.failure_signature), None)
        c_pat = next((e.failure_signature for e in c_evs if e.failure_signature), None)

        b_out = next((e.recovery_outcome for e in reversed(b_evs) if e.recovery_outcome), RecoveryOutcome.INCONCLUSIVE.value)
        c_out = next((e.recovery_outcome for e in reversed(c_evs) if e.recovery_outcome), RecoveryOutcome.INCONCLUSIVE.value)

        b_loops = sum(1 for e in b_evs if e.loop_detected)
        c_loops = sum(1 for e in c_evs if e.loop_detected)

        b_att = max((e.attempt_number for e in b_evs), default=0)
        c_att = max((e.attempt_number for e in c_evs), default=0)

        # Detection latencies
        b_opp = next((e.event_index for e in b_evs if e.recovery_eligible), None)
        b_tr_idx = next((e.event_index for e in b_evs if e.trigger and e.action != "NONE"), None)
        b_lat = (b_tr_idx - b_opp) if (b_opp is not None and b_tr_idx is not None) else None

        c_opp = next((e.event_index for e in c_evs if e.recovery_eligible), None)
        c_tr_idx = next((e.event_index for e in c_evs if e.trigger and e.action != "NONE"), None)
        c_lat = (c_tr_idx - c_opp) if (c_opp is not None and c_tr_idx is not None) else None

        b_task_res = "PASS" if b_out in [RecoveryOutcome.RECOVERED.value, RecoveryOutcome.RECOVERED_AFTER_RETRY.value, RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value] else "FAIL"
        c_task_res = "PASS" if c_out in [RecoveryOutcome.RECOVERED.value, RecoveryOutcome.RECOVERED_AFTER_RETRY.value, RecoveryOutcome.RECOVERED_AFTER_ALTERNATE_PATH.value] else "FAIL"

        # Determine transition
        notes: list[str] = []
        if not b_evs or not c_evs:
            trans = TaskRecoveryTransition.UNPAIRED.value
        elif b_task_res == "FAIL" and c_task_res == "PASS":
            trans = TaskRecoveryTransition.FAIL_TO_RECOVERED.value
            notes.append("Targeted failure successfully resolved by candidate recovery.")
        elif c_loops > b_loops:
            trans = TaskRecoveryTransition.FAIL_TO_LOOP.value
            notes.append(f"Candidate introduced new recovery loops ({b_loops} -> {c_loops}).")
        elif c_out == RecoveryOutcome.BUDGET_EXHAUSTED.value and b_out != RecoveryOutcome.BUDGET_EXHAUSTED.value:
            trans = TaskRecoveryTransition.FAIL_TO_BUDGET_EXHAUSTED.value
            notes.append("Candidate exhausted recovery budget before resolution.")
        elif b_task_res == "FAIL" and c_task_res == "FAIL":
            if b_pat != c_pat and c_pat is not None:
                trans = TaskRecoveryTransition.FAIL_TO_DIFFERENT_FAIL.value
                notes.append(f"Failure signature shifted: '{b_pat}' -> '{c_pat}'.")
            else:
                trans = TaskRecoveryTransition.FAIL_TO_STILL_FAILING.value
                notes.append("Target failure remained unresolved under candidate.")
        elif b_task_res == "PASS" and c_task_res == "PASS":
            trans = TaskRecoveryTransition.PASS_UNCHANGED.value
        else:
            trans = TaskRecoveryTransition.FAIL_TO_STILL_FAILING.value

        pair = RecoveryTaskPairOutcome(
            task_id=tid,
            baseline_failure_pattern=b_pat,
            candidate_failure_pattern=c_pat,
            baseline_recovery_triggered=b_trig,
            candidate_recovery_triggered=c_trig,
            baseline_recovery_action=b_act,
            candidate_recovery_action=c_act,
            baseline_recovery_outcome=b_out,
            candidate_recovery_outcome=c_out,
            baseline_detection_latency=b_lat,
            candidate_detection_latency=c_lat,
            baseline_attempts=b_att,
            candidate_attempts=c_att,
            baseline_loops=b_loops,
            candidate_loops=c_loops,
            baseline_task_result=b_task_res,
            candidate_task_result=c_task_res,
            transition=trans,
            diff_notes=notes,
        )
        pairs.append(pair)

    return pairs


def save_paired_results(
    pairs: List[RecoveryTaskPairOutcome],
    jsonl_path: Path | str,
    csv_path: Path | str,
) -> None:
    """Saves paired results to both JSONL and CSV files."""
    j_p = Path(jsonl_path)
    j_p.parent.mkdir(parents=True, exist_ok=True)
    with j_p.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_dict()) + "\n")

    c_p = Path(csv_path)
    c_p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_id",
        "baseline_task_result",
        "candidate_task_result",
        "transition",
        "baseline_recovery_action",
        "candidate_recovery_action",
        "baseline_detection_latency",
        "candidate_detection_latency",
        "baseline_loops",
        "candidate_loops",
        "baseline_attempts",
        "candidate_attempts",
    ]
    with c_p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in pairs:
            d = p.to_dict()
            writer.writerow({k: d.get(k) for k in fieldnames})
