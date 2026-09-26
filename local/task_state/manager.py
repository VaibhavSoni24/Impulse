"""Task state manager for file-based persistence outside the Git workspace."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from local.task_state.models import TaskState


def get_default_state_path() -> Path:
    """Returns safe state file path outside /workspace (in /tmp or system tempdir)."""
    # In Linux evaluation containers, /tmp is always present and outside /workspace.
    # On Windows development hosts, tempfile.gettempdir() provides safe isolation.
    if os.name == "posix" and Path("/tmp").exists():
        return Path("/tmp/impulse_task_state.json")
    return Path(tempfile.gettempdir()) / "impulse_task_state.json"


class TaskStateManager:
    """Manages TaskState lifecycle, file persistence, and isolation from workspace."""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self.state_path = Path(state_path) if state_path else get_default_state_path()

    def load_or_create(self) -> TaskState:
        """Loads state from persistence file if present, or initializes a clean state."""
        if self.state_path.exists():
            try:
                content = self.state_path.read_text(encoding="utf-8")
                return TaskState.from_json(content)
            except Exception:
                pass
        return TaskState()

    def save(self, state: TaskState) -> Path:
        """Atomically saves the TaskState to the persistence path."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to temporary file in same directory first then atomic rename
        temp_file = self.state_path.with_suffix(".tmp")
        temp_file.write_text(state.to_json(indent=2), encoding="utf-8")
        temp_file.replace(self.state_path)
        return self.state_path

    def clear(self) -> None:
        """Removes the persistent state file if present."""
        if self.state_path.exists():
            self.state_path.unlink()
