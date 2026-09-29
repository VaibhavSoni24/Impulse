"""Clean-Copy Evaluator for IMPULSE (Stage 28).

Orchestrates the authoritative clean-copy evaluation lifecycle:
1. Validate baseline repository cleanliness
2. Create isolated Agent Workspace (Snapshot #1)
3. Load and structurally validate candidate
4. Execute agent via adapter (LIVE, FIXTURE, or UNAVAILABLE)
5. Extract complete PatchBundle (including untracked file intents)
6. Create isolated Validation Workspace (Snapshot #2 from identical baseline)
7. Apply PatchBundle to fresh validation workspace
8. Check semantic patch equivalence
9. Run task verification strictly inside validation workspace
10. Persist structured run artifacts and ingest into SQLite evaluation database
11. Safely dispose of disposable workspaces
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Optional

from local.clean_copy.adapter import AgentExecutionAdapter, FixtureAgentSpec
from local.clean_copy.candidate_loader import CandidateLoader, LoadedCandidate
from local.clean_copy.equivalence import PatchEquivalenceChecker
from local.clean_copy.models import (
    EvaluatorFailureClass,
    EvaluationRunRecord,
    ExecutionMode,
    FailureStage,
    PatchBundle,
)
from local.clean_copy.patch_applier import FreshPatchApplier
from local.clean_copy.patch_extractor import PatchExtractor
from local.clean_copy.snapshot import CleanRepositorySnapshot, SnapshotManager
from local.clean_copy.verifier import CleanCopyVerifier, VerificationResult
from local.evaluation.db import get_connection
from local.runner.task_loader import DEFAULT_TASKS_FILE, TaskLoader, TaskRecord


class CleanCopyEvaluator:
    """Orchestrates end-to-end evaluation against clean repository copies."""

    def __init__(
        self,
        repo_root: Optional[Path | str] = None,
        tasks_file: Optional[Path | str] = None,
        output_dir: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.tasks_file = Path(tasks_file) if tasks_file else DEFAULT_TASKS_FILE
        self.output_dir = Path(output_dir) if output_dir else Path("runs")
        self.db_path = Path(db_path) if db_path else Path("experiments/evaluation.db")

        self.snapshot_mgr = SnapshotManager(self.repo_root)
        self.candidate_loader = CandidateLoader(self.repo_root)
        self.patch_extractor = PatchExtractor()
        self.patch_applier = FreshPatchApplier()
        self.equivalence_checker = PatchEquivalenceChecker()
        self.verifier = CleanCopyVerifier()

    def evaluate_task(
        self,
        task_id: str,
        candidate_ref: str | Path,
        baseline_commit: Optional[str] = None,
        mode: ExecutionMode = ExecutionMode.FIXTURE,
        fixture_spec: Optional[FixtureAgentSpec] = None,
        verification_command: Optional[str] = None,
        allow_dirty_baseline: bool = False,
        persist_db: bool = True,
        split_name: Optional[str] = None,
        split_version: Optional[str] = None,
        split_manifest_sha256: Optional[str] = None,
    ) -> EvaluationRunRecord:
        """Executes full clean-copy evaluation for a single task."""
        start_wall = time.perf_counter()
        start_iso = datetime.now(timezone.utc).isoformat()
        run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{task_id[:16]}"

        record = EvaluationRunRecord(
            run_id=run_id,
            task_id=task_id,
            candidate_id=str(candidate_ref),
            baseline_commit="",
            candidate_config_sha256="",
            start_time=start_iso,
            split_name=split_name or "",
            split_version=split_version or ("v1" if split_name else ""),
            split_manifest_sha256=split_manifest_sha256 or "",
        )

        agent_ws: Optional[CleanRepositorySnapshot] = None
        val_ws: Optional[CleanRepositorySnapshot] = None

        try:
            # 1. Resolve task
            if split_name:
                loader = TaskLoader.from_split(
                    split_name,
                    record.split_version,
                    splits_root=self.repo_root / "benchmark" / "splits",
                )
            else:
                loader = TaskLoader(self.tasks_file)
            try:
                task = loader.get_task(task_id)
            except Exception as e:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.TASK_NOT_FOUND
                record.failure_stage = FailureStage.PREPARE
                record.termination_reason = f"Task lookup failed: {e}"
                return record

            # 2. Resolve & validate candidate
            try:
                candidate = self.candidate_loader.load_candidate(candidate_ref)
                record.candidate_id = candidate.candidate_id
                record.candidate_config_sha256 = candidate.config_sha256
            except Exception as e:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.CANDIDATE_INVALID
                record.failure_stage = FailureStage.CANDIDATE_LOAD
                record.termination_reason = f"Candidate loading failed: {e}"
                return record

            # 3. Create Agent Workspace (Snapshot #1)
            try:
                agent_ws = self.snapshot_mgr.create_snapshot(
                    task_id=task_id,
                    run_id=run_id,
                    baseline_commit=baseline_commit,
                    role="agent",
                    allow_dirty_baseline=allow_dirty_baseline,
                )
                record.baseline_commit = agent_ws.baseline_commit
            except Exception as e:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.BASELINE_NOT_CLEAN if "dirty" in str(e).lower() else EvaluatorFailureClass.BASELINE_NOT_FOUND
                record.failure_stage = FailureStage.PREPARE
                record.termination_reason = f"Failed to create clean agent workspace: {e}"
                return record

            # 4. Execute Agent via Adapter
            adapter = AgentExecutionAdapter(mode=mode, fixture_spec=fixture_spec)
            exec_res = adapter.run(agent_ws, candidate, task)

            record.agent_status = exec_res.status
            record.tool_calls = exec_res.tool_calls_count
            record.turns = exec_res.turns_count

            if exec_res.status == "UNAVAILABLE":
                record.execution_status = "UNAVAILABLE"
                record.failure_class = EvaluatorFailureClass.RUNTIME_UNAVAILABLE
                record.failure_stage = FailureStage.AGENT_EXECUTION
                record.termination_reason = exec_res.termination_reason
                return record

            if exec_res.status != "COMPLETED":
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.AGENT_START_FAILURE
                record.failure_stage = FailureStage.AGENT_EXECUTION
                record.termination_reason = exec_res.termination_reason
                return record

            # 5. Extract Patch
            try:
                bundle = self.patch_extractor.extract_patch(
                    workspace=agent_ws,
                    run_id=run_id,
                    task_id=task_id,
                    candidate_id=candidate.candidate_id,
                )
                record.patch_sha256 = bundle.patch_sha256
                record.files_changed = len(bundle.changed_paths)
                record.patch_lines = len(bundle.tracked_diff.splitlines()) if bundle.tracked_diff else 0
                record.patch_extraction_status = bundle.extraction_status
            except Exception as e:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.PATCH_EXTRACTION_FAILURE
                record.failure_stage = FailureStage.PATCH_EXTRACTION
                record.termination_reason = f"Patch extraction failed: {e}"
                return record

            if bundle.extraction_status == "EMPTY":
                record.execution_status = "COMPLETED"
                record.success = False
                record.patch_apply_status = "SKIPPED"
                record.verification_status = "SKIPPED"
                record.termination_reason = "Agent produced zero workspace modifications; patch is empty."
                return record

            # 6. Create Fresh Validation Workspace (Snapshot #2 from identical baseline commit)
            try:
                val_ws = self.snapshot_mgr.create_snapshot(
                    task_id=task_id,
                    run_id=run_id,
                    baseline_commit=agent_ws.baseline_commit,
                    role="validation",
                    allow_dirty_baseline=allow_dirty_baseline,
                )
            except Exception as e:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.BASELINE_NOT_FOUND
                record.failure_stage = FailureStage.PREPARE
                record.termination_reason = f"Failed to create fresh validation workspace: {e}"
                return record

            # 7. Apply Patch to Fresh Validation Workspace
            applied_ok, apply_msg, applied_diff = self.patch_applier.apply_patch(val_ws, bundle)
            if not applied_ok:
                record.execution_status = "FAILED"
                record.patch_apply_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.PATCH_APPLY_CONFLICT
                record.failure_stage = FailureStage.PATCH_APPLICATION
                record.termination_reason = f"Patch application conflict: {apply_msg}"
                return record

            record.patch_apply_status = "APPLIED"

            # 8. Check Semantic Patch Equivalence
            equiv_ok, equiv_reason = self.equivalence_checker.check_equivalence(
                bundle=bundle,
                agent_root=agent_ws.workspace_dir,
                validation_root=val_ws.workspace_dir,
            )
            if not equiv_ok:
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.PATCH_EQUIVALENCE_FAILURE
                record.failure_stage = FailureStage.PATCH_APPLICATION
                record.termination_reason = f"Patch equivalence failed: {equiv_reason}"
                return record

            # 9. Execute Verification in Fresh Validation Workspace
            ver_res = self.verifier.verify(
                workspace_root=val_ws.workspace_dir,
                task=task,
                custom_command=verification_command,
            )
            record.verification_command = ver_res.command
            record.verification_output = (ver_res.stdout + "\n" + ver_res.stderr).strip()[:10_000]
            record.clean_copy_verified = True

            if ver_res.passed:
                record.verification_status = "PASSED"
                record.success = True
                record.execution_status = "COMPLETED"
                record.termination_reason = "Task resolved: patch cleanly applied and verified in fresh workspace."
            else:
                record.verification_status = "FAILED"
                record.success = False
                record.execution_status = "FAILED"
                record.failure_class = EvaluatorFailureClass.VERIFICATION_TEST_FAILURE
                record.failure_stage = FailureStage.VERIFICATION
                record.termination_reason = ver_res.error_message or "Validation test suite failed."

            return record

        finally:
            record.elapsed_seconds = round(time.perf_counter() - start_wall, 4)
            record.end_time = datetime.now(timezone.utc).isoformat()
            record.compute_manifest_hash()

            # Persist run directory artifacts (Phase 15)
            self._persist_run_artifacts(record, bundle if 'bundle' in locals() else None)

            # Persist into SQLite evaluation database (Phase 16)
            if persist_db:
                self._persist_to_db(record)

            # Cleanup disposable workspaces safely (Phase 18)
            if agent_ws:
                agent_ws.dispose()
            if val_ws:
                val_ws.dispose()

    def _persist_run_artifacts(
        self,
        record: EvaluationRunRecord,
        bundle: Optional[PatchBundle],
    ) -> Path:
        """Persists self-contained execution artifacts into runs/<run_id>/."""
        run_dir = self.output_dir / record.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. manifest.json
        manifest_path = run_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

        # 2. patch directory
        patch_dir = run_dir / "patch"
        patch_dir.mkdir(parents=True, exist_ok=True)
        if bundle:
            (patch_dir / "patch.diff").write_text(bundle.tracked_diff, encoding="utf-8")
            with open(patch_dir / "patch_bundle.json", "w", encoding="utf-8") as f:
                json.dump(bundle.to_dict(), f, indent=2)

        # 3. validation directory
        val_dir = run_dir / "validation"
        val_dir.mkdir(parents=True, exist_ok=True)
        with open(val_dir / "result.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "clean_copy_verified": record.clean_copy_verified,
                    "verification_status": record.verification_status,
                    "command": record.verification_command,
                    "success": record.success,
                },
                f,
                indent=2,
            )
        if record.verification_output:
            (val_dir / "verification.log").write_text(record.verification_output, encoding="utf-8")

        # 4. summary.json
        with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": record.run_id,
                    "task_id": record.task_id,
                    "candidate_id": record.candidate_id,
                    "success": record.success,
                    "execution_status": record.execution_status,
                    "verification_status": record.verification_status,
                    "elapsed_seconds": record.elapsed_seconds,
                    "manifest_hash": record.manifest_hash,
                },
                f,
                indent=2,
            )

        return run_dir

    def _persist_to_db(self, record: EvaluationRunRecord) -> None:
        """Records evaluation outcome in SQLite evaluation database."""
        try:
            from local.evaluation.ingestion import ingest_clean_eval_record
            conn = get_connection(self.db_path)
            try:
                ingest_clean_eval_record(conn, record)
            finally:
                conn.close()
        except Exception:
            # Failure in DB persistence should not crash the evaluator; logged in manifest
            pass
