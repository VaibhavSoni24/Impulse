"""Public API exports for Stage 45 Failure Regression Suite."""

from __future__ import annotations

from local.regressions.catalog import (
    build_regression_manifest,
    get_canonical_catalog,
    load_manifest_from_disk,
    save_catalog_to_disk,
    validate_catalog,
)
from local.regressions.errors import (
    DuplicateRegressionError,
    HeldOutContaminationError,
    InvalidRegressionCaseError,
    RegressionError,
    RegressionExecutionError,
    RegressionManifestError,
)
from local.regressions.models import (
    RegressionCase,
    RegressionCategory,
    RegressionManifest,
    RegressionResultStatus,
    RegressionRunResult,
    RegressionSeverity,
    RegressionStatus,
    RegressionSuiteSummary,
    RegressionType,
)
from local.regressions.reporting import generate_stage45_markdown_report
from local.regressions.runner import RegressionRunner

__all__ = [
    "DuplicateRegressionError",
    "HeldOutContaminationError",
    "InvalidRegressionCaseError",
    "RegressionCase",
    "RegressionCategory",
    "RegressionError",
    "RegressionExecutionError",
    "RegressionManifest",
    "RegressionManifestError",
    "RegressionResultStatus",
    "RegressionRunResult",
    "RegressionRunner",
    "RegressionSeverity",
    "RegressionStatus",
    "RegressionSuiteSummary",
    "RegressionType",
    "build_regression_manifest",
    "generate_stage45_markdown_report",
    "get_canonical_catalog",
    "load_manifest_from_disk",
    "save_catalog_to_disk",
    "validate_catalog",
]
