"""IMPULSE Structured Task State Package (Stage 11).

Provides typed state models, bounded history collections, invariant validation,
isolated file persistence, and concise model-facing rendering.
"""

from local.task_state.manager import TaskStateManager, get_default_state_path
from local.task_state.models import (
    MAX_COLLECTION_SIZE,
    CandidateLocation,
    EditRecord,
    EvidenceItem,
    FailureRecord,
    FinalReviewRecord,
    RepositoryFact,
    TaskState,
    TestRecord,
)
from local.task_state.renderer import render_model_context

__all__ = [
    "MAX_COLLECTION_SIZE",
    "CandidateLocation",
    "EditRecord",
    "EvidenceItem",
    "FailureRecord",
    "FinalReviewRecord",
    "RepositoryFact",
    "TaskState",
    "TaskStateManager",
    "TestRecord",
    "get_default_state_path",
    "render_model_context",
]
