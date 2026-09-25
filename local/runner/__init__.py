"""IMPULSE Local Task Runner.

Infrastructure package for reproducible execution, metadata tracking,
artifact persistence, and execution backend orchestration.
"""

from local.runner.artifacts import ArtifactManager, PathSecurityError
from local.runner.executor import (
    DryRunBackend,
    ExecutionBackend,
    UnavailableLocalBackend,
    get_backend,
)
from local.runner.models import (
    ExecutionResult,
    RunMetadata,
    RunSpec,
    TaskRecord,
)
from local.runner.task_loader import (
    InvalidTaskIdError,
    TaskLoader,
    TaskNotFoundError,
    validate_task_id,
)

__all__ = [
    "ArtifactManager",
    "DryRunBackend",
    "ExecutionBackend",
    "ExecutionResult",
    "InvalidTaskIdError",
    "PathSecurityError",
    "RunMetadata",
    "RunSpec",
    "TaskLoader",
    "TaskNotFoundError",
    "TaskRecord",
    "UnavailableLocalBackend",
    "get_backend",
    "validate_task_id",
]
