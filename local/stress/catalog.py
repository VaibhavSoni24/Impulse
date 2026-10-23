"""Authoritative Catalog and Registry for IMPULSE Stress Test Suite (Stage 46).

Defines the 22 canonical stress cases covering all 11 required stress families:
1. Very large repository (STRESS-REPO-001)
2. Ambiguous issue wording (STRESS-AMBIGUOUS-001, STRESS-LIVE-AMBIGUOUS-001)
3. Misleading function names (STRESS-MISLEADING-001, STRESS-LIVE-MISLEADING-001)
4. Multi-file fix (STRESS-MULTIFILE-001)
5. Hidden dependency relationship (STRESS-GRAPH-001)
6. Failing test with long logs (STRESS-LOG-001)
7. Pre-existing failing test (STRESS-PREEXISTING-001)
8. Required new file (STRESS-NEWFILE-001)
9. Binary or unusual file intent (STRESS-BINARY-001)
10. Repeated test failure (STRESS-RECOVERY-001 through STRESS-RECOVERY-010)
11. Expensive full-suite tests (STRESS-EXPENSIVE-001)

Provides validation functions for deduplication, held-out task protection,
Stage 45 regression references, and manifest serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.splits.held_out_lock import is_held_out_task
from local.regressions.catalog import get_canonical_catalog as get_canonical_regression_catalog
from local.stress.models import (
    StressCase,
    StressCategory,
    StressManifest,
    StressSeverity,
    StressStatus,
    StressType,
)

STRESS_SCHEMA_VERSION = "v1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STRESS_EXP_DIR = PROJECT_ROOT / "experiments" / "stress"


def get_canonical_catalog() -> list[StressCase]:
    """Returns the immutable list of canonical stress cases."""
    return [
        # 1. Very Large Repository
        StressCase(
            stress_id="STRESS-REPO-001",
            version="1.0.0",
            title="Synthetic Large Repository Traversal and Containment",
            category=StressCategory.LARGE_REPO,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Traverse and index a synthetic repository with 120 files across 3 directory levels without path escape, memory leaks, or unbounded runtime.",
            fixture_type="synthetic_nested_repository",
            source_requirement="PLAN.md Stage 46 STRESS 1",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Exact file count discovered",
                "Byte volume tracked accurately",
                "Path containment strictly within fixture root",
                "Inspection terminates within bounded time (< 5.0s)",
                "Directory cleanup leaves zero temporary files",
            ],
            execution_entrypoint="local.stress.invariants.large_repo:check_large_repo_stress",
            resource_limits={"max_files": 1000, "max_depth": 5, "max_duration_seconds": 10.0},
            related_regression_ids=["REG-RETRIEVAL-002", "REG-TESTING-002"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 2. Ambiguous Issue Wording
        StressCase(
            stress_id="STRESS-AMBIGUOUS-001",
            version="1.0.0",
            title="Ambiguous Issue Reconnaissance Policy Enforcement",
            category=StressCategory.AMBIGUOUS_ISSUE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.HIGH,
            scenario_description="Issue presents multiple competing candidate symbols without clear winner; policy forbids premature edit and mandates focused reconnaissance.",
            fixture_type="synthetic_ambiguous_issue",
            source_requirement="PLAN.md Stage 46 STRESS 2",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Premature edit unauthorized when confidence < threshold",
                "Routes to focused reconnaissance disambiguation",
                "Probing bounded to avoid query explosion",
            ],
            execution_entrypoint="local.stress.invariants.ambiguous_issue:check_ambiguous_issue_stress",
            resource_limits={"max_candidate_probes": 5},
            related_regression_ids=["REG-POLICY-001", "REG-RETRIEVAL-001"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-LIVE-AMBIGUOUS-001",
            version="1.0.0",
            title="Live Model Cognitive Disambiguation of Ambiguous Issue",
            category=StressCategory.LIVE_MODEL_EVALUATION,
            stress_type=StressType.LIVE_MODEL_DRIVEN,
            severity=StressSeverity.CRITICAL,
            scenario_description="Live Gemma 4 31B model cognitive reasoning across competing code candidates on real repository context.",
            fixture_type="live_model_evaluation",
            source_requirement="PLAN.md Stage 46 STRESS 2",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Live model accurately identifies root cause despite ambiguous phrasing",
            ],
            execution_entrypoint="local.stress.invariants.blocked_live:check_live_ambiguous_stress",
            resource_limits={"model": "google/gemma-4-31b-it", "hardware": "GPU"},
            related_regression_ids=["REG-BLOCKED-001"],
            testing_tier="live_model_driven",
            status=StressStatus.BLOCKED,
            terminal_status="BLOCKED",
            blocked_reason="Live Gemma 4 31B model inference is not available on local CPU-only host; cognitive disambiguation cannot be executed without live model.",
        ),
        # 3. Misleading Function Names
        StressCase(
            stress_id="STRESS-MISLEADING-001",
            version="1.0.0",
            title="Misleading Function Name AST and Test Grounding",
            category=StressCategory.MISLEADING_NAMES,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Symbol names claim one semantic behavior while AST implementation and test assertions prove another; harness detects the contradiction.",
            fixture_type="synthetic_misleading_source",
            source_requirement="PLAN.md Stage 46 STRESS 3",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "AST inspection reveals conflicting operation (Mult vs Add)",
                "Concrete test assertion failure reproduces contradiction",
                "Symbol name similarity alone rejected as proof of behavior",
            ],
            execution_entrypoint="local.stress.invariants.misleading_names:check_misleading_names_stress",
            resource_limits={"max_duration_seconds": 5.0},
            related_regression_ids=["REG-POLICY-001", "REG-TESTING-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-LIVE-MISLEADING-001",
            version="1.0.0",
            title="Live Model Semantic Disambiguation of Misleading Functions",
            category=StressCategory.LIVE_MODEL_EVALUATION,
            stress_type=StressType.LIVE_MODEL_DRIVEN,
            severity=StressSeverity.CRITICAL,
            scenario_description="Live Gemma 4 31B model cognitive detection that function body contradicts function name without being misled by naming cues.",
            fixture_type="live_model_evaluation",
            source_requirement="PLAN.md Stage 46 STRESS 3",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Live model diagnoses contradiction between name and implementation",
            ],
            execution_entrypoint="local.stress.invariants.blocked_live:check_live_misleading_stress",
            resource_limits={"model": "google/gemma-4-31b-it", "hardware": "GPU"},
            related_regression_ids=["REG-BLOCKED-001"],
            testing_tier="live_model_driven",
            status=StressStatus.BLOCKED,
            terminal_status="BLOCKED",
            blocked_reason="Live Gemma 4 31B model inference is not available on local CPU-only host; semantic reasoning over misleading function names cannot be executed without live model.",
        ),
        # 4. Multi-File Fix
        StressCase(
            stress_id="STRESS-MULTIFILE-001",
            version="1.0.0",
            title="Multi-File Fix Patch Extraction and Clean-Copy Application",
            category=StressCategory.MULTIFILE_FIX,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="A cross-contract bug fix spans caller, implementation, and test files; PatchExtractor captures all hunks while keeping intermediary files clean.",
            fixture_type="synthetic_multifile_repository",
            source_requirement="PLAN.md Stage 46 STRESS 4",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "All modified files represented in PatchBundle",
                "Unified diff preserves hunks across all modified files",
                "Untouched intermediary files remain clean",
                "FreshPatchApplier applies patch without conflict to fresh copy",
                "Tests pass in clean validation copy",
            ],
            execution_entrypoint="local.stress.invariants.multifile_fix:check_multifile_fix_stress",
            resource_limits={"max_duration_seconds": 10.0},
            related_regression_ids=["REG-DIFF-001", "REG-GRAPH-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 5. Hidden Dependency Relationship
        StressCase(
            stress_id="STRESS-GRAPH-001",
            version="1.0.0",
            title="Hidden Dependency Bounded Graph Discovery",
            category=StressCategory.HIDDEN_DEPENDENCY,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Uncover indirect/hidden relational dependencies across 3 hops without triggering context explosion or exceeding neighbor retention bounds.",
            fixture_type="synthetic_call_graph",
            source_requirement="PLAN.md Stage 46 STRESS 5",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Hidden dependency discovered along relational path",
                "Retained neighbors strictly bounded (<= max_retained)",
                "Unrelated graph nodes pruned from expansion",
            ],
            execution_entrypoint="local.stress.invariants.hidden_dependency:check_hidden_dependency_stress",
            resource_limits={"max_retained_neighbors": 5, "max_depth": 3},
            related_regression_ids=["REG-GRAPH-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 6. Failing Test with Long Logs
        StressCase(
            stress_id="STRESS-LOG-001",
            version="1.0.0",
            title="Bounded Long-Log Compaction with Trace Preservation",
            category=StressCategory.LONG_LOGS,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.MEDIUM,
            scenario_description="Test execution outputs 50,000+ bytes of repetitive logs; compaction preserves critical initial traceback and final summary within 1,500 chars.",
            fixture_type="synthetic_verbose_log",
            source_requirement="PLAN.md Stage 46 STRESS 6",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Log output compacted to <= 1,500 characters",
                "Core error trace key preserved",
                "Final failure summary preserved",
                "Truncation banner recorded",
                "Temporary log cleaned up safely",
            ],
            execution_entrypoint="local.stress.invariants.long_log:check_long_log_stress",
            resource_limits={"log_bytes": 50000, "max_summary_length": 1500},
            related_regression_ids=["REG-TESTING-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 7. Pre-Existing Failing Test
        StressCase(
            stress_id="STRESS-PREEXISTING-001",
            version="1.0.0",
            title="Pre-Existing Test Failure Isolation",
            category=StressCategory.PREEXISTING_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Baseline project contains a known failing legacy test; candidate change fixes target test without resolving or being blamed for baseline failure.",
            fixture_type="synthetic_test_project",
            source_requirement="PLAN.md Stage 46 STRESS 7",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Baseline test failure established prior to candidate changes",
                "Pre-existing failure distinguished from newly introduced regression",
                "Target test correctly classified as RESOLVED",
                "Zero false regressions reported",
            ],
            execution_entrypoint="local.stress.invariants.preexisting_failure:check_preexisting_failure_stress",
            resource_limits={"max_duration_seconds": 5.0},
            related_regression_ids=["REG-TESTING-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 8. Required New File
        StressCase(
            stress_id="STRESS-NEWFILE-001",
            version="1.0.0",
            title="Required New File Detection and Clean-Copy Reconstitution",
            category=StressCategory.NEW_FILE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Defect fix requires adding a brand new untracked file; PatchExtractor stages it via 'git add -N .' and FreshPatchApplier creates it in clean copy.",
            fixture_type="synthetic_new_file_repository",
            source_requirement="PLAN.md Stage 46 STRESS 8",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Untracked new file detected in PatchBundle.added_files",
                "Relative file path preserved",
                "Unified diff includes new file creation from /dev/null",
                "FreshPatchApplier writes new file into validation workspace",
                "Validation tests execute and pass with new file present",
            ],
            execution_entrypoint="local.stress.invariants.new_file:check_new_file_stress",
            resource_limits={"max_duration_seconds": 10.0},
            related_regression_ids=["REG-HYGIENE-001", "REG-DIFF-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 9. Binary or Unusual File Intent
        StressCase(
            stress_id="STRESS-BINARY-001",
            version="1.0.0",
            title="Binary File Null-Byte Detection and Safe Diagnostics",
            category=StressCategory.BINARY_FILE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.MEDIUM,
            scenario_description="Binary file with null bytes is evaluated; detector prevents text corruption, avoids leaking binary characters into logs, and handles safely.",
            fixture_type="synthetic_binary_file",
            source_requirement="PLAN.md Stage 46 STRESS 9",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Binary null byte correctly detected",
                "Text-only decode raises UnicodeDecodeError without silent corruption",
                "Diagnostic preview formats safely without control characters",
            ],
            execution_entrypoint="local.stress.invariants.binary_file:check_binary_file_stress",
            resource_limits={"file_bytes": 128},
            related_regression_ids=["REG-SUBMISSION-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 10. Repeated Test Failure Patterns (Stage 35 patterns 1 to 10)
        StressCase(
            stress_id="STRESS-RECOVERY-001",
            version="1.0.0",
            title="Repeated Command Detection and Discrimination",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Detect repeated identical test commands without progress; discriminate distinct commands as non-repeated.",
            fixture_type="synthetic_cycle_history",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Repeated command detected at threshold=2",
                "Distinct command not falsely flagged",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_repeated_command",
            resource_limits={"threshold": 2},
            related_regression_ids=["REG-RECOVERY-001"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-002",
            version="1.0.0",
            title="Repeated Error Signature Detection",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Recurring identical error signature across command variants is recognized as REPEATED_FAILURE.",
            fixture_type="synthetic_cycle_history",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Recurring error signature classified as REPEATED_FAILURE",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_repeated_error",
            resource_limits={"threshold": 2},
            related_regression_ids=["REG-RECOVERY-002"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-003",
            version="1.0.0",
            title="Repeated Code Edit Detection",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Identical code modification attempted across multiple cycles is flagged as REPEATED_EDIT.",
            fixture_type="synthetic_cycle_history",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Identical diff content flagged as NO_PROGRESS on cycle 2",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_repeated_edit",
            resource_limits={"threshold": 2},
            related_regression_ids=["REG-RECOVERY-003"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-004",
            version="1.0.0",
            title="Repeated Hypothesis Diagnosis Detection",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Identical root-cause hypothesis repeated without new diagnostic evidence triggers REPEATED_HYPOTHESIS.",
            fixture_type="synthetic_cycle_history",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Repeated hypothesis string classified as REPEATED_HYPOTHESIS",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_repeated_hypothesis",
            resource_limits={"threshold": 2},
            related_regression_ids=["REG-RECOVERY-004"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-005",
            version="1.0.0",
            title="Recovery Direct Loop and Oscillation Detection",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Alternating A -> B -> A -> B recovery actions detected as an oscillation loop.",
            fixture_type="synthetic_recovery_events",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Oscillation detected and cycle count accurately measured",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_recovery_loop",
            resource_limits={"max_direct_repeats": 2},
            related_regression_ids=["REG-RECOVERY-005"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-006",
            version="1.0.0",
            title="Recovery Thrashing Across Multiple Actions",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.DETERMINISTIC_COMPONENT,
            severity=StressSeverity.HIGH,
            scenario_description="Rapid sequence of 5 distinct failed recovery actions identified as THRASHING.",
            fixture_type="synthetic_recovery_events",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Thrashing recognized and loop_type marked as THRASHING",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_recovery_thrashing",
            resource_limits={"max_direct_repeats": 2},
            related_regression_ids=["REG-RECOVERY-006"],
            testing_tier="deterministic_component",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-007",
            version="1.0.0",
            title="Retry Waste Prevention Under Exhausted Budget",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.HIGH,
            scenario_description="Recovery policy halts further attempts once max retries per failure signature is reached.",
            fixture_type="synthetic_retry_budget",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Retry rejected when attempt count reaches limit",
                "Rationale documents budget exhaustion",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_retry_waste",
            resource_limits={"max_retries": 3},
            related_regression_ids=["REG-RECOVERY-007"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-008",
            version="1.0.0",
            title="Recovery Omission Prevention",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.HIGH,
            scenario_description="Mandates recovery activation after 2 consecutive unhandled test failures.",
            fixture_type="synthetic_recovery_policy",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Recovery trigger mandated after 2 consecutive failures",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_recovery_omission",
            resource_limits={"consecutive_failures": 2},
            related_regression_ids=["REG-RECOVERY-008"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-009",
            version="1.0.0",
            title="Late Recovery Boundary Enforcement",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.MEDIUM,
            scenario_description="Detects when recovery is initiated excessively late (e.g. cycle 5 vs limit of 3).",
            fixture_type="synthetic_recovery_policy",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Delay beyond max_delay flagged as delayed recovery",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_late_recovery",
            resource_limits={"max_delay": 3},
            related_regression_ids=["REG-RECOVERY-009"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        StressCase(
            stress_id="STRESS-RECOVERY-010",
            version="1.0.0",
            title="Failed Recovery Terminal Tracking",
            category=StressCategory.REPEATED_FAILURE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.HIGH,
            scenario_description="Records recovery exhaustion as a terminal failure without entering infinite retries.",
            fixture_type="synthetic_recovery_outcome",
            source_requirement="PLAN.md Stage 46 STRESS 10",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Terminal state set to True",
                "Success marked False with documented final failure reason",
            ],
            execution_entrypoint="local.stress.invariants.repeated_failure:check_stress_failed_recovery",
            resource_limits={},
            related_regression_ids=["REG-RECOVERY-010"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
        # 11. Expensive Full-Suite Tests
        StressCase(
            stress_id="STRESS-EXPENSIVE-001",
            version="1.0.0",
            title="Expensive Full-Suite Feasibility Evaluation",
            category=StressCategory.EXPENSIVE_SUITE,
            stress_type=StressType.ORCHESTRATION_POLICY,
            severity=StressSeverity.HIGH,
            scenario_description="When estimated full-suite runtime exceeds remaining budget, evaluator rejects full suite as NOT_FEASIBLE and preserves targeted validation.",
            fixture_type="synthetic_test_policy",
            source_requirement="PLAN.md Stage 46 STRESS 11",
            provenance={"commit": "9b137adcf25f90ba264f114980852afdd1bfeed0", "stage": "Stage 46"},
            expected_invariants=[
                "Full-suite classified as NOT_FEASIBLE",
                "Rationale documents time budget violation",
                "Targeted validation prioritized over unconstrained run",
                "Mocked execution explicitly reported",
            ],
            execution_entrypoint="local.stress.invariants.expensive_suite:check_expensive_suite_stress",
            resource_limits={"max_runtime_seconds": 600.0, "budget_seconds": 300.0},
            related_regression_ids=["REG-TESTING-002"],
            testing_tier="orchestration_policy",
            status=StressStatus.ACTIVE,
            terminal_status="PASS",
        ),
    ]


def validate_catalog(cases: Optional[list[StressCase]] = None) -> list[str]:
    """Validates stress catalog against integrity rules.

    Rules:
    1. Unique stress IDs.
    2. Unique signatures.
    3. Valid category and stress_type enums.
    4. Valid status values.
    5. Valid execution entrypoint format (module:func).
    6. Non-empty expected_invariants.
    7. All related_regression_ids exist in the Stage 45 regression catalog.
    8. Zero locked held-out task references.
    9. Terminal status consistent with active/blocked status.

    Returns:
        List of error messages (empty if valid).
    """
    if cases is None:
        cases = get_canonical_catalog()

    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_signatures: set[str] = set()

    # Load Stage 45 regression catalog for reference validation
    reg_catalog = get_canonical_regression_catalog()
    valid_reg_ids = {r.regression_id for r in reg_catalog}

    for c in cases:
        # Rule 1: Unique IDs
        if c.stress_id in seen_ids:
            errors.append(f"Duplicate stress_id '{c.stress_id}' found")
        seen_ids.add(c.stress_id)

        # Rule 2: Unique signatures
        if c.signature in seen_signatures:
            errors.append(f"Duplicate signature '{c.signature}' for stress case '{c.stress_id}'")
        seen_signatures.add(c.signature)

        # Rule 5: Entrypoint format
        if ":" not in c.execution_entrypoint:
            errors.append(f"Invalid execution_entrypoint '{c.execution_entrypoint}' in '{c.stress_id}'")

        # Rule 6: Non-empty invariants
        if not c.expected_invariants:
            errors.append(f"Stress case '{c.stress_id}' has empty expected_invariants")

        # Rule 7: Valid regression references
        for reg_id in c.related_regression_ids:
            if reg_id not in valid_reg_ids:
                errors.append(f"Stress case '{c.stress_id}' references unknown regression ID '{reg_id}'")

        # Rule 8: Held-out protection
        lock_p = PROJECT_ROOT / "benchmark" / "splits" / "v1" / "held_out.lock"
        for inv in c.expected_invariants:
            if is_held_out_task(inv, lock_path=lock_p):
                errors.append(f"Stress case '{c.stress_id}' contains held-out task '{inv}' in invariants")
        if is_held_out_task(c.scenario_description, lock_path=lock_p) or is_held_out_task(c.title, lock_path=lock_p):
            errors.append(f"Stress case '{c.stress_id}' references held-out task")

        # Rule 9: Terminal status consistency
        if c.status == StressStatus.BLOCKED and c.terminal_status != "BLOCKED":
            errors.append(f"Blocked stress case '{c.stress_id}' must have terminal_status='BLOCKED', got '{c.terminal_status}'")
        if c.status == StressStatus.ACTIVE and c.terminal_status != "PASS":
            errors.append(f"Active stress case '{c.stress_id}' expected terminal_status='PASS', got '{c.terminal_status}'")

    return errors


def build_stress_manifest(
    cases: Optional[list[StressCase]] = None,
    commit_hash: str = "9b137adcf25f90ba264f114980852afdd1bfeed0",
) -> StressManifest:
    """Builds and hashes the authoritative stress manifest."""
    if cases is None:
        cases = get_canonical_catalog()

    cases_dicts = [c.to_dict() for c in cases]
    now_utc = datetime.now(timezone.utc).isoformat()
    return StressManifest(
        schema_version=STRESS_SCHEMA_VERSION,
        created_at_utc=now_utc,
        commit_hash=commit_hash,
        total_cases=len(cases_dicts),
        cases=cases_dicts,
    )


def save_catalog_to_disk(
    manifest: Optional[StressManifest] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Saves the stress manifest and individual case JSONs to disk."""
    if output_dir is None:
        output_dir = STRESS_EXP_DIR
    if manifest is None:
        manifest = build_stress_manifest()

    cases_dir = output_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    # Save individual cases
    for case_dict in manifest.cases:
        cid = case_dict["stress_id"]
        c_path = cases_dir / f"{cid}.json"
        c_path.write_text(json.dumps(case_dict, indent=2), encoding="utf-8")

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

    return manifest_path


def load_manifest_from_disk(path: Optional[Path] = None) -> StressManifest:
    """Loads and validates a stress manifest from disk."""
    if path is None:
        path = STRESS_EXP_DIR / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Stress manifest file not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    manifest = StressManifest.from_dict(data)

    computed = manifest.compute_sha256()
    if manifest.manifest_sha256 != computed:
        raise ValueError(
            f"Stress manifest SHA256 integrity mismatch: expected {manifest.manifest_sha256}, computed {computed}"
        )
    return manifest
