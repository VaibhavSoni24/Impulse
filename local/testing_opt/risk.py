"""Observable Risk Signal Evaluation and Adaptive Escalation Controller (Stage 34 Sections 8, 9, 26).

Provides:
- Detection of explicit, observable risk signals from diffs, task state, and test outcomes
- Deterministic evaluation of risk severity
- Decision logic for T3 adaptive escalation ladder (TARGETED -> ADJACENT -> SUBSYSTEM -> FULL)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from local.testing_opt.feasibility import FullSuiteFeasibilityEvaluator
from local.testing_opt.models import (
    AdaptiveEscalationTrace,
    FullSuiteFeasibility,
    RiskSignal,
    RiskSignalType,
    TestLevel,
    TestPolicy,
)


class AdaptiveDecision(str, Enum):
    STOP = "STOP"
    ESCALATE = "ESCALATE"


class RiskSignalEvaluator:
    """Evaluates concrete repository and diff observations into structured risk signals."""

    @staticmethod
    def evaluate_diff_risk(
        modified_files: List[str],
        added_lines: int,
        deleted_lines: int,
        is_public_api_modified: bool = False,
        is_shared_utility_modified: bool = False,
        is_test_infra_modified: bool = False,
        is_dependency_config_modified: bool = False,
        has_new_critical_file: bool = False,
    ) -> List[RiskSignal]:
        """Extracts deterministic risk signals from a code modification."""
        signals: List[RiskSignal] = []

        # 1. Multiple files changed
        if len(modified_files) > 1:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.MULTIPLE_FILES_CHANGED.value,
                    severity="MEDIUM" if len(modified_files) <= 3 else "HIGH",
                    rationale=f"Modification spans {len(modified_files)} files.",
                    evidence_reference=", ".join(modified_files),
                )
            )

        # 2. Large diff size (> 50 total lines)
        total_lines = added_lines + deleted_lines
        if total_lines > 50:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.LARGE_DIFF_SIZE.value,
                    severity="MEDIUM" if total_lines <= 150 else "HIGH",
                    rationale=f"Diff size ({total_lines} lines) exceeds threshold (50 lines).",
                    evidence_reference=f"+{added_lines}/-{deleted_lines}",
                )
            )

        # 3. Public API surface
        if is_public_api_modified:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.PUBLIC_API_CHANGED.value,
                    severity="HIGH",
                    rationale="Public module API, function signature, or exports modified.",
                    evidence_reference="public_api",
                )
            )

        # 4. Shared utility
        if is_shared_utility_modified:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.SHARED_UTILITY_CHANGED.value,
                    severity="HIGH",
                    rationale="Shared core utility with broad repository callers modified.",
                    evidence_reference="shared_utility",
                )
            )

        # 5. Test infrastructure
        if is_test_infra_modified:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.TEST_INFRASTRUCTURE_CHANGED.value,
                    severity="HIGH",
                    rationale="Test fixtures, runners, or conftest configurations modified.",
                    evidence_reference="test_infrastructure",
                )
            )

        # 6. Dependency configuration
        if is_dependency_config_modified:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.DEPENDENCY_CONFIG_CHANGED.value,
                    severity="CRITICAL",
                    rationale="Package metadata or dependency requirements modified.",
                    evidence_reference="dependency_config",
                )
            )

        # 7. New critical file
        if has_new_critical_file:
            signals.append(
                RiskSignal(
                    signal_type=RiskSignalType.CRITICAL_PATH_NEW_FILE.value,
                    severity="HIGH",
                    rationale="New source file added to core package execution path.",
                    evidence_reference="critical_path",
                )
            )

        return signals

    @staticmethod
    def compute_aggregate_risk_level(signals: List[RiskSignal]) -> str:
        """Determines aggregate risk level (LOW, MEDIUM, HIGH, CRITICAL)."""
        if not signals:
            return "LOW"
        severities = {s.severity.upper() for s in signals if s.observed}
        if "CRITICAL" in severities:
            return "CRITICAL"
        if "HIGH" in severities:
            return "HIGH"
        if "MEDIUM" in severities:
            return "MEDIUM"
        return "LOW"


class AdaptiveEscalationController:
    """Controls dynamic test level transitions (T3) using explicit deterministic rules."""

    def __init__(self, policy: TestPolicy) -> None:
        self.policy = policy
        self.feasibility_evaluator = FullSuiteFeasibilityEvaluator(policy)

    def decide_next_step(
        self,
        current_level: str,
        test_passed: bool,
        risk_signals: List[RiskSignal],
        commands_executed: int,
        remaining_budget_seconds: float,
        round_index: int = 1,
        suite_feasibility: Optional[FullSuiteFeasibility] = None,
    ) -> AdaptiveEscalationTrace:
        """Decides whether to STOP or ESCALATE to the next test level."""
        # Budget exhaustion guard
        if commands_executed >= self.policy.max_test_commands:
            return AdaptiveEscalationTrace(
                round_index=round_index,
                current_level=current_level,
                test_result="PASS" if test_passed else "FAIL",
                observed_risk_signals=[s.signal_type for s in risk_signals],
                decision="STOP",
                target_level=None,
                decision_rationale=f"Max test commands budget ({self.policy.max_test_commands}) reached.",
                budget_remaining_commands=0,
                budget_remaining_seconds=remaining_budget_seconds,
            )

        if remaining_budget_seconds <= 0:
            return AdaptiveEscalationTrace(
                round_index=round_index,
                current_level=current_level,
                test_result="PASS" if test_passed else "FAIL",
                observed_risk_signals=[s.signal_type for s in risk_signals],
                decision="STOP",
                target_level=None,
                decision_rationale="Runtime budget exhausted.",
                budget_remaining_commands=max(0, self.policy.max_test_commands - commands_executed),
                budget_remaining_seconds=0.0,
            )

        risk_level = RiskSignalEvaluator.compute_aggregate_risk_level(risk_signals)

        # Level 1: TARGETED
        if current_level == TestLevel.TARGETED.value:
            if not test_passed:
                # Targeted test failed -> Escalate to adjacent to verify fault scope
                return AdaptiveEscalationTrace(
                    round_index=round_index,
                    current_level=current_level,
                    test_result="FAIL",
                    observed_risk_signals=[s.signal_type for s in risk_signals],
                    decision="ESCALATE",
                    target_level=TestLevel.ADJACENT.value,
                    decision_rationale="Targeted test failed; escalating to adjacent tests to check fault scope.",
                    budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                    budget_remaining_seconds=remaining_budget_seconds,
                )
            else:
                if risk_level == "LOW":
                    # Passed with low risk -> STOP early
                    return AdaptiveEscalationTrace(
                        round_index=round_index,
                        current_level=current_level,
                        test_result="PASS",
                        observed_risk_signals=[s.signal_type for s in risk_signals],
                        decision="STOP",
                        target_level=None,
                        decision_rationale="Targeted test passed with low regression risk; stopping early.",
                        budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                        budget_remaining_seconds=remaining_budget_seconds,
                    )
                else:
                    # Passed, but high/medium risk -> Escalate to adjacent
                    return AdaptiveEscalationTrace(
                        round_index=round_index,
                        current_level=current_level,
                        test_result="PASS",
                        observed_risk_signals=[s.signal_type for s in risk_signals],
                        decision="ESCALATE",
                        target_level=TestLevel.ADJACENT.value,
                        decision_rationale=f"Targeted test passed, but {risk_level} risk signals detected; escalating to adjacent tests.",
                        budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                        budget_remaining_seconds=remaining_budget_seconds,
                    )

        # Level 2: ADJACENT
        elif current_level == TestLevel.ADJACENT.value:
            if not test_passed:
                # Adjacent regression discovered -> Escalate to subsystem
                return AdaptiveEscalationTrace(
                    round_index=round_index,
                    current_level=current_level,
                    test_result="FAIL",
                    observed_risk_signals=[s.signal_type for s in risk_signals],
                    decision="ESCALATE",
                    target_level=TestLevel.SUBSYSTEM.value,
                    decision_rationale="Adjacent test regression discovered; escalating to subsystem suite.",
                    budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                    budget_remaining_seconds=remaining_budget_seconds,
                )
            else:
                if risk_level in ("LOW", "MEDIUM"):
                    return AdaptiveEscalationTrace(
                        round_index=round_index,
                        current_level=current_level,
                        test_result="PASS",
                        observed_risk_signals=[s.signal_type for s in risk_signals],
                        decision="STOP",
                        target_level=None,
                        decision_rationale="Adjacent tests passed cleanly; risk sufficiently mitigated.",
                        budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                        budget_remaining_seconds=remaining_budget_seconds,
                    )
                else:
                    # High/Critical risk remains
                    return AdaptiveEscalationTrace(
                        round_index=round_index,
                        current_level=current_level,
                        test_result="PASS",
                        observed_risk_signals=[s.signal_type for s in risk_signals],
                        decision="ESCALATE",
                        target_level=TestLevel.SUBSYSTEM.value,
                        decision_rationale=f"Adjacent tests passed, but {risk_level} risk requires subsystem verification.",
                        budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                        budget_remaining_seconds=remaining_budget_seconds,
                    )

        # Level 3: SUBSYSTEM
        elif current_level == TestLevel.SUBSYSTEM.value:
            if not test_passed:
                # Subsystem test failure -> Stop and report
                return AdaptiveEscalationTrace(
                    round_index=round_index,
                    current_level=current_level,
                    test_result="FAIL",
                    observed_risk_signals=[s.signal_type for s in risk_signals],
                    decision="STOP",
                    target_level=None,
                    decision_rationale="Subsystem failure confirmed; halting further broad testing.",
                    budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                    budget_remaining_seconds=remaining_budget_seconds,
                )
            else:
                # Subsystem passed. Check whether full suite is justified and feasible
                feas_status = suite_feasibility or FullSuiteFeasibility.UNKNOWN
                if risk_level in ("HIGH", "CRITICAL") and feas_status == FullSuiteFeasibility.FEASIBLE:
                    return AdaptiveEscalationTrace(
                        round_index=round_index,
                        current_level=current_level,
                        test_result="PASS",
                        observed_risk_signals=[s.signal_type for s in risk_signals],
                        decision="ESCALATE",
                        target_level=TestLevel.FULL.value,
                        decision_rationale="Critical cross-module risk and feasible full suite; escalating to full verification.",
                        budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                        budget_remaining_seconds=remaining_budget_seconds,
                    )
                return AdaptiveEscalationTrace(
                    round_index=round_index,
                    current_level=current_level,
                    test_result="PASS",
                    observed_risk_signals=[s.signal_type for s in risk_signals],
                    decision="STOP",
                    target_level=None,
                    decision_rationale="Subsystem verified; full suite omitted (low risk or infeasible).",
                    budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                    budget_remaining_seconds=remaining_budget_seconds,
                )

        # Level 4: FULL
        else:
            return AdaptiveEscalationTrace(
                round_index=round_index,
                current_level=current_level,
                test_result="PASS" if test_passed else "FAIL",
                observed_risk_signals=[s.signal_type for s in risk_signals],
                decision="STOP",
                target_level=None,
                decision_rationale="Full-suite verification concluded (terminal level).",
                budget_remaining_commands=self.policy.max_test_commands - commands_executed,
                budget_remaining_seconds=remaining_budget_seconds,
            )
