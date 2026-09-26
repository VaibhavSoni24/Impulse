"""Comprehensive tests for the IMPULSE evaluation database (Stage 9)."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from local.evaluation.db import (
    CURRENT_SCHEMA_VERSION,
    get_connection,
    get_schema_version,
    init_database,
)
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


class TestEvaluationDatabase(unittest.TestCase):
    """Test suite validating database schema, foreign keys, ingestion, and querying."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_eval.db"
        init_database(self.db_path)
        self.conn = get_connection(self.db_path)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_schema_initialization_and_version(self) -> None:
        """Verifies all required tables and schema versioning are established."""
        self.assertEqual(get_schema_version(self.conn), CURRENT_SCHEMA_VERSION)

        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}

        required_tables = {
            "schema_version",
            "tasks",
            "candidates",
            "runs",
            "run_events",
            "metrics",
            "failures",
            "submissions",
        }
        self.assertTrue(
            required_tables.issubset(tables),
            f"Missing required tables. Found: {tables}",
        )

    def test_foreign_keys_enforced(self) -> None:
        """Verifies foreign key constraints are strictly enforced."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA foreign_keys;")
        self.assertEqual(cur.fetchone()[0], 1, "Foreign keys must be enabled")

        # Attempt inserting a run with non-existent candidate and task
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO runs (
                    run_id, candidate_id, task_id, model_id, execution_backend,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "run-fk-test",
                    "non-existent-candidate",
                    "non-existent-task",
                    "gemma-4",
                    "unavailable",
                    "test",
                    "2026-09-26T00:00:00Z",
                ),
            )

    def test_stage8_e0_results_ingestion(self) -> None:
        """Verifies ingestion of Stage 8 baseline E0 manifest and results."""
        results_file = Path("experiments/baseline/E0/results.jsonl")
        manifest_file = Path("experiments/baseline/E0/manifest.json")

        self.assertTrue(results_file.exists(), f"Missing {results_file}")
        self.assertTrue(manifest_file.exists(), f"Missing {manifest_file}")

        count = ingest_results(
            conn=self.conn,
            results_path=results_file,
            manifest_path=manifest_file,
            auto_populate_tasks=True,
        )

        self.assertEqual(count, 5, "Must ingest exactly 5 smoke tasks for E0")

        # Verify candidate metadata
        candidates = list_candidates(self.conn)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["candidate_id"], "E0")
        self.assertEqual(candidates[0]["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(candidates[0]["git_tag"], "E0-baseline")

        # Verify runs
        runs = list_runs(self.conn, candidate_id="E0")
        self.assertEqual(len(runs), 5)

        expected_task_ids = {
            "fastapi_14786",
            "rich_4070",
            "fastapi_14479",
            "requests_6629",
            "requests_7505",
        }
        imported_task_ids = {r["task_id"] for r in runs}
        self.assertEqual(imported_task_ids, expected_task_ids)

        for r in runs:
            self.assertEqual(r["status"], "execution_unavailable_local_host")
            self.assertEqual(r["execution_backend"], "local-unavailable")
            self.assertEqual(r["failure_class"], "infrastructure_unavailable")

    def test_null_metrics_preservation_and_zero_fabrication(self) -> None:
        """Verifies unexecuted metrics remain NULL in database and queries."""
        results_file = Path("experiments/baseline/E0/results.jsonl")
        ingest_results(self.conn, results_file)

        runs = list_runs(self.conn, candidate_id="E0")
        for r in runs:
            self.assertIsNone(r["success"], "success must be NULL for unexecuted runs")
            self.assertIsNone(r["tool_calls"], "tool_calls must be NULL, not 0")
            self.assertIsNone(r["turns"], "turns must be NULL, not 0")
            self.assertIsNone(r["files_read"])
            self.assertIsNone(r["files_changed"])
            self.assertIsNone(r["diff_lines"])
            self.assertIsNone(r["diff_bytes"])

        # Check candidate summary strictly avoids reporting a 0% pass rate
        summary = get_candidate_summary(self.conn, "E0")
        self.assertEqual(summary["total_runs"], 5)
        self.assertEqual(summary["resolved_count"], 0)
        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["unexecuted_count"], 5)
        self.assertIsNone(summary["pass_rate"], "pass_rate must be None when no runs were executed")
        self.assertIsNone(summary["avg_tool_calls"], "avg_tool_calls must be None")
        self.assertIsNone(summary["avg_turns"], "avg_turns must be None")

    def test_ingestion_idempotency(self) -> None:
        """Verifies re-ingesting results does not duplicate or alter data."""
        results_file = Path("experiments/baseline/E0/results.jsonl")

        ingest_results(self.conn, results_file)
        stats1 = get_database_stats(self.conn)

        # Re-ingest
        ingest_results(self.conn, results_file)
        stats2 = get_database_stats(self.conn)

        self.assertEqual(stats1, stats2, "Database stats must be identical after re-ingestion")
        self.assertEqual(stats1["runs"], 5)

    def test_multi_candidate_coexistence(self) -> None:
        """Verifies a second candidate can coexist without interfering with E0."""
        # 1. Ingest E0
        ingest_results(self.conn, "experiments/baseline/E0/results.jsonl")

        # 2. Register candidate E1
        with self.conn:
            ensure_candidate(
                conn=self.conn,
                candidate_id="E1",
                model_id="gemma-4-31b-it-qat-w4a16-ct",
                description="Prompt engineering candidate E1",
            )
            ensure_task(self.conn, task_id="fastapi_14786")

            # Insert an executed run for E1
            self.conn.execute(
                """
                INSERT INTO runs (
                    run_id, candidate_id, task_id, model_id, execution_backend,
                    status, success, tool_calls, turns, elapsed_seconds, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "run-e1-001",
                    "E1",
                    "fastapi_14786",
                    "gemma-4-31b-it-qat-w4a16-ct",
                    "mock-evaluator",
                    "completed",
                    1,
                    8,
                    4,
                    45.2,
                    "2026-09-26T12:00:00Z",
                ),
            )

        # 3. Check summaries
        summary_e0 = get_candidate_summary(self.conn, "E0")
        summary_e1 = get_candidate_summary(self.conn, "E1")

        self.assertEqual(summary_e0["total_runs"], 5)
        self.assertIsNone(summary_e0["pass_rate"])

        self.assertEqual(summary_e1["total_runs"], 1)
        self.assertEqual(summary_e1["resolved_count"], 1)
        self.assertEqual(summary_e1["pass_rate"], 1.0)
        self.assertEqual(summary_e1["avg_tool_calls"], 8.0)
        self.assertEqual(summary_e1["avg_turns"], 4.0)

    def test_failure_records_and_infrastructure_distinction(self) -> None:
        """Verifies infrastructure failures are distinguished from task logic failures."""
        ingest_results(self.conn, "experiments/baseline/E0/results.jsonl")

        cur = self.conn.cursor()
        cur.execute("SELECT run_id, failure_class, is_infrastructure FROM failures;")
        failure_rows = cur.fetchall()

        self.assertEqual(len(failure_rows), 5)
        for row in failure_rows:
            self.assertEqual(row["failure_class"], "infrastructure_unavailable")
            self.assertEqual(row["is_infrastructure"], 1)

    def test_no_secret_patch_leakage(self) -> None:
        """Verifies no test_patch or private task patch data is stored in the database."""
        ingest_results(self.conn, "experiments/baseline/E0/results.jsonl")

        cur = self.conn.cursor()
        for tbl in ["tasks", "runs", "candidates", "failures"]:
            cur.execute(f"PRAGMA table_info({tbl});")
            col_names = [r[1] for r in cur.fetchall()]
            self.assertNotIn("test_patch", col_names)
            self.assertNotIn("golden_patch", col_names)
            self.assertNotIn("solution", col_names)

    def test_cli_commands(self) -> None:
        """Verifies CLI subcommands (init, ingest, stats, summary, list-runs) run successfully."""
        from local.evaluation.cli import main

        cli_db = Path(self.temp_dir.name) / "cli_test.db"
        # 1. init
        ret = main(["--db", str(cli_db), "init"])
        self.assertEqual(ret, 0)
        self.assertTrue(cli_db.exists())

        # 2. ingest
        ret = main([
            "--db", str(cli_db),
            "ingest",
            "--results", "experiments/baseline/E0/results.jsonl",
            "--manifest", "experiments/baseline/E0/manifest.json",
        ])
        self.assertEqual(ret, 0)

        # 3. stats
        ret = main(["--db", str(cli_db), "stats"])
        self.assertEqual(ret, 0)

        # 4. summary
        ret = main(["--db", str(cli_db), "summary", "--candidate", "E0"])
        self.assertEqual(ret, 0)

        # 5. list-runs
        ret = main(["--db", str(cli_db), "list-runs", "--candidate", "E0"])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()

