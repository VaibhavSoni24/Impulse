"""Focused unit and integration test suite for Failure Dashboard & Evaluation Reporting (Stage 30).

Validates:
- Phase 1 & 4: Result normalization and typed RunSummary model
- Phase 5 & 23: Authoritative task-type handling vs. explicit UNAVAILABLE reporting
- Phase 6 & 7: Core metric calculations (overall, per-repo, runtime, tool calls, recovery)
- Phase 8 & 24: Candidate and topology reporting (M0-M5 without premature winner declaration)
- Phase 9 & 10: Human-readable summary.md structure and content
- Phase 11: Deterministic failures.jsonl sorting and field preservation
- Phase 12: Machine-readable metrics.csv generation and null handling
- Phase 13: Dashboard manifest creation with cryptographic artifact hashes
- Phase 14: Failure classification (canonical E9 classes vs. evaluator stages)
- Phase 15 & 16: Split integrity and held-out lock enforcement
- Phase 18: Evidence mode isolation (LIVE, FIXTURE, INFRASTRUCTURE_ONLY, UNAVAILABLE)
- Phase 19: Empty dataset, zero-run, and divide-by-zero prevention
- Phase 20: Deterministic synthetic evaluation fixtures
- Phase 28: Secret scanning and path hygiene (no machine paths or credentials)
- Frozen artifact invariance: Stage 24 specialist hashes remain unchanged
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmark.splits.models import SplitManifest
from local.dashboard.generator import (
    DashboardGenerator,
    render_failures_jsonl,
    render_metrics_csv,
    render_summary_markdown,
    verify_dashboard_artifacts,
)
from local.dashboard.integrity import SplitIntegrityError, verify_split_before_dashboard
from local.dashboard.metrics import (
    aggregate_dashboard_report,
    calculate_metric_stats,
    determine_evidence_mode,
)
from local.dashboard.models import (
    DashboardReport,
    EvidenceMode,
    ReportStatus,
    RunSummary,
)
from local.dashboard.queries import (
    build_tasks_lookup,
    fetch_runs_from_db,
    load_runs_from_jsonl,
    run_row_to_summary,
)
from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_clean_eval_record, ingest_results

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFailureDashboardStage30(unittest.TestCase):
    """Test suite for Stage 30 lightweight failure dashboard reporting."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)

        # Create temporary database
        self.db_path = self.test_root / "test_eval.db"
        init_database(self.db_path)

        # Canonical Stage 29 v1 directory
        self.splits_root = PROJECT_ROOT / "benchmark" / "splits"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. RunSummary Model & Normalization
    # -------------------------------------------------------------------------
    def test_01_run_summary_normalization_preserves_nulls(self) -> None:
        """RunSummary preserves null values and extracts fields cleanly."""
        raw = {
            "run_id": "run_01",
            "candidate_id": "M0",
            "task_id": "fastapi_14786",
            "repo": "fastapi/fastapi",
            "status": "completed",
            "success": 1,
            "elapsed_seconds": 12.5,
            "tool_calls": 4,
            "turns": 3,
            "files_changed": 1,
            "diff_lines": 15,
            "recovery_triggered": False,
            "recovery_success": None,
        }
        summary = run_row_to_summary(raw)
        self.assertEqual(summary.run_id, "run_01")
        self.assertEqual(summary.candidate_id, "M0")
        self.assertEqual(summary.task_id, "fastapi_14786")
        self.assertEqual(summary.repository, "fastapi/fastapi")
        self.assertTrue(summary.success)
        self.assertEqual(summary.elapsed_seconds, 12.5)
        self.assertEqual(summary.tool_calls, 4)
        self.assertEqual(summary.turns, 3)
        self.assertEqual(summary.files_changed, 1)
        self.assertEqual(summary.patch_lines, 15)
        self.assertFalse(summary.recovery_triggered)
        self.assertIsNone(summary.recovery_success)

    def test_02_run_summary_handles_unavailable_and_infrastructure(self) -> None:
        """RunSummary detects UNAVAILABLE and INFRASTRUCTURE_ONLY execution modes."""
        raw_unav = {
            "run_id": "run_unav",
            "candidate_id": "E0",
            "task_id": "fastapi_14479",
            "status": "execution_unavailable_local_host",
            "failure_class": "infrastructure_unavailable",
            "resolved": None,
        }
        summary = run_row_to_summary(raw_unav)
        self.assertEqual(summary.execution_mode, EvidenceMode.UNAVAILABLE.value)
        self.assertIsNone(summary.success)

        raw_infra = {
            "run_id": "run_infra",
            "candidate_id": "E0",
            "task_id": "rich_4070",
            "status": "failed",
            "failure_class": "infrastructure_failure",
            "success": 0,
        }
        summary_infra = run_row_to_summary(raw_infra)
        self.assertEqual(summary_infra.execution_mode, EvidenceMode.INFRASTRUCTURE_ONLY.value)
        self.assertFalse(summary_infra.success)

    # -------------------------------------------------------------------------
    # 2. Metric Calculations: Continuous Statistics
    # -------------------------------------------------------------------------
    def test_03_calculate_metric_stats_computes_correct_percentiles(self) -> None:
        """calculate_metric_stats calculates mean, median, and p95 correctly."""
        # Empty input
        empty_stats = calculate_metric_stats([])
        self.assertEqual(empty_stats.count, 0)
        self.assertIsNone(empty_stats.mean)
        self.assertIsNone(empty_stats.median)
        self.assertIsNone(empty_stats.p95)

        # Non-empty input: 1 to 10
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        stats = calculate_metric_stats(vals)
        self.assertEqual(stats.count, 10)
        self.assertEqual(stats.mean, 5.5)
        self.assertEqual(stats.median, 5.5)
        self.assertEqual(stats.p95, 10.0)
        self.assertEqual(stats.min_val, 1.0)
        self.assertEqual(stats.max_val, 10.0)

    # -------------------------------------------------------------------------
    # 3. Overall Pass Rate & Zero Division Safety
    # -------------------------------------------------------------------------
    def test_04_overall_pass_rate_and_empty_dataset_safety(self) -> None:
        """Overall pass rate is computed accurately and never divides by zero."""
        # Empty runs set
        rep_empty = aggregate_dashboard_report("M0", "dev", [])
        self.assertEqual(rep_empty.report_status, ReportStatus.NO_RESULTS)
        self.assertEqual(rep_empty.total_runs_recorded, 0)
        self.assertIsNone(rep_empty.overall_pass_rate)

        # 4 completed runs: 3 pass, 1 fail
        runs = [
            RunSummary("r1", "M0", "t1", repository="repoA", success=True, elapsed_seconds=10.0, execution_mode="LIVE"),
            RunSummary("r2", "M0", "t2", repository="repoA", success=True, elapsed_seconds=15.0, execution_mode="LIVE"),
            RunSummary("r3", "M0", "t3", repository="repoB", success=True, elapsed_seconds=20.0, execution_mode="LIVE"),
            RunSummary("r4", "M0", "t4", repository="repoB", success=False, elapsed_seconds=25.0, execution_mode="LIVE", failure_class="REGRESSION"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)
        self.assertEqual(rep.eligible_run_count, 4)
        self.assertEqual(rep.completed_run_count, 4)
        self.assertEqual(rep.success_count, 3)
        self.assertEqual(rep.failure_count, 1)
        self.assertEqual(rep.overall_pass_rate, 0.75)
        self.assertEqual(rep.overall_failure_rate, 0.25)
        self.assertEqual(rep.report_status, ReportStatus.FAIL)

    # -------------------------------------------------------------------------
    # 4. Repository Breakdown
    # -------------------------------------------------------------------------
    def test_05_repository_breakdown_aggregates_correctly(self) -> None:
        """Repository metrics group tasks and compute pass rates per repository."""
        runs = [
            RunSummary("r1", "M0", "t1", repository="fastapi/fastapi", success=True, execution_mode="LIVE"),
            RunSummary("r2", "M0", "t2", repository="fastapi/fastapi", success=True, execution_mode="LIVE"),
            RunSummary("r3", "M0", "t3", repository="Textualize/rich", success=False, execution_mode="LIVE", failure_class="INCOMPLETE_FIX"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)
        self.assertEqual(len(rep.repository_results), 2)

        repo_map = {r.repository: r for r in rep.repository_results}
        self.assertIn("fastapi/fastapi", repo_map)
        self.assertIn("Textualize/rich", repo_map)

        fastapi_res = repo_map["fastapi/fastapi"]
        self.assertEqual(fastapi_res.completed_runs, 2)
        self.assertEqual(fastapi_res.passed_runs, 2)
        self.assertEqual(fastapi_res.pass_rate, 1.0)

        rich_res = repo_map["Textualize/rich"]
        self.assertEqual(rich_res.completed_runs, 1)
        self.assertEqual(rich_res.passed_runs, 0)
        self.assertEqual(rich_res.failed_runs, 1)
        self.assertEqual(rich_res.pass_rate, 0.0)

    # -------------------------------------------------------------------------
    # 5. Task-Type Handling (Phase 5 & 23)
    # -------------------------------------------------------------------------
    def test_06_task_type_unvailable_when_no_authoritative_metadata(self) -> None:
        """Task-type section reports UNAVAILABLE when source lacks task_type metadata."""
        runs = [
            RunSummary("r1", "M0", "t1", repository="repoA", task_type=None, success=True, execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)
        self.assertEqual(rep.task_type_status, "UNAVAILABLE")
        self.assertIn("does not provide task-type metadata", rep.task_type_reason)
        self.assertEqual(len(rep.task_type_results), 0)

    def test_07_task_type_available_when_metadata_exists(self) -> None:
        """Task-type section reports per-type metrics when authoritative metadata exists."""
        runs = [
            RunSummary("r1", "M0", "t1", repository="repoA", task_type="bugfix", success=True, execution_mode="LIVE"),
            RunSummary("r2", "M0", "t2", repository="repoA", task_type="bugfix", success=False, execution_mode="LIVE", failure_class="COMMAND"),
            RunSummary("r3", "M0", "t3", repository="repoA", task_type="refactor", success=True, execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)
        self.assertEqual(rep.task_type_status, "AVAILABLE")
        self.assertEqual(len(rep.task_type_results), 2)
        tt_map = {t.task_type: t for t in rep.task_type_results}
        self.assertEqual(tt_map["bugfix"].pass_rate, 0.5)
        self.assertEqual(tt_map["refactor"].pass_rate, 1.0)

    # -------------------------------------------------------------------------
    # 6. Failure Categories: Canonical E9 vs Evaluator Pipeline
    # -------------------------------------------------------------------------
    def test_08_failure_categories_distinguish_canonical_from_evaluator(self) -> None:
        """Separates canonical E9 classes from Stage 28 evaluator infrastructure failures."""
        runs = [
            RunSummary("r1", "M0", "t1", success=False, failure_class="ENVIRONMENT", execution_mode="LIVE"),
            RunSummary("r2", "M0", "t2", success=False, failure_class="REGRESSION", execution_mode="LIVE"),
            RunSummary("r3", "M0", "t3", success=False, failure_class="PATCH_APPLY_CONFLICT", failure_stage="PATCH_APPLICATION", execution_mode="LIVE"),
            RunSummary("r4", "M0", "t4", success=False, failure_class="RUNTIME_UNAVAILABLE", failure_stage="PREPARE", execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)

        canon_cats = {c.category: c.count for c in rep.canonical_failures if c.count > 0}
        self.assertEqual(canon_cats.get("ENVIRONMENT"), 1)
        self.assertEqual(canon_cats.get("REGRESSION"), 1)
        self.assertNotIn("PATCH_APPLY_CONFLICT", canon_cats)

        eval_cats = {e.category: e.count for e in rep.evaluator_failures}
        self.assertIn("PATCH_APPLY_CONFLICT", eval_cats)
        self.assertIn("RUNTIME_UNAVAILABLE", eval_cats)
        self.assertIn("STAGE_PATCH_APPLICATION", eval_cats)
        self.assertIn("STAGE_PREPARE", eval_cats)

    # -------------------------------------------------------------------------
    # 7. Recovery Path & Clean-Copy Metrics
    # -------------------------------------------------------------------------
    def test_09_recovery_and_clean_copy_metrics(self) -> None:
        """Aggregates recovery attempts, recovery success rate, and clean-copy verification."""
        runs = [
            RunSummary("r1", "M0", "t1", success=True, recovery_triggered=True, recovery_success=True, clean_copy_verified=True, execution_mode="LIVE"),
            RunSummary("r2", "M0", "t2", success=False, recovery_triggered=True, recovery_success=False, patch_apply_status="CONFLICT", clean_copy_verified=False, execution_mode="LIVE"),
            RunSummary("r3", "M0", "t3", success=False, recovery_triggered=False, verification_status="FAILED", clean_copy_verified=False, execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M0", "dev", runs)
        self.assertEqual(rep.recovery_attempts, 2)
        self.assertEqual(rep.recovery_successes, 1)
        self.assertEqual(rep.recovery_success_rate, 0.5)
        self.assertEqual(rep.patch_apply_conflicts, 1)
        self.assertEqual(rep.verification_failures, 1)
        self.assertEqual(rep.clean_copy_verified_count, 1)

    # -------------------------------------------------------------------------
    # 8. Evidence Mode Isolation (Phase 18)
    # -------------------------------------------------------------------------
    def test_10_evidence_mode_isolation(self) -> None:
        """FIXTURE and LIVE results are never merged into one pass rate."""
        runs_live = [
            RunSummary("r1", "M0", "t1", success=False, execution_mode="LIVE"),
        ]
        runs_fixture = [
            RunSummary("r2", "M0", "t2", success=True, execution_mode="FIXTURE"),
        ]
        combined = runs_live + runs_fixture

        # When targeted for LIVE, FIXTURE runs are skipped
        rep_live = aggregate_dashboard_report("M0", "dev", combined, target_evidence_mode=EvidenceMode.LIVE)
        self.assertEqual(rep_live.eligible_run_count, 1)
        self.assertEqual(rep_live.skipped_count, 1)
        self.assertEqual(rep_live.overall_pass_rate, 0.0)

        # When targeted for FIXTURE, LIVE runs are skipped
        rep_fix = aggregate_dashboard_report("M0", "dev", combined, target_evidence_mode=EvidenceMode.FIXTURE)
        self.assertEqual(rep_fix.eligible_run_count, 1)
        self.assertEqual(rep_fix.skipped_count, 1)
        self.assertEqual(rep_fix.overall_pass_rate, 1.0)
        self.assertEqual(rep_fix.report_status, ReportStatus.FIXTURE_VERIFIED)

    # -------------------------------------------------------------------------
    # 9. Split Integrity & Held-Out Safety (Phase 15 & 16)
    # -------------------------------------------------------------------------
    def test_11_split_integrity_verification_succeeds_on_canonical_splits(self) -> None:
        """verify_split_before_dashboard successfully verifies canonical Stage 29 v1 splits."""
        manifest, sdir = verify_split_before_dashboard("dev", "v1", self.splits_root)
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.splits["dev"].task_count, 67)

        # Verify held_out verifies held_out.lock
        m_held, _ = verify_split_before_dashboard("held_out", "v1", self.splits_root)
        self.assertIsNotNone(m_held)
        self.assertEqual(m_held.splits["held_out"].task_count, 14)

    def test_12_split_integrity_aborts_on_corrupted_manifest(self) -> None:
        """verify_split_before_dashboard raises SplitIntegrityError if manifest is tampered."""
        fake_splits = self.test_root / "fake_splits" / "v1"
        fake_splits.mkdir(parents=True, exist_ok=True)
        fake_manifest = fake_splits / "manifest.json"
        fake_manifest.write_text(json.dumps({"manifest_version": "1.0.0", "splits": {}}), encoding="utf-8")

        with self.assertRaises(SplitIntegrityError):
            verify_split_before_dashboard("dev", "v1", self.test_root / "fake_splits")

    def test_13_split_integrity_aborts_on_tampered_held_out_lock(self) -> None:
        """verify_split_before_dashboard raises SplitIntegrityError if held_out.lock is invalid."""
        # Copy canonical splits to temp dir
        temp_splits = self.test_root / "temp_splits"
        shutil.copytree(self.splits_root, temp_splits)

        # Tamper held_out.lock
        lock_p = temp_splits / "v1" / "held_out.lock"
        lock_data = json.loads(lock_p.read_text(encoding="utf-8"))
        lock_data["manifest_sha256"] = "tampered_fake_manifest_hash"
        lock_p.write_text(json.dumps(lock_data), encoding="utf-8")

        with self.assertRaises(SplitIntegrityError):
            verify_split_before_dashboard("held_out", "v1", temp_splits)

    # -------------------------------------------------------------------------
    # 10. Deterministic Artifact Generation: summary.md, failures.jsonl, metrics.csv
    # -------------------------------------------------------------------------
    def test_14_dashboard_generator_produces_all_four_artifacts(self) -> None:
        """DashboardGenerator generates summary.md, failures.jsonl, metrics.csv, and manifest.json."""
        out_dir = self.test_root / "dashboard_out"
        gen = DashboardGenerator(
            repo_root=PROJECT_ROOT,
            output_dir=out_dir,
            splits_root=self.splits_root,
            split_version="v1",
        )

        runs = [
            RunSummary("r1", "M0", "fastapi_14479", repository="fastapi/fastapi", success=True, elapsed_seconds=12.0, tool_calls=3, turns=2, execution_mode="LIVE"),
            RunSummary("r2", "M0", "fastapi_14786", repository="fastapi/fastapi", success=False, failure_class="REGRESSION", elapsed_seconds=18.0, tool_calls=5, turns=4, execution_mode="LIVE"),
        ]

        report, target_dir = gen.generate(
            candidate_id="M0",
            split_name="dev",
            runs=runs,
        )

        self.assertTrue((target_dir / "summary.md").is_file())
        self.assertTrue((target_dir / "failures.jsonl").is_file())
        self.assertTrue((target_dir / "metrics.csv").is_file())
        self.assertTrue((target_dir / "manifest.json").is_file())

        # Verify summary content
        summary_txt = (target_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("# Candidate / Split Summary: M0 (DEV)", summary_txt)
        self.assertIn("Pass Rate: **50.0%**", summary_txt)
        self.assertIn("`fastapi/fastapi`", summary_txt)
        self.assertIn("REGRESSION", summary_txt)

        # Verify failures.jsonl content and deterministic sorting
        f_lines = (target_dir / "failures.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(f_lines), 1)
        f_obj = json.loads(f_lines[0])
        self.assertEqual(f_obj["task_id"], "fastapi_14786")
        self.assertEqual(f_obj["failure_class"], "REGRESSION")

        # Verify metrics.csv format
        csv_txt = (target_dir / "metrics.csv").read_text(encoding="utf-8")
        reader = list(csv.reader(csv_txt.splitlines()))
        self.assertEqual(len(reader), 2)  # Header + 1 row
        headers = reader[0]
        row = reader[1]
        self.assertEqual(headers[0], "candidate_id")
        self.assertEqual(row[0], "M0")
        self.assertEqual(row[1], "dev")
        self.assertEqual(row[9], "0.5")  # pass_rate

        # Verify manifest.json
        manifest_obj = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("artifact_hashes", manifest_obj)
        self.assertIn("summary_md", manifest_obj["artifact_hashes"])

    def test_15_deterministic_regeneration_is_byte_identical(self) -> None:
        """Repeated report generation on identical inputs yields byte-identical artifacts."""
        out1 = self.test_root / "dash_run1"
        out2 = self.test_root / "dash_run2"

        gen1 = DashboardGenerator(PROJECT_ROOT, output_dir=out1, splits_root=self.splits_root)
        gen2 = DashboardGenerator(PROJECT_ROOT, output_dir=out2, splits_root=self.splits_root)

        runs = [
            RunSummary("r1", "M1", "fastapi_14479", repository="fastapi/fastapi", success=True, execution_mode="LIVE"),
        ]

        rep1, dir1 = gen1.generate("M1", "dev", runs)
        rep2, dir2 = gen2.generate("M1", "dev", runs)

        # Compare generated files
        for f in ["failures.jsonl", "metrics.csv"]:
            b1 = (dir1 / f).read_bytes()
            b2 = (dir2 / f).read_bytes()
            self.assertEqual(b1, b2, f"Byte mismatch in {f}")

    def test_16_verify_dashboard_artifacts_detects_tampering(self) -> None:
        """verify_dashboard_artifacts validates clean artifacts and catches tampering."""
        out_dir = self.test_root / "dash_tamper"
        gen = DashboardGenerator(PROJECT_ROOT, output_dir=out_dir, splits_root=self.splits_root)

        runs = [
            RunSummary("r1", "M2", "fastapi_14479", repository="fastapi/fastapi", success=True, execution_mode="LIVE"),
        ]
        _, target_dir = gen.generate("M2", "dev", runs)

        valid, errs = verify_dashboard_artifacts(target_dir)
        self.assertTrue(valid, f"Verification failed: {errs}")

        # Tamper metrics.csv
        metrics_p = target_dir / "metrics.csv"
        with open(metrics_p, "a", encoding="utf-8") as f:
            f.write("tampered_row\n")

        valid_tampered, errs_tampered = verify_dashboard_artifacts(target_dir)
        self.assertFalse(valid_tampered)
        self.assertTrue(any("metrics.csv" in e for e in errs_tampered))

    # -------------------------------------------------------------------------
    # 11. Security & Path Hygiene (Phase 28)
    # -------------------------------------------------------------------------
    def test_17_dashboard_reports_leak_no_secrets_or_machine_paths(self) -> None:
        """Artifacts contain no credentials, API keys, or absolute user home paths."""
        out_dir = self.test_root / "dash_security"
        gen = DashboardGenerator(PROJECT_ROOT, output_dir=out_dir, splits_root=self.splits_root)

        runs = [
            RunSummary(
                run_id="sec_run",
                candidate_id="M3",
                task_id="fastapi_14479",
                repository="fastapi/fastapi",
                success=False,
                failure_class="ENVIRONMENT",
                termination_reason="Failed connection to https://api.service.internal",
                execution_mode="LIVE",
            ),
        ]
        _, target_dir = gen.generate("M3", "dev", runs)

        for fname in ["summary.md", "failures.jsonl", "metrics.csv", "manifest.json"]:
            content = (target_dir / fname).read_text(encoding="utf-8")
            self.assertNotIn("Users/shubh", content.replace("\\", "/"))
            self.assertNotIn("password=", content.lower())
            self.assertNotIn("api_key=", content.lower())

    # -------------------------------------------------------------------------
    # 12. Database Integration & Query Correctness
    # -------------------------------------------------------------------------
    def test_18_fetch_runs_from_db_with_split_and_tasks_catalog(self) -> None:
        """fetch_runs_from_db integrates with SQLite DB and resolves task metadata."""
        conn = get_connection(self.db_path)

        # Ingest baseline E0 runs
        baseline_file = PROJECT_ROOT / "experiments" / "baseline" / "E0" / "results.jsonl"
        ingest_results(conn, baseline_file, auto_populate_tasks=False)

        tasks_lookup = build_tasks_lookup(self.splits_root, split_version="v1")
        runs = fetch_runs_from_db(
            conn=conn,
            candidate_id="E0",
            split_name="dev",
            split_version="v1",
            tasks_lookup=tasks_lookup,
        )

        self.assertEqual(len(runs), 2)  # In E0, fastapi_14479 and fastapi_14786 are DEV tasks
        for r in runs:
            self.assertEqual(r.candidate_id, "E0")
            self.assertEqual(r.split_name, "dev")
            self.assertEqual(r.repository, "fastapi/fastapi")
            self.assertEqual(r.execution_mode, EvidenceMode.UNAVAILABLE.value)

        conn.close()

    def test_19_actual_baseline_e0_dashboard_execution(self) -> None:
        """Generates dashboard for actual baseline E0 across dev, validation, and held_out."""
        out_dir = self.test_root / "baseline_dash"
        gen = DashboardGenerator(PROJECT_ROOT, output_dir=out_dir, splits_root=self.splits_root)

        tasks_lookup = build_tasks_lookup(self.splits_root, split_version="v1")
        baseline_file = PROJECT_ROOT / "experiments" / "baseline" / "E0" / "results.jsonl"
        all_runs = load_runs_from_jsonl(baseline_file, tasks_lookup=tasks_lookup)

        # Total 5 runs in baseline E0
        self.assertEqual(len(all_runs), 5)

        # DEV: 2 tasks (fastapi)
        dev_runs = [r for r in all_runs if r.split_name == "dev"]
        self.assertEqual(len(dev_runs), 2)
        rep_dev, _ = gen.generate("E0", "dev", dev_runs)
        self.assertEqual(rep_dev.report_status, ReportStatus.NO_LIVE_RESULTS)
        self.assertEqual(rep_dev.unavailable_count, 2)
        self.assertIsNone(rep_dev.overall_pass_rate)

        # VALIDATION: 1 task (rich)
        val_runs = [r for r in all_runs if r.split_name == "validation"]
        self.assertEqual(len(val_runs), 1)
        rep_val, _ = gen.generate("E0", "validation", val_runs)
        self.assertEqual(rep_val.report_status, ReportStatus.NO_LIVE_RESULTS)
        self.assertEqual(rep_val.unavailable_count, 1)

        # HELD_OUT: 2 tasks (requests)
        held_runs = [r for r in all_runs if r.split_name == "held_out"]
        self.assertEqual(len(held_runs), 2)
        rep_held, _ = gen.generate("E0", "held_out", held_runs)
        self.assertEqual(rep_held.report_status, ReportStatus.NO_LIVE_RESULTS)
        self.assertEqual(rep_held.unavailable_count, 2)

    # -------------------------------------------------------------------------
    # 13. Frozen Artifact Verification
    # -------------------------------------------------------------------------
    def test_20_frozen_stage24_artifacts_strictly_invariant(self) -> None:
        """All Stage 24 authoritative hashes remain unchanged."""
        ok, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertTrue(ok, f"Frozen artifact verification failed: {details}")
        for path, det in details.items():
            self.assertEqual(det["status"], "MATCH", f"Mismatch in {path}")

    # -------------------------------------------------------------------------
    # 14. CLI Integration: Generate, Verify, and JSON
    # -------------------------------------------------------------------------
    def test_21_cli_main_generates_and_verifies_dashboard(self) -> None:
        """CLI main supports generation, verification, and JSON output cleanly."""
        from local.dashboard.cli import main

        out_dir = str(self.test_root / "cli_dash")
        db_path = str(self.db_path)

        # 1. Generate via CLI
        code = main([
            "--candidate", "E0",
            "--split", "dev",
            "--db", db_path,
            "--output-dir", out_dir,
            "--json",
        ])
        self.assertEqual(code, 0)

        # 2. Verify via CLI
        verify_code = main([
            "--verify",
            "--output-dir", str(Path(out_dir) / "E0" / "dev"),
        ])
        self.assertEqual(verify_code, 0)

    # -------------------------------------------------------------------------
    # 15. All-Pass and All-Fail Scenarios
    # -------------------------------------------------------------------------
    def test_22_all_tasks_pass_fixture(self) -> None:
        """Fixture with 100% pass rate reports PASS status."""
        runs = [
            RunSummary("r1", "M4", "fastapi_14479", repository="fastapi/fastapi", success=True, elapsed_seconds=10.0, execution_mode="LIVE"),
            RunSummary("r2", "M4", "fastapi_14786", repository="fastapi/fastapi", success=True, elapsed_seconds=12.0, execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M4", "dev", runs)
        self.assertEqual(rep.overall_pass_rate, 1.0)
        self.assertEqual(rep.overall_failure_rate, 0.0)
        self.assertEqual(rep.report_status, ReportStatus.PASS)

    def test_23_all_tasks_fail_fixture(self) -> None:
        """Fixture with 0% pass rate reports FAIL status."""
        runs = [
            RunSummary("r1", "M5", "fastapi_14479", repository="fastapi/fastapi", success=False, failure_class="INCOMPLETE_FIX", elapsed_seconds=10.0, execution_mode="LIVE"),
            RunSummary("r2", "M5", "fastapi_14786", repository="fastapi/fastapi", success=False, failure_class="REGRESSION", elapsed_seconds=12.0, execution_mode="LIVE"),
        ]
        rep = aggregate_dashboard_report("M5", "dev", runs)
        self.assertEqual(rep.overall_pass_rate, 0.0)
        self.assertEqual(rep.overall_failure_rate, 1.0)
        self.assertEqual(rep.report_status, ReportStatus.FAIL)

    # -------------------------------------------------------------------------
    # 16. Topology Reporting (M0–M5) without Winner Declaration (Phase 8 & 24)
    # -------------------------------------------------------------------------
    def test_24_topology_candidates_m0_to_m5_empty_state(self) -> None:
        """Topology candidates M0-M5 report NO_RESULTS and do NOT declare a winner."""
        out_dir = self.test_root / "topo_dash"
        gen = DashboardGenerator(PROJECT_ROOT, output_dir=out_dir, splits_root=self.splits_root)

        for candidate_id in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            rep, target_dir = gen.generate(candidate_id, "validation", runs=[])
            self.assertEqual(rep.report_status, ReportStatus.NO_RESULTS)
            self.assertEqual(rep.completed_run_count, 0)
            self.assertIsNone(rep.overall_pass_rate)

            summary_text = (target_dir / "summary.md").read_text(encoding="utf-8")
            self.assertNotIn("winning topology", summary_text.lower())
            self.assertNotIn("best topology", summary_text.lower())


if __name__ == "__main__":
    unittest.main()
