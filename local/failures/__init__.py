"""Failure classification module (Stage 18 / Candidate E9).

Exports canonical failure categories, classification context, and deterministic classifier.
"""

from local.failures.classifier import FailureClassifierV1
from local.failures.models import (
    EvidenceStrength,
    FailureClass,
    FailureClassification,
    FailureClassificationContext,
)

__all__ = [
    "EvidenceStrength",
    "FailureClass",
    "FailureClassification",
    "FailureClassificationContext",
    "FailureClassifierV1",
]
