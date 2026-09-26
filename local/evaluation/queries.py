"""Query and reporting helpers for the IMPULSE evaluation database."""

from __future__ import annotations

import sqlite3
from typing import Any


def get_database_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Returns row counts for all tables in the database."""
    tables = [
        "schema_version",
        "tasks",
        "candidates",
        "runs",
        "run_events",
        "metrics",
        "failures",
        "submissions",
    ]
    stats: dict[str, int] = {}
    cur = conn.cursor()
    for tbl in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            row = cur.fetchone()
            stats[tbl] = int(row[0]) if row else 0
        except sqlite3.OperationalError:
            stats[tbl] = 0
    return stats


def list_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Returns all recorded candidates and their metadata."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT candidate_id, model_id, git_commit, git_tag,
               prompt_reference, prompt_sha256, agent_config_reference, agent_config_sha256,
               description, created_at
        FROM candidates
        ORDER BY candidate_id ASC;
        """
    )
    return [dict(row) for row in cur.fetchall()]


def list_runs(
    conn: sqlite3.Connection,
    candidate_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Returns filtered run records."""
    query = """
    SELECT run_id, candidate_id, task_id, model_id, adapter_id, execution_backend,
           status, termination_reason, success, elapsed_seconds, timeout_seconds,
           tool_calls_budget, tool_calls, turns, files_read, files_changed,
           diff_lines, diff_bytes, patch_generated, failure_class, source_artifact, created_at
    FROM runs
    WHERE 1=1
    """
    params: list[Any] = []
    if candidate_id:
        query += " AND candidate_id = ?"
        params.append(candidate_id)
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at ASC, run_id ASC;"
    cur = conn.cursor()
    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def get_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """Returns complete details for a single run including candidate and task context."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.*,
               c.git_commit, c.git_tag, c.prompt_reference, c.prompt_sha256,
               t.repo, t.base_commit, t.category, t.selection_rationale
        FROM runs r
        JOIN candidates c ON r.candidate_id = c.candidate_id
        JOIN tasks t ON r.task_id = t.task_id
        WHERE r.run_id = ?;
        """,
        (run_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    run_dict = dict(row)

    # Attach failure info if present
    cur.execute("SELECT * FROM failures WHERE run_id = ?", (run_id,))
    f_row = cur.fetchone()
    run_dict["failure"] = dict(f_row) if f_row else None

    # Attach metrics if present
    cur.execute("SELECT metric_name, metric_value, metric_text FROM metrics WHERE run_id = ?", (run_id,))
    run_dict["metrics"] = [dict(m) for m in cur.fetchall()]

    return run_dict


def get_candidate_summary(conn: sqlite3.Connection, candidate_id: str) -> dict[str, Any]:
    """Computes an empirical summary for a candidate.

    Strictly preserves nulls when metrics were unexecuted.
    """
    runs = list_runs(conn, candidate_id=candidate_id)
    total_runs = len(runs)

    resolved_count = sum(1 for r in runs if r["success"] == 1)
    failed_count = sum(1 for r in runs if r["success"] == 0)
    unexecuted_count = sum(1 for r in runs if r["success"] is None)

    executed_runs = resolved_count + failed_count
    pass_rate = round(resolved_count / executed_runs, 4) if executed_runs > 0 else None

    # Compute averages strictly over non-null recorded values
    tool_calls_vals = [r["tool_calls"] for r in runs if r["tool_calls"] is not None]
    avg_tool_calls = round(sum(tool_calls_vals) / len(tool_calls_vals), 2) if tool_calls_vals else None

    turns_vals = [r["turns"] for r in runs if r["turns"] is not None]
    avg_turns = round(sum(turns_vals) / len(turns_vals), 2) if turns_vals else None

    elapsed_vals = [r["elapsed_seconds"] for r in runs if r["elapsed_seconds"] is not None]
    avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 2) if elapsed_vals else None

    failure_breakdown: dict[str, int] = {}
    status_breakdown: dict[str, int] = {}
    for r in runs:
        st = r["status"]
        status_breakdown[st] = status_breakdown.get(st, 0) + 1
        fc = r["failure_class"]
        if fc:
            failure_breakdown[fc] = failure_breakdown.get(fc, 0) + 1

    return {
        "candidate_id": candidate_id,
        "total_runs": total_runs,
        "resolved_count": resolved_count,
        "failed_count": failed_count,
        "unexecuted_count": unexecuted_count,
        "pass_rate": pass_rate,
        "avg_tool_calls": avg_tool_calls,
        "avg_turns": avg_turns,
        "avg_elapsed_seconds": avg_elapsed,
        "status_breakdown": status_breakdown,
        "failure_breakdown": failure_breakdown,
    }
