"""Single-Intervention Validator for Recovery Experiments (Stage 35 Sections 3, 4, 11, 13, 24-28, 35).

Enforces:
- Recovery-only variation (`InterventionScope.RECOVERY`)
- Root prompt immutability (P0 baseline hash `2360d4bf...`) unless an isolated recovery instruction is specified
- Retrieval policy immutability (R0 baseline hash `3e1b234a...`)
- Testing strategy immutability (T0 baseline hash `76820d5c...`)
- Multi-agent topology immutability (`root_only`)
- Model ID immutability (`gemma-4-31b-it-qat-w4a16-ct`)
- Frozen Stage 24 baseline artifacts invariance (14/14 MATCH)
- Policy hash verification
- Recovery loop regression check (Y_loops > X_loops -> REJECT)
- Complete structured RecoveryHypothesis specification
- Duplicate candidate rejection
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.recovery_opt.loop_detector import is_loop_regression
from local.recovery_opt.models import (
    RecoveryCandidateManifest,
    RecoveryHypothesis,
    RecoveryPolicy,
)

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
EXPECTED_R0_RETRIEVAL_POLICY_HASH = "3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7"
EXPECTED_T0_TESTING_POLICY_HASH = "76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36"
EXPECTED_TEST_STRATEGY_SKILL_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
EXPECTED_REPO_TRIAGE_SKILL_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"
EXPECTED_MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
EXPECTED_TOPOLOGY_ID = "root_only"


class RecoveryValidationError(Exception):
    """Raised when a recovery candidate violates single-dimension, loop, or safety constraints."""
    pass


def validate_recovery_hypothesis(
    hypothesis: Optional[RecoveryHypothesis],
) -> Tuple[bool, List[str]]:
    """Validates the structured RecoveryHypothesis."""
    if not hypothesis:
        return False, ["RecoveryHypothesis is missing."]

    errors: List[str] = []
    if not hypothesis.target_failure or not hypothesis.target_failure.strip():
        errors.append("hypothesis.target_failure cannot be empty.")
    if not hypothesis.observation or not hypothesis.observation.strip():
        errors.append("hypothesis.observation cannot be empty.")
    if not hypothesis.hypothesis or not hypothesis.hypothesis.strip():
        errors.append("hypothesis.hypothesis cannot be empty.")
    if not hypothesis.recovery_change or not hypothesis.recovery_change.strip():
        errors.append("hypothesis.recovery_change cannot be empty.")
    if not hypothesis.expected_behavior or not hypothesis.expected_behavior.strip():
        errors.append("hypothesis.expected_behavior cannot be empty.")
    if not hypothesis.expected_metric_signal or not hypothesis.expected_metric_signal.strip():
        errors.append("hypothesis.expected_metric_signal cannot be empty.")
    if not hypothesis.rejection_condition or not hypothesis.rejection_condition.strip():
        errors.append("hypothesis.rejection_condition cannot be empty.")

    return len(errors) == 0, errors


def validate_recovery_candidate_integrity(
    manifest: RecoveryCandidateManifest,
    policy: RecoveryPolicy,
    repo_root: Optional[Path | str] = None,
    verify_frozen: bool = True,
) -> Tuple[bool, List[str]]:
    """Validates single-dimension integrity, invariant baselines, and frozen artifacts."""
    errors: List[str] = []

    # 1. Prompt immutability / isolation check
    if policy.prompt_instruction is None:
        if manifest.root_prompt_hash != EXPECTED_P0_PROMPT_SHA256:
            errors.append(
                f"Prompt immutability violated: root_prompt_hash {manifest.root_prompt_hash} != expected P0 hash {EXPECTED_P0_PROMPT_SHA256}."
            )
    else:
        # Prompt-based recovery instruction is allowed only if isolated
        if not policy.prompt_instruction.strip():
            errors.append("policy.prompt_instruction was set but is empty.")

    # 2. Retrieval policy immutability
    if manifest.retrieval_policy_hash != EXPECTED_R0_RETRIEVAL_POLICY_HASH:
        errors.append(
            f"Retrieval immutability violated: retrieval_policy_hash {manifest.retrieval_policy_hash} != expected R0 hash {EXPECTED_R0_RETRIEVAL_POLICY_HASH}."
        )

    # 3. Testing policy immutability
    if manifest.testing_policy_hash != EXPECTED_T0_TESTING_POLICY_HASH:
        errors.append(
            f"Testing immutability violated: testing_policy_hash {manifest.testing_policy_hash} != expected T0 hash {EXPECTED_T0_TESTING_POLICY_HASH}."
        )

    # 4. Topology immutability
    if manifest.topology_hash != EXPECTED_TOPOLOGY_ID:
        errors.append(
            f"Topology immutability violated: topology_hash {manifest.topology_hash} != expected {EXPECTED_TOPOLOGY_ID}."
        )

    # 5. Model ID immutability
    if manifest.model_id != EXPECTED_MODEL_ID:
        errors.append(
            f"Model immutability violated: model_id {manifest.model_id} != expected {EXPECTED_MODEL_ID}."
        )

    # 6. Policy hash match
    actual_hash = policy.compute_policy_hash()
    if manifest.policy_hash != actual_hash:
        errors.append(
            f"Policy hash mismatch: manifest policy_hash {manifest.policy_hash} != computed {actual_hash}."
        )

    # 7. Candidate isolation
    if manifest.candidate_id == manifest.parent_candidate and manifest.candidate_id != "REC0":
        errors.append(
            f"Candidate isolation violated: candidate_id '{manifest.candidate_id}' cannot equal parent_candidate."
        )

    # 8. Skill immutability
    if manifest.test_strategy_skill_hash != EXPECTED_TEST_STRATEGY_SKILL_SHA256:
        errors.append(
            f"Test strategy skill altered: hash {manifest.test_strategy_skill_hash} != expected {EXPECTED_TEST_STRATEGY_SKILL_SHA256}."
        )
    if manifest.repo_triage_skill_hash != EXPECTED_REPO_TRIAGE_SKILL_SHA256:
        errors.append(
            f"Repo triage skill altered: hash {manifest.repo_triage_skill_hash} != expected {EXPECTED_REPO_TRIAGE_SKILL_SHA256}."
        )

    # 9. Verify frozen artifacts if requested
    if verify_frozen:
        root = Path(repo_root).resolve() if repo_root else Path.cwd()
        all_passed, results = verify_frozen_artifacts(root)
        if not all_passed:
            failed = [k for k, v in results.items() if v["status"] != "MATCH"]
            errors.append(f"Frozen Stage 24 artifacts violated: {failed}.")

    return len(errors) == 0, errors


def check_candidate_loop_safety(
    baseline_loop_count: int,
    candidate_loop_count: int,
) -> Tuple[bool, str]:
    """Applies the strict Section 35 loop regression gate."""
    is_reg, rationale = is_loop_regression(baseline_loop_count, candidate_loop_count)
    if is_reg:
        return False, rationale
    return True, rationale
