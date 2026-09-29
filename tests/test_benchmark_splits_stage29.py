"""Focused unit and integration test suite for Reproducible Benchmark Splits (Stage 29).

Validates:
- Phase 1 & 2: Source audit and schema preservation
- Phase 3 & 15: Source immutability and explicit exclusion handling
- Phase 5 & 10: Deterministic split generation
- Phase 6 & 8: Repository isolation and commit snapshot clustering
- Phase 7: Duplicate and near-duplicate task detection
- Phase 11: Byte-identical reproduction across repeated runs
- Phase 12 & 13: Manifest integrity and canonical task-set hashing
- Phase 14: Cross-split leakage detection and failure classification
- Phase 16: Held-out protection, locking, and tamper detection
- Phase 17: Smoke set integrity and split mapping
- Phase 20 & 21: Source versioning and change detection
- Phase 22: Regeneration safety (FileExistsError without force)
- Phase 26: Stage 28 CleanCopyEvaluator and TaskLoader integration
- Phase 27: Database persistence of split metadata
- Phase 28: Security and path hygiene (no machine paths or credentials)
- Frozen artifact invariance: Stage 24 specialist hashes remain unchanged
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from benchmark.splits.generator import SplitGenerationError, SplitGenerator
from benchmark.splits.hashing import (
    compute_canonical_task_set_hash,
    compute_file_sha256,
    compute_manifest_sha256,
    compute_task_fingerprint,
)
from benchmark.splits.held_out_lock import (
    create_held_out_lock,
    is_held_out_task,
    verify_held_out_lock,
)
from benchmark.splits.leakage import validate_split_leakage
from benchmark.splits.manifests import (
    detect_source_change,
    load_manifest,
    save_manifest,
    verify_manifest_integrity,
)
from benchmark.splits.models import (
    ExclusionRecord,
    SplitManifest,
    SplitName,
    SplitPolicyType,
)
from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import ExecutionMode
from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.evaluation.db import get_connection, init_database
from local.evaluation.queries import list_runs
from local.runner.task_loader import TaskLoader, TaskNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_synthetic_tasks_file(target_path: Path, records: list[dict]) -> None:
    """Helper to write synthetic JSONL benchmark files."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestBenchmarkSplitsStage29(unittest.TestCase):
    """Test matrix for Stage 29 benchmark dataset splits."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)

        # Create basic synthetic source records
        self.synthetic_source = self.test_root / "synthetic_tasks.jsonl"
        self.sample_records = [
            # Repo A (3 tasks, 2 commits)
            {
                "instance_id": "repoA_task1",
                "repo": "orgA/repoA",
                "base_commit": "commit_A1",
                "problem_statement": "Fix issue 1 in Repo A",
                "hints_text": "Check module A",
                "created_at": "2025-01-01T00:00:00Z",
                "patch": "diff A1",
                "test_patch": "test diff A1",
            },
            {
                "instance_id": "repoA_task2",
                "repo": "orgA/repoA",
                "base_commit": "commit_A1",  # Shared commit with task 1
                "problem_statement": "Fix issue 2 in Repo A",
                "hints_text": "Check module A2",
                "created_at": "2025-01-02T00:00:00Z",
                "patch": "diff A2",
                "test_patch": "test diff A2",
            },
            {
                "instance_id": "repoA_task3",
                "repo": "orgA/repoA",
                "base_commit": "commit_A2",
                "problem_statement": "Fix issue 3 in Repo A",
                "hints_text": "Check module A3",
                "created_at": "2025-01-03T00:00:00Z",
                "patch": "diff A3",
                "test_patch": "test diff A3",
            },
            # Repo B (2 tasks, 2 commits)
            {
                "instance_id": "repoB_task1",
                "repo": "orgB/repoB",
                "base_commit": "commit_B1",
                "problem_statement": "Fix issue 1 in Repo B",
                "hints_text": "",
                "created_at": "2025-02-01T00:00:00Z",
                "patch": "diff B1",
                "test_patch": "test diff B1",
            },
            {
                "instance_id": "repoB_task2",
                "repo": "orgB/repoB",
                "base_commit": "commit_B2",
                "problem_statement": "Fix issue 2 in Repo B",
                "hints_text": "",
                "created_at": "2025-02-02T00:00:00Z",
                "patch": "diff B2",
                "test_patch": "test diff B2",
            },
            # Repo C (1 task, 1 commit)
            {
                "instance_id": "repoC_task1",
                "repo": "orgC/repoC",
                "base_commit": "commit_C1",
                "problem_statement": "Fix issue 1 in Repo C",
                "hints_text": "",
                "created_at": "2025-03-01T00:00:00Z",
                "patch": "diff C1",
                "test_patch": "test diff C1",
            },
        ]
        create_synthetic_tasks_file(self.synthetic_source, self.sample_records)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------
    # 1. Source Parsing & Schema Preservation
    # -------------------------------------------------------------
    def test_01_source_parsing_preserves_all_fields(self) -> None:
        """Source loader preserves all canonical fields without stripping."""
        out_dir = self.test_root / "splits_01"
        gen = SplitGenerator(self.synthetic_source, out_dir, policy_type=SplitPolicyType.REPO_DISJOINT)
        records, exclusions = gen.load_and_validate_source()

        self.assertEqual(len(records), 6)
        self.assertEqual(len(exclusions), 0)
        first = records[0]
        self.assertIn("instance_id", first)
        self.assertIn("repo", first)
        self.assertIn("base_commit", first)
        self.assertIn("problem_statement", first)
        self.assertIn("hints_text", first)
        self.assertIn("created_at", first)
        self.assertIn("patch", first)
        self.assertIn("test_patch", first)

    # -------------------------------------------------------------
    # 2. Exclusions & Malformed Record Handling
    # -------------------------------------------------------------
    def test_02_malformed_and_missing_field_records_excluded_safely(self) -> None:
        """Malformed JSON lines or missing required fields are explicitly excluded."""
        bad_source = self.test_root / "bad_source.jsonl"
        with open(bad_source, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.sample_records[0]) + "\n")
            f.write("NOT_VALID_JSON\n")
            f.write(json.dumps({"repo": "orgX/repoX", "base_commit": "c1"}) + "\n")  # Missing instance_id
            f.write(json.dumps({"instance_id": "missing_repo", "base_commit": "c1"}) + "\n")  # Missing repo
            f.write(json.dumps({"instance_id": "missing_commit", "repo": "orgY/repoY"}) + "\n")  # Missing base_commit

        gen = SplitGenerator(bad_source, self.test_root / "splits_bad")
        records, exclusions = gen.load_and_validate_source()

        self.assertEqual(len(records), 1)
        self.assertEqual(len(exclusions), 4)
        reasons = [e.reason for e in exclusions]
        self.assertTrue(any("JSON decode failure" in r for r in reasons))
        self.assertTrue(any("instance_id" in r for r in reasons))
        self.assertTrue(any("repo" in r for r in reasons))
        self.assertTrue(any("base_commit" in r for r in reasons))

    def test_03_duplicate_task_id_in_source_excluded(self) -> None:
        """Duplicate task IDs in the source are detected and quarantined into exclusions."""
        dup_source = self.test_root / "dup_source.jsonl"
        with open(dup_source, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.sample_records[0]) + "\n")
            f.write(json.dumps(self.sample_records[0]) + "\n")  # Exact duplicate ID

        gen = SplitGenerator(dup_source, self.test_root / "splits_dup")
        records, exclusions = gen.load_and_validate_source()

        self.assertEqual(len(records), 1)
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0].policy_rule, "SOURCE_DUPLICATE_REJECTION")

    # -------------------------------------------------------------
    # 3. REPO_DISJOINT Policy Execution
    # -------------------------------------------------------------
    def test_04_repo_disjoint_policy_guarantees_zero_repo_leakage(self) -> None:
        """REPO_DISJOINT policy partitions repositories with zero cross-split overlap."""
        out_dir = self.test_root / "splits_disjoint"
        gen = SplitGenerator(self.synthetic_source, out_dir, policy_type=SplitPolicyType.REPO_DISJOINT)
        manifest = gen.generate()

        self.assertTrue((out_dir / "dev.jsonl").is_file())
        self.assertTrue((out_dir / "validation.jsonl").is_file())
        self.assertTrue((out_dir / "held_out.jsonl").is_file())
        self.assertTrue((out_dir / "manifest.json").is_file())

        dev_repos = set(manifest.splits["dev"].repo_counts.keys())
        val_repos = set(manifest.splits["validation"].repo_counts.keys())
        held_repos = set(manifest.splits["held_out"].repo_counts.keys())

        # Pairwise disjoint
        self.assertEqual(dev_repos.intersection(val_repos), set())
        self.assertEqual(dev_repos.intersection(held_repos), set())
        self.assertEqual(val_repos.intersection(held_repos), set())

        # Total count preserved
        total_split_tasks = sum(s.task_count for s in manifest.splits.values())
        self.assertEqual(total_split_tasks, len(self.sample_records))

    # -------------------------------------------------------------
    # 4. Commit Snapshot Clustering
    # -------------------------------------------------------------
    def test_05_shared_commit_tasks_never_cross_splits(self) -> None:
        """Tasks sharing a base commit are clustered and never split across boundaries."""
        out_dir = self.test_root / "splits_commit_cluster"
        gen = SplitGenerator(self.synthetic_source, out_dir, policy_type=SplitPolicyType.STRATIFIED_COMMIT_ISOLATED)
        manifest = gen.generate()

        # In sample_records, repoA_task1 and repoA_task2 share commit_A1
        task_split = {}
        for s_name, s_info in manifest.splits.items():
            for tid in s_info.task_ids:
                task_split[tid] = s_name

        self.assertEqual(
            task_split["repoA_task1"],
            task_split["repoA_task2"],
            "Tasks sharing commit_A1 must be in the same split!",
        )

    # -------------------------------------------------------------
    # 5. Deterministic Regeneration & Byte-Identical Reproduction
    # -------------------------------------------------------------
    def test_06_deterministic_regeneration_is_byte_identical(self) -> None:
        """Repeated generation with identical inputs produces byte-identical files and hashes."""
        out_dir1 = self.test_root / "splits_run1"
        out_dir2 = self.test_root / "splits_run2"

        gen1 = SplitGenerator(self.synthetic_source, out_dir1, policy_type=SplitPolicyType.REPO_DISJOINT)
        gen2 = SplitGenerator(self.synthetic_source, out_dir2, policy_type=SplitPolicyType.REPO_DISJOINT)

        m1 = gen1.generate()
        m2 = gen2.generate()

        for split_file in ["dev.jsonl", "validation.jsonl", "held_out.jsonl", "exclusions.json"]:
            f1_bytes = (out_dir1 / split_file).read_bytes()
            f2_bytes = (out_dir2 / split_file).read_bytes()
            self.assertEqual(f1_bytes, f2_bytes, f"Mismatch in {split_file}")

        self.assertEqual(m1.splits["dev"].task_set_sha256, m2.splits["dev"].task_set_sha256)
        self.assertEqual(m1.splits["validation"].task_set_sha256, m2.splits["validation"].task_set_sha256)
        self.assertEqual(m1.splits["held_out"].task_set_sha256, m2.splits["held_out"].task_set_sha256)

    # -------------------------------------------------------------
    # 6. Regeneration Safety
    # -------------------------------------------------------------
    def test_07_regeneration_refuses_overwrite_without_force(self) -> None:
        """SplitGenerator raises FileExistsError if output directory already contains splits."""
        out_dir = self.test_root / "splits_locked"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        gen.generate()

        # Second attempt without force must fail
        with self.assertRaises(FileExistsError):
            gen.generate(force=False)

        # Second attempt with force must succeed
        m2 = gen.generate(force=True)
        self.assertIsNotNone(m2)

    # -------------------------------------------------------------
    # 7. Source Modification Detection
    # -------------------------------------------------------------
    def test_08_detect_source_change_flags_modified_source_dataset(self) -> None:
        """detect_source_change flags when the underlying dataset file content has changed."""
        out_dir = self.test_root / "splits_source_detect"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        manifest = gen.generate()

        # Unmodified check
        changed, msg = detect_source_change(manifest, self.synthetic_source)
        self.assertFalse(changed)

        # Mutate source
        mutated_source = self.test_root / "mutated_tasks.jsonl"
        create_synthetic_tasks_file(mutated_source, self.sample_records[:2])
        changed, msg = detect_source_change(manifest, mutated_source)
        self.assertTrue(changed)
        self.assertIn("Source dataset modified", msg)

    # -------------------------------------------------------------
    # 8. Manifest Integrity Verification
    # -------------------------------------------------------------
    def test_09_verify_manifest_integrity_detects_file_tampering(self) -> None:
        """verify_manifest_integrity validates hashes and detects tampering."""
        out_dir = self.test_root / "splits_tamper"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        manifest = gen.generate()
        manifest_p = out_dir / "manifest.json"

        # Verify clean directory
        valid, errors = verify_manifest_integrity(manifest_p, out_dir)
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

        # Tamper with dev.jsonl
        dev_file = out_dir / "dev.jsonl"
        with open(dev_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"tampered": True}) + "\n")

        valid, errors = verify_manifest_integrity(manifest_p, out_dir)
        self.assertFalse(valid)
        self.assertTrue(any("file_sha256 mismatch" in err or "count mismatch" in err for err in errors))

    # -------------------------------------------------------------
    # 9. Cross-Split Leakage Validator (Injected Failure)
    # -------------------------------------------------------------
    def test_10_leakage_validator_detects_injected_cross_split_task(self) -> None:
        """validate_split_leakage flags cross-split task overlap with FAIL status."""
        splits = {
            "dev": [self.sample_records[0], self.sample_records[1]],
            "validation": [self.sample_records[0]],  # Leaked from dev!
            "held_out": [self.sample_records[3]],
        }
        report = validate_split_leakage(splits, self.sample_records, policy_name="repo_disjoint")

        self.assertEqual(report.status, "FAIL")
        self.assertFalse(report.checks["cross_split_task_disjointness"])
        self.assertIn("repoA_task1", report.cross_split_task_overlap)

    def test_11_leakage_validator_detects_cross_split_commit_overlap(self) -> None:
        """validate_split_leakage flags when tasks sharing a commit cross splits."""
        splits = {
            # repoA_task1 and repoA_task2 share commit_A1
            "dev": [self.sample_records[0]],
            "validation": [self.sample_records[1]],
            "held_out": [self.sample_records[3]],
        }
        report = validate_split_leakage(splits, self.sample_records, policy_name="stratified_commit_isolated")

        self.assertEqual(report.status, "FAIL")
        self.assertFalse(report.checks["commit_snapshot_isolation"])
        self.assertIn("commit_A1", report.cross_split_commit_overlap)

    # -------------------------------------------------------------
    # 10. Held-Out Protection & Locking
    # -------------------------------------------------------------
    def test_12_held_out_lock_creation_and_tamper_detection(self) -> None:
        """Held-out lock correctly registers held-out tasks and detects tampering."""
        out_dir = self.test_root / "splits_lock"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        manifest = gen.generate()

        lock_p = out_dir / "held_out.lock"
        held_out_p = out_dir / "held_out.jsonl"
        self.assertTrue(lock_p.is_file())

        # Verify initial lock
        valid, msg = verify_held_out_lock(lock_p, held_out_p, manifest.manifest_sha256)
        self.assertTrue(valid)

        # Check is_held_out_task
        held_out_ids = manifest.splits["held_out"].task_ids
        for tid in held_out_ids:
            self.assertTrue(is_held_out_task(tid, lock_p))
        dev_id = manifest.splits["dev"].task_ids[0]
        self.assertFalse(is_held_out_task(dev_id, lock_p))

        # Tamper lock with mismatched manifest hash
        valid, msg = verify_held_out_lock(lock_p, held_out_p, "tampered_manifest_hash_12345")
        self.assertFalse(valid)
        self.assertIn("Lock manifest hash mismatch", msg)

    # -------------------------------------------------------------
    # 11. Canonical Task-Set Hash Invariance
    # -------------------------------------------------------------
    def test_13_canonical_task_set_hash_is_invariant_to_order(self) -> None:
        """compute_canonical_task_set_hash yields identical hash regardless of task order."""
        rec1 = self.sample_records[0]
        rec2 = self.sample_records[1]

        h1 = compute_canonical_task_set_hash([rec1, rec2])
        h2 = compute_canonical_task_set_hash([rec2, rec1])
        self.assertEqual(h1, h2)

    # -------------------------------------------------------------
    # 12. Security & Path Hygiene
    # -------------------------------------------------------------
    def test_14_manifest_contains_no_credentials_or_machine_paths(self) -> None:
        """Split manifest does not persist absolute user home paths or sensitive tokens."""
        out_dir = self.test_root / "splits_hygiene"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        manifest = gen.generate()

        manifest_text = json.dumps(manifest.to_dict())
        self.assertNotIn("Users/shubh", manifest_text.replace("\\", "/"))
        self.assertNotIn("api_key", manifest_text.lower())
        self.assertNotIn("token", manifest_text.lower())

    # -------------------------------------------------------------
    # 13. Smoke Set Integrity
    # -------------------------------------------------------------
    def test_15_smoke_benchmark_tasks_file_unmodified(self) -> None:
        """benchmark/tasks/smoke.jsonl remains untouched and contains 5 tasks."""
        smoke_file = PROJECT_ROOT / "benchmark" / "tasks" / "smoke.jsonl"
        self.assertTrue(smoke_file.is_file())
        with open(smoke_file, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 5)

    # -------------------------------------------------------------
    # 14. TaskLoader Integration (Stage 28)
    # -------------------------------------------------------------
    def test_16_task_loader_from_split_loads_tasks(self) -> None:
        """TaskLoader.from_split loads tasks directly from split files."""
        out_dir = self.test_root / "splits_loader"
        gen = SplitGenerator(self.synthetic_source, out_dir)
        gen.generate()

        loader_dev = TaskLoader.from_split("dev", split_version="splits_loader", splits_root=self.test_root)
        dev_ids = loader_dev.list_task_ids()
        self.assertGreater(len(dev_ids), 0)

        task = loader_dev.get_task(dev_ids[0])
        self.assertEqual(task.instance_id, dev_ids[0])

        with self.assertRaises(TaskNotFoundError):
            TaskLoader.from_split("non_existent_split", splits_root=self.test_root)

    # -------------------------------------------------------------
    # 15. CleanCopyEvaluator Integration (Stage 28)
    # -------------------------------------------------------------
    def test_17_clean_copy_evaluator_evaluates_task_with_split_context(self) -> None:
        """CleanCopyEvaluator accepts split_name and records split metadata in run record."""
        eval_db = self.test_root / "eval_test.db"
        init_database(eval_db)

        evaluator = CleanCopyEvaluator(
            repo_root=PROJECT_ROOT,
            tasks_file=self.synthetic_source,
            output_dir=self.test_root / "runs",
            db_path=eval_db,
        )

        record = evaluator.evaluate_task(
            task_id="repoA_task1",
            candidate_ref="M0",
            baseline_commit=PROJECT_ROOT.resolve(),
            mode=ExecutionMode.FIXTURE,
            allow_dirty_baseline=True,
            persist_db=True,
            split_name="dev",
            split_version="v1",
            split_manifest_sha256="test_manifest_sha256",
        )

        self.assertEqual(record.split_name, "dev")
        self.assertEqual(record.split_version, "v1")
        self.assertEqual(record.split_manifest_sha256, "test_manifest_sha256")

        # Query database to confirm persistence
        conn = get_connection(eval_db)
        runs = list_runs(conn, task_id="repoA_task1")
        self.assertEqual(len(runs), 1)
        db_run = runs[0]
        self.assertEqual(db_run["split_name"], "dev")
        self.assertEqual(db_run["split_version"], "v1")
        self.assertEqual(db_run["split_manifest_sha256"], "test_manifest_sha256")

    # -------------------------------------------------------------
    # 16. Actual Competition Dataset Verification
    # -------------------------------------------------------------
    def test_18_actual_competition_dataset_canonical_v1_split(self) -> None:
        """Verifies canonical benchmark/splits/v1 generated from actual competition dataset."""
        v1_dir = PROJECT_ROOT / "benchmark" / "splits" / "v1"
        manifest_p = v1_dir / "manifest.json"
        self.assertTrue(manifest_p.is_file(), "Canonical v1 manifest must exist")

        valid, errors = verify_manifest_integrity(manifest_p, v1_dir)
        self.assertTrue(valid, f"Canonical v1 manifest integrity failed: {errors}")

        manifest = load_manifest(manifest_p)
        self.assertEqual(manifest.source.record_count, 129)
        self.assertEqual(manifest.source.source_sha256, "e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6")
        self.assertEqual(manifest.splits["dev"].task_count, 67)
        self.assertEqual(manifest.splits["validation"].task_count, 48)
        self.assertEqual(manifest.splits["held_out"].task_count, 14)
        self.assertEqual(len(manifest.exclusions), 0)

        # Held out lock check
        lock_p = v1_dir / "held_out.lock"
        held_out_p = v1_dir / "held_out.jsonl"
        lock_valid, lock_msg = verify_held_out_lock(lock_p, held_out_p, manifest.manifest_sha256)
        self.assertTrue(lock_valid, f"Held out lock failed: {lock_msg}")

    # -------------------------------------------------------------
    # 17. Frozen Artifact Verification
    # -------------------------------------------------------------
    def test_19_frozen_stage24_artifacts_strictly_invariant(self) -> None:
        """All Stage 24 authoritative hashes remain unchanged."""
        ok, details = verify_frozen_artifacts(PROJECT_ROOT)
        self.assertTrue(ok, f"Frozen artifact verification failed: {details}")
        for path, det in details.items():
            self.assertEqual(det["status"], "MATCH", f"Mismatch in {path}")

    # -------------------------------------------------------------
    # 18. Stratified Commit-Isolated Policy Test
    # -------------------------------------------------------------
    def test_20_stratified_commit_isolated_distribution(self) -> None:
        """STRATIFIED_COMMIT_ISOLATED partitions repositories while keeping commit clusters intact."""
        out_dir = self.test_root / "splits_stratified"
        gen = SplitGenerator(self.synthetic_source, out_dir, policy_type=SplitPolicyType.STRATIFIED_COMMIT_ISOLATED)
        manifest = gen.generate()

        self.assertIsNotNone(manifest)
        total = sum(s.task_count for s in manifest.splits.values())
        self.assertEqual(total, len(self.sample_records))

        # Check commit snapshot isolation
        report = validate_split_leakage(
            splits={s: [r for r in self.sample_records if r["instance_id"] in info.task_ids] for s, info in manifest.splits.items()},
            source_records=self.sample_records,
            policy_name=SplitPolicyType.STRATIFIED_COMMIT_ISOLATED.value,
        )
        self.assertEqual(report.status, "PASS")
        self.assertTrue(report.checks["commit_snapshot_isolation"])

    # -------------------------------------------------------------
    # 19. Held-Out Task Query Safeguard
    # -------------------------------------------------------------
    def test_21_is_held_out_task_safeguard(self) -> None:
        """is_held_out_task reliably returns True for held_out tasks and False otherwise."""
        v1_lock = PROJECT_ROOT / "benchmark" / "splits" / "v1" / "held_out.lock"
        self.assertTrue(v1_lock.is_file())

        # In canonical v1, requests_6629 is held out, fastapi_14479 is dev
        self.assertTrue(is_held_out_task("requests_6629", v1_lock))
        self.assertFalse(is_held_out_task("fastapi_14479", v1_lock))
        self.assertFalse(is_held_out_task("non_existent_task", v1_lock))

    # -------------------------------------------------------------
    # 20. Audit Report Generation
    # -------------------------------------------------------------
    def test_22_audit_reports_generated(self) -> None:
        """Audit reports in JSON and Markdown format are created and valid."""
        v1_dir = PROJECT_ROOT / "benchmark" / "splits" / "v1"
        audit_json_p = v1_dir / "audit_report.json"
        audit_md_p = v1_dir / "audit_report.md"

        self.assertTrue(audit_json_p.is_file())
        self.assertTrue(audit_md_p.is_file())

        with open(audit_json_p, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("leakage_audit", data)
        self.assertIn("distribution", data)
        self.assertEqual(data["leakage_audit"]["status"], "PASS")

        md_content = audit_md_p.read_text(encoding="utf-8")
        self.assertIn("Benchmark Dataset Splits Audit Report", md_content)
        self.assertIn("Audit Status:** PASS", md_content)

    # -------------------------------------------------------------
    # 21. CLI Verification Action
    # -------------------------------------------------------------
    def test_23_cli_generate_and_verify(self) -> None:
        """CLI main method supports --verify and --audit flags cleanly."""
        from scripts.generate_splits import main

        v1_dir = str(PROJECT_ROOT / "benchmark" / "splits" / "v1")
        exit_code_verify = main(["--verify", "--output-dir", v1_dir])
        self.assertEqual(exit_code_verify, 0)

        exit_code_audit = main(["--audit", "--output-dir", v1_dir])
        self.assertEqual(exit_code_audit, 0)

    # -------------------------------------------------------------
    # 22. Smoke Benchmark Mapping
    # -------------------------------------------------------------
    def test_24_smoke_tasks_mapped_to_splits(self) -> None:
        """All 5 smoke tasks from benchmark/tasks/smoke.jsonl exist across v1 splits."""
        smoke_p = PROJECT_ROOT / "benchmark" / "tasks" / "smoke.jsonl"
        with open(smoke_p, "r", encoding="utf-8") as f:
            smoke_tasks = [json.loads(l) for l in f if l.strip()]

        v1_manifest = load_manifest(PROJECT_ROOT / "benchmark" / "splits" / "v1" / "manifest.json")
        dev_ids = set(v1_manifest.splits["dev"].task_ids)
        val_ids = set(v1_manifest.splits["validation"].task_ids)
        held_ids = set(v1_manifest.splits["held_out"].task_ids)

        all_split_ids = dev_ids | val_ids | held_ids

        for st in smoke_tasks:
            tid = st["instance_id"]
            self.assertIn(tid, all_split_ids, f"Smoke task {tid} missing from splits!")
            if st["repo"] == "fastapi/fastapi":
                self.assertIn(tid, dev_ids)
            elif st["repo"] == "Textualize/rich":
                self.assertIn(tid, val_ids)
            elif st["repo"] == "psf/requests":
                self.assertIn(tid, held_ids)


if __name__ == "__main__":
    unittest.main()

