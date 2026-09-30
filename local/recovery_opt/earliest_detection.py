"""Earliest Detection Point Analysis (Stage 35 Sections 10, 33).

Analyzes recovery traces to compute:
- First observable failure event / turn
- First observable recovery opportunity event / turn
- Actual recovery trigger event / turn
- Detection latency in events (`detection_latency_events`)
- Detection latency in turns (`detection_latency_turns`)
- Recovery outcome

Guarantees that all detection points are grounded exclusively in observable state transitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from local.recovery_opt.models import RecoveryExecutionEvent, RecoveryOutcome


@dataclass
class EarlyDetectionReport:
    """Structured report on detection opportunities and latencies for a task run."""

    task_id: str
    run_id: str
    candidate_id: str
    first_failure_event_index: Optional[int]
    first_recovery_opportunity_event_index: Optional[int]
    actual_recovery_trigger_event_index: Optional[int]
    detection_latency_events: Optional[int]
    first_failure_turn: Optional[int]
    first_recovery_opportunity_turn: Optional[int]
    actual_recovery_trigger_turn: Optional[int]
    detection_latency_turns: Optional[int]
    earliest_action_possible: str
    actual_action_taken: str
    recovery_outcome: str
    improved_latency: bool = False
    evidence_mode: str = "FIXTURE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_early_detection(
    events: List[RecoveryExecutionEvent],
    task_id: str = "",
    run_id: str = "",
    candidate_id: str = "",
) -> EarlyDetectionReport:
    """Computes earliest observable recovery opportunity vs. actual recovery trigger."""
    if not events:
        return EarlyDetectionReport(
            task_id=task_id,
            run_id=run_id,
            candidate_id=candidate_id,
            first_failure_event_index=None,
            first_recovery_opportunity_event_index=None,
            actual_recovery_trigger_event_index=None,
            detection_latency_events=None,
            first_failure_turn=None,
            first_recovery_opportunity_turn=None,
            actual_recovery_trigger_turn=None,
            detection_latency_turns=None,
            earliest_action_possible="NONE",
            actual_action_taken="NONE",
            recovery_outcome=RecoveryOutcome.INCONCLUSIVE.value,
        )

    first_fail_idx: Optional[int] = None
    first_fail_turn: Optional[int] = None
    first_opp_idx: Optional[int] = None
    first_opp_turn: Optional[int] = None
    actual_trig_idx: Optional[int] = None
    actual_trig_turn: Optional[int] = None
    earliest_action = "NONE"
    actual_action = "NONE"
    final_outcome = RecoveryOutcome.INCONCLUSIVE.value
    ev_mode = events[0].evidence_mode if events else "FIXTURE"

    sorted_events = sorted(events, key=lambda e: (e.turn, e.event_index))

    for ev in sorted_events:
        # Check for failure or recovery eligibility
        if ev.failure_signature and first_fail_idx is None:
            first_fail_idx = ev.event_index
            first_fail_turn = ev.turn

        if ev.recovery_eligible and first_opp_idx is None:
            first_opp_idx = ev.event_index
            first_opp_turn = ev.turn
            earliest_action = ev.action or "INSPECT_DIFF"

        # Check for actual recovery trigger
        if ev.trigger and ev.action and ev.action != "NONE" and actual_trig_idx is None:
            actual_trig_idx = ev.event_index
            actual_trig_turn = ev.turn
            actual_action = ev.action

        if ev.recovery_outcome and ev.recovery_outcome != RecoveryOutcome.INCONCLUSIVE.value:
            final_outcome = ev.recovery_outcome

    # Compute latencies
    lat_events: Optional[int] = None
    lat_turns: Optional[int] = None

    if first_opp_idx is not None and actual_trig_idx is not None:
        lat_events = max(0, actual_trig_idx - first_opp_idx)
    elif first_fail_idx is not None and actual_trig_idx is not None:
        lat_events = max(0, actual_trig_idx - first_fail_idx)

    if first_opp_turn is not None and actual_trig_turn is not None:
        lat_turns = max(0, actual_trig_turn - first_opp_turn)
    elif first_fail_turn is not None and actual_trig_turn is not None:
        lat_turns = max(0, actual_trig_turn - first_fail_turn)

    tid = task_id or (events[0].task_id if events else "")
    rid = run_id or (events[0].run_id if events else "")
    cid = candidate_id or (events[0].candidate_id if events else "")

    return EarlyDetectionReport(
        task_id=tid,
        run_id=rid,
        candidate_id=cid,
        first_failure_event_index=first_fail_idx,
        first_recovery_opportunity_event_index=first_opp_idx,
        actual_recovery_trigger_event_index=actual_trig_idx,
        detection_latency_events=lat_events,
        first_failure_turn=first_fail_turn,
        first_recovery_opportunity_turn=first_opp_turn,
        actual_recovery_trigger_turn=actual_trig_turn,
        detection_latency_turns=lat_turns,
        earliest_action_possible=earliest_action,
        actual_action_taken=actual_action,
        recovery_outcome=final_outcome,
        evidence_mode=ev_mode,
    )
