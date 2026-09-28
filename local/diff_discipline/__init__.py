"""IMPULSE Stage 27: Final Diff Discipline & Repository Hygiene.

Provides deterministic repository hygiene auditing, pre-release verification,
scratch and log detection, referential safety checking, and Git review tools.
"""

from __future__ import annotations

from local.diff_discipline.classifier import ArtifactClassifier
from local.diff_discipline.cleaner import SafeCleaner
from local.diff_discipline.detectors import (
    detect_local_config,
    detect_log_file,
    detect_machine_specific,
    detect_scratch_file,
    scan_content_for_debug_markers,
    scan_content_for_machine_paths,
    scan_content_for_secrets,
)
from local.diff_discipline.frozen_verifier import (
    FROZEN_STAGE24_HASHES,
    verify_frozen_artifacts,
)
from local.diff_discipline.git_inspector import GitInspector
from local.diff_discipline.models import (
    ArtifactClass,
    ArtifactFinding,
    GitFileStatus,
    GitReviewSnapshot,
    HygieneAction,
    HygieneReport,
)
from local.diff_discipline.pipeline import FinalDiffReviewPipeline
from local.diff_discipline.reference_checker import ReferenceChecker

__all__ = [
    "ArtifactClass",
    "HygieneAction",
    "GitFileStatus",
    "ArtifactFinding",
    "GitReviewSnapshot",
    "HygieneReport",
    "ArtifactClassifier",
    "SafeCleaner",
    "ReferenceChecker",
    "GitInspector",
    "FinalDiffReviewPipeline",
    "verify_frozen_artifacts",
    "FROZEN_STAGE24_HASHES",
    "detect_scratch_file",
    "detect_log_file",
    "detect_local_config",
    "detect_machine_specific",
    "scan_content_for_debug_markers",
    "scan_content_for_machine_paths",
    "scan_content_for_secrets",
]
