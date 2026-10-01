"""Exception taxonomy for Stage 42 compute portability subsystem."""

from __future__ import annotations


class ComputeError(Exception):
    """Base exception for all compute subsystem errors."""
    pass


class HardwareDetectionError(ComputeError):
    """Raised when hardware inspection encounters unexpected platform failure."""
    pass


class IncompatibleEnvironmentError(ComputeError):
    """Raised when current environment fails mandatory experiment requirements."""
    pass


class PreflightBlockedError(ComputeError):
    """Raised when experiment preflight fails gating criteria."""
    pass


class ArtifactHashMismatchError(ComputeError):
    """Raised when transferred or returned artifact fails SHA-256 verification."""
    pass


class SecretLeakageDetectedError(ComputeError):
    """Raised when an environment artifact or manifest contains sensitive credentials."""
    pass


class NetworkPolicyViolationError(ComputeError):
    """Raised when an offline or restricted task attempts network access."""
    pass


class DiskSpaceInsufficientError(ComputeError):
    """Raised when available disk space falls below required threshold plus safety margin."""
    pass
