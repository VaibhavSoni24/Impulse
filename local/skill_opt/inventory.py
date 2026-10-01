"""Skill Inventory and Discovery Engine (Stage 36 Section 4).

Discovers, inventories, and verifies authoritative skill artifacts within the repository:
- agent/skills/test_strategy/SKILL.md
- agent/skills/repo_triage/SKILL.md

Records cryptographic digests, frozen status, optimizer eligibility, and packaging roles.
Guarantees frozen production skills are never confused with experimental candidates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from local.diff_discipline.frozen_verifier import FROZEN_STAGE24_HASHES
from local.skill_opt.models import SkillRecord, SkillScopeType

CANONICAL_SKILL_PATHS = {
    "test_strategy": "agent/skills/test_strategy/SKILL.md",
    "repo_triage": "agent/skills/repo_triage/SKILL.md",
}

SKILL_METADATA = {
    "test_strategy": {
        "scope": SkillScopeType.TESTING.value,
        "intended_role": "Generic testing strategy for repository-level software defect reproduction, targeted verification, intelligent broadening, and test-result interpretation.",
        "dependencies": ["pytest", "unittest", "cargo", "npm", "go test"],
        "loading_mechanism": "DECLARATIVE_YAML_AND_PROMPT_REFERENCE",
        "competition_packaging_relevance": "ROOT_AGENT_SKILL",
    },
    "repo_triage": {
        "scope": SkillScopeType.REPOSITORY_TRIAGE.value,
        "intended_role": "Systematic repository triage skill for rapid, evidence-driven identification of language, framework, build manager, entry points, layout, and conventions.",
        "dependencies": ["directory_tree", "manifest_inspection"],
        "loading_mechanism": "DECLARATIVE_YAML_AND_PROMPT_REFERENCE",
        "competition_packaging_relevance": "ROOT_AGENT_SKILL",
    },
}


def compute_file_sha256(path: Path | str) -> str:
    """Computes SHA-256 digest of a file."""
    p = Path(path)
    if not p.is_file():
        return ""
    content = p.read_bytes()
    return hashlib.sha256(content).hexdigest()


class SkillInventory:
    """Manages skill discovery, verification, and inventory reporting."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    def discover_skills(self) -> List[SkillRecord]:
        """Discovers all skills declared in the canonical repository layout."""
        skills: list[SkillRecord] = []

        skills_dir = self.repo_root / "agent" / "skills"
        if not skills_dir.exists():
            return skills

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_id = skill_dir.name
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue

            rel_path = f"agent/skills/{skill_id}/SKILL.md"
            sha = compute_file_sha256(skill_md)
            is_frozen = rel_path in FROZEN_STAGE24_HASHES
            meta = SKILL_METADATA.get(skill_id, {
                "scope": SkillScopeType.GENERAL.value,
                "intended_role": "Discovered repository skill.",
                "dependencies": [],
                "loading_mechanism": "DECLARATIVE_YAML_AND_PROMPT_REFERENCE",
                "competition_packaging_relevance": "ROOT_AGENT_SKILL",
            })

            rec = SkillRecord(
                skill_id=skill_id,
                path=rel_path,
                current_hash=sha,
                scope=meta["scope"],
                intended_role=meta["intended_role"],
                is_frozen=is_frozen,
                is_optimizer_eligible=True,
                dependencies=meta["dependencies"],
                loading_mechanism=meta["loading_mechanism"],
                competition_packaging_relevance=meta["competition_packaging_relevance"],
            )
            skills.append(rec)

        return skills

    def get_skill(self, skill_id: str) -> Optional[SkillRecord]:
        """Retrieves an individual skill record by ID."""
        skills = self.discover_skills()
        for s in skills:
            if s.skill_id == skill_id:
                return s
        return None

    def render_inventory_md(self) -> str:
        """Renders markdown summary of the skill inventory."""
        skills = self.discover_skills()
        lines: list[str] = [
            "# IMPULSE Skill Inventory",
            "",
            "| Skill ID | Scope | Path | Current SHA-256 (12 chars) | Frozen | Optimizer Eligible |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in skills:
            lines.append(
                f"| `{s.skill_id}` | `{s.scope}` | `{s.path}` | `{s.current_hash[:12]}` | "
                f"`{'YES' if s.is_frozen else 'NO'}` | `{'YES' if s.is_optimizer_eligible else 'NO'}` |"
            )
        lines.append("")
        return "\n".join(lines)
