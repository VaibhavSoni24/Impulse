"""Ingestion logic for parsing and persisting evaluation results and metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from local.evaluation.db import get_connection
from local.runner.task_loader import TaskLoader


def ensure_candidate(
    conn: sqlite3.Connection,
    candidate_id: str,
    model_id: str,
    git_commit: str | None = None,
    git_tag: str | None = None,
    prompt_reference: str | None = None,
    prompt_sha256: str | None = None,
    agent_config_reference: str | None = None,
    agent_config_sha256: str | None = None,
    description: str | None = None,
    created_at: str | None = None,
) -> None:
    """Inserts or updates candidate metadata in the candidates table."""
    now_iso = created_at or datetime.now(timezone.utc).isoformat()
    sql = """
    INSERT INTO candidates (
        candidate_id, model_id, git_commit, git_tag,
        prompt_reference, prompt_sha256, agent_config_reference, agent_config_sha256,
        description, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(candidate_id) DO UPDATE SET
        model_id=excluded.model_id,
        git_commit=COALESCE(excluded.git_commit, candidates.git_commit),
        git_tag=COALESCE(excluded.git_tag, candidates.git_tag),
        prompt_reference=COALESCE(excluded.prompt_reference, candidates.prompt_reference),
        prompt_sha256=COALESCE(excluded.prompt_sha256, candidates.prompt_sha256),
        agent_config_reference=COALESCE(excluded.agent_config_reference, candidates.agent_config_reference),
        agent_config_sha256=COALESCE(excluded.agent_config_sha256, candidates.agent_config_sha256),
        description=COALESCE(excluded.description, candidates.description),
        created_at=COALESCE(candidates.created_at, excluded.created_at);
    """
    conn.execute(
        sql,
        (
            candidate_id,
            model_id,
            git_commit,
            git_tag,
            prompt_reference,
            prompt_sha256,
            agent_config_reference,
            agent_config_sha256,
            description,
            now_iso,
        ),
    )


def ensure_task(
    conn: sqlite3.Connection,
    task_id: str,
    repo: str = "unknown/unknown",
    base_commit: str = "unknown",
    category: str | None = None,
    selection_rationale: str | None = None,
    problem_statement_chars: int | None = None,
    hints_text_chars: int | None = None,
    created_at: str | None = None,
) -> None:
    """Inserts or updates task metadata in the tasks table."""
    sql = """
    INSERT INTO tasks (
        task_id, repo, base_commit, category, selection_rationale,
        problem_statement_chars, hints_text_chars, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(task_id) DO UPDATE SET
        repo=CASE WHEN excluded.repo != 'unknown/unknown' THEN excluded.repo ELSE tasks.repo END,
        base_commit=CASE WHEN excluded.base_commit != 'unknown' THEN excluded.base_commit ELSE tasks.base_commit END,
        category=COALESCE(excluded.category, tasks.category),
        selection_rationale=COALESCE(excluded.selection_rationale, tasks.selection_rationale),
        problem_statement_chars=COALESCE(excluded.problem_statement_chars, tasks.problem_statement_chars),
        hints_text_chars=COALESCE(excluded.hints_text_chars, tasks.hints_text_chars);
    """
    conn.execute(
        sql,
        (
            task_id,
            repo,
            base_commit,
            category,
            selection_rationale,
            problem_statement_chars,
            hints_text_chars,
            created_at,
        ),
    )


def populate_tasks_from_files(
    conn: sqlite3.Connection,
    tasks_file: Path | str | None = None,
    smoke_file: Path | str | None = None,
) -> int:
    """Pre-populates the tasks table from competition tasks.jsonl and smoke.jsonl."""
    count = 0

    # 1. Load smoke metadata if available (gives category and selection_rationale)
    smoke_meta: dict[str, dict[str, Any]] = {}
    smoke_path = Path(smoke_file) if smoke_file else Path("benchmark/tasks/smoke.jsonl")
    if smoke_path.exists():
        with open(smoke_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line.strip())
                    smoke_meta[rec["instance_id"]] = rec

    # 2. Load full tasks manifest if available
    tasks_path = Path(tasks_file) if tasks_file else Path("data/competition/tasks.jsonl")
    if tasks_path.exists():
        loader = TaskLoader(tasks_path)
        for tid in loader.list_task_ids():
            try:
                task = loader.get_task(tid)
                s_rec = smoke_meta.get(tid, {})
                ensure_task(
                    conn=conn,
                    task_id=task.instance_id,
                    repo=task.repo,
                    base_commit=task.base_commit,
                    category=s_rec.get("category"),
                    selection_rationale=s_rec.get("selection_rationale"),
                    problem_statement_chars=len(task.problem_statement),
                    hints_text_chars=len(task.hints_text),
                    created_at=task.created_at,
                )
                count += 1
            except Exception:
                continue
    elif smoke_meta:
        # Fallback to smoke records if full tasks file is not present
        for tid, s_rec in smoke_meta.items():
            ensure_task(
                conn=conn,
                task_id=s_rec["instance_id"],
                repo=s_rec.get("repo", "unknown"),
                base_commit=s_rec.get("base_commit", "unknown"),
                category=s_rec.get("category"),
                selection_rationale=s_rec.get("selection_rationale"),
            )
            count += 1

    return count


def ingest_manifest(conn: sqlite3.Connection, manifest_path: Path | str) -> str:
    """Ingests a candidate manifest.json into the candidates table.

    Returns the ingested candidate_id.
    """
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidate_id = data["candidate_id"]
    model_id = data.get("model_id", "gemma-4-31b-it-qat-w4a16-ct")

    with conn:
        ensure_candidate(
            conn=conn,
            candidate_id=candidate_id,
            model_id=model_id,
            git_commit=data.get("git_commit"),
            git_tag=data.get("git_tag"),
            prompt_reference=data.get("prompt_reference"),
            prompt_sha256=data.get("prompt_sha256"),
            agent_config_reference=data.get("agent_config_reference"),
            agent_config_sha256=data.get("agent_config_sha256"),
            description=data.get("description") or f"Candidate {candidate_id} baseline",
            created_at=data.get("timestamp"),
        )

    return candidate_id


def ingest_results(
    conn: sqlite3.Connection,
    results_path: Path | str,
    manifest_path: Path | str | None = None,
    auto_populate_tasks: bool = True,
) -> int:
    """Ingests a results.jsonl file into the runs and failures tables.

    Idempotent: Re-ingesting existing run_ids updates records without duplication.
    Preserves null metrics when model execution was unavailable.

    Returns:
        Number of run records ingested.
    """
    res_path = Path(results_path)
    if not res_path.exists():
        raise FileNotFoundError(f"Results file not found: {res_path}")

    # Auto-detect companion manifest if not explicitly given
    if manifest_path is None:
        candidate_manifest = res_path.parent / "manifest.json"
        if candidate_manifest.exists():
            manifest_path = candidate_manifest

    # Ingest candidate manifest if present
    if manifest_path and Path(manifest_path).exists():
        ingest_manifest(conn, manifest_path)

    # Pre-populate tasks from repository manifests if requested
    if auto_populate_tasks:
        with conn:
            populate_tasks_from_files(conn)

    count = 0
    with open(res_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    with conn:
        for line in lines:
            record = json.loads(line)
            run_id = record["run_id"]
            candidate_id = record["candidate_id"]
            task_id = record["task_id"]
            model_id = record.get("model_id", "gemma-4-31b-it-qat-w4a16-ct")

            # Ensure candidate exists (in case manifest was absent)
            ensure_candidate(
                conn=conn,
                candidate_id=candidate_id,
                model_id=model_id,
            )

            # Ensure task exists (in case tasks manifest did not contain it)
            ensure_task(
                conn=conn,
                task_id=task_id,
            )

            # Parse success/resolution state strictly
            # 1 = resolved, 0 = failed, NULL = unexecuted / unavailable
            resolved_raw = record.get("resolved")
            if resolved_raw is True:
                success_val: int | None = 1
            elif resolved_raw is False:
                success_val = 0
            else:
                success_val = None

            status = record.get("status", "unknown")
            termination_reason = record.get("termination_reason")
            elapsed_seconds = record.get("elapsed_time_seconds")
            timeout_seconds = record.get("timeout_seconds")
            tool_calls_budget = record.get("tool_calls_budget")

            # Nullable metric fields - preserve None strictly (do not coerce to 0)
            tool_calls = record.get("tool_calls")
            turns = record.get("turns")
            files_read = record.get("files_read")
            files_changed = record.get("files_changed")
            diff_lines = record.get("diff_lines")
            diff_bytes = record.get("diff_bytes")

            patch_generated = 1 if record.get("patch_generated") else 0
            failure_class = record.get("failure_class")
            source_artifact = str(res_path)
            created_at = record.get("timestamp") or datetime.now(timezone.utc).isoformat()

            run_sql = """
            INSERT INTO runs (
                run_id, candidate_id, task_id, model_id, adapter_id, execution_backend,
                status, termination_reason, success, elapsed_seconds, timeout_seconds,
                tool_calls_budget, tool_calls, turns, files_read, files_changed,
                diff_lines, diff_bytes, patch_generated, failure_class, source_artifact, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(run_id) DO UPDATE SET
                candidate_id=excluded.candidate_id,
                task_id=excluded.task_id,
                model_id=excluded.model_id,
                adapter_id=excluded.adapter_id,
                execution_backend=excluded.execution_backend,
                status=excluded.status,
                termination_reason=excluded.termination_reason,
                success=excluded.success,
                elapsed_seconds=excluded.elapsed_seconds,
                timeout_seconds=excluded.timeout_seconds,
                tool_calls_budget=excluded.tool_calls_budget,
                tool_calls=excluded.tool_calls,
                turns=excluded.turns,
                files_read=excluded.files_read,
                files_changed=excluded.files_changed,
                diff_lines=excluded.diff_lines,
                diff_bytes=excluded.diff_bytes,
                patch_generated=excluded.patch_generated,
                failure_class=excluded.failure_class,
                source_artifact=excluded.source_artifact,
                created_at=excluded.created_at;
            """

            conn.execute(
                run_sql,
                (
                    run_id,
                    candidate_id,
                    task_id,
                    model_id,
                    record.get("adapter_id"),
                    record.get("execution_backend", "unavailable"),
                    status,
                    termination_reason,
                    success_val,
                    elapsed_seconds,
                    timeout_seconds,
                    tool_calls_budget,
                    tool_calls,
                    turns,
                    files_read,
                    files_changed,
                    diff_lines,
                    diff_bytes,
                    patch_generated,
                    failure_class,
                    source_artifact,
                    created_at,
                ),
            )

            # Record failure if flagged or if infrastructure unavailable
            is_infra = 1 if (
                failure_class == "infrastructure_unavailable"
                or status == "execution_unavailable_local_host"
            ) else 0

            if failure_class or is_infra:
                f_class = failure_class or "infrastructure_unavailable"
                fail_sql = """
                INSERT INTO failures (
                    run_id, failure_class, error_message, traceback, is_infrastructure, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    failure_class=excluded.failure_class,
                    error_message=excluded.error_message,
                    traceback=excluded.traceback,
                    is_infrastructure=excluded.is_infrastructure,
                    created_at=excluded.created_at;
                """
                conn.execute(
                    fail_sql,
                    (
                        run_id,
                        f_class,
                        record.get("error_message") or termination_reason,
                        record.get("traceback"),
                        is_infra,
                        created_at,
                    ),
                )

            count += 1

    return count
