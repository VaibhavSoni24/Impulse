"""Deterministic Regression Suite Runner (Stage 45 Phase 4).

Executes registered regression cases independently or in aggregate, verifying invariants,
collecting execution telemetry, and strictly distinguishing PASS, FAIL, BLOCKED, and SKIPPED.
"""

from __future__ import annotations

import importlib
import time
from typing import Any, Dict, List, Optional

from local.regressions.catalog import get_canonical_catalog
from local.regressions.errors import RegressionExecutionError
from local.regressions.models import (
    RegressionCase,
    RegressionResultStatus,
    RegressionRunResult,
    RegressionStatus,
    RegressionSuiteSummary,
    RegressionType,
)


class RegressionRunner:
    """Executes regression cases against deterministic repository invariants."""

    def __init__(self, catalog: Optional[list[RegressionCase]] = None) -> None:
        self.catalog = catalog if catalog is not None else get_canonical_catalog()
        self.cases_by_id = {c.regression_id: c for c in self.catalog}

    def list_cases(self) -> list[dict[str, Any]]:
        """Returns structured metadata list of all registered cases."""
        return [
            {
                "regression_id": c.regression_id,
                "title": c.title,
                "category": c.category.value if hasattr(c.category, "value") else str(c.category),
                "type": c.regression_type.value if hasattr(c.regression_type, "value") else str(c.regression_type),
                "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "entrypoint": c.execution_entrypoint,
            }
            for c in self.catalog
        ]

    def _resolve_entrypoint(self, entrypoint_str: str) -> Any:
        """Dynamically imports and returns the callable entrypoint function."""
        if ":" not in entrypoint_str:
            raise ValueError(f"Invalid entrypoint format '{entrypoint_str}'; expected 'module:function'")
        mod_path, func_name = entrypoint_str.split(":", 1)
        mod = importlib.import_module(mod_path)
        func = getattr(mod, func_name)
        return func

    def run_case(self, case: RegressionCase) -> RegressionRunResult:
        """Executes a single regression case and records structured outcome."""
        start_time = time.perf_counter()

        # 1. Check if DEPRECATED or SKIPPED
        if case.status == RegressionStatus.DEPRECATED:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return RegressionRunResult(
                regression_id=case.regression_id,
                status=RegressionResultStatus.SKIPPED,
                category=case.category.value if hasattr(case.category, "value") else str(case.category),
                regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                expected_invariants=case.expected_invariants,
                actual_result="Case is deprecated and skipped from active execution.",
                provenance=case.provenance,
                execution_time_ms=elapsed_ms,
            )

        # 2. Check if UNREPRESENTED_BLOCKED_FAILURE
        if (
            case.regression_type == RegressionType.UNREPRESENTED_BLOCKED_FAILURE
            or case.status == RegressionStatus.BLOCKED
        ):
            try:
                fn = self._resolve_entrypoint(case.execution_entrypoint)
                passed, reason, details = fn()
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return RegressionRunResult(
                    regression_id=case.regression_id,
                    status=RegressionResultStatus.FAIL,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                    expected_invariants=case.expected_invariants,
                    actual_result="Unexpected error executing blocked checker",
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    error_message=str(e),
                )

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            # If the checker honestly returned False with a BLOCKED message, record BLOCKED
            if not passed and "BLOCKED" in reason:
                return RegressionRunResult(
                    regression_id=case.regression_id,
                    status=RegressionResultStatus.BLOCKED,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                    expected_invariants=case.expected_invariants,
                    actual_result=reason,
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )
            else:
                return RegressionRunResult(
                    regression_id=case.regression_id,
                    status=RegressionResultStatus.FAIL,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                    expected_invariants=case.expected_invariants,
                    actual_result=f"Blocked case unexpectedly passed or failed improperly: {reason}",
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )

        # 3. Active HARNESS or INFRASTRUCTURE regression execution
        try:
            fn = self._resolve_entrypoint(case.execution_entrypoint)
            passed, rationale, details = fn()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if passed:
                return RegressionRunResult(
                    regression_id=case.regression_id,
                    status=RegressionResultStatus.PASS,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                    expected_invariants=case.expected_invariants,
                    actual_result=rationale,
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )
            else:
                return RegressionRunResult(
                    regression_id=case.regression_id,
                    status=RegressionResultStatus.FAIL,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                    expected_invariants=case.expected_invariants,
                    actual_result=rationale,
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return RegressionRunResult(
                regression_id=case.regression_id,
                status=RegressionResultStatus.FAIL,
                category=case.category.value if hasattr(case.category, "value") else str(case.category),
                regression_type=case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type),
                expected_invariants=case.expected_invariants,
                actual_result=f"Invariant check raised exception: {type(e).__name__}: {e}",
                provenance=case.provenance,
                execution_time_ms=elapsed_ms,
                error_message=str(e),
            )

    def run_by_id(self, regression_id: str) -> RegressionRunResult:
        """Executes a single regression case looked up by regression_id."""
        case = self.cases_by_id.get(regression_id)
        if not case:
            raise KeyError(f"Regression ID '{regression_id}' not found in registered catalog.")
        return self.run_case(case)

    def run_all(
        self,
        filter_category: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> RegressionSuiteSummary:
        """Executes all (or filtered) registered regression cases and returns an aggregate summary."""
        t0 = time.perf_counter()
        results: list[RegressionRunResult] = []
        passed = 0
        failed = 0
        blocked = 0
        skipped = 0

        for case in self.catalog:
            cat_str = case.category.value if hasattr(case.category, "value") else str(case.category)
            type_str = case.regression_type.value if hasattr(case.regression_type, "value") else str(case.regression_type)

            if filter_category and cat_str.upper() != filter_category.upper():
                continue
            if filter_type and type_str.upper() != filter_type.upper():
                continue

            res = self.run_case(case)
            results.append(res)

            if res.status == RegressionResultStatus.PASS:
                passed += 1
            elif res.status == RegressionResultStatus.FAIL:
                failed += 1
            elif res.status == RegressionResultStatus.BLOCKED:
                blocked += 1
            elif res.status == RegressionResultStatus.SKIPPED:
                skipped += 1

        total_duration = (time.perf_counter() - t0) * 1000.0

        return RegressionSuiteSummary(
            total_run=len(results),
            passed=passed,
            failed=failed,
            blocked=blocked,
            skipped=skipped,
            duration_ms=total_duration,
            results=results,
        )

    def format_summary_report(self, summary: RegressionSuiteSummary) -> str:
        """Formats a concise human-readable text report of the regression run."""
        lines = [
            "=" * 70,
            "IMPULSE STAGE 45 FAILURE REGRESSION SUITE EXECUTION REPORT",
            "=" * 70,
            f"Total Executed: {summary.total_run}",
            f"Passed:         {summary.passed}",
            f"Failed:         {summary.failed}",
            f"Blocked:        {summary.blocked}",
            f"Skipped:        {summary.skipped}",
            f"Duration:       {summary.duration_ms:.2f} ms",
            f"Overall Status: {'SUCCESS' if summary.success else 'FAILED'}",
            "-" * 70,
            f"{'ID':<20} {'CATEGORY':<18} {'STATUS':<10} {'DETAILS'}",
            "-" * 70,
        ]

        for r in summary.results:
            short_res = (r.actual_result or "")[:40]
            lines.append(f"{r.regression_id:<20} {r.category:<18} {r.status.value:<10} {short_res}")

        lines.append("=" * 70)
        return "\n".join(lines)
