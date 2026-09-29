"""Single-Intervention Validator for Prompt Optimization (Stage 32 Sections 4, 9, 23).

Enforces:
- Prompt-only changes (no Python, YAML, skill, or tool modifications)
- Exactly ONE prompt component modified per experiment
- Parent candidate prompt SHA-256 integrity
- Candidate uniqueness and non-identical content
- Complete structured PromptHypothesis specification
- Strict invariance of frozen Stage 24 baseline artifacts
"""

from __future__ import annotations

import filecmp
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
from local.prompt_opt.models import PromptCandidateManifest, PromptChangeType, PromptHypothesis


class PromptValidationError(Exception):
    """Raised when a prompt candidate violates single-dimension or safety constraints."""
    pass


def _compute_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_prompt_hypothesis(hypothesis: Optional[PromptHypothesis]) -> Tuple[bool, List[str]]:
    """Validates the structured PromptHypothesis."""
    if not hypothesis:
        return False, ["PromptHypothesis is missing."]

    errors: List[str] = []
    if not hypothesis.target_failure or not hypothesis.target_failure.strip():
        errors.append("hypothesis.target_failure cannot be empty.")
    if not hypothesis.observation or not hypothesis.observation.strip():
        errors.append("hypothesis.observation cannot be empty.")
    if not hypothesis.hypothesis or not hypothesis.hypothesis.strip():
        errors.append("hypothesis.hypothesis cannot be empty.")
    if not hypothesis.intervention or not hypothesis.intervention.strip():
        errors.append("hypothesis.intervention cannot be empty.")
    if not hypothesis.expected_behavior or not hypothesis.expected_behavior.strip():
        errors.append("hypothesis.expected_behavior cannot be empty.")
    if not hypothesis.expected_metric_signal or not hypothesis.expected_metric_signal.strip():
        errors.append("hypothesis.expected_metric_signal cannot be empty.")
    if not hypothesis.rejection_condition or not hypothesis.rejection_condition.strip():
        errors.append("hypothesis.rejection_condition cannot be empty.")

    # Validate change type
    valid_types = {t.value for t in PromptChangeType}
    if hypothesis.change_type not in valid_types:
        errors.append(f"Invalid change_type '{hypothesis.change_type}'. Must be one of {sorted(list(valid_types))}.")

    return (len(errors) == 0, errors)


def validate_prompt_candidate_integrity(
    manifest: PromptCandidateManifest,
    candidate_prompt_path: Path | str,
    parent_prompt_path: Optional[Path | str] = None,
    repo_root: Optional[Path | str] = None,
) -> Tuple[bool, List[str]]:
    """Validates a prompt candidate's single-dimension discipline and integrity."""
    errors: List[str] = []
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    c_path = Path(candidate_prompt_path)

    # 1. Candidate ID validation
    if not manifest.candidate_id or not manifest.candidate_id.strip():
        errors.append("candidate_id cannot be empty.")
    if manifest.parent_candidate_id and manifest.candidate_id == manifest.parent_candidate_id:
        errors.append(f"candidate_id '{manifest.candidate_id}' cannot equal parent_candidate_id.")

    # 2. File existence and SHA-256
    if not c_path.is_file():
        errors.append(f"Candidate prompt file not found: {c_path}")
    else:
        actual_hash = _compute_file_sha256(c_path)
        if manifest.prompt_sha256 and actual_hash != manifest.prompt_sha256:
            errors.append(
                f"Candidate prompt SHA-256 mismatch: recorded {manifest.prompt_sha256[:12]}, actual {actual_hash[:12]}"
            )

    # 3. Parent comparison
    if parent_prompt_path:
        p_path = Path(parent_prompt_path)
        if not p_path.is_file():
            errors.append(f"Parent prompt file not found: {p_path}")
        else:
            actual_parent_hash = _compute_file_sha256(p_path)
            if manifest.parent_prompt_sha256 and actual_parent_hash != manifest.parent_prompt_sha256:
                errors.append(
                    f"Parent prompt SHA-256 mismatch: recorded {manifest.parent_prompt_sha256[:12]}, actual {actual_parent_hash[:12]}"
                )

            # Check that prompt actually changed
            if c_path.is_file() and actual_hash == actual_parent_hash:
                errors.append("Candidate prompt is byte-identical to parent prompt. No intervention detected.")

    # 4. Single changed file discipline (Section 4 & 9)
    if not manifest.changed_files:
        errors.append("changed_files cannot be empty.")
    elif len(manifest.changed_files) > 1:
        errors.append(
            f"Multiple prompt files changed ({manifest.changed_files}). "
            "Stage 32 enforces single-component discipline (exactly ONE prompt file per experiment)."
        )

    # 5. Non-prompt file modification rejection (Section 4)
    for f in manifest.changed_files:
        norm_f = f.replace("\\", "/").lower()
        if not (norm_f.endswith(".md") or norm_f.endswith(".txt") or norm_f.endswith(".prompt")):
            errors.append(
                f"Non-prompt file '{f}' listed in changed_files. "
                "Prompt experiments may modify PROMPT files only."
            )

    # 6. Frozen artifact protection (Section 29)
    for f in manifest.changed_files:
        norm_f = f.replace("\\", "/").strip("/")
        if norm_f in FROZEN_STAGE24_HASHES:
            errors.append(
                f"Candidate targets frozen Stage 24 artifact '{norm_f}'. "
                "Frozen baseline artifacts must remain invariant."
            )

    # 7. Hypothesis validation
    if manifest.candidate_id != "P0":
        hyp_ok, hyp_errors = validate_prompt_hypothesis(manifest.hypothesis)
        if not hyp_ok:
            errors.extend(hyp_errors)

    return (len(errors) == 0, errors)
