"""Frozen artifact verification for Stage 27 (Phase 15).

Verifies SHA-256 hashes of frozen specialist definitions, prompts, candidates,
and skills to guarantee zero regression or drift of prior frozen baselines.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import compute_content_sha256, normalize_path

# Frozen SHA-256 digests from Phase 15 specification
FROZEN_STAGE24_HASHES = {
    # Canonical specialist YAMLs and prompts in agent/
    "agent/sub_agents/scout.yaml": "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877",
    "agent/prompts/scout.md": "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805",
    "agent/sub_agents/debugger.yaml": "07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199",
    "agent/prompts/debugger.md": "a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f",
    "agent/sub_agents/reviewer.yaml": "facfcbb4fbc8d42a82f32a6979bf8b090de5857ba92b4641e4a45617b340200c",
    "agent/prompts/reviewer.md": "d2432da56d07170989edbd83add7fe51323df1db6dd458b80f0d893cdb9264c6",
    # Shared root prompt across M0..M5 topologies
    "experiments/candidates/M0/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "experiments/candidates/M1/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "experiments/candidates/M2/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "experiments/candidates/M3/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "experiments/candidates/M4/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    "experiments/candidates/M5/prompts/root.md": "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
    # Canonical skills
    "agent/skills/test_strategy/SKILL.md": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148",
    "agent/skills/repo_triage/SKILL.md": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce",
}


def verify_frozen_artifacts(
    repo_root: Optional[str | Path] = None,
) -> tuple[bool, dict[str, dict[str, str]]]:
    """Verifies that all frozen Stage 24 artifacts match their authoritative SHA-256 hashes.
    
    Returns:
        (all_passed, results_map)
        results_map: {path: {"expected": sha, "actual": sha, "status": "MATCH" | "MISMATCH" | "MISSING"}}
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd()
    all_passed = True
    results: dict[str, dict[str, str]] = {}

    for rel_path, expected_hash in FROZEN_STAGE24_HASHES.items():
        full_path = root / rel_path
        if not full_path.exists():
            all_passed = False
            results[rel_path] = {
                "expected": expected_hash,
                "actual": "MISSING",
                "status": "MISSING",
            }
            continue

        try:
            content = full_path.read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash == expected_hash:
                results[rel_path] = {
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "status": "MATCH",
                }
            else:
                all_passed = False
                results[rel_path] = {
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "status": "MISMATCH",
                }
        except OSError:
            all_passed = False
            results[rel_path] = {
                "expected": expected_hash,
                "actual": "READ_ERROR",
                "status": "ERROR",
            }

    return all_passed, results
