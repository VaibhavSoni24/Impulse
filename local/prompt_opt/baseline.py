"""P0 Frozen Prompt Baseline Establishment (Stage 32 Section 6).

Captures and locks the immutable P0 prompt baseline from the authoritative
M0 candidate root prompt into experiments/prompts/P0/.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from local.prompt_opt.diff import compute_prompt_cost
from local.prompt_opt.models import PromptCandidateManifest


DEFAULT_SOURCE_PROMPT = Path("experiments/candidates/M0/prompts/root.md")
EXPECTED_M0_PROMPT_SHA256 = "2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e"


def _compute_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def establish_p0_baseline(
    source_prompt_path: Optional[Path | str] = None,
    output_dir: Path | str = Path("experiments/prompts/P0"),
    git_commit: str = "",
) -> PromptCandidateManifest:
    """Establishes and locks the immutable P0 baseline prompt under experiments/prompts/P0/."""
    src = Path(source_prompt_path) if source_prompt_path else DEFAULT_SOURCE_PROMPT
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        raise FileNotFoundError(f"Baseline source prompt not found: {src}")

    raw_bytes = src.read_bytes()
    actual_hash = _compute_sha256(raw_bytes)

    if src.resolve() == DEFAULT_SOURCE_PROMPT.resolve():
        if actual_hash != EXPECTED_M0_PROMPT_SHA256:
            raise ValueError(
                f"Source prompt hash mismatch: expected {EXPECTED_M0_PROMPT_SHA256[:12]}, got {actual_hash[:12]}"
            )

    # 1. Write immutable P0 root.md as exact byte-identical replica
    dest_prompt = out / "root.md"
    dest_prompt.write_bytes(raw_bytes)
    prompt_hash = _compute_sha256(dest_prompt.read_bytes())

    # 2. Compute cost metrics
    content_text = raw_bytes.decode("utf-8")
    cost = compute_prompt_cost(content_text)

    # 3. Create manifest
    manifest = PromptCandidateManifest(
        candidate_id="P0",
        parent_candidate_id=None,
        prompt_id="P0_root",
        prompt_path=str(dest_prompt).replace("\\", "/"),
        prompt_sha256=prompt_hash,
        parent_prompt_sha256="",
        source_failure_cluster_id=None,
        target_failure_mode="BASELINE",
        hypothesis=None,
        intervention_type="BASELINE",
        changed_section="NONE",
        changed_files=["root.md"],
        benchmark_split="dev",
        model_id="gemma-4-31b-it-qat-w4a16-ct",
        topology_id="root_only",
        evidence_mode="UNAVAILABLE",
        created_from_commit=git_commit,
        experiment_id="exp-p0-baseline",
        decision="PROMOTED",
        decision_rationale="Immutable baseline prompt established from M0 root topology.",
    )

    manifest.artifact_hashes["root.md"] = prompt_hash

    # 4. Generate report.md
    report_lines = [
        "# Prompt Baseline Report: `P0`",
        "",
        "## Overview",
        "- **Candidate ID:** `P0`",
        "- **Role:** Immutable root prompt baseline for Stage 32 prompt optimization experiments",
        f"- **Source Reference:** `{src}`",
        f"- **SHA-256 Digest:** `{prompt_hash}`",
        f"- **Parent Git Commit:** `{git_commit or 'HEAD'}`",
        "- **Topology:** `root_only` (M0)",
        "- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`",
        "",
        "## Quantitative Cost",
        f"- **Characters:** {cost.char_count}",
        f"- **Lines:** {cost.line_count}",
        f"- **Words:** {cost.word_count}",
        f"- **Estimated Tokens:** {cost.estimated_tokens}",
        "",
        "## Immutability Policy",
        "P0 is the frozen reference prompt. It must never be modified in place.",
        "All subsequent prompt candidates (P1, P2, ...) are single-hypothesis deltas derived from P0 or its descendants.",
        "",
    ]
    report_content = "\n".join(report_lines)
    report_path = out / "report.md"
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report_content)
    manifest.artifact_hashes["report.md"] = _compute_sha256(report_path.read_bytes())

    # 5. Write manifest.json
    man_path = out / "manifest.json"
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")

    return manifest
