"""Focused unit tests for IMPULSE Stage 45 Failure Regression Suite.

Verifies:
1. Manifest structure, loading, and canonical ordering.
2. Integrity validation: duplicate ID detection, duplicate signature detection.
3. Provenance completeness and tracking.
4. Cryptographic held-out split protection and zero contamination enforcement.
5. Runner semantics: PASS, FAIL, BLOCKED, SKIPPED distinctions.
6. Execution of deterministic invariants across all functional domains.
7. Negative tests: invalid manifests, duplicate IDs, missing provenance, fake passes.
8. Machine-readable JSON output and markdown report generation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from benchmark.splits.held_out_lock import load_held_out_lock
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
from local.regressions.invariants.infrastructure import validate_task_not_held_out
from local.regressions.models import (
    RegressionCase,
    RegressionCategory,
    RegressionManifest,
    RegressionResultStatus,
    RegressionSeverity,
    RegressionStatus,
    RegressionSuiteSummary,
    RegressionType,
)
from local.regressions.reporting import generate_stage45_markdown_report
from local.regressions.runner import RegressionRunner


class TestFailureRegressionStage45(unittest.TestCase):
    """Exhaustive test suite for Stage 45 Failure Regression machinery."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RegressionRunner()
        cls.catalog = get_canonical_catalog()
        cls.manifest = build_regression_manifest(cls.catalog)

    # -------------------------------------------------------------------------
    # 1. Catalog & Manifest Validation
    # -------------------------------------------------------------------------
    def test_canonical_catalog_size_and_counts(self) -> None:
        """Verifies total count of registered cases and distribution across tiers."""
        self.assertEqual(len(self.catalog), 22)
        self.assertEqual(self.manifest.total_cases, 22)

        type_counts = self.manifest.cases_by_type
        self.assertEqual(type_counts.get("HARNESS_REGRESSION"), 19)
        self.assertEqual(type_counts.get("INFRASTRUCTURE_REGRESSION"), 1)
        self.assertEqual(type_counts.get("UNREPRESENTED_BLOCKED_FAILURE"), 2)
        self.assertEqual(type_counts.get("FULL_TASK_REGRESSION", 0), 0)

    def test_canonical_catalog_validation_clean(self) -> None:
        """Verifies that the canonical catalog passes validation with zero errors."""
        is_valid, errors = validate_catalog(self.catalog)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_manifest_sha256_integrity(self) -> None:
        """Verifies deterministic SHA-256 calculation on manifest cases."""
        computed_hash = self.manifest.compute_sha256()
        self.assertEqual(self.manifest.manifest_sha256, computed_hash)
        self.assertTrue(len(self.manifest.manifest_sha256) == 64)

    def test_save_and_load_manifest_from_disk(self) -> None:
        """Verifies roundtrip serialization and verification of manifest on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            save_catalog_to_disk(self.manifest, tmp_path)

            manifest_file = tmp_path / "manifest.json"
            self.assertTrue(manifest_file.is_file())

            # Load back and verify
            loaded = load_manifest_from_disk(manifest_file)
            self.assertEqual(loaded.total_cases, 22)
            self.assertEqual(loaded.manifest_sha256, self.manifest.manifest_sha256)

            # Check individual case files
            cases_dir = tmp_path / "cases"
            self.assertTrue(cases_dir.is_dir())
            case_files = list(cases_dir.glob("*.json"))
            self.assertEqual(len(case_files), 22)

    # -------------------------------------------------------------------------
    # 2. Deduplication & Provenance
    # -------------------------------------------------------------------------
    def test_duplicate_regression_id_rejected(self) -> None:
        """Verifies that registering a duplicate regression ID raises DuplicateRegressionError."""
        cases = [c for c in self.catalog]
        dup_case = copy.deepcopy(cases[0])
        dup_case.signature = "DISTINCT:SIGNATURE"  # different signature, same ID
        corrupt_cases = cases + [dup_case]

        with self.assertRaises(DuplicateRegressionError):
            validate_catalog(corrupt_cases)

    def test_duplicate_failure_signature_rejected(self) -> None:
        """Verifies that registering a duplicate failure signature raises DuplicateRegressionError."""
        cases = [c for c in self.catalog]
        dup_case = copy.deepcopy(cases[0])
        dup_case.regression_id = "REG-DISTINCT-999"  # different ID, same signature
        corrupt_cases = cases + [dup_case]

        with self.assertRaises(DuplicateRegressionError):
            validate_catalog(corrupt_cases)

    def test_all_cases_have_valid_provenance(self) -> None:
        """Verifies that every regression case contains non-empty provenance and source tracking."""
        for case in self.catalog:
            with self.subTest(case_id=case.regression_id):
                self.assertIsInstance(case.provenance, dict)
                self.assertIn("stage", case.provenance)
                self.assertIn("source_file", case.provenance)
                self.assertTrue(len(case.expected_invariants) > 0)
                self.assertTrue(len(case.created_from_commit) > 0)

    # -------------------------------------------------------------------------
    # 3. Held-Out Benchmark Split Protection
    # -------------------------------------------------------------------------
    def test_held_out_protection_gate(self) -> None:
        """Verifies that locked held-out tasks are blocked from regression usage."""
        lock = load_held_out_lock("benchmark/splits/v1/held_out.lock")
        self.assertEqual(lock.held_out_count, 14)

        for task_id in lock.held_out_tasks:
            with self.assertRaises(HeldOutContaminationError):
                validate_task_not_held_out(task_id)

    def test_held_out_leakage_in_catalog_rejected(self) -> None:
        """Verifies that catalog validator detects and rejects held-out task references."""
        lock = load_held_out_lock("benchmark/splits/v1/held_out.lock")
        sample_held_out = lock.held_out_tasks[0]

        cases = [c for c in self.catalog]
        contaminated_case = copy.deepcopy(cases[0])
        contaminated_case.regression_id = "REG-CONTAMINATED-001"
        contaminated_case.signature = "CONTAMINATED:SIGNATURE"
        contaminated_case.description = f"Attempting to evaluate on protected task {sample_held_out}"
        corrupt_cases = cases + [contaminated_case]

        with self.assertRaises(HeldOutContaminationError):
            validate_catalog(corrupt_cases)

    def test_non_held_out_task_allowed(self) -> None:
        """Verifies that development tasks pass the held-out validation cleanly."""
        validate_task_not_held_out("dev_test_suite_task_42")

    # -------------------------------------------------------------------------
    # 4. Runner Semantics: PASS, BLOCKED, FAIL, SKIPPED
    # -------------------------------------------------------------------------
    def test_runner_executes_all_and_reports_success(self) -> None:
        """Verifies that running the complete suite produces SUCCESS with 20 PASS and 2 BLOCKED."""
        summary = self.runner.run_all()
        self.assertEqual(summary.total_run, 22)
        self.assertEqual(summary.passed, 20)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.blocked, 2)
        self.assertEqual(summary.skipped, 0)
        self.assertTrue(summary.success)

    def test_runner_filter_by_category(self) -> None:
        """Verifies category filtering in runner."""
        summary = self.runner.run_all(filter_category="RETRIEVAL")
        self.assertEqual(summary.total_run, 2)
        self.assertEqual(summary.passed, 2)
        for r in summary.results:
            self.assertEqual(r.category, "RETRIEVAL")

    def test_runner_filter_by_type(self) -> None:
        """Verifies type filtering in runner."""
        summary = self.runner.run_all(filter_type="UNREPRESENTED_BLOCKED_FAILURE")
        self.assertEqual(summary.total_run, 2)
        self.assertEqual(summary.blocked, 2)
        self.assertEqual(summary.passed, 0)

    def test_runner_lookup_by_id(self) -> None:
        """Verifies lookup and execution by regression ID."""
        res = self.runner.run_by_id("REG-POLICY-001")
        self.assertEqual(res.regression_id, "REG-POLICY-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_runner_unknown_id_raises_key_error(self) -> None:
        """Verifies that unknown regression ID raises KeyError."""
        with self.assertRaises(KeyError):
            self.runner.run_by_id("REG-NONEXISTENT-999")

    def test_deprecated_case_returns_skipped(self) -> None:
        """Verifies that a DEPRECATED case returns SKIPPED status."""
        case = copy.deepcopy(self.catalog[0])
        case.status = RegressionStatus.DEPRECATED
        res = self.runner.run_case(case)
        self.assertEqual(res.status, RegressionResultStatus.SKIPPED)

    # -------------------------------------------------------------------------
    # 5. Core Invariant Checks
    # -------------------------------------------------------------------------
    def test_invariant_retrieval_weak_semantic(self) -> None:
        res = self.runner.run_by_id("REG-RETRIEVAL-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)
        self.assertIn("EXACT_SEARCH", str(res.details))

    def test_invariant_retrieval_budget_exhaustion(self) -> None:
        res = self.runner.run_by_id("REG-RETRIEVAL-002")
        self.assertEqual(res.status, RegressionResultStatus.PASS)
        self.assertIn("STOP_RETRIEVAL", str(res.details))

    def test_invariant_policy_edit_before_recon(self) -> None:
        res = self.runner.run_by_id("REG-POLICY-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_recovery_all_ten_patterns(self) -> None:
        """Verifies all 10 Stage 35 recovery patterns pass their invariant checks."""
        recovery_ids = [
            "REG-RECOVERY-001",
            "REG-RECOVERY-002",
            "REG-RECOVERY-003",
            "REG-RECOVERY-004",
            "REG-RECOVERY-005",
            "REG-RECOVERY-006",
            "REG-RECOVERY-007",
            "REG-RECOVERY-008",
            "REG-RECOVERY-009",
            "REG-RECOVERY-010",
        ]
        for reg_id in recovery_ids:
            with self.subTest(reg_id=reg_id):
                res = self.runner.run_by_id(reg_id)
                self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_hygiene_temporary_files(self) -> None:
        res = self.runner.run_by_id("REG-HYGIENE-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_diff_unrelated_file(self) -> None:
        res = self.runner.run_by_id("REG-DIFF-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_graph_caller_inspection(self) -> None:
        res = self.runner.run_by_id("REG-GRAPH-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_testing_stop_after_first_red_test(self) -> None:
        res = self.runner.run_by_id("REG-TESTING-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_testing_unconstrained_repo_sweep(self) -> None:
        res = self.runner.run_by_id("REG-TESTING-002")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_submission_without_final_diff(self) -> None:
        res = self.runner.run_by_id("REG-SUBMISSION-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_infrastructure_held_out_protection(self) -> None:
        res = self.runner.run_by_id("REG-BENCHMARK-001")
        self.assertEqual(res.status, RegressionResultStatus.PASS)

    def test_invariant_blocked_cases_honestly_blocked(self) -> None:
        """Verifies that blocked cases remain BLOCKED and are never reported as PASS."""
        res1 = self.runner.run_by_id("REG-BLOCKED-001")
        self.assertEqual(res1.status, RegressionResultStatus.BLOCKED)
        self.assertIn("BLOCKED", res1.actual_result)

        res2 = self.runner.run_by_id("REG-BLOCKED-002")
        self.assertEqual(res2.status, RegressionResultStatus.BLOCKED)
        self.assertIn("BLOCKED", res2.actual_result)

    # -------------------------------------------------------------------------
    # 6. Negative Tests & Error Handling
    # -------------------------------------------------------------------------
    def test_case_with_missing_invariants_fails_validation(self) -> None:
        """Verifies that empty expected_invariants raises InvalidRegressionCaseError."""
        case = copy.deepcopy(self.catalog[0])
        case.regression_id = "REG-EMPTY-INV"
        case.signature = "TEST:EMPTY_INV"
        case.expected_invariants = []

        with self.assertRaises(InvalidRegressionCaseError):
            validate_catalog([case])

    def test_case_with_missing_entrypoint_fails_validation(self) -> None:
        """Verifies that empty execution_entrypoint raises InvalidRegressionCaseError."""
        case = copy.deepcopy(self.catalog[0])
        case.regression_id = "REG-EMPTY-ENTRY"
        case.signature = "TEST:EMPTY_ENTRY"
        case.execution_entrypoint = ""

        with self.assertRaises(InvalidRegressionCaseError):
            validate_catalog([case])

    def test_tampered_manifest_sha256_fails_loading(self) -> None:
        """Verifies that tampering with manifest SHA-256 raises RegressionManifestError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            save_catalog_to_disk(self.manifest, tmp_path)

            manifest_file = tmp_path / "manifest.json"
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Tamper hash
            data["manifest_sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            with self.assertRaises(RegressionManifestError):
                load_manifest_from_disk(manifest_file)

    def test_failing_invariant_produces_fail_status(self) -> None:
        """Verifies that when an invariant raises RegressionExecutionError, status is FAIL."""
        failing_case = RegressionCase(
            regression_id="REG-MOCK-FAIL",
            version="1.0.0",
            title="Mock failing regression",
            category=RegressionCategory.POLICY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="MOCK_FAIL",
            description="Mock failing case for test",
            observed_or_synthetic="synthetic",
            provenance={"stage": "Stage 45", "source_file": "tests"},
            fixture_type="mock",
            expected_invariants=["mock invariant fails"],
            execution_entrypoint="tests.test_failure_regression_stage45:_mock_failing_entrypoint",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit="abc",
            signature="MOCK:FAIL",
        )
        res = self.runner.run_case(failing_case)
        self.assertEqual(res.status, RegressionResultStatus.FAIL)
        self.assertIn("RegressionExecutionError", str(res.actual_result))

    def test_report_generation(self) -> None:
        """Verifies markdown report generation contains all mandatory sections."""
        summary = self.runner.run_all()
        report_md = generate_stage45_markdown_report(
            manifest=self.manifest,
            summary=summary,
            focused_test_count=35,
            full_test_count=1224,
            frozen_artifacts_match=True,
            m0_m5_valid=True,
            git_commit="abc123",
        )
        self.assertIn("STAGE 45 COMPLETE, REGRESSION SUITE VERIFIED", report_md)
        self.assertIn("Parent Commit", report_md)
        self.assertIn("Total Registered Regressions", report_md)
        self.assertIn("Coverage by Failure Category", report_md)
        self.assertIn("Held-Out Protection Result", report_md)
        self.assertIn("Deduplication Result", report_md)
        self.assertIn("14/14 MATCH", report_md)
        self.assertIn("ALL PASSED", report_md)


def _mock_failing_entrypoint() -> tuple[bool, str, dict]:
    raise RegressionExecutionError("Intentional failure for negative testing")


if __name__ == "__main__":
    unittest.main()
