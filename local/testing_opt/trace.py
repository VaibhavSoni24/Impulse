"""Testing Telemetry and Diagnostics Engine (Stage 34 Sections 11, 15, 16).

Provides:
- Structured event logging (TestExecutionEvent, AdaptiveEscalationTrace)
- Anomaly and pathology detection (duplicate commands, unnecessary full suite, zero-new-evidence runs)
- Stage 25 context compaction integration (raw vs. compacted output sizes)
- JSONL persistence and serialization
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from local.testing_opt.models import (
    AdaptiveEscalationTrace,
    TestDiagnostics,
    TestExecutionEvent,
    TestLevel,
)


class TestTraceCollector:
    """Collects, analyzes, and serializes test execution traces for a candidate run."""

    def __init__(self, candidate_id: str = "T0") -> None:
        self.candidate_id = candidate_id
        self.events: List[TestExecutionEvent] = []
        self.adaptive_traces: List[AdaptiveEscalationTrace] = []
        self._seen_commands: Set[str] = set()
        self._seen_test_cases: Set[str] = set()
        self._file_edit_since_last_test: bool = True

    def notify_file_edited(self) -> None:
        """Notifies the collector that source files were modified since the last test run."""
        self._file_edit_since_last_test = True

    def record_adaptive_trace(self, trace: AdaptiveEscalationTrace) -> None:
        """Records a T3 adaptive decision trace."""
        self.adaptive_traces.append(trace)

    def record_event(
        self,
        event: TestExecutionEvent,
    ) -> TestExecutionEvent:
        """Records a structured test execution event and analyzes repetition."""
        norm_cmd = event.command.strip()

        # Check duplicate commands without code modifications
        if norm_cmd in self._seen_commands and not self._file_edit_since_last_test:
            event.metadata["is_duplicate_command"] = True
            event.metadata["rerun_without_edit"] = True
        elif norm_cmd in self._seen_commands:
            event.metadata["is_duplicate_command"] = True
        else:
            self._seen_commands.add(norm_cmd)

        # Track test cases
        duplicate_cases = 0
        for tc in event.selected_tests:
            clean_tc = tc.strip()
            if clean_tc in self._seen_test_cases:
                duplicate_cases += 1
            else:
                self._seen_test_cases.add(clean_tc)

        if duplicate_cases > 0:
            event.metadata["duplicate_cases_count"] = duplicate_cases

        self._file_edit_since_last_test = False
        self.events.append(event)
        return event

    def compute_diagnostics(self) -> TestDiagnostics:
        """Analyzes recorded execution events for testing pathologies (Stage 34 Section 16)."""
        diag = TestDiagnostics()

        for ev in self.events:
            # 1. Duplicate command
            if ev.metadata.get("is_duplicate_command", False):
                diag.duplicate_command_count += 1
                diag.diagnostic_messages.append(
                    f"Task {ev.task_id} level {ev.test_level}: duplicate test command `{ev.command}`."
                )

            # 2. Rerun after unchanged code
            if ev.metadata.get("rerun_without_edit", False):
                diag.rerun_unchanged_code_count += 1
                diag.diagnostic_messages.append(
                    f"Task {ev.task_id} level {ev.test_level}: command executed without preceding code edit."
                )

            # 3. Duplicate test cases
            dup_cases = ev.metadata.get("duplicate_cases_count", 0)
            if dup_cases > 0:
                diag.duplicate_case_count += dup_cases
                diag.diagnostic_messages.append(
                    f"Task {ev.task_id} level {ev.test_level}: {dup_cases} duplicate test cases re-executed."
                )

            # 4. Unnecessary full suite (full suite executed when targeted passed and risk was low)
            if ev.test_level == TestLevel.FULL.value and not ev.risk_signals:
                diag.unnecessary_full_suite_count += 1
                diag.diagnostic_messages.append(
                    f"Task {ev.task_id}: Full suite executed despite absence of high-risk signals."
                )

            # 5. Zero new evidence in adjacent / subsystem
            if ev.test_level == TestLevel.ADJACENT.value and ev.failures_detected == 0:
                diag.zero_new_evidence_adjacent_count += 1
            elif ev.test_level == TestLevel.SUBSYSTEM.value and ev.failures_detected == 0:
                diag.zero_new_evidence_subsystem_count += 1

            # 6. Repeated failure
            if ev.result == "FAIL" and ev.failures_detected > 0 and ev.metadata.get("is_duplicate_command", False):
                diag.repeated_failure_count += 1
                diag.diagnostic_messages.append(
                    f"Task {ev.task_id}: Identical failure reproduced repeatedly."
                )

        return diag

    def save_jsonl(self, file_path: Path | str) -> None:
        """Saves recorded events to JSONL."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for ev in self.events:
                f.write(json.dumps(ev.to_dict(), sort_keys=True) + "\n")

    @classmethod
    def load_jsonl(cls, file_path: Path | str) -> List[TestExecutionEvent]:
        """Loads test execution events from JSONL."""
        p = Path(file_path)
        if not p.is_file():
            return []
        events: List[TestExecutionEvent] = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(TestExecutionEvent.from_dict(json.loads(line)))
        return events
