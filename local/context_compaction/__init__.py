"""Context Compaction Subsystem for IMPULSE (Stage 25).

Provides deterministic, loss-bounded context compaction while preserving all
critical diagnostic evidence, stack traces, assertion lines, and file states.
"""

from local.context_compaction.file_tracking import ChangedFileTracker
from local.context_compaction.fingerprints import (
    are_observations_identical,
    compute_content_sha256,
    compute_file_fingerprint,
    normalize_path,
    sanitize_text,
)
from local.context_compaction.log_compaction import compact_test_log
from local.context_compaction.models import (
    CompactionAction,
    CompactedTestLog,
    CompactObservation,
    FactObservationSummary,
    FileFingerprint,
    HypothesisRecord,
    HypothesisStatus,
    ObservationType,
)
from local.context_compaction.observation_summary import (
    FactObservationTracker,
    HypothesisTracker,
    ObservationDeduplicator,
)
from local.context_compaction.adapter import CompactedTaskContext
from local.context_compaction.policy import CompactionPolicy
from local.context_compaction.repo_cache import RepositoryMapCache, RepositoryMapEntry

__all__ = [
    "CompactionAction",
    "ObservationType",
    "HypothesisStatus",
    "FileFingerprint",
    "ChangedFileRecord",
    "CompactedTestLog",
    "FactObservationSummary",
    "HypothesisRecord",
    "CompactObservation",
    "compute_content_sha256",
    "compute_file_fingerprint",
    "are_observations_identical",
    "normalize_path",
    "sanitize_text",
    "ChangedFileTracker",
    "compact_test_log",
    "RepositoryMapCache",
    "RepositoryMapEntry",
    "FactObservationTracker",
    "HypothesisTracker",
    "ObservationDeduplicator",
    "CompactionPolicy",
    "CompactedTaskContext",
]
