"""Command-Line Interface for the Prompt Optimization Loop (Stage 32 Section 26).

Provides:
- Baseline P0 initialization and analysis (--parent P0 --analyze)
- Candidate creation and diff computation (--create)
- Candidate artifact verification (--verify)
- Diff visualization (--diff)
- Report inspection (--report)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.hashing import compute_file_sha256
from local.prompt_opt.baseline import establish_p0_baseline
from local.prompt_opt.diff import compute_prompt_diff, detect_prompt_bloat, render_prompt_diff_md
from local.prompt_opt.experiment import PromptExperimentManager
from local.prompt_opt.models import PromptCandidateManifest, PromptHypothesis


def verify_prompt_candidate_artifacts(candidate_dir: Path | str) -> Tuple[bool, List[str]]:
    """Verifies cryptographic integrity of a prompt candidate's stored artifacts."""
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
    if not (cdir / "root.md").is_file():
        errors.append(f"Required prompt file root.md missing in {cdir}")
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
            errors.append(f"Hash mismatch for {fname}: expected {exp_hash[:8]}, got {actual_hash[:8]}")

    return len(errors) == 0, errors


def run_prompt_cli(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint for prompt optimization operations."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Prompt Optimization Loop (Stage 32)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--parent", type=str, default="P0", help="Parent prompt candidate ID (default: P0)")
    parser.add_argument("--candidate", type=str, default=None, help="Candidate prompt ID (e.g., P1, P2)")
    parser.add_argument("--prompts-dir", type=str, default="experiments/prompts", help="Directory storing prompt candidates")
    parser.add_argument("--analyze", action="store_true", help="Analyze parent prompt baseline and bloat heuristics")
    parser.add_argument("--diff", action="store_true", help="Show prompt diff against parent")
    parser.add_argument("--report", action="store_true", help="Display candidate audit report")
    parser.add_argument("--verify", type=str, default=None, help="Verify candidate artifact directory")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)

    # 1. Verification mode
    if args.verify:
        target = Path(args.verify)
        ok, errors = verify_prompt_candidate_artifacts(target)
        if ok:
            print(f"[OK] Prompt candidate verified: {target}")
            return 0
        else:
            print(f"[ERROR] Verification failed for {target}:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1

    mgr = PromptExperimentManager(prompts_base_dir=args.prompts_dir)

    # 2. Analyze mode
    if args.analyze or (not args.diff and not args.report and not args.candidate):
        p0_man = mgr.ensure_p0_baseline()
        p0_file = Path(p0_man.prompt_path)
        content = p0_file.read_text(encoding="utf-8")
        bloat = detect_prompt_bloat(content)

        if args.json:
            print(json.dumps({
                "candidate_id": p0_man.candidate_id,
                "prompt_sha256": p0_man.prompt_sha256,
                "bloat_detected": bloat.is_bloated,
                "diagnostics": bloat.diagnostics,
            }, indent=2))
        else:
            print(f"==================================================")
            print(f"Prompt Optimization Baseline Analysis: {p0_man.candidate_id}")
            print(f"==================================================")
            print(f"Prompt SHA-256: {p0_man.prompt_sha256}")
            print(f"Length: {len(content)} chars, {len(content.splitlines())} lines")
            print(f"Bloat Diagnostics: {len(bloat.diagnostics)} issue(s) detected")
            for d in bloat.diagnostics:
                print(f"  - {d}")
        return 0

    # 3. Diff mode
    if args.diff:
        if not args.candidate:
            print("[ERROR] --candidate required when viewing prompt diff.", file=sys.stderr)
            return 1
        cand_dir = Path(args.prompts_dir) / args.candidate
        diff_file = cand_dir / "prompt_diff.md"
        if not diff_file.is_file():
            print(f"[ERROR] Diff file not found: {diff_file}", file=sys.stderr)
            return 1
        print(diff_file.read_text(encoding="utf-8"))
        return 0

    # 4. Report mode
    if args.report:
        cid = args.candidate or args.parent
        rep_file = Path(args.prompts_dir) / cid / "report.md"
        if not rep_file.is_file():
            print(f"[ERROR] Report file not found: {rep_file}", file=sys.stderr)
            return 1
        print(rep_file.read_text(encoding="utf-8"))
        return 0

    return 0


def main() -> int:
    """Standard main entrypoint."""
    return run_prompt_cli()


if __name__ == "__main__":
    sys.exit(main())
