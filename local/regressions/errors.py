"""Exception hierarchy for Stage 45 Failure Regression Suite."""

from __future__ import annotations


class RegressionError(Exception):
    """Base exception for all regression subsystem errors."""
    pass


class DuplicateRegressionError(RegressionError):
    """Raised when registering a duplicate regression ID or duplicate failure signature."""
    pass


class HeldOutContaminationError(RegressionError):
    """Raised when a regression case or fixture references or imports a protected held-out task."""
    pass


class InvalidRegressionCaseError(RegressionError):
    """Raised when regression case metadata, invariants, or provenance fail validation."""
    pass


class RegressionExecutionError(RegressionError):
    """Raised when an executable regression invariant fails verification."""
    pass


class RegressionManifestError(RegressionError):
    """Raised when regression manifest loading or verification fails."""
    pass
