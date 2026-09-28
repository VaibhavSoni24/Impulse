"""Artifact classification system for IMPULSE (Stage 27 Phase 3).

Deterministically categorizes any repository file into one of the 14 explicit
ArtifactClass categories and assigns an appropriate HygieneAction (KEEP, REVIEW, REMOVE).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.diff_discipline.detectors import (
    detect_local_config,
    detect_log_file,
    detect_machine_specific,
    detect_scratch_file,
)
from local.diff_discipline.models import (
    ArtifactClass,
    ArtifactFinding,
    HygieneAction,
)

# Explicitly protected path prefixes
PROTECTED_PREFIXES = [
    "agent/",
    "benchmark/",
    "docs/",
    ".agents/",
    "experiments/candidates/",
    "experiments/prompts/",
    "tests/fixtures/",
]

# Root authoritative files
ROOT_DOCUMENTATION_FILES = {
    "AGENTS.md",
    "IMPULSE.md",
    "PLAN.md",
    "README.md",
    "HARNESS_README.md",
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
}

ROOT_CONFIG_FILES = {
    "pyproject.toml",
    ".gitignore",
    "uv.lock",
    ".env.example",
}


class ArtifactClassifier:
    """Classifies repository files into canonical artifact categories."""

    def __init__(self, repo_root: Optional[str | Path] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    def classify_file(
        self,
        rel_path: str,
        is_tracked: bool = False,
        is_referenced: bool = False,
    ) -> ArtifactFinding:
        """Classifies a file path into an ArtifactFinding with ArtifactClass and HygieneAction."""
        norm = normalize_path(rel_path)
        file_name = Path(norm).name

        # 1. Local configuration check (.env, .env.example, credentials.json)
        config_finding = detect_local_config(norm, is_tracked=is_tracked)
        if config_finding is not None:
            return config_finding

        # 2. Machine-specific artifacts (__pycache__, .pytest_cache, .pyc)
        machine_finding = detect_machine_specific(norm, is_tracked=is_tracked)
        if machine_finding is not None:
            return machine_finding

        # 3. Scratch file detection (scratch.py, tmp_*.py, *.bak, *.tmp)
        scratch_finding = detect_scratch_file(
            norm, is_tracked=is_tracked, is_referenced=is_referenced
        )
        if scratch_finding is not None:
            return scratch_finding

        # 4. Log file detection (*.log, *.trace)
        log_finding = detect_log_file(
            norm, is_tracked=is_tracked, is_referenced=is_referenced
        )
        if log_finding is not None:
            return log_finding

        # 5. Core Documentation
        if file_name in ROOT_DOCUMENTATION_FILES or norm.startswith("docs/") or norm.startswith(".agents/rules/"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_DOCUMENTATION,
                recommended_action=HygieneAction.KEEP,
                reason="Authoritative repository documentation.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 6. Core Configuration
        if file_name in ROOT_CONFIG_FILES or norm.startswith(".agents/"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_CONFIG,
                recommended_action=HygieneAction.KEEP,
                reason="Authoritative repository configuration.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 7. Benchmark Data
        if norm.startswith("benchmark/"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_BENCHMARK_DATA,
                recommended_action=HygieneAction.KEEP,
                reason="Canonical benchmark dataset / manifest artifact.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 8. Test Fixtures (permanent versioned test fixtures)
        if norm.startswith("tests/fixtures/"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_TEST_FIXTURE,
                recommended_action=HygieneAction.KEEP,
                reason="Permanent versioned test fixture.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 9. Test Source Code
        if norm.startswith("tests/") and (norm.endswith(".py") or norm.endswith(".json")):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_SOURCE,
                recommended_action=HygieneAction.KEEP,
                reason="Repository verification test suite source.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 10. Required Source Code
        if norm.startswith("agent/") or norm.startswith("local/") or norm.startswith("scripts/"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_SOURCE,
                recommended_action=HygieneAction.KEEP,
                reason="Core IMPULSE agent or runtime subsystem source code.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 11. Authoritative Experiment Reports
        if norm.startswith("experiments/prompts/") and norm.endswith(".md"):
            return ArtifactFinding(
                path=norm,
                artifact_class=ArtifactClass.REQUIRED_REPORT,
                recommended_action=HygieneAction.KEEP,
                reason="Authoritative experiment or stage execution report.",
                confidence=1.0,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 12. Experiment Artifacts & Candidates
        if norm.startswith("experiments/"):
            # Candidate packages or evaluation artifacts
            art_class = (
                ArtifactClass.GENERATED_BUT_TRACKED
                if is_tracked
                else ArtifactClass.REQUIRED_EXPERIMENT_ARTIFACT
            )
            return ArtifactFinding(
                path=norm,
                artifact_class=art_class,
                recommended_action=HygieneAction.KEEP,
                reason="Canonical multi-agent candidate or experiment evaluation artifact.",
                confidence=0.95,
                is_tracked=is_tracked,
                is_referenced=is_referenced,
            )

        # 13. Default UNKNOWN behavior:
        # REPORT, DO NOT DELETE. Only clearly removable artifacts may be automatically cleaned.
        return ArtifactFinding(
            path=norm,
            artifact_class=ArtifactClass.UNKNOWN,
            recommended_action=HygieneAction.REVIEW,
            reason="Unrecognized artifact location/pattern; manual review required.",
            confidence=0.5,
            is_tracked=is_tracked,
            is_referenced=is_referenced,
        )
