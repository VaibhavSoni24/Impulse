"""Candidate loader and structural validator for Clean-Copy Evaluation (Stage 28 Phase 4).

Guarantees:
- Candidate configuration validated before execution
- Deterministic SHA-256 configuration and prompt hashes
- Source candidate directories remain strictly read-only and immutable
- Materializes candidate configuration cleanly into execution workspace
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
from typing import Any, Optional

from local.context_compaction.fingerprints import compute_content_sha256, normalize_path
from local.runner.cli import extract_candidate_metadata
from scripts.validate_submission import SubmissionValidator


class CandidateLoadError(Exception):
    """Raised when candidate cannot be loaded or fails structural validation."""


class LoadedCandidate:
    """Metadata and hashes representing a loaded, validated candidate."""

    def __init__(
        self,
        candidate_id: str,
        candidate_dir: Path,
        model_id: str,
        prompt_id: str,
        config_sha256: str,
        prompt_sha256: str,
        bundle_sha256: str,
        sub_agents: list[str],
        metadata: dict[str, Any],
    ) -> None:
        self.candidate_id = candidate_id
        self.candidate_dir = candidate_dir
        self.model_id = model_id
        self.prompt_id = prompt_id
        self.config_sha256 = config_sha256
        self.prompt_sha256 = prompt_sha256
        self.bundle_sha256 = bundle_sha256
        self.sub_agents = sub_agents
        self.metadata = metadata

    def materialize(self, destination_dir: Path) -> Path:
        """Safely materializes candidate files into an isolated destination directory."""
        dest = destination_dir / "candidate"
        dest.mkdir(parents=True, exist_ok=True)
        for item in self.candidate_dir.iterdir():
            if item.name.startswith((".", "__pycache__")):
                continue
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, target)
        return dest


class CandidateLoader:
    """Loads and validates candidates for clean-copy evaluation."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    def resolve_candidate_dir(self, candidate_ref: str | Path) -> Path:
        """Resolves candidate reference to an absolute filesystem path."""
        p = Path(candidate_ref)
        if p.is_dir() and (p / "agent.yaml").exists():
            return p.resolve()

        # Check experiments/candidates/<name>
        cand_in_experiments = self.repo_root / "experiments" / "candidates" / str(candidate_ref)
        if cand_in_experiments.is_dir():
            return cand_in_experiments.resolve()

        # Fallback to repository project root for test fixtures
        project_root = Path(__file__).resolve().parents[2]
        cand_in_project = project_root / "experiments" / "candidates" / str(candidate_ref)
        if cand_in_project.is_dir():
            return cand_in_project.resolve()

        # Check root agent/
        if str(candidate_ref) in ("agent", "default", "root"):
            agent_dir = self.repo_root / "agent"
            if agent_dir.is_dir():
                return agent_dir.resolve()
            if (project_root / "agent").is_dir():
                return (project_root / "agent").resolve()

        raise CandidateLoadError(f"Candidate directory not found for reference: {candidate_ref}")

    def load_candidate(self, candidate_ref: str | Path) -> LoadedCandidate:
        """Loads, inspects, validates, and hashes a candidate package."""
        cand_dir = self.resolve_candidate_dir(candidate_ref)
        cand_id = cand_dir.name

        # 1. Structural validation using official competition validator rules
        validator = SubmissionValidator(cand_dir)
        validator.validate()
        if validator.errors:
            raise CandidateLoadError(
                f"Candidate {cand_id} failed structural validation: {validator.errors}"
            )

        # 2. Extract metadata
        meta = extract_candidate_metadata(cand_dir)
        model_id = meta.get("model_id", "unknown")
        prompt_id = meta.get("prompt_id", "inline")

        # 3. Compute configuration hashes
        agent_yaml_path = cand_dir / "agent.yaml"
        if not agent_yaml_path.exists():
            agent_yaml_path = cand_dir / "agent.yml"

        config_sha = compute_content_sha256(agent_yaml_path.read_bytes())

        # Prompt hash
        prompt_sha = ""
        prompt_path = cand_dir / "prompts" / "root.md"
        if prompt_path.exists():
            prompt_sha = compute_content_sha256(prompt_path.read_bytes())

        # Sub-agents discovery
        sub_agents: list[str] = []
        sub_agent_dir = cand_dir / "sub_agents"
        if sub_agent_dir.is_dir():
            for f in sorted(sub_agent_dir.glob("*.yaml")):
                sub_agents.append(f.stem)

        # Candidate bundle combined digest
        bundle_hasher = hashlib.sha256()
        for root, dirs, files in os.walk(cand_dir):
            dirs.sort()
            for f in sorted(files):
                if f.startswith((".", "__pycache__")):
                    continue
                file_p = Path(root) / f
                bundle_hasher.update(file_p.relative_to(cand_dir).as_posix().encode("utf-8"))
                bundle_hasher.update(file_p.read_bytes())
        bundle_sha = bundle_hasher.hexdigest()

        return LoadedCandidate(
            candidate_id=cand_id,
            candidate_dir=cand_dir,
            model_id=model_id,
            prompt_id=prompt_id,
            config_sha256=config_sha,
            prompt_sha256=prompt_sha,
            bundle_sha256=bundle_sha,
            sub_agents=sub_agents,
            metadata=meta,
        )
