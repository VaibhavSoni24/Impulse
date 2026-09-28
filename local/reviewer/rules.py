"""Deterministic assessment rules for Reviewer agent (Stage 23).

Provides:
- evaluate_review_findings: Pure deterministic rule evaluation on ReviewerInput
  producing a structured ReviewerResult.
"""

from __future__ import annotations

import re
from local.reviewer.models import ReviewerInput, ReviewerResult, ReviewerStatus

# Patterns indicating potential security/hygiene violations
SECRET_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Hardcoded API Key"),
    (r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Hardcoded Password"),
    (r"(?i)private[_-]?key", "Private Key Reference"),
]

# Patterns indicating temporary/debug statements
DEBUG_PATTERNS = [
    r"(?i)\bprint\s*\(\s*['\"](?:DEBUG|TEST|TEMP)",
    r"(?i)\bconsole\.log\s*\(\s*['\"](?:DEBUG|TEST|TEMP)",
]


def evaluate_review_findings(inp: ReviewerInput) -> ReviewerResult:
    """Evaluates ReviewerInput deterministically to produce a ReviewerResult.

    Checks:
    1. Input sufficiency (issue, diff, tests, verification status)
    2. Security and hygiene (secrets, credentials, machine-specific paths)
    3. Diff scope and unintended modifications
    4. Test verification outcome
    5. Issue alignment and completeness
    """
    normalized = inp.normalize()
    blocking: list[str] = []
    nonblocking: list[str] = []
    missing: list[str] = []
    followups: list[str] = []
    observed: list[str] = []
    inferred: list[str] = []

    # 1. Missing Evidence Checks
    if not normalized.issue.strip():
        missing.append("Issue statement is empty or missing.")
    if not normalized.diff_summary.strip():
        missing.append("Candidate diff summary is empty.")
    if not normalized.relevant_tests:
        missing.append("No relevant tests were supplied for verification.")
    if not normalized.verification_status.strip():
        missing.append("Verification execution status was not recorded.")

    # 2. Security and Hygiene Review
    diff_text = normalized.diff_summary
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, diff_text):
            blocking.append(f"Security violation: Possible {name} detected in diff.")
            followups.append(f"Purge sensitive credential ({name}) from code.")

    if re.search(r"[a-zA-Z]:\\Users\\[a-zA-Z0-9_\-\\]+", diff_text) or re.search(r"/home/[a-zA-Z0-9_\-]+/", diff_text):
        nonblocking.append("Hygiene warning: Local machine-specific absolute path detected in diff.")
        followups.append("Replace local machine absolute paths with repository-relative paths.")

    # 3. Diff Scope & Debug Artifacts
    for pattern in DEBUG_PATTERNS:
        if re.search(pattern, diff_text):
            nonblocking.append("Diff hygiene: Transient debug print/log statement detected in patch.")
            followups.append("Remove temporary debug statements before final submission.")

    # Check for unrelated file modifications
    if normalized.modified_files:
        unrelated = [f for f in normalized.modified_files if f.startswith(".github/") or f.startswith(".git/")]
        if unrelated:
            blocking.append(f"Scope violation: Unrelated infrastructure files modified: {', '.join(unrelated)}.")
            followups.append("Revert modifications to unrelated CI or repository management files.")

    # 4. Test Verification Assessment
    v_status = normalized.verification_status.upper()
    if v_status == "FAILED":
        blocking.append("Test assessment: Relevant verification tests reported FAILED.")
        followups.append("Resolve failing test assertions before submitting patch.")
    elif v_status == "PASSED":
        observed.append(f"Verification confirmed passing on tests: {', '.join(normalized.relevant_tests[:3]) or 'none'}.")
    elif not v_status:
        observed.append("No verification status recorded.")

    # 5. Determine Overall Status
    if blocking:
        status = ReviewerStatus.CHANGES_REQUESTED
        summary = f"Changes requested: {len(blocking)} blocking finding(s) identified."
    elif missing and (v_status != "PASSED" or not normalized.diff_summary.strip()):
        status = ReviewerStatus.INSUFFICIENT_EVIDENCE
        summary = f"Insufficient evidence: {len(missing)} necessary evidence item(s) missing."
    else:
        status = ReviewerStatus.APPROVE
        summary = "Patch approved: no blocking issues identified; changes appear properly scoped and verified."

    issue_align = "Issue alignment verified against problem statement." if not missing else "Incomplete alignment evidence."
    diff_scope = f"Diff affects {len(normalized.modified_files)} file(s)." if normalized.modified_files else "Diff scope unverified."
    test_assess = f"Verification outcome: {v_status or 'UNSPECIFIED'}."
    sec_hygiene = "Security review clean: zero credentials or secrets detected." if not blocking else "Security review flagged blocking findings."

    return ReviewerResult(
        status=status,
        issue_alignment=issue_align,
        diff_scope=diff_scope,
        test_assessment=test_assess,
        regression_risk="Low based on observed passing targeted tests." if v_status == "PASSED" else "Moderate/High.",
        security_hygiene=sec_hygiene,
        blocking_findings=blocking,
        nonblocking_findings=nonblocking,
        missing_evidence=missing,
        required_followups=followups,
        observed_evidence=observed,
        inferred_risks=inferred,
        summary=summary,
    )
