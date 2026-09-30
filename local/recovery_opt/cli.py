"""Command-Line Interface for Recovery Optimization Loop (Stage 35 Section 44).

Provides commands:
- `--candidate REC0/REC1/REC2/REC3`
- `--parent REC0`
- `--analyze`: inspect candidate policy, metrics, and manifest
- `--diff`: display policy diff against parent
- `--report`: display candidate report.md
- `--matrix`: display Pareto Cost/Benefit Frontier table
- `--verify`: verify candidate artifacts, frozen baselines, and loop safety
- `--mine-failures`: mine recovery failure patterns across evaluation sources
- `--cluster`: cluster recovery failure patterns deterministically and select highest-value cluster
- `--json`: machine-readable JSON output
- `--dry-run`: read-only execution without baseline mutation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from local.recovery_opt.clustering import cluster_recovery_failures, select_highest_value_recovery_cluster
from local.recovery_opt.diff import diff_recovery_policies, format_recovery_policy_diff_md
from local.recovery_opt.experiment import RecoveryExperimentManager
from local.recovery_opt.mining import RecoveryTraceMiner
from local.recovery_opt.models import RecoveryCandidateManifest, RecoveryPolicy
from local.recovery_opt.policy import build_rec0_baseline_policy, get_canonical_recovery_policy
from local.recovery_opt.reporting import generate_pareto_frontier_md


def run_recovery_cli(argv: Optional[List[str]] = None) -> int:
    """CLI driver for the Recovery Optimization Loop."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 35: Recovery Optimization Loop CLI"
    )
    parser.add_argument("--candidate", type=str, default=None, help="Candidate ID (e.g. REC0, REC1, REC2, REC3)")
    parser.add_argument("--parent", type=str, default="REC0", help="Parent candidate ID (default: REC0)")
    parser.add_argument("--recovery-dir", type=str, default="experiments/recovery", help="Base directory for recovery artifacts")
    parser.add_argument("--analyze", action="store_true", help="Inspect candidate policy and metrics")
    parser.add_argument("--diff", action="store_true", help="Display policy diff against parent")
    parser.add_argument("--report", action="store_true", help="Display human-readable report.md")
    parser.add_argument("--matrix", action="store_true", help="Display Pareto Cost/Benefit Frontier matrix")
    parser.add_argument("--verify", type=str, default=None, help="Verify candidate directory integrity")
    parser.add_argument("--mine-failures", action="store_true", help="Mine recovery failure patterns from evaluation sources")
    parser.add_argument("--cluster", action="store_true", help="Cluster mined recovery patterns and report highest-value cluster")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Read-only execution without baseline mutation")

    args = parser.parse_args(argv)
    manager = RecoveryExperimentManager(repo_root=Path.cwd())

    # 1. Verification mode
    if args.verify:
        vdir = Path(args.verify)
        cand_id = vdir.name if vdir.is_dir() else args.candidate or "REC0"
        ok, errs = manager.verify_candidate(cand_id)
        if ok:
            if args.json:
                print(json.dumps({"status": "PASS", "candidate_id": cand_id, "path": str(vdir)}, indent=2))
            else:
                print(f"[PASS] Recovery candidate '{cand_id}' artifacts and frozen baselines verified.")
            return 0
        else:
            if args.json:
                print(json.dumps({"status": "FAIL", "candidate_id": cand_id, "errors": errs}, indent=2))
            else:
                print(f"[FAIL] Verification failed for recovery candidate '{cand_id}':", file=sys.stderr)
                for e in errs:
                    print(f"  - {e}", file=sys.stderr)
            return 1

    # 2. Mine failures
    if args.mine_failures:
        miner = RecoveryTraceMiner(repo_root=Path.cwd())
        records = miner.mine_all_sources()
        if args.json:
            print(json.dumps([r.to_dict() for r in records], indent=2))
        else:
            print(f"Mined {len(records)} recovery-relevant failure records from evaluation sources.")
            for r in records[:10]:
                print(f"  - [{r.evidence_mode}] {r.task_id} ({r.failure_class}): {r.failure_signature[:60]}")
        return 0

    # 3. Cluster failures
    if args.cluster:
        miner = RecoveryTraceMiner(repo_root=Path.cwd())
        records = miner.mine_all_sources()
        clusters = cluster_recovery_failures(records)
        selected, status, rationale = select_highest_value_recovery_cluster(clusters, allow_fixture=True)
        if args.json:
            out = {
                "total_clusters": len(clusters),
                "selection_status": status.value,
                "rationale": rationale,
                "selected_cluster": selected.to_dict() if selected else None,
            }
            print(json.dumps(out, indent=2))
        else:
            print(f"Clustered {len(records)} records into {len(clusters)} deterministic recovery clusters.")
            print(f"Selection Status: {status.value}")
            print(f"Rationale: {rationale}")
            if selected:
                print(f"Selected Cluster: {selected.cluster_id} (Pattern: {selected.pattern_type})")
        return 0

    # 4. Diff mode
    if args.diff:
        cid = args.candidate or "REC1"
        cand_pol = get_canonical_recovery_policy(cid)
        parent_pol = get_canonical_recovery_policy(args.parent or "REC0")
        diff_md = format_recovery_policy_diff_md(parent_pol, cand_pol)
        if args.json:
            print(json.dumps(diff_recovery_policies(parent_pol, cand_pol), indent=2))
        else:
            print(diff_md)
        return 0

    # 5. Report mode
    if args.report:
        cid = args.candidate or "REC0"
        cdir = Path(args.recovery_dir) / cid
        rep_file = cdir / "report.md"
        if not rep_file.is_file():
            print(f"[ERROR] Report file not found: {rep_file}", file=sys.stderr)
            return 1
        print(rep_file.read_text(encoding="utf-8"))
        return 0

    # 6. Analyze mode
    if args.analyze:
        cid = args.candidate or "REC0"
        cdir = Path(args.recovery_dir) / cid
        if not cdir.exists():
            # Setup if not exists
            if not args.dry_run:
                manager.setup_canonical_candidates()
        pol_file = cdir / "policy.json"
        if pol_file.is_file():
            p_data = json.loads(pol_file.read_text(encoding="utf-8"))
        else:
            p_data = get_canonical_recovery_policy(cid).to_dict()

        if args.json:
            print(json.dumps({"candidate_id": cid, "policy": p_data}, indent=2))
        else:
            print(f"=== Recovery Candidate Analysis: {cid} ===")
            print(f"Variant: {p_data.get('variant')}")
            print(f"Early Detection: {p_data.get('early_detection_enabled')}")
            print(f"Loop Guard: {p_data.get('loop_guard_enabled')}")
            print(f"Alternate Path Routing: {p_data.get('alternate_path_routing_enabled')}")
            print(f"Retry Budgets: {p_data.get('retry_budgets')}")
        return 0

    # 7. Matrix mode
    if args.matrix:
        base_dir = Path(args.recovery_dir)
        cands_data: list[dict[str, Any]] = []
        if base_dir.exists():
            for cd in sorted(base_dir.iterdir()):
                if cd.is_dir() and (cd / "metrics.json").is_file():
                    try:
                        m_data = json.loads((cd / "metrics.json").read_text(encoding="utf-8"))
                        cands_data.append({
                            "candidate_id": cd.name,
                            "quality_metrics": m_data.get("quality_metrics", {}),
                            "cost_metrics": m_data.get("cost_metrics", {}),
                            "decision": m_data.get("decision", "UNKNOWN"),
                        })
                    except Exception:
                        pass
        if not cands_data:
            print("No recovery candidate metrics found.")
            return 0
        frontier_md = generate_pareto_frontier_md(cands_data)
        if args.json:
            print(json.dumps(cands_data, indent=2))
        else:
            print(frontier_md)
        return 0

    parser.print_help()
    return 0


def main() -> int:
    """Standard main entrypoint."""
    return run_recovery_cli()


if __name__ == "__main__":
    sys.exit(main())
