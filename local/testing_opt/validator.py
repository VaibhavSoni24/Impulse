"""Single-Intervention Validator for Testing Strategy Experiments (Stage 34 Sections 2, 19, 20, 21, 22).

Enforces:
- Testing-only variation (single-dimension discipline)
- Root prompt immutability (hash matches P0 baseline)
- Retrieval policy immutability (hash matches canonical R0 baseline)
- Multi-agent topology immutability (topology fixed to root_only)
- Competition model immutability (model fixed to gemma-4-31b-it-qat-w4a16-ct)
- Frozen Stage 24 test strategy skill invariance (agent/skills/test_strategy/SKILL.md)
- Cryptographic invariance of all 14 frozen Stage 24 baseline artifacts
- Strict policy hash verification
- Complete structured TestHypothesis specification
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.testing_opt.models import TestCandidateManifest, TestHypothesis, TestPolicy

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
EXPECTED_R0_RETRIEVAL_POLICY_HASH = "3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7"
EXPECTED_TEST_STRATEGY_SKILL_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
EXPECTED_MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
EXPECTED_TOPOLOGY_ID = "root_only"

# Aliases
EXPECTED_RETRIEVAL_R0_POLICY_SHA256 = EXPECTED_R0_RETRIEVAL_POLICY_HASH
EXPECTED_FROZEN_TEST_SKILL_SHA256 = EXPECTED_TEST_STRATEGY_SKILL_SHA256


class TestingValidationError(Exception):
    """Raised when a testing strategy candidate violates single-dimension or safety constraints."""
    pass


def validate_test_hypothesis(
    hypothesis: Optional[TestHypothesis],
) -> Tuple[bool, List[str]]:
    """Validates the structured TestHypothesis."""
    if not hypothesis:
        return False, ["TestHypothesis is missing."]

    errors: List[str] = []
    if not hypothesis.target_failure or not hypothesis.target_failure.strip():
        errors.append("hypothesis.target_failure cannot be empty.")
    if not hypothesis.observation or not hypothesis.observation.strip():
        errors.append("hypothesis.observation cannot be empty.")
    if not hypothesis.hypothesis or not hypothesis.hypothesis.strip():
        errors.append("hypothesis.hypothesis cannot be empty.")
    if not hypothesis.testing_change or not hypothesis.testing_change.strip():
        errors.append("hypothesis.testing_change cannot be empty.")
    if not hypothesis.expected_signal or not hypothesis.expected_signal.strip():
        errors.append("hypothesis.expected_signal cannot be empty.")
    if not hypothesis.rejection_condition or not hypothesis.rejection_condition.strip():
        errors.append("hypothesis.rejection_condition cannot be empty.")

    return len(errors) == 0, errors


validate_testing_hypothesis = validate_test_hypothesis


def validate_testing_candidate_integrity(
    manifest: TestCandidateManifest,
    policy: TestPolicy,
    repo_root: Optional[Path | str] = None,
    verify_frozen: bool = True,
) -> Tuple[bool, List[str]]:
    """Validates single-dimension integrity, invariant baselines, and frozen artifacts for a testing candidate."""
    errors: List[str] = []

    # 1. Prompt immutability
    if manifest.prompt_sha256 != EXPECTED_P0_PROMPT_SHA256:
        errors.append(
            f"Prompt immutability violated: prompt_sha256 {manifest.prompt_sha256} != expected P0 hash {EXPECTED_P0_PROMPT_SHA256}."
        )

    # 2. Retrieval policy immutability
    if manifest.retrieval_policy_hash != EXPECTED_R0_RETRIEVAL_POLICY_HASH:
        errors.append(
            f"Retrieval immutability violated: retrieval_policy_hash {manifest.retrieval_policy_hash} != expected R0 hash {EXPECTED_R0_RETRIEVAL_POLICY_HASH}."
        )

    # 3. Topology immutability
    if manifest.topology_id != EXPECTED_TOPOLOGY_ID:
        errors.append(
            f"Topology immutability violated: topology_id {manifest.topology_id} != expected {EXPECTED_TOPOLOGY_ID}."
        )

    # 4. Model ID immutability
    if manifest.model_id != EXPECTED_MODEL_ID:
        errors.append(
            f"Model immutability violated: model_id {manifest.model_id} != expected {EXPECTED_MODEL_ID}."
        )

    # 5. Policy hash match
    computed_policy_hash = policy.compute_policy_hash()
    if manifest.testing_policy_hash != computed_policy_hash:
        errors.append(
            f"Policy hash mismatch: manifest has {manifest.testing_policy_hash}, computed {computed_policy_hash}."
        )

    # 6. Candidate ID uniqueness vs parent
    if manifest.parent_candidate_id and manifest.candidate_id == manifest.parent_candidate_id:
        errors.append(f"Candidate ID cannot be identical to parent ID: {manifest.candidate_id}.")

    # 7. Hypothesis validation (required for any non-baseline candidate)
    if manifest.candidate_id != "T0":
        hyp_ok, hyp_errs = validate_test_hypothesis(manifest.hypothesis)
        if not hyp_ok:
            errors.extend(hyp_errs)

    # 8. Test strategy skill invariance check
    root_path = Path(repo_root) if repo_root else Path.cwd()
    skill_file = root_path / "agent" / "skills" / "test_strategy" / "SKILL.md"
    if skill_file.is_file():
        actual_skill_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()
        if actual_skill_hash != EXPECTED_TEST_STRATEGY_SKILL_SHA256:
            errors.append(
                f"Frozen Stage 24 test strategy skill was altered: hash {actual_skill_hash} != {EXPECTED_TEST_STRATEGY_SKILL_SHA256}."
            )

    # 9. Complete Frozen artifacts verification
    if verify_frozen:
        frozen_ok, frozen_report = verify_frozen_artifacts(root_path)
        if not frozen_ok:
            for fpath, details in frozen_report.items():
                if details["status"] != "MATCH":
                    errors.append(f"Frozen Stage 24 artifact violated: {fpath} ({details['status']})")

    return len(errors) == 0, errors
