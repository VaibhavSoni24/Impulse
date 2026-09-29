"""Clean-Copy Evaluator Integration for FDD (Stage 31 Section 9).

Orchestrates smoke, validation, and held-out evaluation rounds through the authoritative
Stage 28 CleanCopyEvaluator without replacing or bypassing its clean snapshot lifecycle.
Enforces split manifest verification and cryptographic held-out lock checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.hashing import compute_manifest_sha256
from benchmark.splits.held_out_lock import HeldOutViolationError, verify_held_out_lock
from benchmark.splits.manifests import load_manifest, verify_manifest_integrity
from local.clean_copy.adapter import FixtureAgentSpec
from local.clean_copy.evaluator import CleanCopyEvaluator
from local.clean_copy.models import EvaluationRunRecord, ExecutionMode
from local.fdd.models import FailureRecord
from local.fdd.normalization import normalize_failure_record
from local.runner.task_loader import TaskLoader


class FDDEvaluator:
    """Orchestrates FDD evaluation cycles over Stage 28 CleanCopyEvaluator."""

    def __init__(
        self,
        repo_root: Optional[Path | str] = None,
        splits_root: Path | str = Path("benchmark/splits"),
        output_dir: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.splits_root = Path(splits_root)
        self.output_dir = Path(output_dir) if output_dir else Path("runs")
        self.db_path = Path(db_path) if db_path else Path("experiments/evaluation.db")

        self.clean_evaluator = CleanCopyEvaluator(
            repo_root=self.repo_root,
            output_dir=self.output_dir,
            db_path=self.db_path,
        )

    def _verify_split_manifest(self, split_version: str = "v1") -> str:
        """Verifies split manifest integrity and returns its SHA-256 digest."""
        manifest_path = self.splits_root / split_version / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Split manifest not found: {manifest_path}")

        manifest = load_manifest(manifest_path)
        is_valid, errors = verify_manifest_integrity(manifest, self.splits_root / split_version)
        if not is_valid:
            raise ValueError(f"Split manifest integrity check failed: {errors}")

        return compute_manifest_sha256(manifest)

    def _verify_held_out_lock(self, split_version: str = "v1", manifest_sha256: str = "") -> None:
        """Verifies held-out cryptographic lock prior to running held-out confirmation."""
        split_dir = self.splits_root / split_version
        lock_path = split_dir / "held_out.lock"
        file_path = split_dir / "held_out.jsonl"

        if not lock_path.is_file():
            raise HeldOutViolationError(f"Held-out lock file missing: {lock_path}")

        ok, msg = verify_held_out_lock(lock_path, file_path, manifest_sha256)
        if not ok:
            raise HeldOutViolationError(f"Held-out lock verification failed: {msg}")

    def run_smoke(
        self,
        candidate_id: str,
        smoke_tasks: List[str],
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        allow_dirty_baseline: bool = True,
    ) -> Tuple[bool, List[FailureRecord]]:
        """Executes a smoke evaluation round on 1-3 targeted tasks.

        Returns:
            (all_passed, normalized_failure_records)
        """
        if not smoke_tasks:
            return True, []

        records: List[FailureRecord] = []
        all_passed = True

        for task_id in smoke_tasks:
            run_rec = self.clean_evaluator.evaluate_task(
                task_id=task_id,
                candidate_ref=candidate_id,
                mode=mode,
                fixture_spec=fixture_spec,
                allow_dirty_baseline=allow_dirty_baseline,
                persist_db=True,
                split_name="smoke",
            )
            fnorm = normalize_failure_record(run_rec.to_dict(), source_ref=f"smoke:{run_rec.run_id}")
            records.append(fnorm)
            if not run_rec.clean_copy_verified or run_rec.success is False:
                all_passed = False

        return all_passed, records

    def run_validation(
        self,
        candidate_id: str,
        split_name: str = "validation",
        split_version: str = "v1",
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        tasks_limit: Optional[int] = None,
        allow_dirty_baseline: bool = True,
    ) -> List[FailureRecord]:
        """Executes validation split benchmark evaluation using CleanCopyEvaluator."""
        manifest_sha = self._verify_split_manifest(split_version)

        loader = TaskLoader.from_split(
            split_name=split_name,
            split_version=split_version,
            splits_root=self.splits_root,
        )
        task_ids = loader.list_task_ids()
        if tasks_limit is not None and tasks_limit > 0:
            task_ids = task_ids[:tasks_limit]

        records: List[FailureRecord] = []
        for task_id in task_ids:
            run_rec = self.clean_evaluator.evaluate_task(
                task_id=task_id,
                candidate_ref=candidate_id,
                mode=mode,
                fixture_spec=fixture_spec,
                allow_dirty_baseline=allow_dirty_baseline,
                persist_db=True,
                split_name=split_name,
                split_version=split_version,
                split_manifest_sha256=manifest_sha,
            )
            fnorm = normalize_failure_record(run_rec.to_dict(), source_ref=f"val:{run_rec.run_id}")
            records.append(fnorm)

        return records

    def run_held_out(
        self,
        candidate_id: str,
        split_version: str = "v1",
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        tasks_limit: Optional[int] = None,
        allow_dirty_baseline: bool = True,
    ) -> List[FailureRecord]:
        """Executes held-out confirmation evaluation with mandatory cryptographic lock verification."""
        manifest_sha = self._verify_split_manifest(split_version)
        self._verify_held_out_lock(split_version, manifest_sha)

        loader = TaskLoader.from_split(
            split_name="held_out",
            split_version=split_version,
            splits_root=self.splits_root,
        )
        task_ids = loader.list_task_ids()
        if tasks_limit is not None and tasks_limit > 0:
            task_ids = task_ids[:tasks_limit]

        records: List[FailureRecord] = []
        for task_id in task_ids:
            run_rec = self.clean_evaluator.evaluate_task(
                task_id=task_id,
                candidate_ref=candidate_id,
                mode=mode,
                fixture_spec=fixture_spec,
                allow_dirty_baseline=allow_dirty_baseline,
                persist_db=True,
                split_name="held_out",
                split_version=split_version,
                split_manifest_sha256=manifest_sha,
            )
            fnorm = normalize_failure_record(run_rec.to_dict(), source_ref=f"held_out:{run_rec.run_id}")
            records.append(fnorm)

        return records
