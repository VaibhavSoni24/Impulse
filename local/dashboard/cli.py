"""Command-line interface for the IMPULSE Failure Dashboard (Stage 30).

Usage:
    # Generate dashboard for candidate E0 on dev split from default DB:
    python scripts/generate_dashboard.py --candidate E0 --split dev

    # Generate dashboard directly from results file:
    python scripts/generate_dashboard.py --candidate E0 --split dev --results experiments/baseline/E0/results.jsonl

    # Verify generated dashboard artifacts:
    python scripts/generate_dashboard.py --verify --output-dir experiments/dashboard/E0/dev
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Optional

from benchmark.splits.hashing import compute_file_sha256
from local.dashboard.generator import DashboardGenerator
from local.dashboard.models import EvidenceMode
from local.dashboard.queries import (
    build_tasks_lookup,
    fetch_runs_from_db,
    load_runs_from_jsonl,
)
from local.evaluation.db import DEFAULT_DB_PATH, get_connection, init_database
from local.evaluation.ingestion import ingest_results


def verify_dashboard_artifacts(target_dir: Path) -> tuple[bool, list[str]]:
    """Verifies hashes and files in a generated dashboard directory."""
    errors: list[str] = []
    manifest_p = target_dir / "manifest.json"
    if not manifest_p.is_file():
        return False, [f"manifest.json missing in {target_dir}"]

    try:
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"Invalid manifest.json: {e}"]

    artifact_hashes = manifest.get("artifact_hashes", {})
    for fname, exp_hash in artifact_hashes.items():
        actual_name = fname.replace("_", ".")
        actual_file = target_dir / actual_name
        if not actual_file.is_file():
            errors.append(f"Required artifact {actual_name} missing")
            continue
        actual_hash = compute_file_sha256(actual_file)
        if actual_hash != exp_hash:
            errors.append(f"Hash mismatch for {actual_name}: expected {exp_hash[:8]}, got {actual_hash[:8]}")

    return len(errors) == 0, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m local.dashboard",
        description="IMPULSE Lightweight Failure Dashboard Generator (Stage 30)",
    )
    parser.add_argument(
        "--candidate",
        "-c",
        type=str,
        default="E0",
        help="Candidate identifier (e.g. 'E0', 'M0', 'M1', default: 'E0').",
    )
    parser.add_argument(
        "--split",
        "-s",
        type=str,
        default="dev",
        choices=["dev", "validation", "held_out", "all"],
        help="Benchmark split to report on (default: 'dev').",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite evaluation database (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--results",
        "-r",
        type=Path,
        default=None,
        help="Optional direct path to a results.jsonl file to ingest or analyze.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("experiments/dashboard"),
        help="Directory where generated dashboard reports will be saved.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["LIVE", "FIXTURE", "UNAVAILABLE", "INFRASTRUCTURE_ONLY"],
        help="Filter by specific evidence mode.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify manifest and hashes in existing dashboard directory instead of generating.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable report metadata to stdout.",
    )

    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parent.parent.parent

    # Action: Verify existing dashboard
    if args.verify:
        target_dir = args.output_dir
        if not (target_dir / "manifest.json").is_file():
            # Try subfolder
            cand_split_dir = target_dir / args.candidate / args.split.lower()
            if (cand_split_dir / "manifest.json").is_file():
                target_dir = cand_split_dir

        valid, errors = verify_dashboard_artifacts(target_dir)
        if valid:
            print("============================================================")
            print("IMPULSE DASHBOARD VERIFICATION")
            print("============================================================")
            print(f"Directory:       {target_dir}")
            print("Status:          VALID & VERIFIED")
            print("============================================================")
            return 0
        else:
            print("============================================================", file=sys.stderr)
            print("IMPULSE DASHBOARD VERIFICATION FAILED", file=sys.stderr)
            print("============================================================", file=sys.stderr)
            print(f"Directory:       {target_dir}", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    # Action: Generate dashboard
    tasks_lookup = build_tasks_lookup(
        splits_root=project_root / "benchmark" / "splits",
        split_version="v1",
        tasks_file=project_root / "data" / "competition" / "tasks.jsonl",
    )

    runs = []
    source_db_sha = ""

    # If results file explicitly passed:
    if args.results and args.results.is_file():
        runs = load_runs_from_jsonl(
            args.results,
            candidate_id=args.candidate,
            split_name=args.split,
            tasks_lookup=tasks_lookup,
        )
    else:
        # Connect to DB; initialize schema
        db_p = args.db
        init_database(db_p)

        # Check if DB has any runs; if completely empty, check if baseline E0 results exist to ingest
        conn_check = get_connection(db_p)
        try:
            cur = conn_check.cursor()
            cur.execute("SELECT COUNT(*) FROM runs;")
            total_db_runs = cur.fetchone()[0]
        except Exception:
            total_db_runs = 0
        finally:
            conn_check.close()

        if total_db_runs == 0:
            baseline_e0 = project_root / "experiments" / "baseline" / "E0" / "results.jsonl"
            if baseline_e0.is_file():
                conn_init = get_connection(db_p)
                try:
                    ingest_results(conn_init, baseline_e0, auto_populate_tasks=False)
                finally:
                    conn_init.close()

        conn = get_connection(db_p)
        try:
            runs = fetch_runs_from_db(
                conn=conn,
                candidate_id=args.candidate,
                split_name=args.split,
                split_version="v1",
                tasks_lookup=tasks_lookup,
            )
        finally:
            conn.close()

        if db_p.is_file():
            source_db_sha = compute_file_sha256(db_p)

    target_mode = EvidenceMode(args.mode) if args.mode else None

    generator = DashboardGenerator(
        repo_root=project_root,
        output_dir=args.output_dir,
        splits_root=project_root / "benchmark" / "splits",
        split_version="v1",
    )

    report, out_dir = generator.generate(
        candidate_id=args.candidate,
        split_name=args.split,
        runs=runs,
        target_evidence_mode=target_mode,
        source_db_sha256=source_db_sha,
    )

    if args.json:
        summary_data = {
            "candidate_id": report.candidate_id,
            "split_name": report.split_name,
            "evidence_mode": report.evidence_mode.value,
            "report_status": report.report_status.value,
            "overall_pass_rate": report.overall_pass_rate,
            "completed_runs": report.completed_run_count,
            "total_runs": report.total_runs_recorded,
            "output_dir": str(out_dir),
        }
        print(json.dumps(summary_data, indent=2))
    else:
        print("============================================================")
        print("IMPULSE FAILURE DASHBOARD REPORT GENERATED (STAGE 30)")
        print("============================================================")
        print(f"Candidate:         {report.candidate_id}")
        print(f"Split:             {report.split_name.upper()} ({report.split_version})")
        print(f"Evidence Mode:     {report.evidence_mode.value}")
        print(f"Report Status:     {report.report_status.value}")
        print(f"Total Runs:        {report.total_runs_recorded}")
        print(f"Completed Runs:    {report.completed_run_count}")
        rate_str = f"{round(report.overall_pass_rate * 100.0, 2)}%" if report.overall_pass_rate is not None else "N/A"
        print(f"Overall Pass Rate: {rate_str}")
        print(f"Output Directory:  {out_dir}")
        print("Artifacts:")
        print(f"  - Summary:       {out_dir / 'summary.md'}")
        print(f"  - Failures:      {out_dir / 'failures.jsonl'}")
        print(f"  - Metrics:       {out_dir / 'metrics.csv'}")
        print(f"  - Manifest:      {out_dir / 'manifest.json'}")
        print("============================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
