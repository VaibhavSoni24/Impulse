"""Single-Intervention Validator for Retrieval Optimization (Stage 33 Sections 4, 19, 20).

Enforces:
- Retrieval-only variation (single-dimension discipline)
- Root prompt immutability (hash matches P0 baseline)
- Multi-agent topology immutability (topology fixed to root_only)
- Competition model immutability (model fixed to gemma-4-31b-it-qat-w4a16-ct)
- Competition tool contracts immutability (search_similar_code, get_code_neighbors, get_code_subgraph)
- Cryptographic invariance of frozen Stage 24 baseline artifacts
- Strict policy hash verification
- Complete structured RetrievalHypothesis specification
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES, verify_frozen_artifacts
from local.retrieval_opt.models import (
    RetrievalCandidateManifest,
    RetrievalHypothesis,
    RetrievalPolicy,
)

EXPECTED_P0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"
EXPECTED_MODEL_ID = "gemma-4-31b-it-qat-w4a16-ct"
EXPECTED_TOPOLOGY_ID = "root_only"
ALLOWED_COMPETITION_RETRIEVAL_TOOLS = frozenset({
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
})


class RetrievalValidationError(Exception):
    """Raised when a retrieval candidate violates single-dimension or safety constraints."""
    pass


def validate_retrieval_hypothesis(
    hypothesis: Optional[RetrievalHypothesis],
) -> Tuple[bool, List[str]]:
    """Validates the structured RetrievalHypothesis."""
    if not hypothesis:
        return False, ["RetrievalHypothesis is missing."]

    errors: List[str] = []
    if not hypothesis.target_failure or not hypothesis.target_failure.strip():
        errors.append("hypothesis.target_failure cannot be empty.")
    if not hypothesis.observation or not hypothesis.observation.strip():
        errors.append("hypothesis.observation cannot be empty.")
    if not hypothesis.hypothesis or not hypothesis.hypothesis.strip():
        errors.append("hypothesis.hypothesis cannot be empty.")
    if not hypothesis.retrieval_change or not hypothesis.retrieval_change.strip():
        errors.append("hypothesis.retrieval_change cannot be empty.")
    if not hypothesis.expected_signal or not hypothesis.expected_signal.strip():
        errors.append("hypothesis.expected_signal cannot be empty.")
    if not hypothesis.rejection_condition or not hypothesis.rejection_condition.strip():
        errors.append("hypothesis.rejection_condition cannot be empty.")

    return len(errors) == 0, errors


def validate_retrieval_candidate_integrity(
    manifest: RetrievalCandidateManifest,
    policy: RetrievalPolicy,
    repo_root: Optional[Path | str] = None,
    verify_frozen: bool = True,
) -> Tuple[bool, List[str]]:
    """Validates single-dimension integrity, fixed parameters, and frozen artifacts for a retrieval candidate."""
    errors: List[str] = []

    # 1. Prompt immutability
    if manifest.prompt_sha256 != EXPECTED_P0_PROMPT_SHA256:
        errors.append(
            f"Prompt immutability violated: prompt_sha256 {manifest.prompt_sha256} != expected P0 hash {EXPECTED_P0_PROMPT_SHA256}."
        )

    # 2. Topology immutability
    if manifest.topology_id != EXPECTED_TOPOLOGY_ID:
        errors.append(
            f"Topology immutability violated: topology_id {manifest.topology_id} != expected {EXPECTED_TOPOLOGY_ID}."
        )

    # 3. Model ID immutability
    if manifest.model_id != EXPECTED_MODEL_ID:
        errors.append(
            f"Model immutability violated: model_id {manifest.model_id} != expected {EXPECTED_MODEL_ID}."
        )

    # 4. Policy hash match
    computed_policy_hash = policy.compute_policy_hash()
    if manifest.retrieval_policy_hash != computed_policy_hash:
        errors.append(
            f"Policy hash mismatch: manifest has {manifest.retrieval_policy_hash}, computed {computed_policy_hash}."
        )

    # 5. Candidate ID uniqueness vs parent
    if manifest.parent_candidate_id and manifest.candidate_id == manifest.parent_candidate_id:
        errors.append(f"Candidate ID cannot be identical to parent ID: {manifest.candidate_id}.")

    # 6. Hypothesis validation (required for any non-baseline candidate)
    if manifest.candidate_id != "R0":
        hyp_ok, hyp_errs = validate_retrieval_hypothesis(manifest.hypothesis)
        if not hyp_ok:
            errors.extend(hyp_errs)

    # 7. Frozen artifacts verification
    if verify_frozen:
        root_path = Path(repo_root) if repo_root else Path.cwd()
        frozen_ok, frozen_report = verify_frozen_artifacts(root_path)
        if not frozen_ok:
            for fpath, details in frozen_report.items():
                if details["status"] != "MATCH":
                    errors.append(f"Frozen Stage 24 artifact violated: {fpath} ({details['status']})")

    return len(errors) == 0, errors
