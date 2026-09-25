"""Task loader for resolving competition benchmark tasks from tasks.jsonl."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from local.runner.models import TaskRecord

DEFAULT_TASKS_FILE = Path("data/competition/tasks.jsonl")

# Safe task ID regex: alphanumeric, underscores, hyphens, and dots only
TASK_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


class TaskLoaderError(Exception):
    """Base exception for task loading failures."""


class TaskNotFoundError(TaskLoaderError):
    """Raised when the requested task instance_id cannot be found in the dataset."""


class InvalidTaskIdError(TaskLoaderError):
    """Raised when a task ID fails safety or format validation."""


def validate_task_id(task_id: str) -> None:
    """Validates task ID for safety and format correctness.

    Prevents path traversal, empty IDs, or excessively long strings.
    """
    if not task_id or not isinstance(task_id, str):
        raise InvalidTaskIdError("Task ID must be a non-empty string.")

    cleaned = task_id.strip()
    if len(cleaned) > 128:
        raise InvalidTaskIdError(f"Task ID exceeds maximum length of 128 chars: {len(cleaned)}")

    # Reject path traversal patterns explicitly
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise InvalidTaskIdError(f"Task ID contains forbidden path navigation sequences: {task_id!r}")

    if not TASK_ID_REGEX.match(cleaned):
        raise InvalidTaskIdError(
            f"Task ID contains invalid characters. Must match {TASK_ID_REGEX.pattern}: {task_id!r}"
        )


class TaskLoader:
    """Loads and queries competition tasks from tasks.jsonl."""

    def __init__(self, tasks_file: Path | str = DEFAULT_TASKS_FILE) -> None:
        self.tasks_file = Path(tasks_file)

    def _ensure_file_exists(self) -> None:
        if not self.tasks_file.exists():
            raise TaskLoaderError(f"Tasks manifest not found: {self.tasks_file}")

    def list_task_ids(self) -> list[str]:
        """Returns a list of all available task instance_ids in the dataset."""
        self._ensure_file_exists()
        task_ids: list[str] = []
        with open(self.tasks_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                    instance_id = record.get("instance_id")
                    if instance_id:
                        task_ids.append(str(instance_id))
                except json.JSONDecodeError:
                    continue
        return task_ids

    def get_task(self, task_id: str) -> TaskRecord:
        """Finds and returns the TaskRecord for a given instance_id."""
        validate_task_id(task_id)
        self._ensure_file_exists()

        target_id = task_id.strip()
        with open(self.tasks_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                if record.get("instance_id") == target_id:
                    return TaskRecord(
                        instance_id=record["instance_id"],
                        repo=record.get("repo", ""),
                        base_commit=record.get("base_commit", ""),
                        problem_statement=record.get("problem_statement", ""),
                        hints_text=record.get("hints_text", ""),
                        created_at=record.get("created_at", ""),
                        has_test_patch=bool(record.get("test_patch")),
                    )

        raise TaskNotFoundError(f"Task with instance_id '{target_id}' not found in {self.tasks_file}.")
