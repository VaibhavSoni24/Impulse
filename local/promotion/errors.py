"""Exception hierarchy for Stage 44 Candidate Promotion Gate."""

from __future__ import annotations


class PromotionError(Exception):
    """Base exception for all candidate promotion gate errors."""
    pass


class CandidateNotFoundError(PromotionError):
    """Raised when the specified candidate is not registered in the candidate registry."""
    pass


class BaselineNotFoundError(PromotionError):
    """Raised when the specified baseline candidate is not registered in the candidate registry."""
    pass


class PromotionGateFailureError(PromotionError):
    """Raised when attempting to promote a candidate that fails promotion gate requirements."""
    pass


class InvalidCurrentBestError(PromotionError):
    """Raised when the current-best candidate pointer violates consistency or integrity rules."""
    pass


class ForbiddenBypassError(PromotionError):
    """Raised when attempting an unauthorized bypass (e.g. --force) of the promotion gate."""
    pass


class MultiDimensionConfoundingError(PromotionError):
    """Raised when a candidate introduces multiple confounding changes without declaring combined ablation."""
    pass


class UnverifiedCandidateError(PromotionError):
    """Raised when attempting promotion actions on unverified or ungrounded candidate states."""
    pass
