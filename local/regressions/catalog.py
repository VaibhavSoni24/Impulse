"""Authoritative Failure-to-Regression Catalog and Registry (Stage 45 Phase 3, 7, 8).

Defines the complete, candidate-independent regression catalog capturing all discovered
failure modes across IMPULSE development. Enforces:
1. Strict deduplication of regression IDs and failure signatures.
2. Cryptographic held-out benchmark split protection.
3. Provenance tracking back to specific stages, commits, and taxonomy entries.
4. Clean separation of harness, infrastructure, and honest blocked failure types.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.splits.held_out_lock import is_held_out_task
from local.regressions.errors import (
    DuplicateRegressionError,
    HeldOutContaminationError,
    InvalidRegressionCaseError,
    RegressionManifestError,
)
from local.regressions.models import (
    RegressionCase,
    RegressionCategory,
    RegressionManifest,
    RegressionResultStatus,
    RegressionSeverity,
    RegressionStatus,
    RegressionType,
)

STAGE45_PARENT_COMMIT = "097ad5a90564c64da1c53714c600af8d4ee5a2ae"


def get_canonical_catalog() -> list[RegressionCase]:
    """Constructs and returns the authoritative 22 regression cases of IMPULSE Stage 45."""
    return [
        # 1. RETRIEVAL: Weak Semantic Search Mislead
        RegressionCase(
            regression_id="REG-RETRIEVAL-001",
            version="1.0.0",
            title="Weak semantic retrieval fallback to exact search",
            category=RegressionCategory.RETRIEVAL,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="WEAK_SEMANTIC_SEARCH_MISLEAD",
            description="Prevents weak semantic search candidates from misleading agent localization; requires fallback to exact search when similarity is below threshold.",
            observed_or_synthetic="synthetic",
            provenance={
                "stage": "Stage 33",
                "plan_requirement": "semantic search misleads agent",
                "source_file": "local/retrieval_opt/policy.py",
                "candidate_ids": ["R0", "R1"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "fallback_behavior['on_semantic_failure'] == 'EXACT_SEARCH'",
                "similarity_threshold >= 0.50",
                "low similarity candidate (< 0.50) triggers fallback",
            ],
            execution_entrypoint="local.regressions.invariants.retrieval:check_weak_semantic_fallback",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["R1", "M0"],
            signature="RETRIEVAL:WEAK_SEMANTIC_SEARCH_MISLEAD",
        ),
        # 2. RETRIEVAL: Budget Exhaustion
        RegressionCase(
            regression_id="REG-RETRIEVAL-002",
            version="1.0.0",
            title="Semantic retrieval budget exhaustion and bounded expansion",
            category=RegressionCategory.RETRIEVAL,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="RETRIEVAL_BUDGET_EXHAUSTION",
            description="Prevents unbounded semantic tool expansion by enforcing strict call budgets and stopping retrieval on budget exhaustion.",
            observed_or_synthetic="synthetic",
            provenance={
                "stage": "Stage 33",
                "plan_requirement": "semantic search call budget exhaustion",
                "source_file": "local/retrieval_opt/policy.py",
                "candidate_ids": ["R1", "R4"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "max_semantic_calls bounded (1-5)",
                "fallback_behavior['on_budget_exhausted'] == 'STOP_RETRIEVAL'",
                "max_retrieved_items bounded (<= 25)",
            ],
            execution_entrypoint="local.regressions.invariants.retrieval:check_retrieval_budget_exhaustion",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["R1"],
            signature="RETRIEVAL:RETRIEVAL_BUDGET_EXHAUSTION",
        ),
        # 3. POLICY: Edit Before Evidence / Tests
        RegressionCase(
            regression_id="REG-POLICY-001",
            version="1.0.0",
            title="Prohibit edits before reading tests and establishing reconnaissance",
            category=RegressionCategory.POLICY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="EDIT_BEFORE_TEST_OR_RECON",
            description="Enforces strict operational workflow discipline: cheap direct reconnaissance and test evidence must precede edit hypothesis and file modifications.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 21",
                "plan_requirement": "agent edits before reading tests",
                "source_file": "local/scout/trigger.py",
                "candidate_ids": ["E1", "M0"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "exact_recon_completed == False blocks edit hypothesis trigger",
                "premature edit hypothesis blocks scout uncertainty trigger",
                "workflow demands initial direct repository reconnaissance",
            ],
            execution_entrypoint="local.regressions.invariants.policy:check_edit_before_evidence_policy",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["M0", "S1"],
            signature="POLICY:EDIT_BEFORE_TEST_OR_RECON",
        ),
        # 4. RECOVERY: Repeated Command
        RegressionCase(
            regression_id="REG-RECOVERY-001",
            version="1.0.0",
            title="Detect repeated failing command across cycle threshold",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="REPEATED_COMMAND",
            description="Detects repeated execution of identical test command without progress within 2 cycles.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 19",
                "plan_requirement": "agent loops on failing test",
                "taxonomy_entry": "REPEATED_COMMAND",
                "source_file": "local/progress/detector.py",
                "candidate_ids": ["E10", "REC0"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "NoProgressDetectorV1 flags lack of progress on cycle 2",
                "assessment.status == NO_PROGRESS",
                "assessment.reason in (REPEATED_FAILURE, REPEATED_EDIT)",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_repeated_command_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["E10", "M0"],
            signature="RECOVERY:REPEATED_COMMAND",
        ),
        # 5. RECOVERY: Repeated Error
        RegressionCase(
            regression_id="REG-RECOVERY-002",
            version="1.0.0",
            title="Detect repeated identical error signature without new evidence",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="REPEATED_ERROR",
            description="Detects recurring identical failure signature and stack trace without diagnostic shift.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "REPEATED_ERROR",
                "source_file": "local/progress/detector.py",
                "candidate_ids": ["REC0", "REC1"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "identical error signature flags NO_PROGRESS at threshold=2",
                "reason == REPEATED_FAILURE",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_repeated_error_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC1"],
            signature="RECOVERY:REPEATED_ERROR",
        ),
        # 6. RECOVERY: Repeated Edit
        RegressionCase(
            regression_id="REG-RECOVERY-003",
            version="1.0.0",
            title="Detect materially identical repeated code edits",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="REPEATED_EDIT",
            description="Detects when the agent re-applies materially identical or cosmetic code modifications after verification failure.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 19",
                "taxonomy_entry": "REPEATED_EDIT",
                "source_file": "local/progress/detector.py",
                "candidate_ids": ["E10", "REC0"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "normalized edit comparison detects equivalence across whitespace",
                "assessment.status == NO_PROGRESS",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_repeated_edit_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["E10"],
            signature="RECOVERY:REPEATED_EDIT",
        ),
        # 7. RECOVERY: Repeated Hypothesis
        RegressionCase(
            regression_id="REG-RECOVERY-004",
            version="1.0.0",
            title="Detect repeated root-cause hypothesis without new evidence",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.MEDIUM,
            source_failure_type="REPEATED_HYPOTHESIS",
            description="Detects repeated exploration of an already-falsified root-cause hypothesis.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 19",
                "taxonomy_entry": "REPEATED_HYPOTHESIS",
                "source_file": "local/progress/detector.py",
                "candidate_ids": ["E10", "REC0"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "normalized hypothesis comparison detects case-insensitive equivalence",
                "assessment.status == NO_PROGRESS",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_repeated_hypothesis_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["E10"],
            signature="RECOVERY:REPEATED_HYPOTHESIS",
        ),
        # 8. RECOVERY: Recovery Loop
        RegressionCase(
            regression_id="REG-RECOVERY-005",
            version="1.0.0",
            title="Detect oscillating recovery actions (A -> B -> A -> B)",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="RECOVERY_LOOP",
            description="Detects cyclic oscillations between alternating recovery interventions on unchanged defect state.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 35",
                "plan_requirement": "agent loops on failing test",
                "taxonomy_entry": "RECOVERY_LOOP",
                "source_file": "local/recovery_opt/loop_detector.py",
                "candidate_ids": ["REC0", "REC2"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "RecoveryLoopDetector.analyze_events detects oscillation",
                "loop_detected == True",
                "loop_type in ('OSCILLATION', 'DIRECT_LOOP')",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_recovery_loop_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC2"],
            signature="RECOVERY:RECOVERY_LOOP",
        ),
        # 9. RECOVERY: Recovery Thrashing
        RegressionCase(
            regression_id="REG-RECOVERY-006",
            version="1.0.0",
            title="Detect recovery thrashing across unverified interventions",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="RECOVERY_THRASHING",
            description="Detects rapid successive trial of disparate recovery actions without intermediate verification or evidence progress.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "RECOVERY_THRASHING",
                "source_file": "local/recovery_opt/loop_detector.py",
                "candidate_ids": ["REC0", "REC1"],
                "note": "observed recovery failure pattern mined in Stage 35",
            },
            fixture_type="harness_detector",
            expected_invariants=[
                "tracks consecutive unimproved recovery attempts",
                "flags thrashing when attempts exceed threshold without evidence change",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_recovery_thrashing_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC1"],
            signature="RECOVERY:RECOVERY_THRASHING",
        ),
        # 10. RECOVERY: Retry Waste
        RegressionCase(
            regression_id="REG-RECOVERY-007",
            version="1.0.0",
            title="Prevent retry waste via bounded retry budgets",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="RETRY_WASTE",
            description="Prevents wasteful infinite retry loops by terminating with BUDGET_EXHAUSTED once configured retry bounds are met.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "RETRY_WASTE",
                "source_file": "local/recovery_opt/models.py",
                "candidate_ids": ["REC0", "REC1"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "attempts exceeding max_test_failure_retries flag is_exhausted",
                "'budget_exhausted' included in policy stop_conditions",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_retry_waste_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC1"],
            signature="RECOVERY:RETRY_WASTE",
        ),
        # 11. RECOVERY: Recovery Omission
        RegressionCase(
            regression_id="REG-RECOVERY-008",
            version="1.0.0",
            title="Prevent recovery omission upon verified test failure",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="RECOVERY_OMISSION",
            description="Requires explicit failure classification and eligibility evaluation whenever meaningful test verification fails.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "RECOVERY_OMISSION",
                "source_file": "local/recovery_opt/models.py",
                "candidate_ids": ["M0", "REC0"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "meaningful failure classes require fallback rule assignment",
                "'on_test_failure' present in recovery fallback rules",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_recovery_omission_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["M0"],
            signature="RECOVERY:RECOVERY_OMISSION",
        ),
        # 12. RECOVERY: Late Recovery
        RegressionCase(
            regression_id="REG-RECOVERY-009",
            version="1.0.0",
            title="Prevent late recovery via early no-progress detection",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.MEDIUM,
            source_failure_type="LATE_RECOVERY",
            description="Enforces that no-progress thresholds do not exceed 3 turns, triggering intervention before episode exhaustion.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "LATE_RECOVERY",
                "source_file": "local/recovery_opt/models.py",
                "candidate_ids": ["REC0", "REC1"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "no_progress_threshold_turns <= 3",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_late_recovery_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC1"],
            signature="RECOVERY:LATE_RECOVERY",
        ),
        # 13. RECOVERY: Failed Recovery Escalation
        RegressionCase(
            regression_id="REG-RECOVERY-010",
            version="1.0.0",
            title="Escalate failed recovery to alternate path",
            category=RegressionCategory.RECOVERY,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="FAILED_RECOVERY",
            description="Enforces clean escalation to alternate tool or path when primary recovery fails (RETRY_THEN_ALTERNATE).",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 35",
                "taxonomy_entry": "FAILED_RECOVERY",
                "source_file": "local/recovery_opt/models.py",
                "candidate_ids": ["REC0", "REC3"],
                "note": "synthetic harness regression derived from documented failure mode",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "fallback_rules['on_tool_failure'] == 'RETRY_THEN_ALTERNATE'",
                "alternate_path_routing_enabled == True",
            ],
            execution_entrypoint="local.regressions.invariants.recovery:check_failed_recovery_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["REC3"],
            signature="RECOVERY:FAILED_RECOVERY",
        ),
        # 14. HYGIENE: Temporary File Left Behind
        RegressionCase(
            regression_id="REG-HYGIENE-001",
            version="1.0.0",
            title="Detect and clean temporary scratch files and debug logs",
            category=RegressionCategory.HYGIENE,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="TEMPORARY_FILE_LEFT_BEHIND",
            description="Detects scratch scripts, temporary patches, and debug logs; verifies that SafeCleaner approves removal for untracked files while protecting tracked files.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 27",
                "plan_requirement": "agent leaves temporary file",
                "source_file": "local/diff_discipline/detectors.py",
                "candidate_ids": ["D1", "M0"],
                "note": "synthetic filesystem harness regression derived from Stage 27 hygiene discipline",
            },
            fixture_type="harness_filesystem",
            expected_invariants=[
                "scratch files detected with recommended_action REMOVE",
                "temp patches detected with recommended_action REMOVE",
                "debug logs detected with recommended_action REMOVE",
                "SafeCleaner approves untracked removal, rejects tracked removal",
            ],
            execution_entrypoint="local.regressions.invariants.hygiene:check_temporary_file_hygiene",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["D1", "M0"],
            signature="HYGIENE:TEMPORARY_FILE_LEFT_BEHIND",
        ),
        # 15. DIFF_DISCIPLINE: Unrelated File Modified
        RegressionCase(
            regression_id="REG-DIFF-001",
            version="1.0.0",
            title="Detect and block modifications to unrelated files",
            category=RegressionCategory.DIFF_DISCIPLINE,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="UNRELATED_FILE_MODIFIED",
            description="Prevents unintentional modifications outside defect scope (e.g. CI workflow files or infrastructure scripts) from entering submission diffs.",
            observed_or_synthetic="observed",
            provenance={
                "stage": "Stage 23",
                "plan_requirement": "agent changes unrelated file",
                "source_file": "local/reviewer/rules.py",
                "candidate_ids": ["V1", "M0"],
                "note": "synthetic harness regression derived from Reviewer rules",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "clean diff approved by reviewer rules",
                "diff touching unrelated files blocked with CHANGES_REQUESTED",
                "Scope violation reported in blocking findings",
            ],
            execution_entrypoint="local.regressions.invariants.diff:check_unrelated_file_diff_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["V1", "M0"],
            signature="DIFF_DISCIPLINE:UNRELATED_FILE_MODIFIED",
        ),
        # 16. CALLER_INSPECTION: Caller Not Inspected
        RegressionCase(
            regression_id="REG-GRAPH-001",
            version="1.0.0",
            title="Disciplined caller and relationship exploration under contract changes",
            category=RegressionCategory.CALLER_INSPECTION,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="CALLER_NOT_INSPECTED",
            description="Enforces that contract-sensitive symbols undergo relational caller exploration while preventing context explosion when source is sufficient.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 13",
                "plan_requirement": "agent fails to inspect caller",
                "source_file": "local/graph/controller.py",
                "candidate_ids": ["E4", "M0"],
                "note": "synthetic harness regression derived from Graph Neighbor Policy V1",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "approves exploration when symbol is promising and relationships unresolved",
                "blocks exploration when direct source is already sufficient",
                "blocks consecutive neighbor calls without intermediate reading",
                "blocks graph neighbor exploration outside localization phase",
            ],
            execution_entrypoint="local.regressions.invariants.graph:check_caller_inspection_discipline",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["E4", "M0"],
            signature="CALLER_INSPECTION:CALLER_NOT_INSPECTED",
        ),
        # 17. TESTING: Stop After First Red Test
        RegressionCase(
            regression_id="REG-TESTING-001",
            version="1.0.0",
            title="Prohibit premature stopping on first failing test; require escalation",
            category=RegressionCategory.TESTING,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.HIGH,
            source_failure_type="STOP_AFTER_FIRST_RED_TEST",
            description="Enforces that test policies do not treat a failing test as sufficient final validation and mandate escalation on test failure.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 34",
                "plan_requirement": "agent stops after first red test",
                "source_file": "local/testing_opt/policy.py",
                "candidate_ids": ["T0", "T1", "T2"],
                "note": "synthetic harness regression derived from Testing Strategy policies",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "T1 policy has escalate_on_targeted_failure=True",
                "stop_rules forbid stopping on failure as pass",
                "T2 policy escalates on adjacent regressions",
            ],
            execution_entrypoint="local.regressions.invariants.testing:check_stop_after_first_red_test",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["T1", "T2"],
            signature="TESTING:STOP_AFTER_FIRST_RED_TEST",
        ),
        # 18. TESTING: Unconstrained Repository Sweep
        RegressionCase(
            regression_id="REG-TESTING-002",
            version="1.0.0",
            title="Prevent unconstrained repository-wide test sweeps on localized changes",
            category=RegressionCategory.TESTING,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.MEDIUM,
            source_failure_type="UNCONSTRAINED_REPO_SWEEP",
            description="Enforces bounded execution parameters in baseline test policy and verifies feasibility evaluator rejects full suite sweeps under T0.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 34",
                "plan_requirement": "unconstrained repository sweeps",
                "source_file": "local/testing_opt/feasibility.py",
                "candidate_ids": ["T0"],
                "note": "synthetic harness regression derived from Testing Feasibility evaluator",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "full_suite_enabled == False in T0",
                "max_test_commands bounded (<= 3)",
                "feasibility evaluator returns NOT_FEASIBLE under T0",
            ],
            execution_entrypoint="local.regressions.invariants.testing:check_unconstrained_repo_sweep",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["T0"],
            signature="TESTING:UNCONSTRAINED_REPO_SWEEP",
        ),
        # 19. SUBMISSION: Submit Without Final Diff Review
        RegressionCase(
            regression_id="REG-SUBMISSION-001",
            version="1.0.0",
            title="Require final diff review and verification evidence before submission",
            category=RegressionCategory.SUBMISSION,
            regression_type=RegressionType.HARNESS_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="SUBMIT_WITHOUT_FINAL_DIFF",
            description="Structurally enforces that patch submission is rejected unless candidate diff, verification evidence, and final review readiness are complete.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 23",
                "plan_requirement": "agent submits without final diff review",
                "source_file": "local/reviewer/trigger.py",
                "candidate_ids": ["V1", "M0"],
                "note": "synthetic harness regression derived from Reviewer trigger rules",
            },
            fixture_type="harness_policy",
            expected_invariants=[
                "unverified patch rejected by is_review_ready",
                "empty diff rejected by is_review_ready",
                "valid verified diff confirmed ready for review",
            ],
            execution_entrypoint="local.regressions.invariants.submission:check_submit_without_final_diff",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["V1", "M0"],
            signature="SUBMISSION:SUBMIT_WITHOUT_FINAL_DIFF",
        ),
        # 20. INFRASTRUCTURE: Held-Out Split Contamination
        RegressionCase(
            regression_id="REG-BENCHMARK-001",
            version="1.0.0",
            title="Cryptographic held-out split protection and leakage prevention",
            category=RegressionCategory.INFRASTRUCTURE,
            regression_type=RegressionType.INFRASTRUCTURE_REGRESSION,
            severity=RegressionSeverity.CRITICAL,
            source_failure_type="HELD_OUT_CONTAMINATION",
            description="Verifies the cryptographic held_out.lock and guarantees that no held-out benchmark task is consumed into development or regression suites.",
            observed_or_synthetic="architectural_invariant",
            provenance={
                "stage": "Stage 29",
                "plan_requirement": "Held-out protection",
                "source_file": "benchmark/splits/held_out_lock.py",
                "candidate_ids": ["M0"],
                "note": "deterministic infrastructure regression verifying cryptographic held-out lock",
            },
            fixture_type="infrastructure_lock",
            expected_invariants=[
                "held-out lock file verified with 14 locked tasks",
                "is_held_out_task returns True for locked tasks",
                "validate_task_not_held_out raises HeldOutContaminationError on protected task",
                "dev tasks pass cleanly",
            ],
            execution_entrypoint="local.regressions.invariants.infrastructure:check_held_out_protection_invariant",
            required_capabilities=["local_cpu"],
            status=RegressionStatus.ACTIVE,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["M0"],
            signature="INFRASTRUCTURE:HELD_OUT_CONTAMINATION",
        ),
        # 21. ENVIRONMENT_BLOCKED: 31B Context Length Degradation
        RegressionCase(
            regression_id="REG-BLOCKED-001",
            version="1.0.0",
            title="Gemma 4 31B long-context reasoning degradation (>32k tokens)",
            category=RegressionCategory.ENVIRONMENT_BLOCKED,
            regression_type=RegressionType.UNREPRESENTED_BLOCKED_FAILURE,
            severity=RegressionSeverity.HIGH,
            source_failure_type="CONTEXT_DEGRADATION_31B",
            description="Captures documented reasoning degradation of Gemma 4 31B on long context (>32k tokens). Preserved honestly as BLOCKED on local CPU host.",
            observed_or_synthetic="blocked_environment",
            provenance={
                "stage": "Stage 42",
                "plan_requirement": "honest blocked failure representation",
                "source_file": "local/compute/environment.py",
                "candidate_ids": ["M0", "L1"],
                "note": "unrepresented blocked failure preserved without live GPU execution fabrication",
            },
            fixture_type="unrepresented_stub",
            expected_invariants=[
                "status remains BLOCKED on local CPU",
                "cannot be silently marked as PASS without live GPU inference",
            ],
            execution_entrypoint="local.regressions.invariants.blocked:check_long_context_degradation_blocked",
            required_capabilities=["cuda_gpu", "gemma_31b_weights"],
            status=RegressionStatus.BLOCKED,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["M0", "L1"],
            signature="ENVIRONMENT_BLOCKED:CONTEXT_DEGRADATION_31B",
        ),
        # 22. ENVIRONMENT_BLOCKED: Kaggle Container Network Isolation Timeout
        RegressionCase(
            regression_id="REG-BLOCKED-002",
            version="1.0.0",
            title="Kaggle air-gapped container network timeout on unbundled wheels",
            category=RegressionCategory.ENVIRONMENT_BLOCKED,
            regression_type=RegressionType.UNREPRESENTED_BLOCKED_FAILURE,
            severity=RegressionSeverity.HIGH,
            source_failure_type="KAGGLE_NETWORK_ISOLATION_TIMEOUT",
            description="Captures container timeout in air-gapped Kaggle sandbox when external wheels are not pre-packaged. Preserved honestly as BLOCKED on local host.",
            observed_or_synthetic="blocked_environment",
            provenance={
                "stage": "Stage 42",
                "plan_requirement": "honest blocked failure representation",
                "source_file": "local/compute/environment.py",
                "candidate_ids": ["M0"],
                "note": "unrepresented blocked failure preserved without live Kaggle container fabrication",
            },
            fixture_type="unrepresented_stub",
            expected_invariants=[
                "status remains BLOCKED on non-container host",
                "requires verified Kaggle container runtime before activation",
            ],
            execution_entrypoint="local.regressions.invariants.blocked:check_kaggle_network_isolation_blocked",
            required_capabilities=["kaggle_container_runtime"],
            status=RegressionStatus.BLOCKED,
            created_from_stage="Stage 45",
            created_from_commit=STAGE45_PARENT_COMMIT,
            related_candidate_ids=["M0"],
            signature="ENVIRONMENT_BLOCKED:KAGGLE_NETWORK_ISOLATION_TIMEOUT",
        ),
    ]


def validate_catalog(cases: list[RegressionCase]) -> tuple[bool, list[str]]:
    """Validates catalog integrity: duplicate IDs, duplicate signatures, held-out tasks, required fields."""
    seen_ids: set[str] = set()
    seen_signatures: set[str] = set()
    errors: list[str] = []

    for case in cases:
        # Check duplicate ID
        if case.regression_id in seen_ids:
            msg = f"Duplicate regression ID detected: '{case.regression_id}'"
            errors.append(msg)
            raise DuplicateRegressionError(msg)
        seen_ids.add(case.regression_id)

        # Check duplicate failure signature
        if case.signature in seen_signatures:
            msg = f"Duplicate failure signature detected: '{case.signature}' in case '{case.regression_id}'"
            errors.append(msg)
            raise DuplicateRegressionError(msg)
        seen_signatures.add(case.signature)

        # Check held-out contamination in provenance or description
        prov_str = json.dumps(case.provenance)
        for val in (case.description, case.title, prov_str):
            # Check if any locked held-out task appears
            lock_path = Path("benchmark/splits/v1/held_out.lock")
            if lock_path.is_file():
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        lock_data = json.load(f)
                    for ht in lock_data.get("held_out_tasks", []):
                        if ht and ht in val:
                            msg = f"Held-out task '{ht}' referenced in case '{case.regression_id}' without authorization"
                            errors.append(msg)
                            raise HeldOutContaminationError(msg)
                except (DuplicateRegressionError, HeldOutContaminationError):
                    raise
                except Exception:
                    pass

        # Check required fields
        if not case.expected_invariants:
            msg = f"Case '{case.regression_id}' has empty expected_invariants"
            errors.append(msg)
            raise InvalidRegressionCaseError(msg)

        if not case.execution_entrypoint:
            msg = f"Case '{case.regression_id}' has empty execution_entrypoint"
            errors.append(msg)
            raise InvalidRegressionCaseError(msg)

        if not case.provenance:
            msg = f"Case '{case.regression_id}' is missing required provenance"
            errors.append(msg)
            raise InvalidRegressionCaseError(msg)

    return len(errors) == 0, errors


def build_regression_manifest(
    cases: Optional[list[RegressionCase]] = None,
    git_commit: str = STAGE45_PARENT_COMMIT,
) -> RegressionManifest:
    """Builds the canonical RegressionManifest with counts, distributions, and integrity hash."""
    if cases is None:
        cases = get_canonical_catalog()

    validate_catalog(cases)

    by_type: dict[str, int] = {}
    by_cat: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for c in cases:
        t_val = c.regression_type.value if hasattr(c.regression_type, "value") else str(c.regression_type)
        cat_val = c.category.value if hasattr(c.category, "value") else str(c.category)
        s_val = c.status.value if hasattr(c.status, "value") else str(c.status)

        by_type[t_val] = by_type.get(t_val, 0) + 1
        by_cat[cat_val] = by_cat.get(cat_val, 0) + 1
        by_status[s_val] = by_status.get(s_val, 0) + 1

    manifest = RegressionManifest(
        schema_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        git_commit=git_commit,
        total_cases=len(cases),
        cases_by_type=by_type,
        cases_by_category=by_cat,
        cases_by_status=by_status,
        cases=cases,
    )
    manifest.manifest_sha256 = manifest.compute_sha256()
    return manifest


def save_catalog_to_disk(
    manifest: RegressionManifest,
    output_dir: Path | str = "experiments/regressions",
) -> None:
    """Saves the canonical manifest and individual case JSON files to disk."""
    out_p = Path(output_dir)
    cases_dir = out_p / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    # Save individual cases
    for case in manifest.cases:
        case_file = cases_dir / f"{case.regression_id}.json"
        with open(case_file, "w", encoding="utf-8") as f:
            json.dump(case.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

    # Save manifest.json
    manifest_file = out_p / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


def load_manifest_from_disk(
    manifest_path: Path | str = "experiments/regressions/manifest.json",
) -> RegressionManifest:
    """Loads and verifies a RegressionManifest from disk."""
    p = Path(manifest_path)
    if not p.is_file():
        raise RegressionManifestError(f"Manifest file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    manifest = RegressionManifest.from_dict(data)
    computed_hash = manifest.compute_sha256()
    if manifest.manifest_sha256 and manifest.manifest_sha256 != computed_hash:
        raise RegressionManifestError(
            f"Manifest SHA-256 mismatch: recorded {manifest.manifest_sha256[:12]}, computed {computed_hash[:12]}"
        )

    return manifest
