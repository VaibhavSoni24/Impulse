#!/usr/bin/env python3
"""CLI Utility for Deterministic Submission Packaging (Stage 48).

Packages an explicitly selected IMPULSE agent candidate directory into a
deterministic, reproducible competition ZIP archive with an external
reproducibility manifest and post-build security validation.

Usage:
    python scripts/package_submission.py --source <path> [options]

Options:
    --source PATH     Path to source candidate or agent package directory (REQUIRED)
    --output PATH     Destination path for submission ZIP (default: submission.zip)
    --manifest PATH   Destination path for manifest JSON (default: <output>.manifest.json)
    --check-only      Dry-run: validate source and plan package contents without writing files
    --json            Output machine-readable JSON results to stdout
    --strict          Strict mode: treat validation warnings as fatal errors
    --force           Allow overwriting pre-existing output archive and manifest files
    -h, --help        Show this help message and exit

Exit Codes:
    0: Success (packaged and validated, or check-only passed)
    1: Source validation or dependency verification failed
    2: Post-packaging verification or manifest consistency failed
    3: Invocation / CLI / I/O error (missing source, existing output without --force)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local.packaging.models import PackagerConfig, PackagerResult
from local.packaging.packager import SubmissionPackager


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 48: Deterministic Submission Packager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Package candidate M0 to a test output directory:
  python scripts/package_submission.py --source experiments/candidates/M0 --output experiments/packaging/stage48/submission.zip

  # Dry-run check on agent directory without writing files:
  python scripts/package_submission.py --source agent --check-only

  # Machine-readable JSON output:
  python scripts/package_submission.py --source experiments/candidates/M0 --check-only --json

Exit Codes:
  0: Packaging succeeded and verified (or check-only passed)
  1: Source validation or dependency verification failed
  2: Post-build archive verification failed
  3: CLI error, source missing, or destination exists without --force
""",
    )

    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Path to source agent or candidate package directory (REQUIRED; no guessing)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="submission.zip",
        help="Destination path for the generated ZIP archive (default: submission.zip)",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        type=str,
        default=None,
        help="Destination path for reproducibility manifest JSON (default: <output>.manifest.json)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Dry run: validate source and display planned members without creating archive",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in machine-readable JSON format",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: treat non-fatal validation warnings as errors",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Allow overwriting pre-existing output archive and manifest files",
    )

    return parser.parse_args(args)


def format_human_readable_report(result: PackagerResult, check_only: bool = False) -> str:
    """Renders a clean, structured CLI summary for console users."""
    lines: list[str] = [
        "=" * 64,
        f"IMPULSE Deterministic Submission Packager (Stage 48){' [DRY RUN]' if check_only else ''}",
        "=" * 64,
        f"Source:          {result.source_path}",
        f"Candidate ID:    {result.candidate_id or '(None)'}",
        f"Agent Name:      {result.agent_name or '(Unspecified)'}",
        f"Base Model:      {result.base_model or '(Unspecified)'}",
    ]

    if not check_only:
        lines.extend([
            f"Output Archive:  {result.output_path or '(None)'}",
            f"Manifest File:   {result.manifest_path or '(None)'}",
            f"Archive SHA-256: {result.archive_sha256 or '(None)'}",
            f"Archive Size:    {result.archive_size_bytes:,} bytes",
        ])

    lines.extend([
        f"Packaged Files:  {result.total_files_packaged}",
        f"Uncompressed:    {result.total_uncompressed_bytes:,} bytes",
        f"Status:          {'SUCCESS' if result.success else 'FAILED'} (Exit code {result.exit_code})",
        "-" * 64,
    ])

    if result.manifest_data and "members" in result.manifest_data:
        members = result.manifest_data["members"]
        lines.append(f"Packaged Members ({len(members)}):")
        for i, m in enumerate(members, start=1):
            lines.append(f"  [{i}] {m['path']} ({m['size_bytes']:,} bytes) - {m['sha256'][:16]}...")
        lines.append("-" * 64)

    if result.excluded_files:
        lines.append(f"Excluded Files ({len(result.excluded_files)}):")
        for ef in result.excluded_files:
            lines.append(f"  [-] {ef['path']} ({ef['reason']})")
        lines.append("-" * 64)

    if result.errors:
        lines.append("Errors:")
        for err in result.errors:
            lines.append(f"  [ERROR] {err}")
        lines.append("-" * 64)

    if result.warnings:
        lines.append("Warnings:")
        for warn in result.warnings:
            lines.append(f"  [WARN] {warn}")
        lines.append("-" * 64)

    val = result.archive_validation or result.source_validation
    if val:
        lines.append(
            f"Validation:      {'PASS' if val.overall_valid else 'FAIL'} "
            f"({val.passed_count} passed, {val.failed_count} failed, {val.warnings_count} warnings, "
            f"{val.skipped_count} skipped, {val.unavailable_count} unavailable)"
        )
        if val.unavailable_count > 0:
            lines.append("Official Compiler: UNAVAILABLE (Local declarative validation verified)")

    lines.append("=" * 64)
    return "\n".join(lines)


def main(args: list[str] | None = None) -> int:
    parsed_args = parse_args(args)

    # 1. Require --source explicitly (do not guess winner or default arbitrarily)
    if not parsed_args.source:
        err_msg = (
            "Error: --source PATH is required.\n"
            "An explicit candidate directory must be specified (e.g. '--source experiments/candidates/M0' or '--source agent').\n"
            "No candidate can be inferred as the approved final winner without explicit user selection."
        )
        if parsed_args.json:
            print(
                json.dumps({
                    "success": False,
                    "exit_code": 3,
                    "errors": [err_msg],
                }, indent=2)
            )
        else:
            print(err_msg, file=sys.stderr)
        return 3

    # Resolve manifest path default if omitted
    manifest_path = parsed_args.manifest
    if not manifest_path:
        out_p = Path(parsed_args.output)
        manifest_path = str(out_p.with_name(f"{out_p.name}.manifest.json"))

    config = PackagerConfig(
        source_path=parsed_args.source,
        output_path=parsed_args.output,
        manifest_path=manifest_path,
        check_only=parsed_args.check_only,
        strict_mode=parsed_args.strict,
        force=parsed_args.force,
    )

    packager = SubmissionPackager(config=config, repo_root=REPO_ROOT)
    result = packager.run()

    if parsed_args.json:
        print(result.to_json(indent=2))
    else:
        report = format_human_readable_report(result, check_only=parsed_args.check_only)
        if result.success:
            print(report)
        else:
            print(report, file=sys.stderr)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
