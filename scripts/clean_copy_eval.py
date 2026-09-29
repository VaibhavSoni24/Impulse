#!/usr/bin/env python3
"""CLI utility for Stage 28 Clean-Copy Evaluation.

Executes autonomous agent candidates against benchmark tasks using strict
clean-copy evaluation:
clean snapshot -> candidate load -> run agent -> extract patch ->
fresh snapshot -> apply patch -> verify -> record result.

Usage:
    python scripts/clean_copy_eval.py -t <task_id> -c <candidate> [--mode fixture|live|unavailable] [--json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import ExecutionMode
from local.runner.task_loader import DEFAULT_TASKS_FILE, TaskLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IMPULSE Clean-Copy Evaluator (Stage 28)"
    )
    parser.add_argument(
        "--task",
        "-t",
        dest="task_id",
        type=str,
        help="Target task instance ID (e.g. 'fastapi_14479').",
    )
    parser.add_argument(
        "--candidate",
        "-c",
        dest="candidate_ref",
        type=str,
        default="M0",
        help="Candidate identifier or directory (default: 'M0').",
    )
    parser.add_argument(
        "--baseline",
        dest="baseline_commit",
        type=str,
        default=None,
        help="Explicit baseline Git commit SHA (defaults to HEAD).",
    )
    parser.add_argument(
        "--mode",
        dest="mode",
        type=str,
        default="fixture",
        choices=["fixture", "live", "unavailable"],
        help="Execution mode (default: 'fixture').",
    )
    parser.add_argument(
        "--split",
        dest="split_name",
        type=str,
        default=None,
        choices=["dev", "validation", "held_out"],
        help="Target benchmark split (e.g. 'dev', 'validation', 'held_out').",
    )
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=DEFAULT_TASKS_FILE,
        help="Path to tasks.jsonl manifest.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("runs"),
        help="Directory to store evaluation runs (default: 'runs').",
    )
    parser.add_argument(
        "--allow-dirty-baseline",
        action="store_true",
        help="Allow running when the developer repository working tree has uncommitted changes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output evaluation run record as JSON.",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List available benchmark tasks and exit.",
    )

    args = parser.parse_args(argv)

    if args.list_tasks:
        loader = TaskLoader(args.tasks_file)
        task_ids = loader.list_task_ids()
        print(f"Available tasks ({len(task_ids)} total):")
        for tid in task_ids:
            print(f"  - {tid}")
        return 0

    if not args.task_id:
        parser.error("--task / -t is required.")

    mode_enum = ExecutionMode(args.mode.upper())

    evaluator = CleanCopyEvaluator(
        repo_root=PROJECT_ROOT,
        tasks_file=args.tasks_file,
        output_dir=args.output_dir,
    )

    record = evaluator.evaluate_task(
        task_id=args.task_id,
        candidate_ref=args.candidate_ref,
        baseline_commit=args.baseline_commit,
        mode=mode_enum,
        allow_dirty_baseline=args.allow_dirty_baseline,
        split_name=args.split_name,
    )

    if args.json:
        print(json.dumps(record.to_dict(), indent=2))
    else:
        print("=" * 65)
        print("IMPULSE CLEAN-COPY EVALUATION REPORT (STAGE 28/29)")
        print("=" * 65)
        print(f"Run ID:                 {record.run_id}")
        print(f"Task ID:                {record.task_id}")
        print(f"Candidate:              {record.candidate_id}")
        if record.split_name:
            v_str = record.split_version if record.split_version.startswith("v") else f"v{record.split_version}"
            print(f"Split:                  {record.split_name.upper()} ({v_str})")
        print(f"Baseline Commit:        {record.baseline_commit[:12] if record.baseline_commit else 'N/A'}")
        print(f"Candidate Config SHA:   {record.candidate_config_sha256[:12] if record.candidate_config_sha256 else 'N/A'}")
        print(f"Execution Status:       {record.execution_status}")
        print(f"Patch Extraction:       {record.patch_extraction_status}")
        print(f"Patch Apply:            {record.patch_apply_status}")
        print(f"Verification Status:    {record.verification_status}")
        print(f"Clean-Copy Verified:    {record.clean_copy_verified}")
        print(f"Overall Success:        {record.success}")
        print(f"Files Changed:          {record.files_changed}")
        print(f"Patch Lines:            {record.patch_lines}")
        print(f"Termination Reason:     {record.termination_reason}")
        if record.failure_class:
            print(f"Failure Class:          {record.failure_class}")
        if record.failure_stage:
            print(f"Failure Stage:          {record.failure_stage}")
        print(f"Elapsed Time:           {record.elapsed_seconds:.4f}s")
        print("=" * 65)

    return 0 if record.success else 1


if __name__ == "__main__":
    sys.exit(main())
