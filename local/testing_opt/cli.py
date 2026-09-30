"""Command-Line Interface for the Testing Strategy Optimization Loop (Stage 34).

Provides:
- Baseline T0 initialization and inspection (--parent T0 --analyze)
- Candidate creation and policy diff computation (--diff)
- Candidate artifact verification (--verify)
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
from local.testing_opt.diff import compute_test_policy_diff, render_test_policy_diff_md
from local.testing_opt.experiment import TestingExperimentManager
from local.testing_opt.metrics import (
    build_test_quality_cost_frontier,
    render_test_quality_cost_frontier_md,
)
from local.testing_opt.models import (
    TestCandidateManifest,
    TestCostMetrics,
    TestEvidenceMetrics,
    TestHypothesis,
    TestPolicy,
)
from local.testing_opt.policy import build_t0_targeted_policy, get_canonical_testing_policy


def verify_testing_candidate_artifacts(candidate_dir: Path | str) -> Tuple[bool, List[str]]:
    """Verifies cryptographic integrity of a testing strategy candidate's stored artifacts."""
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


def run_testing_cli(argv: Optional[List[str]] = None) -> int:
    """CLI driver for the Testing Strategy Optimization Loop."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 34: Testing Strategy Optimization Loop CLI"
    )
    parser.add_argument("--candidate", type=str, default=None, help="Testing candidate ID (e.g. T0, T1, T2, T3)")
    parser.add_argument("--parent", type=str, default=None, help="Parent testing candidate ID")
    parser.add_argument("--variant", type=str, default=None, help="Testing strategy variant (T0, T1, T2, T3)")
    parser.add_argument("--testing-dir", type=str, default="experiments/testing", help="Base directory for testing artifacts")
    parser.add_argument("--analyze", action="store_true", help="Inspect and analyze candidate or baseline")
    parser.add_argument("--diff", action="store_true", help="Display policy diff against parent")
    parser.add_argument("--report", action="store_true", help="Display human-readable report.md")
    parser.add_argument("--matrix", action="store_true", help="Display Quality/Cost Pareto frontier matrix")
    parser.add_argument("--verify", type=str, default=None, help="Verify artifact hashes of candidate directory")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)
    manager = TestingExperimentManager(testing_base_dir=args.testing_dir)

    # 1. Verification mode
    if args.verify:
        vdir = Path(args.verify)
        is_ok, errs = verify_testing_candidate_artifacts(vdir)
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
        cid = args.candidate or args.parent or "T0"
        if cid == "T0":
            t0_man = manager.ensure_t0_baseline()
            t0_pol_file = Path(args.testing_dir) / "T0" / "policy.json"
            pol_data = json.loads(t0_pol_file.read_text(encoding="utf-8"))
            if args.json:
                print(json.dumps({"manifest": t0_man.to_dict(), "policy": pol_data}, indent=2))
            else:
                print("==================================================")
                print(f"Testing Strategy Baseline Analysis: {t0_man.candidate_id} ({t0_man.strategy_variant})")
                print("==================================================")
                print(f"Policy Hash: {t0_man.test_policy_hash}")
                print(f"Targeted Enabled: {pol_data.get('targeted_enabled')}")
                print(f"Adjacent Enabled: {pol_data.get('adjacent_enabled')}")
                print(f"Subsystem Enabled: {pol_data.get('subsystem_enabled')}")
                print(f"Full Suite Enabled: {pol_data.get('full_suite_enabled')}")
                print(f"Adaptive Enabled: {pol_data.get('adaptive_enabled')}")
            return 0

    # 3. Diff mode
    if args.diff:
        if not args.candidate:
            print("[ERROR] --candidate required when viewing policy diff.", file=sys.stderr)
            return 1
        cand_dir = Path(args.testing_dir) / args.candidate
        pol_file = cand_dir / "policy.json"
        if not pol_file.is_file():
            print(f"[ERROR] Policy file not found: {pol_file}", file=sys.stderr)
            return 1
        cand_pol = TestPolicy.from_dict(json.loads(pol_file.read_text(encoding="utf-8")))
        parent_id = args.parent or "T0"
        parent_file = Path(args.testing_dir) / parent_id / "policy.json"
        if not parent_file.is_file():
            parent_pol = build_t0_targeted_policy()
        else:
            parent_pol = TestPolicy.from_dict(json.loads(parent_file.read_text(encoding="utf-8")))
        pdiff = compute_test_policy_diff(parent_pol, cand_pol)
        print(render_test_policy_diff_md(pdiff))
        return 0

    # 4. Report mode
    if args.report:
        cid = args.candidate or args.parent or "T0"
        rep_file = Path(args.testing_dir) / cid / "report.md"
        if not rep_file.is_file():
            print(f"[ERROR] Report file not found: {rep_file}", file=sys.stderr)
            return 1
        print(rep_file.read_text(encoding="utf-8"))
        return 0

    # 5. Frontier matrix mode
    if args.matrix:
        base_path = Path(args.testing_dir)
        candidates_data: List[Dict[str, Any]] = []
        if base_path.exists():
            for cdir in sorted(base_path.iterdir()):
                if cdir.is_dir() and (cdir / "metrics.json").is_file():
                    try:
                        m_data = json.loads((cdir / "metrics.json").read_text(encoding="utf-8"))
                        q = TestEvidenceMetrics.from_dict(m_data["quality"])
                        cost = TestCostMetrics.from_dict(m_data["cost"])
                        candidates_data.append({
                            "candidate_id": cdir.name,
                            "strategy_id": cdir.name,
                            "quality": q,
                            "cost": cost,
                        })
                    except Exception:
                        pass
        if not candidates_data:
            print("No completed testing candidate metrics found.")
            return 0
        frontier_rows = build_test_quality_cost_frontier(candidates_data)
        if args.json:
            print(json.dumps(frontier_rows, indent=2))
        else:
            print("==================================================")
            print("Testing Quality vs Cost Frontier Matrix")
            print("==================================================")
            print(render_test_quality_cost_frontier_md(frontier_rows))
        return 0

    return 0


def main() -> int:
    """Standard main entrypoint."""
    return run_testing_cli()


if __name__ == "__main__":
    sys.exit(main())
