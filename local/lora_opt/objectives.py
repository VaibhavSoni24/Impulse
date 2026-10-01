"""Candidate Training Objective Definition and Selection Engine (Stage 37 Sections 8, 9).

Formulates behaviorally narrow, measurable LoRA candidate objectives derived from
the measured failure taxonomy and architecture.

Applies the strict Selection Rule (Section 9):
- Selects exactly ONE primary objective
- Optionally ONE secondary candidate
- Rejects overly broad objectives ("make the agent smarter")
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from local.failures.models import FailureClass
from local.lora_opt.models import CandidateObjective, ObjectiveStatus

CANONICAL_CANDIDATE_OBJECTIVES: list[CandidateObjective] = [
    CandidateObjective(
        objective_id="OBJ-TOOL-DISCIPLINE",
        name="Reduce Repeated Failing Commands & Improve Tool Invocation Correctness",
        problem_definition=(
            "Agent repeatedly executes identical failing shell or test commands (FailureClass.COMMAND "
            "and Stage 19 REPEATED_COMMAND_FAILURE) without inspecting error traces or adjusting arguments."
        ),
        target_failure_classes=[FailureClass.COMMAND.value],
        observable_input="Command execution failure output (non-zero exit code or stderr) in agent context.",
        desired_behavior="Inspect failure trace and immediately adjust arguments, fix syntax, or choose alternative verification.",
        undesired_behavior="Re-issuing verbatim identical failed command without argument or environment adjustments.",
        training_signal="Trajectory pairs demonstrating rapid parameter correction vs. repeated verbatim failure.",
        evaluation_metric="command_redundancy_count and repeated_command_loop_rate",
        primary_benchmark_split="dev",
        negative_behavior="Repeating identical command when stdout/stderr diagnostic is unchanged.",
        possible_confounders=["Intermittent environment network flakiness requiring single transient retry."],
        minimum_evidence_required="Validated baseline trajectories exhibiting command redundancy.",
        status=ObjectiveStatus.PRIMARY_SELECTED.value,
    ),
    CandidateObjective(
        objective_id="OBJ-TARGETED-TEST-SELECTION",
        name="Improve Targeted Test Selection After Code Edits",
        problem_definition=(
            "Agent executes broad repository test sweeps or irrelevant test files after a localized edit, "
            "exhausting tool call and execution time budgets."
        ),
        target_failure_classes=[FailureClass.COMMAND.value, FailureClass.REGRESSION.value],
        observable_input="Source code diff and repository test directory structure.",
        desired_behavior="Formulate narrow test command targeting the specific test module exercising modified symbols.",
        undesired_behavior="Running full test suites (e.g. 'pytest tests/') or unrelated unit tests after localized edits.",
        training_signal="Trajectories selecting exact target test symbol matching modified diff hunk.",
        evaluation_metric="targeted_test_selection_accuracy and irrelevant_tests_executed_count",
        primary_benchmark_split="dev",
        negative_behavior="Executing test suites covering components unrelated to modified files.",
        possible_confounders=["Multi-module architectural dependencies requiring broader verification."],
        minimum_evidence_required="Validated test discovery trajectories across dev benchmark tasks.",
        status=ObjectiveStatus.SECONDARY_CANDIDATE.value,
    ),
    CandidateObjective(
        objective_id="OBJ-GENERIC-SWE-AGENT",
        name="General Autonomous Software Engineering Capability",
        problem_definition="Make the agent generically smarter and solve more SWE-bench repository defects.",
        target_failure_classes=["ALL"],
        observable_input="Complete issue statement and entire repository tree.",
        desired_behavior="Solve all tasks correctly without error.",
        undesired_behavior="Any failure to resolve an issue.",
        training_signal="End-to-end task success trajectories.",
        evaluation_metric="overall_pass_rate",
        primary_benchmark_split="dev",
        negative_behavior="Any incorrect patch.",
        possible_confounders=["Retrieval, prompting, testing strategy, recovery loops, and host environment."],
        minimum_evidence_required="Unobtainable for single-dimension causal isolation.",
        status=ObjectiveStatus.REJECTED_TOO_BROAD.value,
    ),
]


class ObjectiveSelector:
    """Evaluates candidate objectives and enforces the strict Selection Rule."""

    def __init__(self, objectives: Optional[List[CandidateObjective]] = None) -> None:
        self.objectives = objectives or CANONICAL_CANDIDATE_OBJECTIVES

    def evaluate_and_select(self) -> Tuple[Optional[CandidateObjective], Optional[CandidateObjective], List[CandidateObjective]]:
        """Applies selection rule: returns (primary, secondary, all_candidates)."""
        primary: Optional[CandidateObjective] = None
        secondary: Optional[CandidateObjective] = None

        for obj in self.objectives:
            # Rejection rule: "ALL" target classes or generic "make smarter" problem definition
            if "ALL" in obj.target_failure_classes or "smarter" in obj.problem_definition.lower():
                obj.status = ObjectiveStatus.REJECTED_TOO_BROAD.value
                continue

            if obj.objective_id == "OBJ-TOOL-DISCIPLINE":
                obj.status = ObjectiveStatus.PRIMARY_SELECTED.value
                primary = obj
            elif obj.objective_id == "OBJ-TARGETED-TEST-SELECTION" and not secondary:
                obj.status = ObjectiveStatus.SECONDARY_CANDIDATE.value
                secondary = obj
        return primary, secondary, self.objectives


def get_candidate_objectives() -> List[CandidateObjective]:
    """Returns freshly copied instances of canonical candidate objectives."""
    return [CandidateObjective.from_dict(o.to_dict()) for o in CANONICAL_CANDIDATE_OBJECTIVES]


def select_objectives(
    candidates: Optional[List[CandidateObjective]] = None,
) -> Tuple[Optional[CandidateObjective], Optional[CandidateObjective]]:
    """Applies strict selection rule and returns (primary, secondary)."""
    selector = ObjectiveSelector(candidates)
    primary, secondary, _ = selector.evaluate_and_select()
    return primary, secondary
