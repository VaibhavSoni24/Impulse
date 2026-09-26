"""Schema definition and migration logic for the IMPULSE evaluation database."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

CURRENT_SCHEMA_VERSION = 1

SCHEMA_VERSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);
"""

TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    category TEXT,
    selection_rationale TEXT,
    problem_statement_chars INTEGER,
    hints_text_chars INTEGER,
    created_at TEXT
);
"""

CANDIDATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    git_commit TEXT,
    git_tag TEXT,
    prompt_reference TEXT,
    prompt_sha256 TEXT,
    agent_config_reference TEXT,
    agent_config_sha256 TEXT,
    description TEXT,
    created_at TEXT
);
"""

RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    adapter_id TEXT,
    execution_backend TEXT NOT NULL,
    status TEXT NOT NULL,
    termination_reason TEXT,
    success INTEGER,              -- 1 = resolved, 0 = failed, NULL = unexecuted / unavailable
    elapsed_seconds REAL,
    timeout_seconds INTEGER,
    tool_calls_budget INTEGER,
    tool_calls INTEGER,           -- NULL if unexecuted / unavailable
    turns INTEGER,                -- NULL if unexecuted / unavailable
    files_read INTEGER,           -- NULL if unexecuted / unavailable
    files_changed INTEGER,        -- NULL if unexecuted / unavailable
    diff_lines INTEGER,           -- NULL if unexecuted / unavailable
    diff_bytes INTEGER,           -- NULL if unexecuted / unavailable
    patch_generated INTEGER DEFAULT 0,
    failure_class TEXT,
    source_artifact TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
"""

RUN_EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT,
    duration_seconds REAL,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, seq)
);
"""

METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_text TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id, metric_name)
);
"""

FAILURES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS failures (
    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    failure_class TEXT NOT NULL,
    error_message TEXT,
    traceback TEXT,
    is_infrastructure INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE (run_id)
);
"""

SUBMISSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS submissions (
    submission_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    archive_sha256 TEXT NOT NULL,
    eval_pass_rate REAL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_runs_candidate ON runs(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);",
    "CREATE INDEX IF NOT EXISTS idx_runs_success ON runs(success);",
    "CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_failures_class ON failures(failure_class);",
]


def init_schema(conn: sqlite3.Connection) -> None:
    """Initializes the database schema if tables do not exist."""
    conn.execute("PRAGMA foreign_keys = ON;")
    with conn:
        conn.execute(SCHEMA_VERSION_TABLE_SQL)
        conn.execute(TASKS_TABLE_SQL)
        conn.execute(CANDIDATES_TABLE_SQL)
        conn.execute(RUNS_TABLE_SQL)
        conn.execute(RUN_EVENTS_TABLE_SQL)
        conn.execute(METRICS_TABLE_SQL)
        conn.execute(FAILURES_TABLE_SQL)
        conn.execute(SUBMISSIONS_TABLE_SQL)

        for idx_sql in INDEXES_SQL:
            conn.execute(idx_sql)

        # Record schema version if not already present
        cur = conn.cursor()
        cur.execute("SELECT version FROM schema_version WHERE version = ?", (CURRENT_SCHEMA_VERSION,))
        if cur.fetchone() is None:
            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                (
                    CURRENT_SCHEMA_VERSION,
                    now_iso,
                    "Stage 9 initial schema: runs, run_events, tasks, candidates, metrics, failures, submissions",
                ),
            )
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION};")
