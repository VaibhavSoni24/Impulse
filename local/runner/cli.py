"""Command-line interface and orchestrator for the IMPULSE local task runner."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local.runner.artifacts import ArtifactManager
from local.runner.executor import get_backend
from local.runner.models import ExecutionResult, RunMetadata, RunSpec, TaskRecord
from local.runner.task_loader import (
    DEFAULT_TASKS_FILE,
    InvalidTaskIdError,
    TaskLoader,
    TaskNotFoundError,
    validate_task_id,
)


def get_git_commit() -> str | None:
    """Safely retrieves current Git commit hash if in a git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0:
            commit = res.stdout.strip()
            if re.match(r"^[0-9a-fA-F]{40}$", commit):
                return commit
    except Exception:
        pass
    return None


def extract_candidate_metadata(candidate_dir: Path) -> dict[str, str]:
    """Extracts model identifier and prompt reference from candidate agent.yaml."""
    agent_yaml = candidate_dir / "agent.yaml"
    if not agent_yaml.exists():
        # Check for agent.yml
        agent_yaml = candidate_dir / "agent.yml"
    if not agent_yaml.exists():
        return {
            "model_id": "unknown",
            "prompt_id": "unknown",
            "candidate_name": candidate_dir.name,
        }

    model_id = "unknown"
    prompt_id = "inline"
    candidate_name = candidate_dir.name

    with open(agent_yaml, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("model:"):
                model_id = stripped.split("model:", 1)[1].strip().strip("'\"")
            elif stripped.startswith("name:"):
                candidate_name = stripped.split("name:", 1)[1].strip().strip("'\"")
            elif stripped.startswith("instruction:"):
                parts = stripped.split("instruction:", 1)[1].strip()
                if "!include" in parts:
                    prompt_id = parts.split("!include", 1)[1].strip().strip("'\"")
                else:
                    prompt_id = "inline"

    return {
        "model_id": model_id,
        "prompt_id": prompt_id,
        "candidate_name": candidate_name,
    }


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for local runner CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m local.runner",
        description="IMPULSE Local Task Runner: Orchestrates candidate runs against benchmark tasks.",
    )

    parser.add_argument(
        "--task",
        "-t",
        dest="task_id",
        type=str,
        help="Target task instance ID (e.g., 'fastapi_15661').",
    )
    parser.add_argument(
        "--candidate",
        "-c",
        dest="candidate_id",
        type=str,
        default="E0",
        help="Candidate identifier (default: 'E0').",
    )
    parser.add_argument(
        "--candidate-dir",
        dest="candidate_dir",
        type=Path,
        default=Path("agent"),
        help="Path to candidate directory containing agent.yaml (default: 'agent').",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        dest="output_dir",
        type=Path,
        default=Path("runs"),
        help="Directory where run artifacts are stored (default: 'runs').",
    )
    parser.add_argument(
        "--timeout",
        dest="timeout_seconds",
        type=int,
        default=None,
        help="Execution timeout in seconds (optional).",
    )
    parser.add_argument(
        "--tool-budget",
        dest="tool_calls_budget",
        type=int,
        default=None,
        help="Maximum allowed tool calls (optional).",
    )
    parser.add_argument(
        "--backend",
        dest="backend_name",
        type=str,
        default="unavailable",
        help="Execution backend to invoke (default: 'unavailable', options: 'unavailable', 'dry-run').",
    )
    parser.add_argument(
        "--tasks-file",
        dest="tasks_file",
        type=Path,
        default=DEFAULT_TASKS_FILE,
        help=f"Path to tasks.jsonl manifest (default: '{DEFAULT_TASKS_FILE}').",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List all available task IDs and exit.",
    )

    return parser


def run_task(spec: RunSpec, tasks_file: Path = DEFAULT_TASKS_FILE) -> RunMetadata:
    """Executes a single candidate run orchestration against a task."""
    validate_task_id(spec.task_id)

    # 1. Resolve task
    loader = TaskLoader(tasks_file)
    task = loader.get_task(spec.task_id)

    # 2. Extract candidate metadata
    cand_info = extract_candidate_metadata(spec.candidate_dir)
    model_id = cand_info["model_id"]
    prompt_id = cand_info["prompt_id"]

    # 3. Create run directory and initialize artifacts
    artifact_mgr = ArtifactManager(spec.output_dir)
    start_dt = datetime.now(timezone.utc)
    run_dir = artifact_mgr.create_run_directory(
        candidate_id=spec.candidate_id,
        task_id=spec.task_id,
        timestamp=start_dt,
    )
    run_id = run_dir.name

    # 4. Snapshot candidate & write task metadata
    artifact_mgr.snapshot_candidate(spec.candidate_dir, run_dir)
    artifact_mgr.write_task_metadata(task, run_dir)

    # 5. Execute backend
    backend = get_backend(spec.backend_name)
    start_perf = time.perf_counter()
    exec_result: ExecutionResult = backend.execute(spec, task, run_dir)
    elapsed = time.perf_counter() - start_perf
    end_dt = datetime.now(timezone.utc)

    # 6. Assemble RunMetadata
    metadata = RunMetadata(
        run_id=run_id,
        candidate_id=spec.candidate_id,
        task_id=spec.task_id,
        model_id=model_id,
        prompt_id=prompt_id,
        execution_backend=backend.name,
        status=exec_result.status,
        termination_reason=exec_result.termination_reason,
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
        elapsed_time_seconds=round(elapsed, 4),
        timeout_seconds=spec.timeout_seconds,
        tool_calls_budget=spec.tool_calls_budget,
        git_commit=get_git_commit(),
        tool_calls_count=exec_result.tool_calls_count,
        turns_count=exec_result.turns_count,
        error_message=exec_result.error_message,
        patch_generated=bool(exec_result.patch),
        run_dir=str(run_dir),
    )

    # 7. Write run.json
    artifact_mgr.write_run_metadata(metadata, run_dir)

    # 8. Write log
    log_content = (
        f"IMPULSE Local Task Runner Log\n"
        f"=============================\n"
        f"Run ID:            {metadata.run_id}\n"
        f"Candidate ID:      {metadata.candidate_id}\n"
        f"Task ID:           {metadata.task_id}\n"
        f"Model ID:          {metadata.model_id}\n"
        f"Backend:           {metadata.execution_backend}\n"
        f"Status:            {metadata.status}\n"
        f"Termination:       {metadata.termination_reason}\n"
        f"Elapsed:           {metadata.elapsed_time_seconds:.4f}s\n"
    )
    artifact_mgr.write_log(run_dir, "runner.log", log_content)

    return metadata


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    loader = TaskLoader(args.tasks_file)

    if args.list_tasks:
        try:
            task_ids = loader.list_task_ids()
            print(f"Available tasks ({len(task_ids)} total):")
            for tid in task_ids:
                print(f"  - {tid}")
            return 0
        except Exception as e:
            print(f"Error listing tasks: {e}", file=sys.stderr)
            return 1

    if not args.task_id:
        parser.error("The --task / -t argument is required (or use --list-tasks).")

    spec = RunSpec(
        task_id=args.task_id,
        candidate_id=args.candidate_id,
        candidate_dir=args.candidate_dir,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
        tool_calls_budget=args.tool_calls_budget,
        backend_name=args.backend_name,
    )

    try:
        metadata = run_task(spec, args.tasks_file)
        print("=" * 60)
        print("IMPULSE TASK RUN SUMMARY")
        print("=" * 60)
        print(f"Run ID:             {metadata.run_id}")
        print(f"Task ID:            {metadata.task_id}")
        print(f"Candidate:          {metadata.candidate_id} (Model: {metadata.model_id})")
        print(f"Prompt Ref:         {metadata.prompt_id}")
        print(f"Backend:            {metadata.execution_backend}")
        print(f"Status:             {metadata.status}")
        print(f"Termination Reason: {metadata.termination_reason}")
        print(f"Run Directory:      {metadata.run_dir}")
        print(f"Elapsed Time:       {metadata.elapsed_time_seconds:.4f}s")
        print("=" * 60)
        return 0
    except (TaskNotFoundError, InvalidTaskIdError) as e:
        print(f"Task error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Runner execution error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
