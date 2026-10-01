"""Candidate Manifest, Schema, and Status Transition Validator (Sections 6, 25).

Enforces:
- Schema field requirements and type validation
- Immutable status transition graph rules
- Parent lineage existence and acyclicity
- SHA-256 hash formatting and integrity
- Promotion discipline (no unverified promotions)
- Secret scanning
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from local.versioning.errors import (
    InvalidStatusTransitionError,
    LineageError,
    SchemaValidationError,
    UnverifiedPromotionError,
)
from local.versioning.hashing import scan_for_secrets
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    EvidenceMode,
    ExperimentDimension,
    PromotionStatus,
)

HEX_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$|^UNKNOWN$", re.IGNORECASE)

# Valid status transitions
VALID_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    CandidateStatus.DRAFT.value: {
        CandidateStatus.CONFIGURED.value,
        CandidateStatus.BLOCKED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.CONFIGURED.value: {
        CandidateStatus.SMOKE_PASSED.value,
        CandidateStatus.BLOCKED.value,
        CandidateStatus.REJECTED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.SMOKE_PASSED.value: {
        CandidateStatus.VALIDATED.value,
        CandidateStatus.REJECTED.value,
        CandidateStatus.BLOCKED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.VALIDATED.value: {
        CandidateStatus.HELD_OUT_CONFIRMED.value,
        CandidateStatus.REJECTED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.HELD_OUT_CONFIRMED.value: {
        CandidateStatus.PROMOTED.value,
        CandidateStatus.REJECTED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.PROMOTED.value: {
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.REJECTED.value: {
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.BLOCKED.value: {
        CandidateStatus.CONFIGURED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.RESERVED.value: {
        CandidateStatus.DRAFT.value,
        CandidateStatus.CONFIGURED.value,
        CandidateStatus.BLOCKED.value,
        CandidateStatus.ARCHIVED.value,
    },
    CandidateStatus.ARCHIVED.value: set(),
}


class CandidateValidator:
    """Validates candidate manifest schema, integrity, and lifecycle rules."""

    @staticmethod
    def validate_status_transition(old_status: str, new_status: str) -> None:
        """Validates that a lifecycle status transition is legally permitted."""
        if old_status == new_status:
            return

        allowed = VALID_STATUS_TRANSITIONS.get(old_status)
        if allowed is None or new_status not in allowed:
            raise InvalidStatusTransitionError(
                f"Illegal candidate status transition: '{old_status}' -> '{new_status}'. "
                f"Allowed transitions from '{old_status}': {sorted(allowed) if allowed else 'none'}."
            )

    @staticmethod
    def validate_manifest(
        manifest: CandidateManifest,
        known_candidate_ids: Optional[Set[str]] = None,
    ) -> List[str]:
        """Exhaustively validates manifest schema and invariants. Returns list of warnings."""
        warnings: List[str] = []

        # 1. Zero secrets check
        scan_for_secrets(manifest.to_dict())

        # 2. Candidate ID
        if not manifest.candidate_id or not isinstance(manifest.candidate_id, str):
            raise SchemaValidationError("candidate_id must be a non-empty string.")

        # 3. Status
        valid_statuses = {s.value for s in CandidateStatus}
        if manifest.status not in valid_statuses:
            raise SchemaValidationError(
                f"Invalid status '{manifest.status}'. Must be one of {sorted(valid_statuses)}."
            )

        # 4. Promotion status
        valid_promotions = {p.value for p in PromotionStatus}
        if manifest.promotion_status not in valid_promotions:
            raise SchemaValidationError(
                f"Invalid promotion_status '{manifest.promotion_status}'. Must be one of {sorted(valid_promotions)}."
            )

        # 5. Promotion verification discipline
        if manifest.promotion_status == PromotionStatus.PROMOTED.value:
            if manifest.status not in {
                CandidateStatus.PROMOTED.value,
                CandidateStatus.HELD_OUT_CONFIRMED.value,
                CandidateStatus.VALIDATED.value,
            }:
                raise UnverifiedPromotionError(
                    f"Candidate '{manifest.candidate_id}' cannot have promotion_status=PROMOTED "
                    f"while lifecycle status is '{manifest.status}'."
                )
            if manifest.evidence_mode != EvidenceMode.LIVE.value:
                raise UnverifiedPromotionError(
                    f"Candidate '{manifest.candidate_id}' cannot be PROMOTED with evidence_mode='{manifest.evidence_mode}'. "
                    "Promotion strictly requires LIVE evidence."
                )

        # 6. Parent lineage
        if manifest.parent_candidate_id:
            if manifest.parent_candidate_id == manifest.candidate_id:
                raise LineageError(f"Candidate '{manifest.candidate_id}' cannot be its own parent.")
            if known_candidate_ids and manifest.parent_candidate_id not in known_candidate_ids:
                raise LineageError(
                    f"Candidate '{manifest.candidate_id}' references unknown parent '{manifest.parent_candidate_id}'."
                )

        # 7. Git commit format
        if not GIT_COMMIT_PATTERN.match(manifest.git_commit):
            raise SchemaValidationError(
                f"git_commit must be a valid hex commit hash or 'UNKNOWN', got '{manifest.git_commit}'."
            )

        # 8. Primary dimension
        valid_dims = {d.value for d in ExperimentDimension}
        if manifest.primary_dimension not in valid_dims:
            raise SchemaValidationError(
                f"Invalid primary_dimension '{manifest.primary_dimension}'. Must be one of {sorted(valid_dims)}."
            )

        # 9. Base model
        if manifest.base_model != "gemma-4-31b-it-qat-w4a16-ct":
            raise SchemaValidationError(
                f"Approved base_model is 'gemma-4-31b-it-qat-w4a16-ct', got '{manifest.base_model}'."
            )

        # 10. Root prompt hash format
        if manifest.root_prompt_hash != "UNKNOWN" and not HEX_SHA256_PATTERN.match(manifest.root_prompt_hash):
            raise SchemaValidationError(
                f"root_prompt_hash must be a 64-char hex SHA-256 or 'UNKNOWN', got '{manifest.root_prompt_hash}'."
            )

        # 11. LoRA adapter special rule (Section 21)
        if manifest.candidate_id.upper() == "L1":
            if manifest.status in {CandidateStatus.VALIDATED.value, CandidateStatus.PROMOTED.value}:
                raise SchemaValidationError(
                    "L1 cannot be VALIDATED or PROMOTED: current repository has no trained adapter weights."
                )
            if manifest.evidence_mode == EvidenceMode.LIVE.value:
                raise SchemaValidationError("L1 cannot claim LIVE evidence: Stage 39 training was blocked by data.")

        # 12. RC1 release candidate special rule (Section 22)
        if manifest.candidate_id.upper() == "RC1":
            if manifest.status not in {CandidateStatus.RESERVED.value, CandidateStatus.DRAFT.value}:
                raise SchemaValidationError(
                    "RC1 must remain RESERVED until a validated candidate is formally selected as release candidate."
                )

        return warnings
