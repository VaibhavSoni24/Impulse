"""Normalization layer for failure-driven analysis (Stage 31 Section 4).

Converts raw evaluation records from SQLite database, failures.jsonl files,
or RunSummary instances into typed FailureRecord models with strict
actionability determination.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.dashboard.models import EvidenceMode, RunSummary
from local.fdd.models import FailureRecord
from local.failures.models import FailureClass


def is_infrastructure_failure(failure_class: str, status: str, termination_reason: str) -> bool:
    """Detects whether a failure is caused by environment/hardware availability limits."""
    fc = (failure_class or "").lower()
    st = (status or "").lower()
    tr = (termination_reason or "").lower()

    if "infrastructure" in fc or "unavailable" in fc:
        return True
    if "execution_unavailable" in st or "local-unavailable" in st:
        return True
    if "lack" in tr and "gpu" in tr:
        return True
    return False


def normalize_failure_record(
    raw: dict[str, Any] | RunSummary,
    source_ref: str = "",
) -> FailureRecord:
    """Normalizes an individual failure record, determining cognitive actionability."""
    if isinstance(raw, RunSummary):
        d = raw.to_dict()
    else:
        d = dict(raw)

    run_id = str(d.get("run_id", ""))
    candidate_id = str(d.get("candidate_id", ""))
    task_id = str(d.get("task_id", ""))
    split = str(d.get("split") or d.get("split_name") or "dev")
    repo = str(d.get("repository") or d.get("repo") or "")
    mode = str(d.get("evidence_mode") or d.get("execution_mode") or EvidenceMode.UNAVAILABLE.value).upper()
    run_status = str(d.get("run_status") or d.get("execution_status") or d.get("status") or "UNKNOWN")
    success = d.get("success")

    # Normalize failure class/category
    fc = (d.get("failure_class") or d.get("failure_category") or "UNKNOWN").strip().upper()
    fs = (d.get("failure_stage") or "UNKNOWN").strip().upper()
    term_reason = str(d.get("termination_reason") or "")

    is_infra = is_infrastructure_failure(fc, run_status, term_reason)

    # Actionable only if it's a real executed failure (not unexecuted/infrastructure limit)
    is_actionable = False
    if mode in [EvidenceMode.LIVE.value, EvidenceMode.FIXTURE.value]:
        if success is False and not is_infra:
            is_actionable = True

    return FailureRecord(
        run_id=run_id,
        candidate_id=candidate_id,
        task_id=task_id,
        split=split,
        repository=repo,
        evidence_mode=mode,
        run_status=run_status,
        success=success,
        failure_category=fc,
        failure_stage=fs,
        termination_reason=term_reason,
        runtime_seconds=d.get("elapsed_seconds") if d.get("elapsed_seconds") is not None else d.get("runtime_seconds"),
        tool_calls=d.get("tool_calls"),
        turns=d.get("turns"),
        files_changed=d.get("files_changed"),
        diff_lines=d.get("patch_lines") if d.get("patch_lines") is not None else d.get("diff_lines"),
        recovery_triggered=d.get("recovery_triggered"),
        recovery_success=d.get("recovery_success"),
        evaluator_stage=d.get("evaluator_stage"),
        source_record_reference=source_ref or f"run:{run_id}",
        is_actionable=is_actionable,
    )


def normalize_failures_from_summaries(
    summaries: List[RunSummary],
    source_ref: str = "run_summaries",
) -> List[FailureRecord]:
    """Normalizes a list of RunSummary objects."""
    records: list[FailureRecord] = []
    for s in summaries:
        if s.success is False or s.failure_class:
            records.append(normalize_failure_record(s, source_ref=f"{source_ref}:{s.run_id}"))
    return records


def normalize_failures_from_jsonl(
    jsonl_path: Path | str,
) -> List[FailureRecord]:
    """Loads and normalizes failure records from a failures.jsonl file."""
    path = Path(jsonl_path)
    if not path.is_file():
        return []

    records: list[FailureRecord] = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            raw_rec = json.loads(line)
            records.append(normalize_failure_record(raw_rec, source_ref=f"{path.name}:{idx}"))

    return records
