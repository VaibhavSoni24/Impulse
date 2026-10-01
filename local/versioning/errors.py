"""Exception hierarchy for Stage 43 candidate versioning subsystem."""

from __future__ import annotations


class VersioningError(Exception):
    """Base exception for all candidate versioning errors."""
    pass


class DuplicateCandidateError(VersioningError):
    """Raised when attempting to register an existing candidate ID."""
    pass


class ImmutableCandidateError(VersioningError):
    """Raised when attempting to overwrite or alter a finalized candidate manifest."""
    pass


class InvalidStatusTransitionError(VersioningError):
    """Raised when a candidate attempts an illegal lifecycle status transition."""
    pass


class LineageError(VersioningError):
    """Raised when a candidate references an invalid, circular, or nonexistent parent."""
    pass


class SecretDetectedInManifestError(VersioningError):
    """Raised when credentials or private paths are discovered in a manifest."""
    pass


class SchemaValidationError(VersioningError):
    """Raised when candidate manifest data fails schema rules."""
    pass


class UnverifiedPromotionError(VersioningError):
    """Raised when a candidate is declared PROMOTED without required empirical proof."""
    pass


class MultiDimensionExperimentError(VersioningError):
    """Raised when an ordinary experiment alters multiple major dimensions without declaration."""
    pass
