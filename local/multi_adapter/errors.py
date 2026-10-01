"""Custom exception hierarchy for Stage 41 Multi-Adapter Experimentation.

Enforces fail-closed evaluation boundaries and scientific prerequisites.
"""

from __future__ import annotations


class MultiAdapterError(Exception):
    """Base exception for all Stage 41 multi-adapter errors."""
    pass


class SingleAdapterPrerequisiteError(MultiAdapterError):
    """Raised when multi-adapter execution is attempted before a single adapter is empirically validated and promoted."""
    pass


class RoleConflictError(MultiAdapterError):
    """Raised when role assignment violates isolation, duplicate assignment, or role capabilities."""
    pass


class BaseModelMismatchError(MultiAdapterError):
    """Raised when an adapter was trained on an incompatible or different base model."""
    pass


class UnvalidatedAdapterError(MultiAdapterError):
    """Raised when an adapter without verified training provenance or promotion is assigned."""
    pass


class DryRunError(MultiAdapterError):
    """Raised when multi-adapter dry-run encountered invariant or schema violations."""
    pass
