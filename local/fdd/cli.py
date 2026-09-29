"""Command-Line Interface for the Failure-Driven Development (FDD) Loop (Stage 31 Section 17).

Provides composable, deterministic CLI operations:
- Failure analysis & normalization (--analyze)
- Failure clustering (--cluster)
- Deterministic cluster selection (--select)
- Artifact verification (--verify)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.hashing import compute_file_sha256
from local.dashboard.queries import build_tasks_lookup, fetch_runs_from_db
from local.evaluation.db import get_connection
from local.fdd.clustering import cluster_failures
from local.fdd.models import FDDExperimentManifest, FDDState, PromotionDecision
from local.fdd.normalization import (
    normalize_failures_from_jsonl,
    normalize_failures_from_summaries,
)
from local.fdd.prioritization import (
    STATUS_NO_ACTIONABLE,
    STATUS_NO_ACTIONABLE_LIVE,
    STATUS_SELECTED,
    select_highest_value_cluster,
)


def verify_fdd_artifacts(experiment_dir: Path | str) -> Tuple[bool, List[str]]:
    """Verifies cryptographic integrity of an FDD experiment artifact directory."""
    exp_p = Path(experiment_dir)
    errors: List[str] = []

    man_p = exp_p / "manifest.json"
    if not man_p.is_file():
        return False, [f"manifest.json missing in {exp_p}"]

    try:
        with open(man_p, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return False, [f"Failed to parse manifest.json: {e}"]

    # Required files
    for fname in ["intervention.json", "cluster.json", "result.json", "report.md"]:
        fpath = exp_p / fname
        if not fpath.is_file():
            errors.append(f"Required artifact {fname} missing in {exp_p}")

    # Verify hashes
    artifact_hashes = manifest.get("artifact_hashes", {})
    for fname, exp_hash in artifact_hashes.items():
        fpath = exp_p / fname
        if not fpath.is_file():
            continue
        actual_hash = compute_file_sha256(fpath)
        if actual_hash != exp_hash:
            errors.append(f"Hash mismatch for {fname}: expected {exp_hash[:8]}, got {actual_hash[:8]}")

    return len(errors) == 0, errors


def run_fdd_cli(argv: Optional[List[str]] = None) -> int:
    """Entry point for the run_fdd command line tool."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Failure-Driven Development (FDD) Loop (Stage 31)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--candidate", type=str, default="E0", help="Baseline candidate identifier (default: E0)")
    parser.add_argument("--split", type=str, default="dev", help="Split name to analyze (default: dev)")
    parser.add_argument("--db-path", type=str, default="experiments/evaluation.db", help="SQLite evaluation database path")
    parser.add_argument("--results", type=str, default=None, help="Optional direct path to results.jsonl")
    parser.add_argument("--analyze", action="store_true", help="Analyze and summarize failure records without modifications")
    parser.add_argument("--cluster", action="store_true", help="Deterministically cluster failures and output summary")
    parser.add_argument("--select", action="store_true", help="Select highest-value failure cluster using prioritization policy")
    parser.add_argument("--allow-fixtures", action="store_true", help="Allow fixture-mode failures in cluster selection (default: live only)")
    parser.add_argument("--verify", type=str, default=None, help="Verify integrity of an experiment directory")
    parser.add_argument("--dry-run", action="store_true", help="Execute without writing candidate or experiment changes")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args(argv)

    # 1. Verification mode
    if args.verify:
        v_path = Path(args.verify)
        ok, errors = verify_fdd_artifacts(v_path)
        if ok:
            print(f"[OK] FDD experiment directory verified successfully: {v_path}")
            return 0
        else:
            print(f"[ERROR] Verification failed for {v_path}:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    # Load records
    db_p = Path(args.db_path)
    records = []
    if args.results and Path(args.results).is_file():
        records = normalize_failures_from_jsonl(args.results)
    elif db_p.is_file():
        conn = get_connection(db_p)
        try:
            tasks_lookup = build_tasks_lookup()
            runs = fetch_runs_from_db(conn, args.candidate, split_name=args.split, tasks_lookup=tasks_lookup)
            records = normalize_failures_from_summaries(runs, source_ref=f"db:{args.candidate}")
        finally:
            conn.close()
    else:
        fallback_jsonl = Path(f"experiments/baseline/{args.candidate}/results.jsonl")
        if fallback_jsonl.is_file():
            records = normalize_failures_from_jsonl(fallback_jsonl)

    # 2. Analyze mode
    if args.analyze or (not args.cluster and not args.select):
        actionable_count = len([r for r in records if r.is_actionable])
        infra_count = len([r for r in records if not r.is_actionable])
        modes = sorted(list({r.evidence_mode for r in records}))

        if args.json:
            print(json.dumps({
                "candidate": args.candidate,
                "split": args.split,
                "total_records": len(records),
                "actionable_records": actionable_count,
                "infrastructure_records": infra_count,
                "evidence_modes": modes,
            }, indent=2))
        else:
            print(f"==================================================")
            print(f"FDD Analysis for Candidate: {args.candidate} (Split: {args.split})")
            print(f"==================================================")
            print(f"Total Records: {len(records)}")
            print(f"Actionable Failures: {actionable_count}")
            print(f"Infrastructure / Unavailable Runs: {infra_count}")
            print(f"Evidence Modes Present: {', '.join(modes) if modes else 'NONE'}")
            if actionable_count == 0:
                print("\n[NOTE] No actionable live failures found. Local host environment has no live completed Gemma 4 inference.")

        if not args.cluster and not args.select:
            return 0

    # 3. Cluster mode
    clusters = cluster_failures(records)
    if args.cluster and not args.select:
        if args.json:
            print(json.dumps([c.to_dict() for c in clusters], indent=2))
        else:
            print(f"\nDiscovered {len(clusters)} Failure Clusters:")
            for idx, c in enumerate(clusters, start=1):
                status_str = "ACTIONABLE" if c.is_actionable else "INFRASTRUCTURE/NON-ACTIONABLE"
                print(f"  [{idx}] {c.cluster_id}: {c.failure_category} ({c.failure_stage}) | "
                      f"Runs: {c.affected_runs_count}, Tasks: {c.unique_tasks_count}, "
                      f"Eligible: {c.eligible_completed_run_count} [{status_str}]")
        return 0

    # 4. Select mode
    if args.select:
        best_cluster, status = select_highest_value_cluster(
            clusters,
            require_live=not args.allow_fixtures,
        )

        if args.json:
            print(json.dumps({
                "selection_status": status,
                "selected_cluster": best_cluster.to_dict() if best_cluster else None,
            }, indent=2))
        else:
            print(f"\nCluster Selection Result:")
            print(f"Selection Status: {status}")
            if best_cluster:
                print(f"Selected Cluster ID: {best_cluster.cluster_id}")
                print(f"Target Failure Mode: {best_cluster.failure_category}")
                print(f"Eligible Completed Runs: {best_cluster.eligible_completed_run_count}")
                print(f"Unique Tasks Affected: {best_cluster.unique_tasks_count}")
            else:
                print("Selected Cluster: None")
                if status == STATUS_NO_ACTIONABLE_LIVE:
                    print("Reason: No eligible completed live failure runs found in candidate evaluation records.")
                    print("Stage 31 preserves strict evidence: infrastructure limits are not reinterpreted as cognitive failures.")

        return 0

    return 0


def main() -> int:
    """Standard main entrypoint."""
    return run_fdd_cli()


if __name__ == "__main__":
    sys.exit(main())
