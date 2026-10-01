"""Custom error and exception hierarchy for Stage 40 LoRA Ablation.

Enforces fail-closed evaluation boundaries and security gates.
"""

from __future__ import annotations


class AblationError(Exception):
    """Base exception for all Stage 40 ablation errors."""
    pass


class MissingAdapterError(AblationError):
    """Raised when an adapter artifact is required for evaluation but does not exist."""
    pass


class InvalidAdapterError(AblationError):
    """Raised when an adapter artifact exists but violates structural, schema, or manifest requirements."""
    pass


class InvarianceViolationError(AblationError):
    """Raised when an ablation condition violates frozen baseline dimensions or introduces unallowed changes."""
    pass


class SecondaryConditionBlockedError(AblationError):
    """Raised when Condition C (prompt variant) or Condition D (retrieval variant) is invoked before Condition B is evaluated."""
    pass


class HeldOutViolationError(AblationError):
    """Raised when an ablation experiment attempts to tune hyperparameters against the held-out benchmark split."""
    pass


class PromotionGateError(AblationError):
    """Raised when candidate promotion rules are violated."""
    pass


class DryRunError(AblationError):
    """Raised when dry-run validation encounters a critical invariant or schema failure."""
    pass
