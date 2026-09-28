"""Data models and output contracts for the Reviewer agent (Stage 23).

Defines:
- ReviewerStatus enum (APPROVE, CHANGES_REQUESTED, INSUFFICIENT_EVIDENCE)
  (Strictly categorical: no numeric scores, confidence ratings, or 0-100 quality scores)
- ReviewerPolicy enum (UNAVAILABLE, AVAILABLE_AT_FINAL_REVIEW)
- ReviewerInput dataclass with bounded input data contract
- ReviewerResult dataclass with structured review findings and TaskState integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from local.task_state.models import TaskState

MAX_SUMMARY_LEN = 500
MAX_ITEMS_COUNT = 20
MAX_INPUT_TEXT_LEN = 2000


class ReviewerStatus(str, Enum):
    """Categorical outcome of Reviewer final assessment.

    No numeric scores or confidence ratings are permitted.
    """

    APPROVE = "APPROVE"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReviewerPolicy(str, Enum):
    """Invocation policy for the Reviewer agent."""

    UNAVAILABLE = "UNAVAILABLE"  # V0: Reviewer unavailable
    AVAILABLE_AT_FINAL_REVIEW = "AVAILABLE_AT_FINAL_REVIEW"  # V1: Reviewer available at final review point


@dataclass
class ReviewerInput:
    """Bounded, structured input contract provided to the Reviewer agent."""

    issue: str = ""
    diff_summary: str = ""
    relevant_tests: list[str] = field(default_factory=list)
    result_summary: str = ""
    modified_files: list[str] = field(default_factory=list)
    failure_classification: str = ""
    verification_status: str = ""
    repository_facts: list[str] = field(default_factory=list)

    def normalize(self) -> ReviewerInput:
        """Returns a sanitized, bounded copy of the input."""
        return ReviewerInput(
            issue=self.issue[:MAX_INPUT_TEXT_LEN],
            diff_summary=self.diff_summary[:MAX_INPUT_TEXT_LEN],
            relevant_tests=list(self.relevant_tests[:MAX_ITEMS_COUNT]),
            result_summary=self.result_summary[:MAX_INPUT_TEXT_LEN],
            modified_files=list(self.modified_files[:MAX_ITEMS_COUNT]),
            failure_classification=self.failure_classification[:MAX_SUMMARY_LEN],
            verification_status=self.verification_status[:MAX_SUMMARY_LEN],
            repository_facts=list(self.repository_facts[:MAX_ITEMS_COUNT]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Converts input contract to dictionary."""
        return {
            "issue": self.issue[:MAX_INPUT_TEXT_LEN],
            "diff_summary": self.diff_summary[:MAX_INPUT_TEXT_LEN],
            "relevant_tests": list(self.relevant_tests[:MAX_ITEMS_COUNT]),
            "result_summary": self.result_summary[:MAX_INPUT_TEXT_LEN],
            "modified_files": list(self.modified_files[:MAX_ITEMS_COUNT]),
            "failure_classification": self.failure_classification[:MAX_SUMMARY_LEN],
            "verification_status": self.verification_status[:MAX_SUMMARY_LEN],
            "repository_facts": list(self.repository_facts[:MAX_ITEMS_COUNT]),
        }


@dataclass
class ReviewerResult:
    """Structured, bounded final review evidence produced by the read-only Reviewer agent."""

    status: ReviewerStatus = ReviewerStatus.INSUFFICIENT_EVIDENCE
    issue_alignment: str = ""
    diff_scope: str = ""
    test_assessment: str = ""
    regression_risk: str = ""
    security_hygiene: str = ""
    blocking_findings: list[str] = field(default_factory=list)
    nonblocking_findings: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    required_followups: list[str] = field(default_factory=list)
    observed_evidence: list[str] = field(default_factory=list)
    inferred_risks: list[str] = field(default_factory=list)
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts ReviewerResult to a serializable dictionary representation."""
        return {
            "status": self.status.value if isinstance(self.status, ReviewerStatus) else str(self.status),
            "issue_alignment": self.issue_alignment[:MAX_SUMMARY_LEN],
            "diff_scope": self.diff_scope[:MAX_SUMMARY_LEN],
            "test_assessment": self.test_assessment[:MAX_SUMMARY_LEN],
            "regression_risk": self.regression_risk[:MAX_SUMMARY_LEN],
            "security_hygiene": self.security_hygiene[:MAX_SUMMARY_LEN],
            "blocking_findings": list(self.blocking_findings[:MAX_ITEMS_COUNT]),
            "nonblocking_findings": list(self.nonblocking_findings[:MAX_ITEMS_COUNT]),
            "missing_evidence": list(self.missing_evidence[:MAX_ITEMS_COUNT]),
            "required_followups": list(self.required_followups[:MAX_ITEMS_COUNT]),
            "observed_evidence": list(self.observed_evidence[:MAX_ITEMS_COUNT]),
            "inferred_risks": list(self.inferred_risks[:MAX_ITEMS_COUNT]),
            "summary": self.summary[:MAX_SUMMARY_LEN],
            "timestamp": self.timestamp,
        }

    def format_summary(self) -> str:
        """Produces a compact, human-readable summary for inspection."""
        blocking_str = "; ".join(self.blocking_findings[:2]) if self.blocking_findings else "None"
        nonblocking_str = "; ".join(self.nonblocking_findings[:2]) if self.nonblocking_findings else "None"
        followups_str = "; ".join(self.required_followups[:2]) if self.required_followups else "None"
        obs_str = "; ".join(self.observed_evidence[:2]) if self.observed_evidence else "None"
        return (
            f"=== Reviewer Assessment Result ===\n"
            f"Status:       {self.status.value}\n"
            f"Alignment:    {self.issue_alignment or 'Not specified'}\n"
            f"Scope:        {self.diff_scope or 'Not specified'}\n"
            f"Tests:        {self.test_assessment or 'Not specified'}\n"
            f"Security:     {self.security_hygiene or 'Clean'}\n"
            f"Blocking:     {blocking_str}\n"
            f"Non-blocking: {nonblocking_str}\n"
            f"Follow-ups:   {followups_str}\n"
            f"Observed:     {obs_str}\n"
            f"Summary:      {self.summary or 'None'}\n"
            f"=================================="
        )

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Records Reviewer findings into TaskState without log bloat or secret leakage."""
        clean_summary = self.summary[:MAX_SUMMARY_LEN] or "Reviewer final assessment completed"
        status_val = self.status.value if isinstance(self.status, ReviewerStatus) else str(self.status)

        # Update TaskState.final_review record
        state.final_review.diff_inspected = True
        state.final_review.notes = f"Reviewer ({status_val}): {clean_summary}"
        if self.status == ReviewerStatus.APPROVE:
            state.final_review.intended_files_only = True
            state.final_review.scratch_files_removed = True

        # Record structured observation into TaskState evidence
        supports_hyp = True if self.status == ReviewerStatus.APPROVE else (False if self.status == ReviewerStatus.CHANGES_REQUESTED else None)
        observation = (
            f"Reviewer assessment ({status_val}): {clean_summary}. "
            f"Blocking findings: {len(self.blocking_findings)}. "
            f"Non-blocking findings: {len(self.nonblocking_findings)}. "
            f"Follow-ups: {', '.join(self.required_followups[:2]) or 'none'}."
        )[:MAX_SUMMARY_LEN]

        state.add_evidence(
            observation=observation,
            source="reviewer_agent",
            supports_hypothesis=supports_hyp,
        )
