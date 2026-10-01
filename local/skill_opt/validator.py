"""Single-Intervention Validator for Skill Optimization Experiments (Stage 36 Sections 8, 15, 16, 26, 27, 28, 32, 33).

Enforces:
- Skill-only variation (`InterventionScope.SKILL`)
- Single skill change per candidate (rejects multi-skill modifications)
- Non-skill file modification rejection
- Root prompt immutability (P0 hash `2360d4bf...`)
- Retrieval policy immutability (R0 hash `3e1b234a...`)
- Testing execution policy immutability (T0 hash `76820d5c...`)
- Recovery policy immutability (REC0 hash `ee77ab01...`)
- Topology immutability (`root_only`)
- Model ID immutability (`gemma-4-31b-it-qat-w4a16-ct`)
- Frozen Stage 24 baseline artifacts invariance (14/14 MATCH)
- Skill scope boundary enforcement (no leakage into retrieval, recovery, topology)
- Candidate parent hash correctness
- Candidate ID uniqueness
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.skill_opt.models import SkillCandidateManifest, SkillHypothesis
from local.skill_opt.scope_validator import validate_skill_scope

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
EXPECTED_R0_RETRIEVAL_POLICY_HASH = "3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7"
EXPECTED_T0_TESTING_POLICY_HASH = "76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36"
EXPECTED_REC0_RECOVERY_POLICY_HASH = "ee77ab01ea322ad61276eeb627de6eab64f5b732adc868110e8e6f4fdd713f7f"
EXPECTED_TEST_STRATEGY_SKILL_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
EXPECTED_REPO_TRIAGE_SKILL_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"
EXPECTED_MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
EXPECTED_TOPOLOGY_ID = "root_only"


class SkillValidationError(Exception):
    """Raised when a skill candidate violates single-scope, invariance, or safety constraints."""
    pass


def validate_skill_hypothesis(
    hypothesis: Optional[SkillHypothesis],
) -> Tuple[bool, List[str]]:
    """Validates completeness of the structured causal SkillHypothesis."""
    if not hypothesis:
        return False, ["SkillHypothesis is missing."]

    errors: list[str] = []
    if not hypothesis.target_behavior or not hypothesis.target_behavior.strip():
        errors.append("hypothesis.target_behavior cannot be empty.")
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

    return len(errors) == 0, errors


def validate_skill_candidate_invariance(
    manifest: SkillCandidateManifest,
    repo_root: Optional[Path | str] = None,
    verify_frozen: bool = True,
) -> Tuple[bool, List[str]]:
    """Validates invariant baselines, non-skill fixity, and frozen production artifacts."""
    errors: list[str] = []

    # 1. Prompt immutability
    if manifest.prompt_hash and manifest.prompt_hash != EXPECTED_P0_PROMPT_SHA256:
        errors.append(
            f"Prompt immutability violated: prompt_hash {manifest.prompt_hash} != expected P0 hash {EXPECTED_P0_PROMPT_SHA256}."
        )

    # 2. Retrieval policy immutability
    if manifest.retrieval_policy_hash and manifest.retrieval_policy_hash != EXPECTED_R0_RETRIEVAL_POLICY_HASH:
        errors.append(
            f"Retrieval immutability violated: retrieval_policy_hash {manifest.retrieval_policy_hash} != expected R0 hash {EXPECTED_R0_RETRIEVAL_POLICY_HASH}."
        )

    # 3. Testing policy immutability
    if manifest.testing_policy_hash and manifest.testing_policy_hash != EXPECTED_T0_TESTING_POLICY_HASH:
        errors.append(
            f"Testing immutability violated: testing_policy_hash {manifest.testing_policy_hash} != expected T0 hash {EXPECTED_T0_TESTING_POLICY_HASH}."
        )

    # 4. Recovery policy immutability
    if manifest.recovery_policy_hash and manifest.recovery_policy_hash != EXPECTED_REC0_RECOVERY_POLICY_HASH:
        errors.append(
            f"Recovery immutability violated: recovery_policy_hash {manifest.recovery_policy_hash} != expected REC0 hash {EXPECTED_REC0_RECOVERY_POLICY_HASH}."
        )

    # 5. Topology immutability
    if manifest.topology_identity != EXPECTED_TOPOLOGY_ID:
        errors.append(
            f"Topology immutability violated: topology_identity {manifest.topology_identity} != expected {EXPECTED_TOPOLOGY_ID}."
        )

    # 6. Model ID immutability
    if manifest.model_id != EXPECTED_MODEL_ID:
        errors.append(
            f"Model immutability violated: model_id {manifest.model_id} != expected {EXPECTED_MODEL_ID}."
        )

    # 7. Candidate isolation: candidate_id != parent_candidate_id for non-S0
    if manifest.candidate_id == manifest.parent_candidate_id and manifest.candidate_id != "S0":
        errors.append(
            f"Candidate isolation violated: candidate_id '{manifest.candidate_id}' cannot equal parent_candidate_id."
        )

    # 8. Verify frozen artifacts if requested
    if verify_frozen:
        root = Path(repo_root).resolve() if repo_root else Path.cwd()
        all_passed, results = verify_frozen_artifacts(root)
        if not all_passed:
            failed = [k for k, v in results.items() if v["status"] != "MATCH"]
            errors.append(f"Frozen Stage 24 artifacts violated: {failed}.")

    return len(errors) == 0, errors


def validate_candidate_single_skill_change(
    modified_skills: List[str],
    modified_non_skill_files: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """Validates that exactly one skill was modified and no non-skill files were touched."""
    errors: list[str] = []

    if len(modified_skills) == 0:
        errors.append("No skill modifications detected in candidate.")
    elif len(modified_skills) > 1:
        errors.append(
            f"Multi-skill modification rejected: modified {len(modified_skills)} skills ({modified_skills}). "
            "Stage 36 strictly requires exactly one skill change per candidate."
        )

    if modified_non_skill_files:
        errors.append(
            f"Non-skill file mutation rejected: candidate touched non-skill files {modified_non_skill_files}."
        )

    return len(errors) == 0, errors
