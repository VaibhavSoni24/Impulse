"""Command-line interface for the IMPULSE evaluation database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from local.evaluation.db import DEFAULT_DB_PATH, get_connection, init_database
from local.evaluation.ingestion import ingest_manifest, ingest_results, populate_tasks_from_files
from local.evaluation.queries import (
    get_candidate_summary,
    get_database_stats,
    list_candidates,
    list_runs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m local.evaluation",
        description="IMPULSE Evaluation Database: store, query, and analyze candidate experiment runs.",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database file (default: {DEFAULT_DB_PATH}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize the database schema.")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest experiment results or manifests.")
    ingest_parser.add_argument(
        "--results",
        "-r",
        dest="results_path",
        type=Path,
        required=True,
        help="Path to results.jsonl file to ingest.",
    )
    ingest_parser.add_argument(
        "--manifest",
        "-m",
        dest="manifest_path",
        type=Path,
        default=None,
        help="Optional path to companion manifest.json (auto-detected if omitted).",
    )
    ingest_parser.add_argument(
        "--no-auto-tasks",
        dest="auto_tasks",
        action="store_false",
        default=True,
        help="Skip auto-populating tasks catalog from dataset manifests.",
    )

    # stats
    stats_parser = subparsers.add_parser("stats", help="Display table row counts.")

    # summary
    summary_parser = subparsers.add_parser("summary", help="Display candidate performance summary.")
    summary_parser.add_argument(
        "--candidate",
        "-c",
        dest="candidate_id",
        type=str,
        default="E0",
        help="Candidate identifier (default: E0).",
    )

    # list-runs
    list_parser = subparsers.add_parser("list-runs", help="List runs in the database.")
    list_parser.add_argument(
        "--candidate",
        "-c",
        dest="candidate_id",
        type=str,
        default=None,
        help="Filter by candidate identifier.",
    )
    list_parser.add_argument(
        "--task",
        "-t",
        dest="task_id",
        type=str,
        default=None,
        help="Filter by task identifier.",
    )
    list_parser.add_argument(
        "--status",
        dest="status",
        type=str,
        default=None,
        help="Filter by execution status.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        path = init_database(args.db_path)
        print(f"Initialized IMPULSE evaluation database at: {path}")
        return 0

    conn = get_connection(args.db_path)
    try:
        # Ensure schema is ready
        init_database(args.db_path)

        if args.command == "ingest":
            count = ingest_results(
                conn=conn,
                results_path=args.results_path,
                manifest_path=args.manifest_path,
                auto_populate_tasks=args.auto_tasks,
            )
            print(f"Successfully ingested {count} run(s) from {args.results_path}")
            return 0

        elif args.command == "stats":
            stats = get_database_stats(conn)
            print("=" * 40)
            print("IMPULSE EVALUATION DATABASE STATS")
            print("=" * 40)
            for tbl, cnt in stats.items():
                print(f"  {tbl:16s}: {cnt}")
            print("=" * 40)
            return 0

        elif args.command == "summary":
            summary = get_candidate_summary(conn, args.candidate_id)
            print("=" * 50)
            print(f"EVALUATION SUMMARY: Candidate {args.candidate_id}")
            print("=" * 50)
            print(f"Total Runs:       {summary['total_runs']}")
            print(f"Resolved (Pass):  {summary['resolved_count']}")
            print(f"Failed:           {summary['failed_count']}")
            print(f"Unexecuted:       {summary['unexecuted_count']}")
            pr = summary['pass_rate']
            print(f"Pass Rate:        {pr if pr is not None else 'N/A (unexecuted)'}")
            tc = summary['avg_tool_calls']
            print(f"Avg Tool Calls:   {tc if tc is not None else 'N/A'}")
            print(f"Status Breakdown: {summary['status_breakdown']}")
            print(f"Failures:         {summary['failure_breakdown']}")
            print("=" * 50)
            return 0

        elif args.command == "list-runs":
            runs = list_runs(
                conn,
                candidate_id=args.candidate_id,
                task_id=args.task_id,
                status=args.status,
            )
            print(f"Found {len(runs)} run(s):")
            for r in runs:
                res_str = "RESOLVED" if r["success"] == 1 else ("FAILED" if r["success"] == 0 else "UNEXECUTED")
                print(
                    f"  [{r['run_id']}] {r['candidate_id']} | {r['task_id']} | "
                    f"{r['status']} | {res_str} | backend={r['execution_backend']}"
                )
            return 0

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
