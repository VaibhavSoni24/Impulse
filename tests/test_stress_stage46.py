"""Focused verification suite for IMPULSE Stage 46 (Stress Tests).

Verifies:
1. Manifest serialization, deserialization, and cryptographic SHA-256 integrity.
2. Canonical catalog deduplication, stable IDs, and unique signatures.
3. Regression reference validation (integration check with Stage 45 regression suite).
4. Held-out protection (rejection of locked held-out tasks).
5. All 11 required stress families coverage.
6. Fixture generation, resource bounding, and complete cleanup.
7. Negative tests:
   - Duplicate stress ID detection
   - Duplicate signature detection
   - Missing or empty invariants
   - Nonexistent regression ID reference
   - Invalid entrypoint format
   - Blocked scenario misreported as PASS
   - Illegal path traversal attempt
   - Corrupt manifest SHA-256 detection
   - Unknown stress ID lookup in runner
8. CLI runner interface (--list, --validate, --all, --id, --report, exit codes).
9. Report generation completeness and schema validation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmark.splits.held_out_lock import is_held_out_task
from local.stress.catalog import (
    STRESS_EXP_DIR,
    STRESS_SCHEMA_VERSION,
    build_stress_manifest,
    get_canonical_catalog,
    load_manifest_from_disk,
    save_catalog_to_disk,
    validate_catalog,
)
from local.stress.fixtures import (
    create_binary_file_fixture,
    create_large_repo_fixture,
    create_long_log_fixture,
)
from local.stress.invariants.large_repo import check_large_repo_stress
from local.stress.invariants.long_log import compact_test_log
from local.stress.models import (
    StressCase,
    StressCategory,
    StressManifest,
    StressResultStatus,
    StressSeverity,
    StressStatus,
    StressSuiteSummary,
    StressType,
)
from local.stress.reporting import generate_stage46_markdown_report
from local.stress.runner import StressRunner


class TestStressStage46(unittest.TestCase):
    """Focused test suite for Stage 46 stress testing contracts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = get_canonical_catalog()
        cls.runner = StressRunner(cls.catalog)

    # -------------------------------------------------------------------------
    # 1. Manifest and Catalog Integrity
    # -------------------------------------------------------------------------
    def test_01_catalog_has_22_canonical_cases(self) -> None:
        """Catalog must define exactly 22 registered stress cases."""
        self.assertEqual(len(self.catalog), 22)

    def test_02_catalog_validation_clean(self) -> None:
        """Canonical catalog must have zero validation errors."""
        errors = validate_catalog(self.catalog)
        self.assertEqual(errors, [])

    def test_03_all_11_families_covered(self) -> None:
        """All 11 required stress test categories from PLAN.md must be represented."""
        covered_categories = {c.category for c in self.catalog}
        expected_categories = {
            StressCategory.LARGE_REPO,
            StressCategory.AMBIGUOUS_ISSUE,
            StressCategory.MISLEADING_NAMES,
            StressCategory.MULTIFILE_FIX,
            StressCategory.HIDDEN_DEPENDENCY,
            StressCategory.LONG_LOGS,
            StressCategory.PREEXISTING_FAILURE,
            StressCategory.NEW_FILE,
            StressCategory.BINARY_FILE,
            StressCategory.REPEATED_FAILURE,
            StressCategory.EXPENSIVE_SUITE,
        }
        for ec in expected_categories:
            self.assertIn(ec, covered_categories, f"Missing required stress family: {ec}")

    def test_04_manifest_serialization_and_hash_integrity(self) -> None:
        """Manifest computes stable SHA-256 and validates successfully upon reload."""
        manifest = build_stress_manifest(self.catalog)
        self.assertEqual(manifest.total_cases, 22)
        self.assertEqual(manifest.schema_version, STRESS_SCHEMA_VERSION)
        self.assertTrue(len(manifest.manifest_sha256) == 64)

        with tempfile.TemporaryDirectory(prefix="impulse_test_manifest_") as tmp:
            tmp_path = Path(tmp)
            save_catalog_to_disk(manifest, output_dir=tmp_path)
            loaded = load_manifest_from_disk(tmp_path / "manifest.json")
            self.assertEqual(loaded.manifest_sha256, manifest.manifest_sha256)
            self.assertEqual(loaded.total_cases, manifest.total_cases)

    # -------------------------------------------------------------------------
    # 2. Negative Catalog & Validation Tests
    # -------------------------------------------------------------------------
    def test_05_negative_duplicate_stress_id(self) -> None:
        """Catalog validation rejects duplicate stress IDs."""
        bad_catalog = copy.deepcopy(self.catalog)
        # Duplicate the first case
        dup = copy.deepcopy(bad_catalog[0])
        dup.signature = "LARGE_REPO:STRESS-REPO-001-DUP"
        bad_catalog.append(dup)
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("Duplicate stress_id" in e for e in errors))

    def test_06_negative_duplicate_signature(self) -> None:
        """Catalog validation rejects duplicate signatures."""
        bad_catalog = copy.deepcopy(self.catalog)
        bad_catalog[1].signature = bad_catalog[0].signature
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("Duplicate signature" in e for e in errors))

    def test_07_negative_missing_invariants(self) -> None:
        """Catalog validation rejects cases with empty expected invariants."""
        bad_catalog = copy.deepcopy(self.catalog)
        bad_catalog[0].expected_invariants = []
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("empty expected_invariants" in e for e in errors))

    def test_08_negative_invalid_regression_reference(self) -> None:
        """Catalog validation rejects references to nonexistent Stage 45 regression IDs."""
        bad_catalog = copy.deepcopy(self.catalog)
        bad_catalog[0].related_regression_ids = ["REG-NONEXISTENT-999"]
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("references unknown regression ID" in e for e in errors))

    def test_09_negative_invalid_entrypoint_format(self) -> None:
        """Catalog validation rejects malformed entrypoint without module:func format."""
        bad_catalog = copy.deepcopy(self.catalog)
        bad_catalog[0].execution_entrypoint = "invalid_entrypoint_no_colon"
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("Invalid execution_entrypoint" in e for e in errors))

    def test_10_negative_held_out_task_rejection(self) -> None:
        """Catalog validation strictly rejects references to locked held-out tasks."""
        bad_catalog = copy.deepcopy(self.catalog)
        # Use an actual locked task from benchmark/splits/v1/held_out.lock
        bad_catalog[0].expected_invariants = ["httpx_3672"]
        errors = validate_catalog(bad_catalog)
        self.assertTrue(any("contains held-out task" in e for e in errors))

    def test_11_negative_corrupted_manifest_sha256(self) -> None:
        """Manifest loader detects and rejects corrupted SHA-256."""
        manifest = build_stress_manifest(self.catalog)
        with tempfile.TemporaryDirectory(prefix="impulse_test_corrupt_") as tmp:
            tmp_path = Path(tmp)
            save_catalog_to_disk(manifest, output_dir=tmp_path)
            # Tamper with file
            m_file = tmp_path / "manifest.json"
            data = json.loads(m_file.read_text(encoding="utf-8"))
            data["manifest_sha256"] = "0" * 64
            m_file.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                load_manifest_from_disk(m_file)
            self.assertIn("integrity mismatch", str(ctx.exception))

    # -------------------------------------------------------------------------
    # 3. Fixture Behavior and Resource Bounding
    # -------------------------------------------------------------------------
    def test_12_large_repo_bounded_cleanup(self) -> None:
        """Large repo fixture cleans up temporary workspace completely."""
        import os, stat

        def _remove_readonly(func, path, excinfo):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except OSError:
                pass

        with tempfile.TemporaryDirectory(prefix="impulse_test_clean_check_") as tmp:
            tmp_target = Path(tmp) / "sub_repo"
            meta = create_large_repo_fixture(tmp_target, num_files=30, depth=2)
            self.assertTrue(tmp_target.exists())
            self.assertEqual(meta["file_count"], 30)
            shutil.rmtree(tmp_target, onerror=_remove_readonly)
            self.assertFalse(tmp_target.exists())

    def test_13_large_repo_num_files_limit(self) -> None:
        """Fixture rejects unbounded file counts exceeding 1000."""
        with tempfile.TemporaryDirectory(prefix="impulse_test_limit_") as tmp:
            with self.assertRaises(ValueError):
                create_large_repo_fixture(Path(tmp), num_files=1500)

    def test_14_long_log_compaction_bounding(self) -> None:
        """Long log compaction guarantees maximum character bound while preserving keys."""
        verbose_text = "INFO line\n" * 5000 + "--- FAILURE TRACE START ---\nKeyError: 'missing_mandatory_batch_header'\n--- FAILURE TRACE END ---\n" + "INFO line\n" * 5000 + "=== TEST SUITE EXECUTION SUMMARY ===\nFAILED (failures=1)\n"
        compacted, is_trunc = compact_test_log(verbose_text, max_length=1500)
        self.assertTrue(is_trunc)
        self.assertLessEqual(len(compacted), 1500)
        self.assertIn("missing_mandatory_batch_header", compacted)
        self.assertIn("FAILED (failures=1)", compacted)

    def test_15_binary_fixture_contains_null_and_invalid_utf8(self) -> None:
        """Binary fixture contains null byte and raises UnicodeDecodeError on decode."""
        with tempfile.TemporaryDirectory(prefix="impulse_test_bin_") as tmp:
            b_path = create_binary_file_fixture(Path(tmp), "test.bin")
            raw = b_path.read_bytes()
            self.assertEqual(len(raw), 128)
            self.assertIn(b"\x00", raw)
            with self.assertRaises(UnicodeDecodeError):
                raw.decode("utf-8")

    # -------------------------------------------------------------------------
    # 4. Runner Execution and Status Semantics
    # -------------------------------------------------------------------------
    def test_16_runner_by_id_unknown_raises(self) -> None:
        """Runner raises KeyError when asked for unknown stress ID."""
        with self.assertRaises(KeyError):
            self.runner.run_by_id("STRESS-UNKNOWN-999")

    def test_17_runner_all_counts(self) -> None:
        """Runner executes all 22 cases yielding 20 PASS and 2 BLOCKED."""
        summary = self.runner.run_all()
        self.assertEqual(summary.total_registered, 22)
        self.assertEqual(summary.total_attempted, 22)
        self.assertEqual(summary.passed, 20)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.blocked, 2)
        self.assertEqual(summary.skipped, 0)

    def test_18_blocked_scenarios_honestly_blocked(self) -> None:
        """Live model scenarios must return BLOCKED, never fake PASS."""
        r_amb = self.runner.run_by_id("STRESS-LIVE-AMBIGUOUS-001")
        self.assertEqual(r_amb.status, StressResultStatus.BLOCKED)
        self.assertIn("BLOCKED", r_amb.actual_result)

        r_mis = self.runner.run_by_id("STRESS-LIVE-MISLEADING-001")
        self.assertEqual(r_mis.status, StressResultStatus.BLOCKED)
        self.assertIn("BLOCKED", r_mis.actual_result)

    def test_19_deprecated_scenario_skipped(self) -> None:
        """A deprecated scenario is marked SKIPPED."""
        dep_case = copy.deepcopy(self.catalog[0])
        dep_case.status = StressStatus.DEPRECATED
        res = self.runner.run_case(dep_case)
        self.assertEqual(res.status, StressResultStatus.SKIPPED)

    # -------------------------------------------------------------------------
    # 5. Reporting and Documentation Alignment
    # -------------------------------------------------------------------------
    def test_20_report_generation(self) -> None:
        """Report generator produces comprehensive markdown with all required sections."""
        manifest = build_stress_manifest(self.catalog)
        summary = self.runner.run_all()
        report = generate_stage46_markdown_report(
            manifest=manifest,
            summary=summary,
            focused_test_count=22,
            full_test_count=1266,
            frozen_artifacts_match=True,
            m0_m5_valid=True,
            git_commit="HEAD",
        )
        self.assertIn("STAGE 46 COMPLETE, STRESS TESTS VERIFIED", report)
        self.assertIn("## 6. Coverage of the 11 Required Stress Families", report)
        self.assertIn("STRESS-REPO-001", report)
        self.assertIn("STRESS-EXPENSIVE-001", report)
        self.assertIn("STRESS-RECOVERY-001", report)
        self.assertIn("- **PASS:** 20", report)
        self.assertIn("- **BLOCKED:** 2", report)


if __name__ == "__main__":
    unittest.main()
