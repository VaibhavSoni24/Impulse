"""Structured Recovery Trace Collector and Diagnostics (Stage 35 Sections 40, 41).

Collects externally observable recovery execution events and persists them to `recovery_trace.jsonl`.
Evaluates deterministic diagnostics for:
1. late_recovery
2. repeated_identical_recovery
3. recovery_oscillation
4. retry_waste
5. recovery_without_state_change
6. missed_recovery_opportunity
7. failed_recovery
8. recovery_causing_unrelated_regression
9. recovery_causing_excessive_testing
10. recovery_causing_excessive_retrieval
11. recovery_budget_exhaustion
12. recovery_success_after_unnecessary_repetitions
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.recovery_opt.models import (
    RecoveryDiagnostics,
    RecoveryExecutionEvent,
    RecoveryOutcome,
)


class RecoveryTraceCollector:
    """Manages telemetry recording and diagnostics for recovery execution."""

    def __init__(self, trace_file: Optional[Path | str] = None) -> None:
        self.trace_file = Path(trace_file) if trace_file else None
        self.events: list[RecoveryExecutionEvent] = []

    def record_event(self, event: RecoveryExecutionEvent) -> None:
        """Records an individual recovery execution event."""
        self.events.append(event)
        if self.trace_file:
            self.trace_file.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")

    def load_events(self, trace_file: Path | str) -> List[RecoveryExecutionEvent]:
        """Loads events from an existing recovery_trace.jsonl."""
        p = Path(trace_file)
        self.events.clear()
        if not p.exists():
            return self.events

        with p.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        self.events.append(RecoveryExecutionEvent.from_dict(d))
                    except (json.JSONDecodeError, KeyError):
                        continue
        return self.events

    def evaluate_diagnostics(
        self,
        events: Optional[List[RecoveryExecutionEvent]] = None,
    ) -> RecoveryDiagnostics:
        """Evaluates 12 deterministic diagnostic conditions across recorded events."""
        evs = events if events is not None else self.events
        if not evs:
            return RecoveryDiagnostics()

        diag = RecoveryDiagnostics()
        notes: list[str] = []

        # Sort events
        sorted_evs = sorted(evs, key=lambda e: (e.turn, e.event_index))

        # 1. Late recovery
        first_opp = next((e.event_index for e in sorted_evs if e.recovery_eligible), None)
        first_trig = next((e.event_index for e in sorted_evs if e.trigger and e.action != "NONE"), None)
        if first_opp is not None and first_trig is not None and (first_trig - first_opp) >= 3:
            diag.late_recovery = True
            notes.append(f"Late recovery: triggered {first_trig - first_opp} events after first observable opportunity.")

        # 2. Repeated identical recovery
        for i in range(1, len(sorted_evs)):
            if (
                sorted_evs[i].action
                and sorted_evs[i].action != "NONE"
                and sorted_evs[i].action == sorted_evs[i - 1].action
                and sorted_evs[i].failure_signature == sorted_evs[i - 1].failure_signature
                and not sorted_evs[i].evidence_changed
            ):
                diag.repeated_identical_recovery = True
                notes.append(f"Repeated identical recovery: action '{sorted_evs[i].action}' executed repeatedly with no state change.")
                break

        # 3. Recovery oscillation
        actions = [e.action for e in sorted_evs if e.action and e.action != "NONE"]
        if len(actions) >= 4:
            for i in range(len(actions) - 3):
                if actions[i] == actions[i + 2] and actions[i + 1] == actions[i + 3] and actions[i] != actions[i + 1]:
                    diag.recovery_oscillation = True
                    notes.append(f"Recovery oscillation detected between '{actions[i]}' and '{actions[i+1]}'.")
                    break

        # 4. Retry waste
        retries_wasted = 0
        for i in range(1, len(sorted_evs)):
            if sorted_evs[i].attempt_number > 1 and not sorted_evs[i].evidence_changed:
                retries_wasted += 1
        if retries_wasted >= 2:
            diag.retry_waste = True
            notes.append(f"Retry waste: {retries_wasted} retries executed without evidence or state change.")

        # 5. Recovery without state change
        for e in sorted_evs:
            if e.action and e.action != "NONE" and not e.evidence_changed and e.state_before == e.state_after:
                diag.recovery_without_state_change = True
                notes.append("Recovery without state change: action finished with state_before == state_after.")
                break

        # 6. Missed recovery opportunity
        if any(e.recovery_eligible for e in sorted_evs) and not any(e.action and e.action != "NONE" for e in sorted_evs):
            diag.missed_recovery_opportunity = True
            notes.append("Missed recovery opportunity: recovery was eligible but no recovery action was executed.")

        # 7. Failed recovery
        if any(e.recovery_outcome == RecoveryOutcome.NOT_RECOVERED.value for e in sorted_evs):
            diag.failed_recovery = True
            notes.append("Failed recovery: one or more recovery attempts failed to resolve the failure.")

        # 8. Recovery causing unrelated regression
        if any(e.metadata.get("collateral_regression", False) for e in sorted_evs):
            diag.recovery_causing_unrelated_regression = True
            notes.append("Recovery causing unrelated regression: collateral regression observed.")

        # 9. Excessive testing
        test_actions = sum(1 for e in sorted_evs if "TEST" in (e.action or "").upper())
        if test_actions >= 4:
            diag.recovery_causing_excessive_testing = True
            notes.append(f"Excessive testing: {test_actions} test executions caused during recovery.")

        # 10. Excessive retrieval
        search_actions = sum(1 for e in sorted_evs if any(k in (e.action or "").upper() for k in ["SEARCH", "RETRIEV", "TREE", "GRAPH"]))
        if search_actions >= 5:
            diag.recovery_causing_excessive_retrieval = True
            notes.append(f"Excessive retrieval: {search_actions} retrieval calls caused during recovery.")

        # 11. Budget exhaustion
        if any(e.recovery_outcome == RecoveryOutcome.BUDGET_EXHAUSTED.value or "budget" in e.stop_reason.lower() for e in sorted_evs):
            diag.recovery_budget_exhaustion = True
            notes.append("Recovery budget exhaustion: recovery terminated due to budget exhaustion.")

        # 12. Recovery success after unnecessary repetitions
        reps_before_success = 0
        succeeded = False
        for e in sorted_evs:
            if e.recovery_outcome in [RecoveryOutcome.RECOVERED.value, RecoveryOutcome.RECOVERED_AFTER_RETRY.value]:
                succeeded = True
                break
            if e.action and e.action != "NONE":
                reps_before_success += 1
        if succeeded and reps_before_success >= 3:
            diag.recovery_success_after_unnecessary_repetitions = True
            notes.append(f"Recovery succeeded after {reps_before_success} previous recovery attempts.")

        diag.diagnostic_notes = notes
        return diag
