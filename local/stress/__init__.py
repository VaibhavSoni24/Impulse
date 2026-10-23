"""IMPULSE Stress Test Suite (Stage 46).

Deterministic, resource-bounded stress tests designed to expose failure modes
under difficult conditions (very large repos, ambiguous wording, misleading names,
multi-file fixes, hidden dependencies, long logs, pre-existing failures, new files,
binary files, repeated failures, and expensive test suites) before candidate release.
"""

from __future__ import annotations

from local.stress.models import (
    StressCase,
    StressCategory,
    StressManifest,
    StressResultStatus,
    StressRunResult,
    StressSeverity,
    StressStatus,
    StressSuiteSummary,
    StressType,
)
from local.stress.runner import StressRunner

__all__ = [
    "StressCase",
    "StressCategory",
    "StressManifest",
    "StressResultStatus",
    "StressRunResult",
    "StressRunner",
    "StressSeverity",
    "StressStatus",
    "StressSuiteSummary",
    "StressType",
]
