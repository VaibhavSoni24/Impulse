"""Deterministic failure classifier implementation (Stage 18 / Candidate E9).

Provides FailureClassifierV1 which evaluates failure evidence in a strict,
deterministic order to assign one of the eight canonical failure classes.
"""

from __future__ import annotations

import re
from typing import ClassVar

from local.failures.models import (
    EvidenceStrength,
    FailureClass,
    FailureClassification,
    FailureClassificationContext,
)


class FailureClassifierV1:
    """Deterministic, evidence-driven failure classifier.

    Evaluates observable failure context in a fixed, reproducible priority order:
    1. COMMAND: Malformed syntax, invalid flags, incorrect CLI usage.
    2. ENVIRONMENT: Missing runtime, dependencies, system tools, permissions.
    3. PRE_EXISTING_FAILURE: Failure observed in baseline prior to edits.
    4. REGRESSION: Baseline passed; post-edit test broke existing behavior.
    5. INCOMPLETE_FIX: Core direction correct, but edge or branch remains.
    6. WRONG_HYPOTHESIS: Evidence contradicts assumed root cause or subsystem.
    7. NEW_EDGE_CASE: Primary fix succeeds; boundary/unconsidered input fails.
    8. UNKNOWN: Evidence ambiguous or insufficient.
    """

    # Signatures for malformed command invocations (syntax / argument errors)
    COMMAND_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"error:\s*unrecognized argument", re.IGNORECASE),
        re.compile(r"usage:\s+[\w\-]+", re.IGNORECASE),
        re.compile(r"invalid option", re.IGNORECASE),
        re.compile(r"syntax error near unexpected token", re.IGNORECASE),
        re.compile(r"unknown flag:", re.IGNORECASE),
        re.compile(r"unrecognized option", re.IGNORECASE),
        re.compile(r"pytest:\s*error:\s*unrecognized arguments", re.IGNORECASE),
        re.compile(r"pytest:\s*error:\s*file or directory not found:.*\.py::\w+", re.IGNORECASE),
        re.compile(r"bad option:", re.IGNORECASE),
        re.compile(r"command line syntax error", re.IGNORECASE),
    ]

    # Signatures for missing runtime, tools, libraries, or system-level permissions
    ENVIRONMENT_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"ModuleNotFoundError:\s*No module named", re.IGNORECASE),
        re.compile(r"ImportError:\s*cannot import name", re.IGNORECASE),
        re.compile(r"command not found", re.IGNORECASE),
        re.compile(r":\s*not found", re.IGNORECASE),
        re.compile(r"PermissionError:\s*\[Errno 13\]", re.IGNORECASE),
        re.compile(r"Permission denied", re.IGNORECASE),
        re.compile(r"ConnectionRefusedError:", re.IGNORECASE),
        re.compile(r"No such file or directory:.*(?:python|pytest|git|sh|bash)", re.IGNORECASE),
        re.compile(r"Virtualenv not found", re.IGNORECASE),
        re.compile(r"Unsupported Python version", re.IGNORECASE),
    ]

    # Boundary / Edge case keywords in test names or failure traces
    EDGE_CASE_KEYWORDS: ClassVar[list[str]] = [
        "boundary",
        "empty",
        "none_value",
        "null",
        "zero",
        "overflow",
        "unicode",
        "corner_case",
        "edge_case",
        "special_chars",
    ]

    def classify(self, context: FailureClassificationContext) -> FailureClassification:
        """Classifies a failure context deterministically."""
        combined_output = f"{context.stdout}\n{context.stderr}\n{context.test_output}"

        # -------------------------------------------------------------
        # Step 1: COMMAND Invocation Error
        # -------------------------------------------------------------
        for pattern in self.COMMAND_PATTERNS:
            if pattern.search(combined_output):
                match = pattern.search(combined_output)
                matched_text = match.group(0) if match else "command syntax error"
                return FailureClassification(
                    failure_class=FailureClass.COMMAND,
                    evidence_strength=EvidenceStrength.STRONG,
                    rationale="Command failed due to invalid CLI arguments, options, or invocation syntax.",
                    relevant_command=context.command,
                    evidence=[f"Output matches command syntax pattern: '{matched_text}'"],
                )

        # -------------------------------------------------------------
        # Step 2: ENVIRONMENT Problem
        # -------------------------------------------------------------
        if context.environment_details:
            return FailureClassification(
                failure_class=FailureClass.ENVIRONMENT,
                evidence_strength=EvidenceStrength.STRONG,
                rationale="Execution failed due to verified host environment constraints.",
                relevant_command=context.command,
                evidence=[context.environment_details],
            )

        for pattern in self.ENVIRONMENT_PATTERNS:
            if pattern.search(combined_output):
                match = pattern.search(combined_output)
                matched_text = match.group(0) if match else "environment dependency failure"
                return FailureClassification(
                    failure_class=FailureClass.ENVIRONMENT,
                    evidence_strength=EvidenceStrength.STRONG,
                    rationale="Execution failed due to missing dependency, runtime, binary, or permissions.",
                    relevant_command=context.command,
                    evidence=[f"Output matches environment error pattern: '{matched_text}'"],
                )

        # -------------------------------------------------------------
        # Step 3: PRE_EXISTING_FAILURE
        # -------------------------------------------------------------
        if context.baseline_result is not None and context.baseline_result.upper() == "FAILED":
            return FailureClassification(
                failure_class=FailureClass.PRE_EXISTING_FAILURE,
                evidence_strength=EvidenceStrength.STRONG,
                rationale="The failing test was already failing during baseline execution before any edits.",
                relevant_command=context.command,
                evidence=[
                    f"Baseline result recorded as {context.baseline_result}",
                    "Failure pre-dates current changes",
                ],
            )

        # -------------------------------------------------------------
        # Step 4: REGRESSION
        # -------------------------------------------------------------
        if context.baseline_result is not None and context.baseline_result.upper() == "PASSED":
            # Test previously passed, but now fails after patch
            return FailureClassification(
                failure_class=FailureClass.REGRESSION,
                evidence_strength=EvidenceStrength.STRONG,
                rationale="Test passed during baseline run, but failed after changes were introduced.",
                relevant_command=context.command,
                evidence=[
                    "Baseline status: PASSED",
                    f"Post-patch exit code: {context.exit_code}",
                ],
            )

        # -------------------------------------------------------------
        # Step 5: INCOMPLETE_FIX
        # -------------------------------------------------------------
        # Check if primary error is partially addressed or related assertions remain
        if context.is_related_to_changes is True and context.previous_test_result == "FAILED":
            # If the output shows progress (e.g. primary assertion passed, secondary failed)
            # or partial fix indicator
            if "AssertionError" in combined_output and ("partially" in combined_output.lower() or "remaining" in combined_output.lower() or context.metadata.get("partial_fix") is True):
                return FailureClassification(
                    failure_class=FailureClass.INCOMPLETE_FIX,
                    evidence_strength=EvidenceStrength.MODERATE,
                    rationale="Fix is directionally aligned with hypothesis, but verification reveals unfulfilled assertions.",
                    relevant_command=context.command,
                    evidence=["Modified component failed on secondary assertion", "Hypothesis remains plausible"],
                )

        # Metadata explicit indicator for incomplete fix
        if context.metadata.get("incomplete_fix") is True:
            return FailureClassification(
                failure_class=FailureClass.INCOMPLETE_FIX,
                evidence_strength=EvidenceStrength.MODERATE,
                rationale="Implementation addresses core issue but omits related execution paths.",
                relevant_command=context.command,
                evidence=["Explicit indicator: incomplete fix"],
            )

        # -------------------------------------------------------------
        # Step 6: WRONG_HYPOTHESIS
        # -------------------------------------------------------------
        if context.is_related_to_changes is False and context.modified_files:
            # Failure persists in a subsystem unrelated to modified files, or traceback shows different root cause
            return FailureClassification(
                failure_class=FailureClass.WRONG_HYPOTHESIS,
                evidence_strength=EvidenceStrength.MODERATE,
                rationale="Failure evidence contradicts current hypothesis; defect originates outside modified components.",
                relevant_command=context.command,
                evidence=[
                    f"Modified files: {context.modified_files}",
                    "Failure points to different subsystem or unaffected causal mechanism",
                ],
            )

        if context.metadata.get("wrong_hypothesis") is True:
            return FailureClassification(
                failure_class=FailureClass.WRONG_HYPOTHESIS,
                evidence_strength=EvidenceStrength.STRONG,
                rationale="Failure evidence directly refutes the assumed root cause.",
                relevant_command=context.command,
                evidence=["Explicit indicator: wrong hypothesis"],
            )

        # -------------------------------------------------------------
        # Step 7: NEW_EDGE_CASE
        # -------------------------------------------------------------
        is_edge = context.is_edge_case or any(kw in context.command.lower() or kw in combined_output.lower() for kw in self.EDGE_CASE_KEYWORDS)
        if is_edge and ("AssertionError" in combined_output or context.exit_code != 0):
            # Check if this is an edge case distinct from general regression
            if context.baseline_result is None or context.baseline_result.upper() != "PASSED":
                return FailureClassification(
                    failure_class=FailureClass.NEW_EDGE_CASE,
                    evidence_strength=EvidenceStrength.MODERATE,
                    rationale="Core implementation functional, but boundary condition or unconsidered input fails.",
                    relevant_command=context.command,
                    evidence=["Failure triggered by boundary condition / edge case input"],
                )

        # -------------------------------------------------------------
        # Step 8: UNKNOWN (Insufficient or Ambiguous Evidence)
        # -------------------------------------------------------------
        return FailureClassification(
            failure_class=FailureClass.UNKNOWN,
            evidence_strength=EvidenceStrength.UNKNOWN,
            rationale="Available evidence is insufficient or ambiguous to reliably classify.",
            relevant_command=context.command,
            evidence=["Insufficient diagnostic signals in output"],
        )
