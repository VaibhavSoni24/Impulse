"""IMPULSE Evaluation Database Package.

Provides SQLite persistence, schema management, ingestion, and querying
for candidate evaluation runs, tasks, metrics, and failures.
"""

from local.evaluation.db import DEFAULT_DB_PATH, get_connection, init_database
from local.evaluation.ingestion import (
    ensure_candidate,
    ensure_task,
    ingest_manifest,
    ingest_results,
    populate_tasks_from_files,
)
from local.evaluation.queries import (
    get_candidate_summary,
    get_database_stats,
    get_run,
    list_candidates,
    list_runs,
)
from local.evaluation.schema import CURRENT_SCHEMA_VERSION

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_DB_PATH",
    "ensure_candidate",
    "ensure_task",
    "get_candidate_summary",
    "get_connection",
    "get_database_stats",
    "get_run",
    "ingest_manifest",
    "ingest_results",
    "init_database",
    "list_candidates",
    "list_runs",
    "populate_tasks_from_files",
]
