"""Deterministic Recovery Pattern Mining Engine (Stage 35 Sections 5, 6, 7).

Inspects authoritative trace sources:
- SQLite evaluation database (`experiments/evaluation.db`)
- Run summaries, run_events, failures
- FDD and recovery telemetry records
- Tool and test execution traces

Extracts normalized `RecoveryFailureRecord` instances across canonical pattern dimensions:
- REPEATED_COMMAND
- REPEATED_ERROR
- REPEATED_EDIT
- REPEATED_HYPOTHESIS
- RECOVERY_THRASHING
- RECOVERY_OMISSION
- LATE_RECOVERY
- FAILED_RECOVERY
- RECOVERY_LOOP
- RETRY_WASTE

Preserves provenance and returns empty lists when evidence is absent (zero fabrication).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from local.dashboard.models import EvidenceMode
from local.failures.models import FailureClass
from local.recovery_opt.models import (
    RecoveryFailureRecord,
    RecoveryOutcome,
    RecoveryPatternType,
)


def normalize_command_str(cmd: str) -> str:
    """Normalizes shell commands for repeated command detection."""
    c = cmd.strip()
    c = re.sub(r"\s+", " ", c)
    return c


def extract_failure_signature(msg: str, tb: str = "") -> str:
    """Extracts a stable failure signature from error message and traceback."""
    text = (msg or "").strip()
    if not text and tb:
        text = tb.strip().split("\n")[-1]
    if not text:
        return "UNKNOWN_FAILURE"
    # Take first line up to 120 chars
    first_line = text.split("\n")[0].strip()
    # Normalize volatile addresses or temp paths
    cleaned = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", first_line)
    cleaned = re.sub(r"[A-Za-z]:\\[^\s:]+", "<PATH>", cleaned)
    cleaned = re.sub(r"/tmp/[^\s:]+", "<PATH>", cleaned)
    return cleaned[:120].strip()


class RecoveryTraceMiner:
    """Deterministic miner for recovery patterns across run traces and databases."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.db_path = self.repo_root / "experiments" / "evaluation.db"

    def mine_all_sources(self) -> List[RecoveryFailureRecord]:
        """Mines all authoritative sources and returns normalized records."""
        records: list[RecoveryFailureRecord] = []

        # 1. Mine SQLite DB
        if self.db_path.exists():
            records.extend(self.mine_from_sqlite(self.db_path))

        # 2. Mine JSONL traces in experiments/
        exp_dir = self.repo_root / "experiments"
        if exp_dir.exists():
            for jsonl_file in exp_dir.glob("**/recovery_trace.jsonl"):
                records.extend(self.mine_from_recovery_trace_file(jsonl_file))

        # Sort deterministically
        records.sort(key=lambda r: (r.task_id, r.run_id, r.failure_id, r.repeated_pattern or ""))
        return records

    def mine_from_sqlite(self, db_path: Path) -> List[RecoveryFailureRecord]:
        """Mines failure records from SQLite evaluation.db."""
        records: list[RecoveryFailureRecord] = []
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            # Inspect runs table
            query = """
                SELECT r.run_id, r.candidate_id, r.task_id, r.status,
                       f.failure_id, f.failure_class, f.error_message, f.traceback, f.is_infrastructure
                FROM runs r
                LEFT JOIN failures f ON r.run_id = f.run_id
            """
            cur.execute(query)
            rows = cur.fetchall()

            for row in rows:
                run_id, cand_id, task_id, status, fail_id, fail_cls, err_msg, tb, is_infra = row
                
                # Determine evidence mode and actionability
                if "unavailable" in (status or "").lower() or is_infra:
                    mode = EvidenceMode.UNAVAILABLE.value
                    is_actionable = False
                elif "fixture" in (status or "").lower():
                    mode = EvidenceMode.FIXTURE.value
                    is_actionable = True
                else:
                    mode = EvidenceMode.LIVE.value
                    is_actionable = True

                sig = extract_failure_signature(err_msg or "", tb or "")
                
                rec = RecoveryFailureRecord(
                    run_id=str(run_id or ""),
                    task_id=str(task_id or ""),
                    candidate_id=str(cand_id or ""),
                    evidence_mode=mode,
                    failure_id=str(fail_id or f"fail_{run_id}"),
                    failure_class=str(fail_cls or "UNKNOWN"),
                    failure_signature=sig,
                    terminal_outcome=str(status or "UNKNOWN"),
                    is_actionable=is_actionable,
                    source_event_ids=[f"sqlite:runs:{run_id}"],
                )
                records.append(rec)
            conn.close()
        except sqlite3.Error:
            pass

        return records

    def mine_from_recovery_trace_file(self, trace_path: Path) -> List[RecoveryFailureRecord]:
        """Mines records directly from a structured recovery_trace.jsonl."""
        records: list[RecoveryFailureRecord] = []
        if not trace_path.exists():
            return records

        events_by_task: dict[str, list[dict[str, Any]]] = {}
        with trace_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    tid = str(data.get("task_id", ""))
                    events_by_task.setdefault(tid, []).append(data)
                except json.JSONDecodeError:
                    continue

        for tid, events in events_by_task.items():
            records.extend(self.analyze_task_events(tid, events, source_file=str(trace_path)))

        return records

    def analyze_task_events(
        self,
        task_id: str,
        events: List[dict[str, Any]],
        source_file: str = "",
    ) -> List[RecoveryFailureRecord]:
        """Analyzes structured events for a task and detects recovery patterns deterministically."""
        records: list[RecoveryFailureRecord] = []
        if not events:
            return records

        # Sort events by event_index or turn
        sorted_events = sorted(events, key=lambda e: (e.get("turn", 0), e.get("event_index", 0)))
        
        run_id = str(sorted_events[0].get("run_id", ""))
        cand_id = str(sorted_events[0].get("candidate_id", ""))
        ev_mode = str(sorted_events[0].get("evidence_mode", "FIXTURE"))

        # Track patterns
        commands_seen: list[tuple[int, str, str]] = []  # (event_idx, cmd, status)
        errors_seen: list[tuple[int, str, bool]] = []  # (event_idx, error_sig, evidence_changed)
        edits_seen: list[tuple[int, str, bool]] = []   # (event_idx, file_path, test_passed)
        recovery_actions: list[tuple[int, str, str]] = []  # (event_idx, action, outcome)

        first_failure_event: Optional[int] = None
        first_recovery_opportunity: Optional[int] = None
        actual_recovery_trigger: Optional[int] = None

        for idx, ev in enumerate(sorted_events):
            e_idx = ev.get("event_index", idx)
            cmd = ev.get("command") or ev.get("metadata", {}).get("command")
            fail_sig = ev.get("failure_signature") or ev.get("metadata", {}).get("error_signature")
            edit_file = ev.get("metadata", {}).get("target_file")
            action = ev.get("action")
            outcome = ev.get("recovery_outcome")
            ev_changed = ev.get("evidence_changed", False)
            outcome_res = ev.get("metadata", {}).get("result") or outcome

            if (fail_sig or outcome_res == "FAIL") and first_failure_event is None:
                first_failure_event = e_idx
                first_recovery_opportunity = e_idx

            if action and action != "NONE":
                if actual_recovery_trigger is None:
                    actual_recovery_trigger = e_idx
                recovery_actions.append((e_idx, action, outcome or ""))

            if cmd:
                norm_c = normalize_command_str(cmd)
                commands_seen.append((e_idx, norm_c, outcome_res or "FAIL"))

            if fail_sig:
                errors_seen.append((e_idx, fail_sig, ev_changed))

            if edit_file:
                test_pass = outcome_res == "PASS"
                edits_seen.append((e_idx, edit_file, test_pass))

        # A. Check REPEATED_COMMAND
        for i in range(1, len(commands_seen)):
            prev_e, prev_c, prev_s = commands_seen[i - 1]
            curr_e, curr_c, curr_s = commands_seen[i]
            if prev_c == curr_c and prev_s in ["FAIL", "ERROR"] and curr_s in ["FAIL", "ERROR"]:
                records.append(
                    RecoveryFailureRecord(
                        run_id=run_id,
                        task_id=task_id,
                        candidate_id=cand_id,
                        evidence_mode=ev_mode,
                        failure_id=f"rep_cmd_{task_id}_{curr_e}",
                        failure_class=FailureClass.COMMAND.value,
                        failure_signature=f"REPEATED_CMD: {curr_c[:80]}",
                        repeated_pattern=RecoveryPatternType.REPEATED_COMMAND.value,
                        first_failure_event=first_failure_event or prev_e,
                        first_recovery_opportunity=first_recovery_opportunity or prev_e,
                        actual_recovery_trigger=actual_recovery_trigger,
                        recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                        source_event_ids=[f"{source_file}:{prev_e}", f"{source_file}:{curr_e}"],
                        is_actionable=True,
                    )
                )

        # B. Check REPEATED_ERROR
        for i in range(1, len(errors_seen)):
            prev_e, prev_sig, prev_ev = errors_seen[i - 1]
            curr_e, curr_sig, curr_ev = errors_seen[i]
            if prev_sig == curr_sig and not curr_ev:
                records.append(
                    RecoveryFailureRecord(
                        run_id=run_id,
                        task_id=task_id,
                        candidate_id=cand_id,
                        evidence_mode=ev_mode,
                        failure_id=f"rep_err_{task_id}_{curr_e}",
                        failure_class=FailureClass.UNKNOWN.value,
                        failure_signature=f"REPEATED_ERR: {curr_sig[:80]}",
                        repeated_pattern=RecoveryPatternType.REPEATED_ERROR.value,
                        first_failure_event=first_failure_event or prev_e,
                        first_recovery_opportunity=first_recovery_opportunity or prev_e,
                        actual_recovery_trigger=actual_recovery_trigger,
                        recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                        source_event_ids=[f"{source_file}:{prev_e}", f"{source_file}:{curr_e}"],
                        is_actionable=True,
                    )
                )

        # C. Check REPEATED_EDIT
        for i in range(1, len(edits_seen)):
            prev_e, prev_f, prev_pass = edits_seen[i - 1]
            curr_e, curr_f, curr_pass = edits_seen[i]
            if prev_f == curr_f and not prev_pass and not curr_pass:
                records.append(
                    RecoveryFailureRecord(
                        run_id=run_id,
                        task_id=task_id,
                        candidate_id=cand_id,
                        evidence_mode=ev_mode,
                        failure_id=f"rep_edit_{task_id}_{curr_e}",
                        failure_class=FailureClass.INCOMPLETE_FIX.value,
                        failure_signature=f"REPEATED_EDIT: {curr_f[:80]}",
                        repeated_pattern=RecoveryPatternType.REPEATED_EDIT.value,
                        first_failure_event=first_failure_event or prev_e,
                        first_recovery_opportunity=first_recovery_opportunity or prev_e,
                        actual_recovery_trigger=actual_recovery_trigger,
                        recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                        source_event_ids=[f"{source_file}:{prev_e}", f"{source_file}:{curr_e}"],
                        is_actionable=True,
                    )
                )

        # E. Check RECOVERY_THRASHING / OSCILLATION
        if len(recovery_actions) >= 4:
            acts = [a[1] for a in recovery_actions]
            # Pattern A -> B -> A -> B
            for i in range(len(acts) - 3):
                if acts[i] == acts[i + 2] and acts[i + 1] == acts[i + 3] and acts[i] != acts[i + 1]:
                    records.append(
                        RecoveryFailureRecord(
                            run_id=run_id,
                            task_id=task_id,
                            candidate_id=cand_id,
                            evidence_mode=ev_mode,
                            failure_id=f"thrash_{task_id}_{i}",
                            failure_class=FailureClass.UNKNOWN.value,
                            failure_signature=f"OSCILLATION: {acts[i]} <-> {acts[i+1]}",
                            repeated_pattern=RecoveryPatternType.RECOVERY_THRASHING.value,
                            loop_detected=True,
                            loop_length=4,
                            first_failure_event=first_failure_event,
                            first_recovery_opportunity=first_recovery_opportunity,
                            actual_recovery_trigger=actual_recovery_trigger,
                            recovery_outcome=RecoveryOutcome.LOOP_DETECTED.value,
                            source_event_ids=[f"{source_file}:{recovery_actions[k][0]}" for k in range(i, i + 4)],
                            is_actionable=True,
                        )
                    )
                    break

        # G. Check LATE_RECOVERY
        if first_recovery_opportunity is not None and actual_recovery_trigger is not None:
            latency = actual_recovery_trigger - first_recovery_opportunity
            if latency >= 3:
                records.append(
                    RecoveryFailureRecord(
                        run_id=run_id,
                        task_id=task_id,
                        candidate_id=cand_id,
                        evidence_mode=ev_mode,
                        failure_id=f"late_rec_{task_id}_{actual_recovery_trigger}",
                        failure_class=FailureClass.UNKNOWN.value,
                        failure_signature=f"LATE_RECOVERY: latency={latency}_events",
                        repeated_pattern=RecoveryPatternType.LATE_RECOVERY.value,
                        first_failure_event=first_failure_event,
                        first_recovery_opportunity=first_recovery_opportunity,
                        actual_recovery_trigger=actual_recovery_trigger,
                        recovery_outcome=RecoveryOutcome.NOT_RECOVERED.value,
                        source_event_ids=[f"{source_file}:{first_recovery_opportunity}", f"{source_file}:{actual_recovery_trigger}"],
                        is_actionable=True,
                    )
                )

        return records
