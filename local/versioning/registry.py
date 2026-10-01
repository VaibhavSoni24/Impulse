"""Candidate Registry and Lifecycle Manager for Stage 43 (Sections 5, 26, 28, 29, 31).

Coordinates:
- Registration of immutable candidate manifests
- Append-only lifecycle event recording in experiments/candidates/history.jsonl
- Registry tracking in experiments/candidates/registry.json
- Current-best candidate tracking in experiments/candidates/current_best.json
- Historical candidate import from verified repository evidence
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from local.versioning.errors import (
    DuplicateCandidateError,
    ImmutableCandidateError,
    LineageError,
)
from local.versioning.hashing import (
    compute_canonical_dict_hash,
    compute_file_sha256,
    normalize_machine_paths,
)
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    CurrentBestPointer,
    EvidenceMode,
    ExperimentDimension,
    LifecycleEvent,
    LifecycleEventType,
    PromotionStatus,
)
from local.versioning.validation import CandidateValidator


class CandidateRegistry:
    """Manages the canonical candidate registry and persistence layer."""

    def __init__(self, candidates_dir: Optional[Path] = None, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent.parent
        self.candidates_dir = candidates_dir or (self.repo_root / "experiments" / "candidates")
        self.registry_file = self.candidates_dir / "registry.json"
        self.history_file = self.candidates_dir / "history.jsonl"
        self.current_best_file = self.candidates_dir / "current_best.json"
        self.schema_file = self.candidates_dir / "schema.json"

        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def load_registry(self) -> Dict[str, Any]:
        """Loads registry mapping from registry.json."""
        if not self.registry_file.is_file():
            return {"schema_version": "1.0.0", "candidates": {}}
        try:
            return json.loads(self.registry_file.read_text(encoding="utf-8"))
        except Exception:
            return {"schema_version": "1.0.0", "candidates": {}}

    def list_candidate_ids(self) -> List[str]:
        """Returns sorted list of registered candidate IDs."""
        reg = self.load_registry()
        return sorted(reg.get("candidates", {}).keys())

    def get_candidate(self, candidate_id: str) -> Optional[CandidateManifest]:
        """Loads CandidateManifest for a given candidate_id."""
        cand_dir = self.candidates_dir / candidate_id
        manifest_file = cand_dir / "manifest.json"
        if not manifest_file.is_file():
            return None
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return CandidateManifest(**data)

    def record_event(self, event: LifecycleEvent) -> None:
        """Appends an immutable lifecycle event to history.jsonl."""
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def register_candidate(
        self,
        manifest: CandidateManifest,
        actor: str = "IMPULSE-Registry",
        reason: str = "Initial candidate registration",
        overwrite_finalized: bool = False,
    ) -> str:
        """Registers a new candidate with validation, hashing, and event recording."""
        known_ids = set(self.list_candidate_ids())

        # Duplicate ID and Immutability check
        if manifest.candidate_id in known_ids:
            cand_dir = self.candidates_dir / manifest.candidate_id
            if (cand_dir / "manifest.json").is_file():
                existing = self.get_candidate(manifest.candidate_id)
                if existing:
                    manifest_dict = manifest.to_dict()
                    new_hash = compute_canonical_dict_hash(manifest_dict, exclude_keys=["manifest_hash"])
                    if existing.manifest_hash and existing.manifest_hash != new_hash:
                        raise ImmutableCandidateError(
                            f"Candidate '{manifest.candidate_id}' is finalized and immutable. "
                            "Cannot modify candidate configuration in place. Create a new candidate ID."
                        )
                    elif not overwrite_finalized:
                        raise DuplicateCandidateError(
                            f"Candidate '{manifest.candidate_id}' is already registered in registry."
                        )

        # Parent lineage check
        if manifest.parent_candidate_id and known_ids:
            if manifest.parent_candidate_id not in known_ids:
                raise LineageError(
                    f"Parent '{manifest.parent_candidate_id}' is not registered in the candidate registry."
                )

        # Validate schema and invariants
        CandidateValidator.validate_manifest(manifest, known_candidate_ids=known_ids)

        # Compute canonical manifest hash
        manifest_dict = manifest.to_dict()
        manifest_hash = compute_canonical_dict_hash(manifest_dict, exclude_keys=["manifest_hash"])
        manifest.manifest_hash = manifest_hash
        manifest_dict["manifest_hash"] = manifest_hash

        # Normalize any machine paths
        manifest_dict = normalize_machine_paths(manifest_dict, self.repo_root)

        # Persist manifest to experiments/candidates/<candidate_id>/manifest.json
        cand_dir = self.candidates_dir / manifest.candidate_id
        cand_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = cand_dir / "manifest.json"

        # Immutability check
        if manifest_file.is_file() and not overwrite_finalized:
            old_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if old_data.get("manifest_hash") != manifest_hash:
                raise ImmutableCandidateError(
                    f"Manifest for finalized candidate '{manifest.candidate_id}' cannot be modified in place. "
                    "Use a new candidate ID or bump the patch version for non-behavioral metadata corrections."
                )

        manifest_file.write_text(json.dumps(manifest_dict, indent=2), encoding="utf-8")

        # Update registry.json
        reg = self.load_registry()
        reg.setdefault("candidates", {})[manifest.candidate_id] = {
            "version": manifest.candidate_version,
            "status": manifest.status,
            "parent": manifest.parent_candidate_id,
            "primary_dimension": manifest.primary_dimension,
            "git_commit": manifest.git_commit,
            "manifest_hash": manifest_hash,
            "created_at": manifest.created_at,
        }
        self.registry_file.write_text(json.dumps(reg, indent=2), encoding="utf-8")

        # Record event in history.jsonl
        event = LifecycleEvent(
            candidate_id=manifest.candidate_id,
            event_type=LifecycleEventType.REGISTERED.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            git_commit=manifest.git_commit,
            actor=actor,
            reason=reason,
            source_manifest_hash=manifest_hash,
            notes=f"Registered candidate version {manifest.candidate_version}",
        )
        self.record_event(event)

        return manifest_hash

    def set_current_best(
        self,
        candidate_id: str,
        rationale: str,
        actor: str = "IMPULSE-Registry",
    ) -> CurrentBestPointer:
        """Sets the active current-best candidate pointer."""
        cand = self.get_candidate(candidate_id)
        if not cand:
            raise ValueError(f"Candidate '{candidate_id}' not found in registry.")

        if cand.status not in {
            CandidateStatus.VALIDATED.value,
            CandidateStatus.SMOKE_PASSED.value,
            CandidateStatus.PROMOTED.value,
            CandidateStatus.HELD_OUT_CONFIRMED.value,
        }:
            raise ValueError(
                f"Candidate '{candidate_id}' with status '{cand.status}' cannot be current best. "
                "Must be VALIDATED, SMOKE_PASSED, or PROMOTED."
            )

        now = datetime.now(timezone.utc).isoformat()
        pointer = CurrentBestPointer(
            candidate_id=cand.candidate_id,
            candidate_version=cand.candidate_version,
            status=cand.status,
            updated_at=now,
            git_commit=cand.git_commit,
            manifest_hash=cand.manifest_hash or "",
            rationale=rationale,
        )

        self.current_best_file.write_text(json.dumps(pointer.to_dict(), indent=2), encoding="utf-8")

        # Record lifecycle event
        event = LifecycleEvent(
            candidate_id=cand.candidate_id,
            event_type=LifecycleEventType.PROMOTED.value if cand.promotion_status == PromotionStatus.PROMOTED.value else "DESIGNATED_CURRENT_BEST",
            timestamp=now,
            git_commit=cand.git_commit,
            actor=actor,
            reason=rationale,
            source_manifest_hash=cand.manifest_hash or "",
            notes=f"Current best designated as {candidate_id}",
        )
        self.record_event(event)

        return pointer

    def get_current_best(self) -> Optional[CurrentBestPointer]:
        """Loads active current-best pointer."""
        if not self.current_best_file.is_file():
            return None
        data = json.loads(self.current_best_file.read_text(encoding="utf-8"))
        return CurrentBestPointer(**data)

    def write_schema(self) -> Path:
        """Generates machine-readable JSON schema for candidate manifests."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "ImpulseCandidateManifest",
            "type": "object",
            "required": [
                "candidate_id",
                "candidate_version",
                "status",
                "parent_candidate_id",
                "git_commit",
                "created_at",
                "description",
                "experiment_type",
                "primary_dimension",
                "change_summary",
                "base_model",
                "root_prompt_hash",
                "benchmark_manifest_hash",
                "compute_environment_id",
                "evidence_mode",
                "promotion_status",
            ],
            "properties": {
                "candidate_id": {"type": "string"},
                "candidate_version": {"type": "string"},
                "status": {"type": "string", "enum": [s.value for s in CandidateStatus]},
                "parent_candidate_id": {"type": ["string", "null"]},
                "git_commit": {"type": "string"},
                "created_at": {"type": "string"},
                "description": {"type": "string"},
                "experiment_type": {"type": "string"},
                "primary_dimension": {"type": "string", "enum": [d.value for d in ExperimentDimension]},
                "change_summary": {"type": "object"},
                "base_model": {"type": "string", "const": "gemma-4-31b-it-qat-w4a16-ct"},
                "model_revision": {"type": ["string", "null"]},
                "root_prompt_hash": {"type": "string"},
                "skill_hashes": {"type": "object"},
                "sub_agent_hashes": {"type": "object"},
                "tool_contract_hashes": {"type": "object"},
                "retrieval_version": {"type": "string"},
                "testing_version": {"type": "string"},
                "recovery_version": {"type": "string"},
                "topology": {"type": "string"},
                "adapter_id": {"type": ["string", "null"]},
                "adapter_sha256": {"type": ["string", "null"]},
                "benchmark_manifest_hash": {"type": "string"},
                "dev_split_hash": {"type": "string"},
                "validation_split_hash": {"type": "string"},
                "held_out_split_hash": {"type": "string"},
                "runtime_settings": {"type": "object"},
                "sampling_settings": {"type": "object"},
                "compute_environment_id": {"type": "string"},
                "evidence_mode": {"type": "string", "enum": [e.value for e in EvidenceMode]},
                "result_status": {"type": "string"},
                "promotion_status": {"type": "string", "enum": [p.value for p in PromotionStatus]},
                "manifest_hash": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        }
        self.schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        return self.schema_file
