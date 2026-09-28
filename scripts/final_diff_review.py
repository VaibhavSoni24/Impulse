#!/usr/bin/env python3
"""CLI utility for Final Diff Discipline and Repository Hygiene (Stage 27).

Runs the deterministic pre-release review sequence, detects development artifacts,
verifies frozen invariant baselines, audits untracked files, and produces
reproducible hygiene reports.

Usage:
    python scripts/final_diff_review.py [--repo-root PATH] [--clean] [--check-only] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.diff_discipline.pipeline import FinalDiffReviewPipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IMPULSE Final Diff Discipline & Repository Hygiene Reviewer"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Root directory of the IMPULSE repository (defaults to project root)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Conservatively remove high-confidence untracked scratch artifacts",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all tracked files in addition to changed and untracked files",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit with code 1 if repository is unclean or actionable violations exist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report formatted as JSON",
    )

    args = parser.parse_args()

    pipeline = FinalDiffReviewPipeline(repo_root=args.repo_root)
    report = pipeline.run_review(
        auto_clean=args.clean,
        scan_all_tracked=args.all,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(pipeline.format_report(report))

    if args.check_only and not report.is_clean:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
