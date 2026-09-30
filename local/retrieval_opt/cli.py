"""Command-Line Interface for the Retrieval Optimization Loop (Stage 33).

Provides:
- Baseline R0 initialization and inspection (--parent R0 --analyze)
- Candidate creation and policy diff computation (--create)
- Candidate artifact verification (--verify)
- Policy diff visualization (--diff)
- Experiment report viewing (--report)
- Frontier comparison matrix (--matrix)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.hashing import compute_file_sha256
from local.retrieval_opt.diff import compute_retrieval_policy_diff, render_retrieval_policy_diff_md
from local.retrieval_opt.experiment import RetrievalExperimentManager
from local.retrieval_opt.metrics import (
    build_quality_cost_frontier,
    render_quality_cost_frontier_md,
)
from local.retrieval_opt.models import (
    RetrievalCandidateManifest,
    RetrievalCostMetrics,
    RetrievalHypothesis,
    RetrievalPolicy,
    RetrievalQualityMetrics,
)
from local.retrieval_opt.policy import get_canonical_policy


def verify_retrieval_candidate_artifacts(candidate_dir: Path | str) -> Tuple[bool, List[str]]:
    """Verifies cryptographic integrity of a retrieval candidate's stored artifacts."""
    cdir = Path(candidate_dir)
    errors: List[str] = []

    man_path = cdir / "manifest.json"
    if not man_path.is_file():
        return False, [f"manifest.json missing in {cdir}"]

    try:
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"Failed to parse manifest.json: {e}"]

    # Required files
    if not (cdir / "policy.json").is_file():
        errors.append(f"Required policy file policy.json missing in {cdir}")
    if not (cdir / "report.md").is_file():
        errors.append(f"Required report file report.md missing in {cdir}")

    # Check hashes
    artifact_hashes = manifest.get("artifact_hashes", {})
    for fname, exp_hash in artifact_hashes.items():
        fpath = cdir / fname
        if not fpath.is_file():
            errors.append(f"Artifact {fname} specified in manifest but missing on disk.")
            continue
        actual_hash = compute_file_sha256(fpath)
        if actual_hash != exp_hash:
            errors.append(f"Hash mismatch for {fname}: manifest {exp_hash} != disk {actual_hash}")

    return len(errors) == 0, errors


def run_retrieval_cli(argv: Optional[List[str]] = None) -> int:
    """CLI driver for the Retrieval Optimization Loop."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 33: Retrieval Optimization Loop CLI"
    )
    parser.add_argument("--candidate", type=str, default=None, help="Retrieval candidate ID (e.g. R0, R1)")
    parser.add_argument("--parent", type=str, default=None, help="Parent retrieval candidate ID")
    parser.add_argument("--variant", type=str, default=None, help="Retrieval variant (R0, R1, R2, R3, R4)")
    parser.add_argument("--retrieval-dir", type=str, default="experiments/retrieval", help="Base directory for retrieval artifacts")
    parser.add_argument("--analyze", action="store_true", help="Inspect and analyze candidate or baseline")
    parser.add_argument("--diff", action="store_true", help="Display policy diff against parent")
    parser.add_argument("--report", action="store_true", help="Display human-readable report.md")
    parser.add_argument("--matrix", action="store_true", help="Display Quality/Cost Pareto frontier matrix")
    parser.add_argument("--verify", type=str, default=None, help="Verify artifact hashes of candidate directory")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)
    manager = RetrievalExperimentManager(retrieval_base_dir=args.retrieval_dir)

    # 1. Verification mode
    if args.verify:
        vdir = Path(args.verify)
        is_ok, errs = verify_retrieval_candidate_artifacts(vdir)
        if is_ok:
            if args.json:
                print(json.dumps({"status": "PASS", "path": str(vdir)}, indent=2))
            else:
                print(f"[PASS] All artifacts in {vdir} match manifest cryptographic hashes.")
            return 0
        else:
            if args.json:
                print(json.dumps({"status": "FAIL", "path": str(vdir), "errors": errs}, indent=2))
            else:
                print(f"[FAIL] Cryptographic integrity check failed for {vdir}:", file=sys.stderr)
                for err in errs:
                    print(f"  - {err}", file=sys.stderr)
            return 1

    # 2. Baseline or candidate analysis
    if args.analyze:
        cid = args.candidate or args.parent or "R0"
        if cid == "R0":
            r0_man = manager.ensure_r0_baseline()
            r0_pol_file = Path(args.retrieval_dir) / "R0" / "policy.json"
            pol_data = json.loads(r0_pol_file.read_text(encoding="utf-8"))
            if args.json:
                print(json.dumps({"manifest": r0_man.to_dict(), "policy": pol_data}, indent=2))
            else:
                print("==================================================")
                print(f"Retrieval Baseline Analysis: {r0_man.candidate_id} ({r0_man.retrieval_variant})")
                print("==================================================")
                print(f"Policy Hash: {r0_man.retrieval_policy_hash}")
                print(f"Semantic Search: {'Enabled' if pol_data.get('semantic_retrieval_enabled') else 'Disabled'}")
                print(f"Neighbors: {'Enabled' if pol_data.get('neighbor_retrieval_enabled') else 'Disabled'}")
                print(f"Subgraph: {'Enabled' if pol_data.get('subgraph_retrieval_enabled') else 'Disabled'}")
                print(f"Dynamic Depth: {'Enabled' if pol_data.get('dynamic_depth_enabled') else 'Disabled'}")
            return 0

    # 3. Diff mode
    if args.diff:
        if not args.candidate:
            print("[ERROR] --candidate required when viewing policy diff.", file=sys.stderr)
            return 1
        cand_dir = Path(args.retrieval_dir) / args.candidate
        pol_file = cand_dir / "policy.json"
        if not pol_file.is_file():
            print(f"[ERROR] Policy file not found: {pol_file}", file=sys.stderr)
            return 1
        cand_pol = RetrievalPolicy.from_dict(json.loads(pol_file.read_text(encoding="utf-8")))
        parent_id = args.parent or "R0"
        parent_file = Path(args.retrieval_dir) / parent_id / "policy.json"
        if not parent_file.is_file():
            parent_pol = build_r0_baseline_policy()
        else:
            parent_pol = RetrievalPolicy.from_dict(json.loads(parent_file.read_text(encoding="utf-8")))
        pdiff = compute_retrieval_policy_diff(parent_pol, cand_pol)
        print(render_retrieval_policy_diff_md(pdiff))
        return 0

    # 4. Report mode
    if args.report:
        cid = args.candidate or args.parent or "R0"
        rep_file = Path(args.retrieval_dir) / cid / "report.md"
        if not rep_file.is_file():
            print(f"[ERROR] Report file not found: {rep_file}", file=sys.stderr)
            return 1
        print(rep_file.read_text(encoding="utf-8"))
        return 0

    # 5. Frontier matrix mode
    if args.matrix:
        base_path = Path(args.retrieval_dir)
        candidates_data: List[Dict[str, Any]] = []
        if base_path.exists():
            for cdir in sorted(base_path.iterdir()):
                if cdir.is_dir() and (cdir / "metrics.json").is_file():
                    try:
                        m_data = json.loads((cdir / "metrics.json").read_text(encoding="utf-8"))
                        q = RetrievalQualityMetrics.from_dict(m_data["quality"])
                        cost = RetrievalCostMetrics.from_dict(m_data["cost"])
                        candidates_data.append({
                            "candidate_id": cdir.name,
                            "variant": cdir.name,
                            "quality": q,
                            "cost": cost,
                        })
                    except Exception:
                        pass
        if not candidates_data:
            print("No completed retrieval candidate metrics found.")
            return 0
        frontier_rows = build_quality_cost_frontier(candidates_data)
        if args.json:
            print(json.dumps(frontier_rows, indent=2))
        else:
            print("==================================================")
            print("Retrieval Quality vs Cost Frontier Matrix")
            print("==================================================")
            print(render_quality_cost_frontier_md(frontier_rows))
        return 0

    return 0


def main() -> int:
    """Standard main entrypoint."""
    return run_retrieval_cli()


if __name__ == "__main__":
    sys.exit(main())
