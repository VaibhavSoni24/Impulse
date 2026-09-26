"""Deterministic No-Progress Detector implementation (Stage 19 / Candidate E10).

Provides NoProgressDetectorV1 to detect when repeated repair and verification
cycles fail to produce meaningful change across configurable cycle thresholds.
"""

from __future__ import annotations

from typing import Any

from local.progress.models import (
    CycleSnapshot,
    NoProgressReason,
    ProgressAssessment,
    ProgressStatus,
    normalize_code_edit,
    normalize_text,
)


class NoProgressDetectorV1:
    """Deterministic, reproducible no-progress detector.

    Identifies lack of meaningful progress across consecutive verification cycles:
    - REPEATED_FAILURE: Same failure signature reproduced without improvement.
    - REPEATED_HYPOTHESIS: Same root-cause hypothesis repeated without new evidence.
    - REPEATED_EDIT: Same or materially equivalent edit attempted without new outcome.
    - NO_NEW_EVIDENCE: Verification repeated with effectively unchanged diagnostic state.

    A single failure never triggers NO_PROGRESS.
    Configurable threshold defaults to 2 consecutive materially equivalent unsuccessful cycles.
    """

    DEFAULT_THRESHOLD: int = 2

    def __init__(self, threshold: int = DEFAULT_THRESHOLD) -> None:
        if threshold < 2:
            raise ValueError(f"Threshold must be at least 2 consecutive cycles, got {threshold}")
        self.threshold = threshold
        self.history: list[CycleSnapshot] = []
        self._consecutive_no_progress_count: int = 0

    @property
    def consecutive_count(self) -> int:
        """Current count of consecutive cycles without progress."""
        return self._consecutive_no_progress_count

    def reset(self) -> None:
        """Resets detector state and cycle history."""
        self.history.clear()
        self._consecutive_no_progress_count = 0

    def record_cycle(self, snapshot: CycleSnapshot) -> ProgressAssessment:
        """Records a new cycle snapshot and assesses progress against history."""
        previous = self.history[-1] if self.history else None
        assessment = self.evaluate_transition(
            previous=previous,
            current=snapshot,
            current_streak=self._consecutive_no_progress_count,
            threshold=self.threshold,
        )
        self.history.append(snapshot)
        self._consecutive_no_progress_count = assessment.consecutive_no_progress_count
        return assessment

    @classmethod
    def evaluate_transition(
        cls,
        previous: CycleSnapshot | None,
        current: CycleSnapshot,
        current_streak: int = 0,
        threshold: int = DEFAULT_THRESHOLD,
    ) -> ProgressAssessment:
        """Stateless evaluation of progress from previous cycle to current cycle."""
        # -------------------------------------------------------------
        # 1. Successful verification resets streak immediately
        # -------------------------------------------------------------
        if current.test_result.upper() == "PASSED":
            return ProgressAssessment(
                status=ProgressStatus.PROGRESS,
                reason=NoProgressReason.NONE,
                consecutive_no_progress_count=0,
                threshold=threshold,
                rationale="Verification passed cleanly; constructive progress confirmed.",
                signals=["Test status: PASSED"],
            )

        # -------------------------------------------------------------
        # 2. Check for insufficient evidence in current snapshot
        # -------------------------------------------------------------
        has_current_signals = bool(
            current.test_command
            or current.test_result
            or current.failure_class
            or current.failure_signature
            or current.edit_content
            or current.modified_files
        )
        if not has_current_signals:
            return ProgressAssessment(
                status=ProgressStatus.INSUFFICIENT_EVIDENCE,
                reason=NoProgressReason.UNKNOWN,
                consecutive_no_progress_count=current_streak,
                threshold=threshold,
                rationale="Snapshot lacks diagnostic or execution signals to assess progress.",
                signals=["Empty snapshot signals"],
            )

        # -------------------------------------------------------------
        # 3. First cycle establishes baseline (single failure != no-progress)
        # -------------------------------------------------------------
        if previous is None:
            return ProgressAssessment(
                status=ProgressStatus.PROGRESS,
                reason=NoProgressReason.NONE,
                consecutive_no_progress_count=1,
                threshold=threshold,
                rationale="Initial cycle established baseline failure state.",
                signals=["Initial cycle recorded"],
            )

        # -------------------------------------------------------------
        # 4. Check for Meaningful Progress Signals
        # -------------------------------------------------------------
        progress_signals: list[str] = []

        # A. Failure class changed because new evidence emerged
        if (
            current.failure_class
            and previous.failure_class
            and current.failure_class != previous.failure_class
        ):
            progress_signals.append(
                f"Failure class changed: {previous.failure_class} -> {current.failure_class}"
            )

        # B. Failing test / signature changed (different failure or test)
        if (
            current.failure_signature
            and previous.failure_signature
            and current.failure_fingerprint() != previous.failure_fingerprint()
        ):
            progress_signals.append("Failing test signature changed")

        # C. Hypothesis changed materially
        if (
            current.hypothesis
            and previous.hypothesis
            and current.hypothesis_fingerprint() != previous.hypothesis_fingerprint()
        ):
            progress_signals.append("Hypothesis changed materially")

        # D. Relevant source files modified changed meaningfully
        prev_relevant = previous.relevant_modified_files()
        curr_relevant = current.relevant_modified_files()
        if curr_relevant and prev_relevant != curr_relevant:
            # Check if actual relevant source files changed
            progress_signals.append(f"Relevant modified files changed: {curr_relevant}")

        # E. Diagnostic evidence fingerprint changed with new observations
        if (
            current.evidence_items
            and len(current.evidence_items) > len(previous.evidence_items)
            and current.evidence_fingerprint() != previous.evidence_fingerprint()
        ):
            progress_signals.append("New diagnostic evidence observations recorded")

        # If any meaningful progress signal was detected:
        if progress_signals:
            return ProgressAssessment(
                status=ProgressStatus.PROGRESS,
                reason=NoProgressReason.NONE,
                consecutive_no_progress_count=1,
                threshold=threshold,
                rationale="Constructive change detected between consecutive cycles.",
                signals=progress_signals,
            )

        # -------------------------------------------------------------
        # 5. No Meaningful Progress Detected: Identify Specific Reason
        # -------------------------------------------------------------
        new_streak = current_streak + 1
        lack_reasons: list[str] = []

        # Check REPEATED_EDIT (whitespace-only or exact same edit)
        is_repeated_edit = False
        if current.edit_content and previous.edit_content:
            norm_curr = normalize_code_edit(current.edit_content)
            norm_prev = normalize_code_edit(previous.edit_content)
            if norm_curr == norm_prev:
                is_repeated_edit = True
                lack_reasons.append("Materially identical or whitespace-only edit repeated")

        # Check REPEATED_HYPOTHESIS
        is_repeated_hypothesis = False
        if (
            current.hypothesis
            and previous.hypothesis
            and current.hypothesis_fingerprint() == previous.hypothesis_fingerprint()
        ):
            is_repeated_hypothesis = True
            lack_reasons.append("Identical hypothesis pursued without revision")

        # Check REPEATED_FAILURE
        is_repeated_failure = False
        if (
            current.failure_signature
            and previous.failure_signature
            and current.failure_fingerprint() == previous.failure_fingerprint()
        ):
            is_repeated_failure = True
            lack_reasons.append("Same failure signature reproduced across cycles")

        # Check NO_NEW_EVIDENCE
        is_no_new_evidence = False
        if current.evidence_fingerprint() == previous.evidence_fingerprint():
            is_no_new_evidence = True
            lack_reasons.append("No new diagnostic evidence appeared")

        # Assign primary canonical reason based on priority
        if is_repeated_edit:
            primary_reason = NoProgressReason.REPEATED_EDIT
        elif is_repeated_hypothesis:
            primary_reason = NoProgressReason.REPEATED_HYPOTHESIS
        elif is_repeated_failure:
            primary_reason = NoProgressReason.REPEATED_FAILURE
        elif is_no_new_evidence:
            primary_reason = NoProgressReason.NO_NEW_EVIDENCE
        else:
            primary_reason = NoProgressReason.REPEATED_FAILURE

        # -------------------------------------------------------------
        # 6. Apply Threshold Boundary
        # -------------------------------------------------------------
        if new_streak >= threshold:
            return ProgressAssessment(
                status=ProgressStatus.NO_PROGRESS,
                reason=primary_reason,
                consecutive_no_progress_count=new_streak,
                threshold=threshold,
                rationale=(
                    f"No meaningful progress detected across {new_streak} consecutive cycles "
                    f"(threshold: {threshold})."
                ),
                signals=lack_reasons,
            )

        # Streak has not yet reached threshold: single repetition
        return ProgressAssessment(
            status=ProgressStatus.PROGRESS,
            reason=NoProgressReason.NONE,
            consecutive_no_progress_count=new_streak,
            threshold=threshold,
            rationale=(
                f"Cycle lacked progress, but consecutive streak ({new_streak}) "
                f"remains below threshold ({threshold})."
            ),
            signals=lack_reasons,
        )
