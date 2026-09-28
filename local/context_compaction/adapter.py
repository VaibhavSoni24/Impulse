"""Integration adapter between Context Compaction and TaskState / E9 / E10 / E11 (Stage 25).

Provides CompactedTaskContext to coordinate file tracking, observation deduplication,
test log compaction, and repository caching with the authoritative TaskState without
altering the semantics or algorithms of E9 (failure classification), E10 (no-progress
detection), or E11 (recovery).
"""

from __future__ import annotations

from typing import Any, Union
from pathlib import Path

from local.context_compaction.file_tracking import ChangedFileTracker
from local.context_compaction.fingerprints import compute_content_sha256
from local.context_compaction.log_compaction import compact_test_log
from local.context_compaction.models import (
    ChangedFileRecord,
    CompactionAction,
    CompactedTestLog,
    CompactObservation,
    FactObservationSummary,
    ObservationType,
)
from local.context_compaction.observation_summary import (
    FactObservationTracker,
    HypothesisTracker,
    ObservationDeduplicator,
)
from local.context_compaction.policy import CompactionPolicy
from local.context_compaction.repo_cache import RepositoryMapCache
from local.failures.models import FailureClassificationContext
from local.progress.models import CycleSnapshot
from local.task_state.models import TaskState


class CompactedTaskContext:
    """Coordinates context compaction while keeping TaskState as authoritative store.
    
    Guarantees:
    - Bounded memory footprint
    - Deterministic observation deduplication
    - Safe test-log compaction preserving all diagnostic lines
    - Seamless bridges to E9 FailureClassificationContext and E10 CycleSnapshot
    """

    def __init__(self, task_state: TaskState | None = None) -> None:
        self.state: TaskState = task_state or TaskState()
        self.file_tracker = ChangedFileTracker()
        self.fact_tracker = FactObservationTracker()
        self.hypothesis_tracker = HypothesisTracker()
        self.deduplicator = ObservationDeduplicator()
        self.repo_cache = RepositoryMapCache()

    def record_file_read(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        note: str = "",
    ) -> tuple[CompactObservation, bool]:
        """Records a file read observation.
        
        Evaluates compaction safety: unchanged files are compacted to a lightweight reference.
        """
        rec, is_new_or_changed = self.file_tracker.record_file_observation(
            path=path,
            content=content,
            observation_note=note,
        )

        action = CompactionAction.SAFE_TO_COMPACT if not is_new_or_changed else CompactionAction.PRESERVE_WITH_STRUCTURE

        obs, is_new_obs = self.deduplicator.record_observation(
            obs_type=ObservationType.FILE_READ,
            action=action,
            source=str(path),
            content=content if isinstance(content, str) else str(content),
            metadata={
                "path": str(path),
                "is_unchanged": not is_new_or_changed,
                "latest_fingerprint": rec.latest_fingerprint,
                "edit_count": rec.edit_count,
            },
        )
        return obs, is_new_or_changed

    def record_file_edit(
        self,
        path: Union[str, Path],
        new_content: Union[str, bytes],
        rationale: str = "",
    ) -> ChangedFileRecord:
        """Records a file edit both in the tracker and in TaskState."""
        rec = self.file_tracker.mark_file_edit(
            path=path,
            new_content=new_content,
            edit_description=rationale,
        )
        self.state.add_edit(
            path=str(path),
            description=f"Edited (rev {rec.edit_count})",
            rationale=rationale,
        )
        # Invalidate repo-map cache if the manifest digest changed
        new_digest = self.file_tracker.get_manifest_digest()
        self.repo_cache.set_current_state(new_digest)
        return rec

    def record_repository_fact(
        self,
        category: str,
        fact_key: str,
        value: str,
    ) -> FactObservationSummary:
        """Records an architectural fact, deduplicating repetitions in TaskState."""
        summary, is_new_or_changed = self.fact_tracker.record_fact(
            category=category,
            fact_key=fact_key,
            value=value,
        )
        # Only add to TaskState if new or changed to avoid unbounded duplicates
        if is_new_or_changed:
            self.state.add_repository_fact(
                category=category,
                fact=f"{fact_key}: {value}",
                source="compacted_fact_tracker",
            )
        return summary

    def record_test_run(
        self,
        command: str,
        exit_code: int,
        stdout: str,
        stderr: str = "",
    ) -> CompactedTestLog:
        """Compacts test output and records structured outcome in TaskState."""
        compact_log = compact_test_log(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

        summary_text = (
            f"Runner: {compact_log.runner} | Exit: {compact_log.exit_code} | "
            f"Failing: {len(compact_log.failing_tests)} | "
            f"Passed: {compact_log.passed_count}"
        )
        if compact_log.error_lines:
            summary_text += f" | Error: {compact_log.error_lines[0][:150]}"

        self.state.add_test(
            command=command,
            outcome=compact_log.outcome,
            summary=summary_text,
        )

        # Record observation
        action = CompactionPolicy.evaluate(
            obs_type=ObservationType.TEST_LOG,
            content=compact_log.preserved_text,
            metadata={
                "exit_code": exit_code,
                "failed_count": compact_log.failed_count,
                "command": command,
            },
        )
        self.deduplicator.record_observation(
            obs_type=ObservationType.TEST_LOG,
            action=action,
            source=command,
            content=compact_log.preserved_text,
            metadata={"exit_code": exit_code, "outcome": compact_log.outcome},
        )

        return compact_log

    def create_failure_classification_context(
        self,
        compact_log: CompactedTestLog,
    ) -> FailureClassificationContext:
        """Bridges a CompactedTestLog to E9 FailureClassificationContext safely."""
        return FailureClassificationContext(
            command=compact_log.command,
            exit_code=compact_log.exit_code,
            stdout=compact_log.preserved_text,
            stderr=compact_log.stderr_summary,
            test_output=compact_log.preserved_text,
        )

    def create_cycle_snapshot(
        self,
        compact_log: CompactedTestLog,
        failure_class: str | None = None,
        cycle_id: str | int = "",
    ) -> CycleSnapshot:
        """Bridges compacted context to an E10 CycleSnapshot for no-progress evaluation."""
        modified = [r.path for r in self.file_tracker.list_changed_files()]
        fail_sig = ""
        if compact_log.failing_tests:
            fail_sig = "::".join(compact_log.failing_tests)
        if compact_log.error_lines:
            fail_sig = f"{fail_sig} | {compact_log.error_lines[0]}" if fail_sig else compact_log.error_lines[0]

        return CycleSnapshot(
            cycle_id=cycle_id,
            test_command=compact_log.command,
            test_result="PASSED" if compact_log.outcome == "PASS" else "FAILED",
            failure_class=failure_class,
            failure_signature=fail_sig,
            hypothesis=self.state.hypothesis,
            modified_files=modified,
            edit_content="; ".join(f"{e.path}:{e.description}" for e in self.state.edits[-3:]),
            evidence_items=[ev.observation for ev in self.state.evidence[-5:]],
            relevant_source_files=modified,
        )
