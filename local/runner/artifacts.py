"""Artifact collection and directory management for the local task runner."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local.runner.models import RunMetadata, TaskRecord

# Safe pattern for path components
SAFE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class ArtifactManagerError(Exception):
    """Base exception for artifact manager errors."""


class PathSecurityError(ArtifactManagerError):
    """Raised when an output or run path attempts traversal or escapes boundaries."""


def sanitize_component(name: str) -> str:
    """Sanitizes an input string to be a safe path component."""
    cleaned = name.strip().replace("..", "__")
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", cleaned)
    if not cleaned:
        return "unknown"
    return cleaned[:64]


def validate_path_safety(base_dir: Path, target_dir: Path) -> None:
    """Verifies that target_dir is strictly contained within base_dir."""
    base_resolved = base_dir.resolve()
    target_resolved = target_dir.resolve()
    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise PathSecurityError(
            f"Security violation: Target directory {target_resolved} escapes base {base_resolved}"
        )


class ArtifactManager:
    """Manages the creation of run directories and persistence of run artifacts."""

    def __init__(self, base_output_dir: Path | str = Path("runs")) -> None:
        self.base_output_dir = Path(base_output_dir)

    def create_run_directory(
        self,
        candidate_id: str,
        task_id: str,
        timestamp: datetime | None = None,
    ) -> Path:
        """Creates a unique, collision-resistant run directory.

        Format: runs/YYYYMMDD-HHMMSS-<candidate>-<task>/
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        ts_str = timestamp.strftime("%Y%m%d-%H%M%S")
        safe_candidate = sanitize_component(candidate_id)
        safe_task = sanitize_component(task_id)
        folder_name = f"{ts_str}-{safe_candidate}-{safe_task}"

        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = self.base_output_dir / folder_name

        validate_path_safety(self.base_output_dir, run_dir)

        # Handle collisions without overwriting
        counter = 1
        original_dir = run_dir
        while run_dir.exists():
            run_dir = self.base_output_dir / f"{folder_name}-{counter}"
            validate_path_safety(self.base_output_dir, run_dir)
            counter += 1

        run_dir.mkdir(parents=True, exist_ok=False)

        # Create subdirectories for artifacts and logs
        (run_dir / "logs").mkdir(exist_ok=True)
        (run_dir / "candidate_snapshot").mkdir(exist_ok=True)

        return run_dir

    def snapshot_candidate(self, candidate_dir: Path, run_dir: Path) -> None:
        """Copies candidate configuration files into the run snapshot directory."""
        validate_path_safety(self.base_output_dir, run_dir)
        snapshot_dir = run_dir / "candidate_snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        if not candidate_dir.exists() or not candidate_dir.is_dir():
            return

        for item in candidate_dir.iterdir():
            if item.name.startswith((".", "__pycache__")):
                continue
            dest = snapshot_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, dest)

    def write_task_metadata(self, task: TaskRecord, run_dir: Path) -> Path:
        """Writes non-sensitive task metadata to task_metadata.json."""
        validate_path_safety(self.base_output_dir, run_dir)
        path = run_dir / "task_metadata.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task.to_metadata_dict(), f, indent=2)
        return path

    def write_run_metadata(self, metadata: RunMetadata, run_dir: Path) -> Path:
        """Writes authoritative execution metadata to run.json."""
        validate_path_safety(self.base_output_dir, run_dir)
        path = run_dir / "run.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        return path

    def write_log(self, run_dir: Path, log_name: str, content: str) -> Path:
        """Writes content to a log file within logs/."""
        validate_path_safety(self.base_output_dir, run_dir)
        log_dir = run_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        path = log_dir / sanitize_component(log_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
