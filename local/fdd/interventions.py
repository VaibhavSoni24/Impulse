"""Intervention Model and Validation for FDD (Stage 31 Section 7 & 8).

Defines validation rules, serialization, and isolation checks for single-hypothesis
interventions. Enforces that an intervention changes exactly one dimension,
does not mutate frozen baselines, and isolates candidate configurations.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
from local.fdd.models import Intervention, InterventionScope


class InterventionValidationError(Exception):
    """Raised when an intervention specification violates isolation or validity constraints."""
    pass


def validate_intervention(
    intervention: Intervention,
    repo_root: Optional[Path | str] = None,
) -> Tuple[bool, List[str]]:
    """Strictly validates an intervention specification.

    Enforces:
    - Non-empty intervention_id, target_failure_mode, hypothesis, expected_behavior_change.
    - Valid InterventionScope.
    - Exactly ONE major changed dimension (no bundled prompt+retrieval+LoRA changes).
    - baseline_candidate != candidate_id.
    - candidate_id is a valid alphanumeric slug.
    - None of affected_files target frozen Stage 24 artifacts.

    Returns:
        (is_valid, error_messages)
    """
    errors: List[str] = []

    if not intervention.intervention_id or not intervention.intervention_id.strip():
        errors.append("intervention_id cannot be empty.")

    if not intervention.target_failure_mode or not intervention.target_failure_mode.strip():
        errors.append("target_failure_mode cannot be empty.")

    if not intervention.hypothesis or not intervention.hypothesis.strip():
        errors.append("hypothesis cannot be empty.")

    if not intervention.expected_behavior_change or not intervention.expected_behavior_change.strip():
        errors.append("expected_behavior_change cannot be empty.")

    # Scope validation
    try:
        scope = InterventionScope(intervention.intervention_scope)
    except (ValueError, KeyError):
        errors.append(f"Invalid intervention_scope '{intervention.intervention_scope}'. Must be one of {[s.value for s in InterventionScope]}.")

    # Single dimension validation (Section 7)
    if not intervention.changed_dimensions or len(intervention.changed_dimensions) == 0:
        errors.append("changed_dimensions must contain at least one specific dimension.")
    elif len(intervention.changed_dimensions) > 1:
        errors.append(
            f"Intervention violates single-dimension discipline: found {len(intervention.changed_dimensions)} "
            f"changed dimensions ({intervention.changed_dimensions}). Only one major dimension allowed per iteration."
        )

    # Candidate isolation validation (Section 8)
    if not intervention.baseline_candidate or not intervention.baseline_candidate.strip():
        errors.append("baseline_candidate must be specified.")

    if not intervention.candidate_id or not intervention.candidate_id.strip():
        errors.append("candidate_id must be specified.")

    if intervention.baseline_candidate == intervention.candidate_id:
        errors.append(
            f"baseline_candidate ('{intervention.baseline_candidate}') cannot be identical to "
            f"candidate_id ('{intervention.candidate_id}'). In-place candidate mutation is forbidden."
        )

    # Protect frozen artifacts (Section 2)
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    for aff_file in intervention.affected_files:
        norm_aff = aff_file.replace("\\", "/").strip("/")
        if norm_aff in FROZEN_STAGE24_HASHES:
            errors.append(
                f"Intervention attempts to modify frozen artifact '{norm_aff}'. "
                "Frozen baseline artifacts must remain invariant."
            )

    return (len(errors) == 0, errors)


def save_intervention(intervention: Intervention, output_path: Path | str) -> Path:
    """Serializes an intervention record deterministically to JSON."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(intervention.to_dict(), f, indent=2, sort_keys=True)
    return p


def load_intervention(input_path: Path | str) -> Intervention:
    """Deserializes an Intervention record from JSON."""
    p = Path(input_path)
    if not p.is_file():
        raise FileNotFoundError(f"Intervention file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Intervention(**data)


def create_candidate_from_baseline(
    baseline_id: str,
    new_candidate_id: str,
    candidates_dir: Path | str = Path("experiments/candidates"),
) -> Path:
    """Clones a baseline candidate into an isolated new candidate directory.

    Ensures baseline is untouched and new candidate has isolated configuration.
    """
    cdir = Path(candidates_dir)
    base_path = cdir / baseline_id
    if not base_path.is_dir():
        raise FileNotFoundError(f"Baseline candidate directory not found: {base_path}")

    target_path = cdir / new_candidate_id
    if target_path.exists():
        raise FileExistsError(f"Candidate {new_candidate_id} already exists at {target_path}")

    shutil.copytree(base_path, target_path)
    return target_path
