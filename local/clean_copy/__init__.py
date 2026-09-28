"""IMPULSE Stage 28: Clean-Copy Evaluator.

Provides clean repository snapshotting, candidate loading, isolated agent execution,
patch extraction, fresh patch application, semantic equivalence checking, and
task verification strictly against clean repository copies.
"""

from __future__ import annotations

from local.clean_copy.adapter import (
    AgentExecutionAdapter,
    FixtureAction,
    FixtureAgentSpec,
    check_live_runtime_available,
)
from local.clean_copy.candidate_loader import (
    CandidateLoader,
    CandidateLoadError,
    LoadedCandidate,
)
from local.clean_copy.equivalence import PatchEquivalenceChecker
from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import (
    EvaluatorFailureClass,
    EvaluationRunRecord,
    ExecutionMode,
    FailureStage,
    PatchBundle,
    WorkspaceCreationMethod,
)
from local.clean_copy.patch_applier import FreshPatchApplier, PatchApplicationError
from local.clean_copy.patch_extractor import PatchExtractionError, PatchExtractor
from local.clean_copy.snapshot import (
    CleanRepositorySnapshot,
    SnapshotManager,
)
from local.clean_copy.verifier import CleanCopyVerifier, VerificationResult

__all__ = [
    "CleanCopyEvaluator",
    "CleanRepositorySnapshot",
    "SnapshotManager",
    "CandidateLoader",
    "CandidateLoadError",
    "LoadedCandidate",
    "AgentExecutionAdapter",
    "FixtureAction",
    "FixtureAgentSpec",
    "check_live_runtime_available",
    "PatchExtractor",
    "PatchExtractionError",
    "FreshPatchApplier",
    "PatchApplicationError",
    "PatchEquivalenceChecker",
    "CleanCopyVerifier",
    "VerificationResult",
    "EvaluationRunRecord",
    "PatchBundle",
    "FailureStage",
    "EvaluatorFailureClass",
    "ExecutionMode",
    "WorkspaceCreationMethod",
]
