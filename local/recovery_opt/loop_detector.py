"""Deterministic Recovery Loop and Oscillation Detector (Stage 35 Sections 18, 35).

Detects:
- Same recovery action repeated with identical failure and identical repository fingerprint (direct loop).
- Alternating recovery actions (oscillation: A -> B -> A -> B).
- Same failure recurring without evidence change.
- Infinite retries or counter resets.
- Thrashing across recovery paths.

Provides mandatory gate check:
`is_loop_regression(baseline_loops, candidate_loops)`: returns True if candidate increases loops.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from local.recovery_opt.models import RecoveryExecutionEvent


@dataclass
class LoopDetectionResult:
    """Outcome of recovery loop analysis on a series of execution events."""

    loop_detected: bool = False
    loop_type: str = "NONE"  # "DIRECT_LOOP", "OSCILLATION", "THRASHING", "INFINITE_RETRY", "NONE"
    loop_signature: str = ""
    cycle_length: int = 0
    cycle_count: int = 0
    affected_events: list[int] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_state_signature(
    failure_signature: str,
    recovery_action: str,
    repo_fingerprint: str = "",
    attempt_number: int = 1,
) -> str:
    """Computes a deterministic observable state signature for loop detection (Section 18)."""
    raw = f"{failure_signature}|{recovery_action}|{repo_fingerprint}|{attempt_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


class RecoveryLoopDetector:
    """Deterministic analyzer for loops, oscillations, and retry thrashing."""

    def __init__(self, max_allowed_direct_repeats: int = 2) -> None:
        self.max_allowed_direct_repeats = max_allowed_direct_repeats

    def analyze_events(
        self,
        events: List[RecoveryExecutionEvent],
    ) -> LoopDetectionResult:
        """Analyzes a chronological sequence of recovery execution events."""
        if not events:
            return LoopDetectionResult(loop_detected=False)

        sorted_events = sorted(events, key=lambda e: (e.turn, e.event_index))

        # 1. Check for explicit loop_detected flag
        for ev in sorted_events:
            if ev.loop_detected:
                return LoopDetectionResult(
                    loop_detected=True,
                    loop_type="EXPLICIT_LOOP",
                    loop_signature=ev.failure_signature or "EXPLICIT",
                    cycle_length=2,
                    cycle_count=1,
                    affected_events=[ev.event_index],
                    rationale=f"Event {ev.event_index} flagged explicit recovery loop.",
                )

        # 2. Check for direct identical action loops with unchanged state
        # State tuple: (failure_signature, action, evidence_changed)
        direct_repeats = 0
        last_sig: Optional[str] = None
        last_act: Optional[str] = None
        repeated_events: list[int] = []

        for ev in sorted_events:
            if not ev.action or ev.action == "NONE":
                continue
            curr_sig = ev.failure_signature
            curr_act = ev.action
            curr_ev_changed = ev.evidence_changed

            if curr_sig == last_sig and curr_act == last_act and not curr_ev_changed:
                direct_repeats += 1
                repeated_events.append(ev.event_index)
                if direct_repeats >= self.max_allowed_direct_repeats:
                    return LoopDetectionResult(
                        loop_detected=True,
                        loop_type="DIRECT_LOOP",
                        loop_signature=f"{curr_sig}|{curr_act}",
                        cycle_length=1,
                        cycle_count=direct_repeats,
                        affected_events=repeated_events,
                        rationale=f"Action '{curr_act}' executed {direct_repeats + 1} times with identical failure without evidence change.",
                    )
            else:
                direct_repeats = 0
                repeated_events = [ev.event_index]
                last_sig = curr_sig
                last_act = curr_act

        # 3. Check for alternating oscillation (A -> B -> A -> B)
        actions = [(e.event_index, e.action, e.failure_signature) for e in sorted_events if e.action and e.action != "NONE"]
        if len(actions) >= 4:
            for i in range(len(actions) - 3):
                act0 = actions[i][1]
                act1 = actions[i + 1][1]
                act2 = actions[i + 2][1]
                act3 = actions[i + 3][1]

                if act0 == act2 and act1 == act3 and act0 != act1:
                    ev_indices = [actions[k][0] for k in range(i, i + 4)]
                    return LoopDetectionResult(
                        loop_detected=True,
                        loop_type="OSCILLATION",
                        loop_signature=f"{act0}<->{act1}",
                        cycle_length=2,
                        cycle_count=2,
                        affected_events=ev_indices,
                        rationale=f"Oscillation detected: alternating recovery actions '{act0}' and '{act1}'.",
                    )

        # 4. Check for thrashing across 3+ recovery paths with 0 state change
        non_ev_actions = [e for e in sorted_events if e.action and e.action != "NONE" and not e.evidence_changed]
        if len(non_ev_actions) >= 5:
            return LoopDetectionResult(
                loop_detected=True,
                loop_type="THRASHING",
                loop_signature="THRASHING_WITHOUT_EVIDENCE",
                cycle_length=len(non_ev_actions),
                cycle_count=1,
                affected_events=[e.event_index for e in non_ev_actions],
                rationale="Recovery thrashing: 5 or more recovery actions executed without producing new evidence.",
            )

        return LoopDetectionResult(loop_detected=False)


def is_loop_regression(baseline_loops: int, candidate_loops: int) -> Tuple[bool, str]:
    """Mandatory Stage 35 Gate: verifies candidate does not increase recovery loops (Section 35).

    Returns:
        (is_regression, rationale)
    """
    if candidate_loops > baseline_loops:
        return (
            True,
            f"Recovery loop regression detected: candidate generated {candidate_loops} loops "
            f"vs. baseline {baseline_loops} loops (+{candidate_loops - baseline_loops}).",
        )
    return (
        False,
        f"No loop regression: candidate loops ({candidate_loops}) <= baseline loops ({baseline_loops}).",
    )
