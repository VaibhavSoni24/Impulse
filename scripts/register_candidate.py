#!/usr/bin/env python3
"""CLI Utility for Registering a New Candidate Manifest (Stage 43 Section 26).

Usage:
    python scripts/register_candidate.py --id <candidate_id> --parent <parent_id> --dimension <dimension> [--description <desc>]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local.versioning.errors import (
    DuplicateCandidateError,
    UnverifiedPromotionError,
)
from local.versioning.hashing import compute_file_sha256
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    EvidenceMode,
    ExperimentDimension,
    PromotionStatus,
)
from local.versioning.registry import CandidateRegistry


def resolve_git_commit(repo_root: Path) -> str:
    """Resolves current git commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMPULSE Stage 43: Register New Candidate")
    parser.add_argument("--id", type=str, required=True, help="Canonical candidate ID (e.g. E3, R3)")
    parser.add_argument("--parent", type=str, required=True, help="Parent candidate ID (e.g. E2, R2)")
    parser.add_argument(
        "--dimension",
        type=str,
        required=True,
        choices=[d.value for d in ExperimentDimension],
        help="Primary controlled experimental dimension",
    )
    parser.add_argument("--description", type=str, default="", help="Candidate description")
    parser.add_argument("--version", type=str, default="1.0.0", help="Semantic candidate version")
    parser.add_argument("--status", type=str, default="CONFIGURED", choices=[s.value for s in CandidateStatus])
    parser.add_argument("--promotion-status", type=str, default="NOT_PROMOTED", choices=[p.value for p in PromotionStatus])

    parsed = parser.parse_args(args)

    # Disallow unverified manual promotion
    if parsed.promotion_status == PromotionStatus.PROMOTED.value:
        print("ERROR: Manual declaration of PROMOTED is forbidden without verified held-out evidence.")
        return 1

    registry = CandidateRegistry(repo_root=REPO_ROOT)
    git_commit = resolve_git_commit(REPO_ROOT)

    parent_manifest = registry.get_candidate(parsed.parent)
    if not parent_manifest:
        print(f"ERROR: Parent candidate '{parsed.parent}' not found in registry.")
        return 1

    # Resolve prompt hash
    prompt_path = REPO_ROOT / "agent" / "prompts" / "root.md"
    prompt_hash = compute_file_sha256(prompt_path) if prompt_path.is_file() else parent_manifest.root_prompt_hash

    # Construct new candidate manifest inheriting baseline invariants
    manifest = CandidateManifest(
        candidate_id=parsed.id,
        candidate_version=parsed.version,
        status=parsed.status,
        parent_candidate_id=parsed.parent,
        git_commit=git_commit,
        created_at=datetime.now(timezone.utc).isoformat(),
        description=parsed.description or f"Candidate {parsed.id} branching from {parsed.parent}",
        experiment_type=f"{parsed.dimension}_optimization",
        primary_dimension=parsed.dimension,
        change_summary={
            "primary_dimension": parsed.dimension,
            "changed_components": [parsed.dimension],
            "unchanged_components": [
                dim.value for dim in ExperimentDimension if dim.value != parsed.dimension
            ],
            "rationale": parsed.description,
        },
        base_model="gemma-4-31b-it-qat-w4a16-ct",
        model_revision=None,
        root_prompt_hash=prompt_hash,
        skill_hashes=parent_manifest.skill_hashes,
        sub_agent_hashes=parent_manifest.sub_agent_hashes,
        tool_contract_hashes=parent_manifest.tool_contract_hashes,
        retrieval_version=parent_manifest.retrieval_version,
        testing_version=parent_manifest.testing_version,
        recovery_version=parent_manifest.recovery_version,
        topology=parent_manifest.topology,
        adapter_id=parent_manifest.adapter_id,
        adapter_sha256=parent_manifest.adapter_sha256,
        benchmark_manifest_hash=parent_manifest.benchmark_manifest_hash,
        dev_split_hash=parent_manifest.dev_split_hash,
        validation_split_hash=parent_manifest.validation_split_hash,
        held_out_split_hash=parent_manifest.held_out_split_hash,
        runtime_settings=parent_manifest.runtime_settings,
        sampling_settings=parent_manifest.sampling_settings,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="UNEXECUTED",
        promotion_status=parsed.promotion_status,
    )

    try:
        m_hash = registry.register_candidate(
            manifest,
            actor="CLI-User",
            reason=f"Registered via CLI branching from {parsed.parent}",
        )
        print(f"[SUCCESS] Candidate '{parsed.id}' registered. Manifest Hash: {m_hash[:16]}...")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
