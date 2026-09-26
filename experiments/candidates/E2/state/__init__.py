"""Candidate E2 state interface re-exporting structured TaskState."""

from local.task_state import (
    CandidateLocation,
    EditRecord,
    EvidenceItem,
    FailureRecord,
    FinalReviewRecord,
    RepositoryFact,
    TaskState,
    TaskStateManager,
    TestRecord,
    get_default_state_path,
    render_model_context,
)

__all__ = [
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
