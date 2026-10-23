"""Deterministic Runner for IMPULSE Stress Test Suite (Stage 46).

Executes stress test cases independently or in aggregate, measuring execution time,
recording fixture metrics, and strictly distinguishing PASS, FAIL, BLOCKED, and SKIPPED.
"""

from __future__ import annotations

import importlib
import time
from typing import Any, Dict, List, Optional

from local.stress.catalog import get_canonical_catalog
from local.stress.models import (
    StressCase,
    StressResultStatus,
    StressRunResult,
    StressStatus,
    StressSuiteSummary,
    StressType,
)


class StressExecutionError(Exception):
    """Raised when an unexpected error occurs during stress test execution."""


class StressRunner:
    """Executes registered stress test scenarios against isolated fixtures."""

    def __init__(self, catalog: Optional[list[StressCase]] = None) -> None:
        self.catalog = catalog if catalog is not None else get_canonical_catalog()
        self.cases_by_id = {c.stress_id: c for c in self.catalog}

    def list_cases(self) -> list[dict[str, Any]]:
        """Returns structured metadata list of all registered stress cases."""
        return [
            {
                "stress_id": c.stress_id,
                "title": c.title,
                "category": c.category.value if hasattr(c.category, "value") else str(c.category),
                "type": c.stress_type.value if hasattr(c.stress_type, "value") else str(c.stress_type),
                "testing_tier": c.testing_tier,
                "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "terminal_status": c.terminal_status,
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

    def run_case(self, case: StressCase) -> StressRunResult:
        """Executes a single stress case and records structured outcome."""
        start_time = time.perf_counter()

        # 1. Check if DEPRECATED or SKIPPED
        if case.status == StressStatus.DEPRECATED:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return StressRunResult(
                stress_id=case.stress_id,
                status=StressResultStatus.SKIPPED,
                category=case.category.value if hasattr(case.category, "value") else str(case.category),
                stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                testing_tier=case.testing_tier,
                expected_invariants=case.expected_invariants,
                actual_result="Case is deprecated and skipped from active execution.",
                provenance=case.provenance,
                execution_time_ms=elapsed_ms,
            )

        # 2. Check if BLOCKED / LIVE_MODEL_DRIVEN
        if case.status == StressStatus.BLOCKED or case.stress_type == StressType.LIVE_MODEL_DRIVEN:
            try:
                fn = self._resolve_entrypoint(case.execution_entrypoint)
                passed, reason, details = fn()
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return StressRunResult(
                    stress_id=case.stress_id,
                    status=StressResultStatus.FAIL,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                    testing_tier=case.testing_tier,
                    expected_invariants=case.expected_invariants,
                    actual_result="Unexpected error executing blocked checker",
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    error_message=str(e),
                )

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            if not passed and "BLOCKED" in reason:
                return StressRunResult(
                    stress_id=case.stress_id,
                    status=StressResultStatus.BLOCKED,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                    testing_tier=case.testing_tier,
                    expected_invariants=case.expected_invariants,
                    actual_result=reason,
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )
            else:
                return StressRunResult(
                    stress_id=case.stress_id,
                    status=StressResultStatus.FAIL,
                    category=case.category.value if hasattr(case.category, "value") else str(case.category),
                    stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                    testing_tier=case.testing_tier,
                    expected_invariants=case.expected_invariants,
                    actual_result=f"Blocked case unexpectedly passed or failed improperly: {reason}",
                    provenance=case.provenance,
                    execution_time_ms=elapsed_ms,
                    details=details,
                )

        # 3. Active Deterministic or Orchestration stress execution
        try:
            fn = self._resolve_entrypoint(case.execution_entrypoint)
            passed, rationale, details = fn()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            status = StressResultStatus.PASS if passed else StressResultStatus.FAIL
            return StressRunResult(
                stress_id=case.stress_id,
                status=status,
                category=case.category.value if hasattr(case.category, "value") else str(case.category),
                stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                testing_tier=case.testing_tier,
                expected_invariants=case.expected_invariants,
                actual_result=rationale,
                provenance=case.provenance,
                execution_time_ms=elapsed_ms,
                fixture_metrics=details,
                details=details,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return StressRunResult(
                stress_id=case.stress_id,
                status=StressResultStatus.FAIL,
                category=case.category.value if hasattr(case.category, "value") else str(case.category),
                stress_type=case.stress_type.value if hasattr(case.stress_type, "value") else str(case.stress_type),
                testing_tier=case.testing_tier,
                expected_invariants=case.expected_invariants,
                actual_result=f"Stress check raised exception: {type(e).__name__}: {e}",
                provenance=case.provenance,
                execution_time_ms=elapsed_ms,
                error_message=str(e),
            )

    def run_by_id(self, stress_id: str) -> StressRunResult:
        """Executes a single stress case by ID."""
        case = self.cases_by_id.get(stress_id)
        if not case:
            raise KeyError(f"Stress ID '{stress_id}' not found in registered catalog.")
        return self.run_case(case)

    def run_all(
        self,
        filter_category: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> StressSuiteSummary:
        """Executes all (or filtered) registered stress cases and aggregates outcomes."""
        t0 = time.perf_counter()
        results: list[StressRunResult] = []

        to_run = self.catalog
        if filter_category:
            to_run = [
                c for c in to_run
                if (c.category.value if hasattr(c.category, "value") else str(c.category)).upper() == filter_category.upper()
            ]
        if filter_type:
            to_run = [
                c for c in to_run
                if (c.stress_type.value if hasattr(c.stress_type, "value") else str(c.stress_type)).upper() == filter_type.upper()
            ]

        for case in to_run:
            res = self.run_case(case)
            results.append(res)

        total_elapsed_ms = (time.perf_counter() - t0) * 1000.0

        passed = sum(1 for r in results if r.status == StressResultStatus.PASS)
        failed = sum(1 for r in results if r.status == StressResultStatus.FAIL)
        blocked = sum(1 for r in results if r.status == StressResultStatus.BLOCKED)
        skipped = sum(1 for r in results if r.status == StressResultStatus.SKIPPED)

        det_comp = sum(1 for r in results if r.testing_tier == "deterministic_component")
        orch_pol = sum(1 for r in results if r.testing_tier == "orchestration_policy")
        live_model = sum(1 for r in results if r.testing_tier == "live_model_driven")

        live_exec = sum(1 for r in results if r.testing_tier == "live_model_driven" and r.status == StressResultStatus.PASS)
        live_blocked = sum(1 for r in results if r.testing_tier == "live_model_driven" and r.status == StressResultStatus.BLOCKED)

        return StressSuiteSummary(
            schema_version="v1.0.0",
            total_registered=len(self.catalog),
            total_attempted=len(results),
            passed=passed,
            failed=failed,
            blocked=blocked,
            skipped=skipped,
            deterministic_component_count=det_comp,
            orchestration_policy_count=orch_pol,
            live_model_driven_count=live_model,
            live_scenarios_executed=live_exec,
            live_scenarios_blocked=live_blocked,
            total_elapsed_ms=total_elapsed_ms,
            results=results,
        )
