"""Query and normalization engine for the IMPULSE Failure Dashboard (Stage 30).

Extracts and normalizes evaluation runs from SQLite database, clean-copy records,
or JSONL results files into typed RunSummary objects.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from local.dashboard.models import EvidenceMode, RunSummary


def build_tasks_lookup(
    splits_root: Path | str = Path("benchmark/splits"),
    split_version: str = "v1",
    tasks_file: Optional[Path | str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Builds a mapping from task_id (instance_id) to task metadata (repo, base_commit, task_type).

    Checks split files first, then fallback to competition tasks.jsonl.
    """
    lookup: Dict[str, Dict[str, Any]] = {}

    # 1. From split files if available
    splits_dir = Path(splits_root) / split_version
    if splits_dir.is_dir():
        for split_name in ["dev", "validation", "held_out"]:
            split_p = splits_dir / f"{split_name}.jsonl"
            if split_p.is_file():
                with open(split_p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            tid = rec.get("instance_id")
                            if tid:
                                lookup[tid] = {
                                    "repo": rec.get("repo", ""),
                                    "base_commit": rec.get("base_commit", ""),
                                    "task_type": rec.get("task_type"),  # Often None
                                    "split_name": split_name,
                                }

    # 2. Supplementary check in general tasks file
    t_file = Path(tasks_file) if tasks_file else Path("data/competition/tasks.jsonl")
    if t_file.is_file():
        with open(t_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    tid = rec.get("instance_id")
                    if tid and tid not in lookup:
                        lookup[tid] = {
                            "repo": rec.get("repo", ""),
                            "base_commit": rec.get("base_commit", ""),
                            "task_type": rec.get("task_type"),
                        }

    return lookup


def normalize_execution_mode(raw_record: dict[str, Any]) -> str:
    """Classifies execution mode into LIVE, FIXTURE, INFRASTRUCTURE_ONLY, or UNAVAILABLE."""
    backend = str(raw_record.get("execution_backend", "")).lower()
    status = str(raw_record.get("status", "")).lower()
    failure_class = str(raw_record.get("failure_class", "")).lower()
    mode = str(raw_record.get("mode", "")).upper()

    if mode == "FIXTURE" or backend == "fixture" or "fixture" in status:
        return EvidenceMode.FIXTURE.value
    if (
        status == "execution_unavailable_local_host"
        or backend == "local-unavailable"
        or "unavailable" in failure_class
        or failure_class == "runtime_unavailable"
    ):
        return EvidenceMode.UNAVAILABLE.value
    if "infrastructure" in failure_class:
        return EvidenceMode.INFRASTRUCTURE_ONLY.value
    if raw_record.get("inference_executed") is False and raw_record.get("verification_executed") is False:
        return EvidenceMode.UNAVAILABLE.value

    # If completed live model inference:
    return EvidenceMode.LIVE.value


def run_row_to_summary(
    row: dict[str, Any],
    tasks_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> RunSummary:
    """Converts a SQLite row dictionary or JSONL record into a normalized RunSummary."""
    task_id = str(row.get("task_id", ""))
    t_info = tasks_lookup.get(task_id, {}) if tasks_lookup else {}

    # Extract repository
    repo = row.get("repo")
    if not repo or repo in ["unknown/unknown", "unknown"]:
        repo = t_info.get("repo", "")
    if not repo or repo in ["unknown/unknown", "unknown"]:
        # Fallback heuristic: task_ids start with repo name prefix (e.g. fastapi_14786)
        if "_" in task_id:
            prefix = task_id.split("_")[0]
            prefix_map = {
                "fastapi": "fastapi/fastapi",
                "rich": "Textualize/rich",
                "requests": "psf/requests",
                "httpx": "encode/httpx",
            }
            repo = prefix_map.get(prefix, prefix)

    # Extract task_type
    task_type = row.get("task_type") or t_info.get("task_type")

    # Extract split_name
    split_name = row.get("split_name") or t_info.get("split_name", "")

    # Success normalization: 1 -> True, 0 -> False, None -> None
    raw_success = row.get("success")
    if raw_success is None:
        raw_success = row.get("resolved")
    success_val: Optional[bool] = None
    if raw_success is not None:
        if isinstance(raw_success, bool):
            success_val = raw_success
        elif isinstance(raw_success, (int, float)):
            success_val = bool(raw_success == 1)
        elif str(raw_success).lower() in ["true", "1", "pass", "resolved"]:
            success_val = True
        elif str(raw_success).lower() in ["false", "0", "fail", "failed"]:
            success_val = False

    # Execution mode
    exec_mode = normalize_execution_mode(row)

    # Recovery signals
    rec_trig = row.get("recovery_triggered")
    rec_succ = row.get("recovery_success")
    if rec_trig is not None:
        rec_trig = bool(rec_trig)
    if rec_succ is not None:
        rec_succ = bool(rec_succ)

    # Clean-copy verification
    cc_ver = row.get("clean_copy_verified")
    if cc_ver is not None:
        cc_ver = bool(cc_ver)

    return RunSummary(
        run_id=str(row.get("run_id", "")),
        candidate_id=str(row.get("candidate_id", "")),
        task_id=task_id,
        split_name=split_name,
        split_version=str(row.get("split_version", "v1")),
        repository=repo,
        task_type=task_type,
        execution_mode=exec_mode,
        success=success_val,
        execution_status=str(row.get("status") or row.get("execution_status") or "UNKNOWN"),
        termination_reason=row.get("termination_reason"),
        failure_class=row.get("failure_class"),
        failure_stage=row.get("failure_stage"),
        elapsed_seconds=row.get("elapsed_seconds") if row.get("elapsed_seconds") is not None else row.get("elapsed_time_seconds"),
        tool_calls=row.get("tool_calls"),
        turns=row.get("turns"),
        files_changed=row.get("files_changed"),
        patch_lines=row.get("diff_lines") if row.get("diff_lines") is not None else row.get("patch_lines"),
        recovery_triggered=rec_trig,
        recovery_success=rec_succ,
        final_review_status=row.get("final_review_status"),
        patch_apply_status=row.get("patch_apply_status"),
        verification_status=row.get("verification_status"),
        clean_copy_verified=cc_ver,
        created_at=str(row.get("created_at") or row.get("timestamp") or ""),
    )


def fetch_runs_from_db(
    conn: sqlite3.Connection,
    candidate_id: str,
    split_name: Optional[str] = None,
    split_version: str = "v1",
    tasks_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[RunSummary]:
    """Queries the SQLite database for runs matching candidate and optional split."""
    query = """
    SELECT r.*, t.repo, t.base_commit, t.category AS task_type
    FROM runs r
    LEFT JOIN tasks t ON r.task_id = t.task_id
    WHERE r.candidate_id = ?
    """
    params: list[Any] = [candidate_id]

    norm_split = split_name.lower().strip() if split_name else None
    if norm_split and norm_split != "all":
        query += " AND (r.split_name = ? OR r.split_name IS NULL OR r.split_name = '')"
        params.append(norm_split)

    query += " ORDER BY r.created_at ASC, r.run_id ASC;"

    cur = conn.cursor()
    try:
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        # If tasks table or certain columns are not yet present
        try:
            fallback_query = "SELECT * FROM runs WHERE candidate_id = ? ORDER BY created_at ASC, run_id ASC;"
            cur.execute(fallback_query, [candidate_id])
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            rows = []

    summaries: list[RunSummary] = []
    for row in rows:
        summary = run_row_to_summary(row, tasks_lookup=tasks_lookup)
        # If split filter is active and summary split wasn't in DB row, check resolved split
        if norm_split and norm_split != "all":
            if summary.split_name and summary.split_name.lower() != norm_split:
                continue
            # If split was unassigned in DB, bind it to the target split if task belongs to it
            if not summary.split_name and tasks_lookup and summary.task_id in tasks_lookup:
                target_split = tasks_lookup[summary.task_id].get("split_name")
                if target_split and target_split.lower() != norm_split:
                    continue
                summary.split_name = norm_split
        summaries.append(summary)

    return summaries


def load_runs_from_jsonl(
    jsonl_path: Path | str,
    candidate_id: Optional[str] = None,
    split_name: Optional[str] = None,
    tasks_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[RunSummary]:
    """Loads evaluation runs from a results.jsonl file."""
    path = Path(jsonl_path)
    if not path.is_file():
        return []

    runs: list[RunSummary] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if candidate_id and record.get("candidate_id") != candidate_id:
                continue
            summary = run_row_to_summary(record, tasks_lookup=tasks_lookup)
            norm_split = split_name.lower().strip() if split_name else None
            if norm_split and norm_split != "all":
                if summary.split_name and summary.split_name.lower() != norm_split:
                    continue
                if not summary.split_name and tasks_lookup and summary.task_id in tasks_lookup:
                    assigned = tasks_lookup[summary.task_id].get("split_name")
                    if assigned and assigned.lower() != norm_split:
                        continue
                    summary.split_name = norm_split
            runs.append(summary)

    return runs
