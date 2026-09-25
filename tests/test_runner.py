"""Focused unit tests for the IMPULSE local task runner infrastructure."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from local.runner.artifacts import (
    ArtifactManager,
    PathSecurityError,
    sanitize_component,
    validate_path_safety,
)
from local.runner.cli import extract_candidate_metadata, run_task
from local.runner.executor import (
    DryRunBackend,
    UnavailableLocalBackend,
    get_backend,
)
from local.runner.models import (
    ExecutionResult,
    RunMetadata,
    RunSpec,
    TaskRecord,
)
from local.runner.task_loader import (
    DEFAULT_TASKS_FILE,
    InvalidTaskIdError,
    TaskLoader,
    TaskNotFoundError,
    validate_task_id,
)


class TestTaskLoader(unittest.TestCase):
    """Tests for TaskLoader and task ID validation."""

    def setUp(self) -> None:
        self.loader = TaskLoader(DEFAULT_TASKS_FILE)

    def test_list_tasks(self) -> None:
        task_ids = self.loader.list_task_ids()
        self.assertGreaterEqual(len(task_ids), 1)
        self.assertEqual(len(task_ids), 129)
        self.assertIn("fastapi_15661", task_ids)

    def test_get_valid_task(self) -> None:
        task = self.loader.get_task("fastapi_15661")
        self.assertEqual(task.instance_id, "fastapi_15661")
        self.assertEqual(task.repo, "fastapi/fastapi")
        self.assertEqual(task.base_commit, "ee22a4b8ca46dcce26c8c183afc4992a888d8be2")
        self.assertTrue(len(task.problem_statement) > 0)
        self.assertTrue(task.has_test_patch)

    def test_task_not_found(self) -> None:
        with self.assertRaises(TaskNotFoundError):
            self.loader.get_task("nonexistent_task_99999")

    def test_invalid_task_ids(self) -> None:
        invalid_cases = [
            "",
            "   ",
            "../fastapi_15661",
            "fastapi/15661",
            "fastapi\\15661",
            "task; rm -rf /",
            "task with spaces",
            "a" * 200,  # exceeds length
        ]
        for bad_id in invalid_cases:
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(InvalidTaskIdError):
                    validate_task_id(bad_id)


class TestArtifactManager(unittest.TestCase):
    """Tests for run directory creation, snapshotting, and path safety."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="impulse_test_artifacts_"))
        self.manager = ArtifactManager(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_run_directory_format(self) -> None:
        dt = datetime(2026, 9, 25, 12, 30, 45, tzinfo=timezone.utc)
        run_dir = self.manager.create_run_directory("E0", "fastapi_15661", timestamp=dt)
        self.assertTrue(run_dir.exists())
        self.assertEqual(run_dir.name, "20260925-123045-E0-fastapi_15661")
        self.assertTrue((run_dir / "logs").exists())
        self.assertTrue((run_dir / "candidate_snapshot").exists())

    def test_collision_resistance(self) -> None:
        dt = datetime(2026, 9, 25, 12, 30, 45, tzinfo=timezone.utc)
        dir1 = self.manager.create_run_directory("E0", "fastapi_15661", timestamp=dt)
        dir2 = self.manager.create_run_directory("E0", "fastapi_15661", timestamp=dt)
        self.assertNotEqual(dir1, dir2)
        self.assertEqual(dir2.name, "20260925-123045-E0-fastapi_15661-1")

    def test_path_safety_validation(self) -> None:
        sub_dir = self.temp_dir / "valid_child"
        validate_path_safety(self.temp_dir, sub_dir)

        outside_dir = Path(tempfile.gettempdir())
        if outside_dir.resolve() != self.temp_dir.resolve():
            with self.assertRaises(PathSecurityError):
                validate_path_safety(self.temp_dir, outside_dir)

    def test_sanitize_component(self) -> None:
        self.assertEqual(sanitize_component("normal-name_1"), "normal-name_1")
        self.assertEqual(sanitize_component("../../etc/passwd"), "______etc_passwd")
        self.assertEqual(sanitize_component("   "), "unknown")


class TestExecutionBackends(unittest.TestCase):
    """Tests for execution backend behavior and registry."""

    def test_backend_registry(self) -> None:
        b1 = get_backend("unavailable")
        self.assertIsInstance(b1, UnavailableLocalBackend)
        b2 = get_backend("local-unavailable")
        self.assertIsInstance(b2, UnavailableLocalBackend)
        b3 = get_backend("dry-run")
        self.assertIsInstance(b3, DryRunBackend)

        with self.assertRaises(ValueError):
            get_backend("nonexistent_backend")

    def test_unavailable_backend_does_not_fabricate(self) -> None:
        backend = UnavailableLocalBackend()
        spec = RunSpec(
            task_id="fastapi_15661",
            candidate_id="E0",
            candidate_dir=Path("agent"),
        )
        task = TaskRecord(
            instance_id="fastapi_15661",
            repo="fastapi/fastapi",
            base_commit="abc",
            problem_statement="test issue",
        )
        result = backend.execute(spec, task, Path("dummy"))
        self.assertEqual(result.status, "execution_unavailable_local_host")
        self.assertIn("L4 GPUs", result.termination_reason)
        self.assertIsNone(result.patch)
        self.assertEqual(result.tool_calls_count, 0)
        self.assertEqual(result.turns_count, 0)


class TestCandidateMetadataAndRun(unittest.TestCase):
    """Tests candidate inspection and full non-executing orchestration."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="impulse_test_run_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_candidate_metadata_e0(self) -> None:
        meta = extract_candidate_metadata(Path("agent"))
        self.assertEqual(meta["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(meta["prompt_id"], "prompts/root.md")
        self.assertEqual(meta["candidate_name"], "impulse_e0_baseline")

    def test_end_to_end_orchestration_unavailable_backend(self) -> None:
        spec = RunSpec(
            task_id="fastapi_15661",
            candidate_id="E0",
            candidate_dir=Path("agent"),
            output_dir=self.temp_dir,
            backend_name="unavailable",
            timeout_seconds=300,
            tool_calls_budget=20,
        )

        metadata = run_task(spec, DEFAULT_TASKS_FILE)

        self.assertEqual(metadata.task_id, "fastapi_15661")
        self.assertEqual(metadata.candidate_id, "E0")
        self.assertEqual(metadata.model_id, "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(metadata.prompt_id, "prompts/root.md")
        self.assertEqual(metadata.execution_backend, "local-unavailable")
        self.assertEqual(metadata.status, "execution_unavailable_local_host")
        self.assertEqual(metadata.timeout_seconds, 300)
        self.assertEqual(metadata.tool_calls_budget, 20)
        self.assertFalse(metadata.patch_generated)

        run_path = Path(metadata.run_dir)
        self.assertTrue(run_path.exists())

        # Verify run.json
        run_json = run_path / "run.json"
        self.assertTrue(run_json.exists())
        with open(run_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["run_id"], metadata.run_id)
        self.assertEqual(data["status"], "execution_unavailable_local_host")

        # Verify task_metadata.json
        task_meta = run_path / "task_metadata.json"
        self.assertTrue(task_meta.exists())
        with open(task_meta, "r", encoding="utf-8") as f:
            tdata = json.load(f)
        self.assertEqual(tdata["instance_id"], "fastapi_15661")

        # Verify candidate snapshot
        snapshot_agent_yaml = run_path / "candidate_snapshot" / "agent.yaml"
        self.assertTrue(snapshot_agent_yaml.exists())

        # Verify logs
        log_file = run_path / "logs" / "runner.log"
        self.assertTrue(log_file.exists())

    def test_end_to_end_orchestration_dry_run_backend(self) -> None:
        spec = RunSpec(
            task_id="fastapi_15661",
            candidate_id="E0",
            candidate_dir=Path("agent"),
            output_dir=self.temp_dir,
            backend_name="dry-run",
        )

        metadata = run_task(spec, DEFAULT_TASKS_FILE)
        self.assertEqual(metadata.status, "dry_run_completed")
        self.assertEqual(metadata.execution_backend, "dry-run")


if __name__ == "__main__":
    unittest.main()
