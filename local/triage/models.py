"""Data models and representations for repository triage (Stage 17)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any

from local.task_state.models import TaskState


@dataclass
class RepoTriageSummary:
    """Compact summary of repository triage reconnaissance."""

    language: str = "unknown"
    framework: str = "unknown"
    package_manager: str = "unknown"
    entry_points: list[str] = field(default_factory=list)
    source_layout: str = "unknown"
    test_layout: str = "unknown"
    ci_convention: str = "unknown"
    relevant_commands: list[str] = field(default_factory=list)
    important_config: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    def format_summary(self) -> str:
        """Renders a clean, bounded human-readable triage summary."""
        entry_points_str = ", ".join(self.entry_points) if self.entry_points else "None detected"
        commands_str = "; ".join(self.relevant_commands) if self.relevant_commands else "None detected"
        config_str = ", ".join(self.important_config) if self.important_config else "None detected"
        unknowns_str = ", ".join(self.unknowns) if self.unknowns else "None"

        return (
            "=== Repository Triage Summary ===\n"
            f"Language(s):          {self.language}\n"
            f"Framework:            {self.framework}\n"
            f"Package Manager:      {self.package_manager}\n"
            f"Entry Point(s):       {entry_points_str}\n"
            f"Source Layout:        {self.source_layout}\n"
            f"Test Layout:          {self.test_layout}\n"
            f"CI / Build Command:   {commands_str}\n"
            f"Key Configurations:   {config_str}\n"
            f"Unknowns / Ambiguity: {unknowns_str}\n"
            "================================="
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the summary into a JSON-safe dictionary."""
        return asdict(self)

    def integrate_into_task_state(self, state: TaskState) -> None:
        """Concisely records verified repository triage facts into TaskState.

        Guarantees:
        - No huge tree dumps or raw file copies.
        - Strict bounded facts.
        - Categorized entries for easy recall across turns.
        """
        state.add_repository_fact(
            category="environment",
            fact=f"Language: {self.language}; Framework: {self.framework}; Tooling: {self.package_manager}",
            source="repo_triage",
        )
        if self.source_layout != "unknown" or self.test_layout != "unknown":
            state.add_repository_fact(
                category="layout",
                fact=f"Source: {self.source_layout}; Tests: {self.test_layout}",
                source="repo_triage",
            )
        if self.entry_points:
            state.add_repository_fact(
                category="architecture",
                fact=f"Entry points: {', '.join(self.entry_points[:3])}",
                source="repo_triage",
            )
        if self.relevant_commands:
            state.add_repository_fact(
                category="conventions",
                fact=f"Build/Test commands: {'; '.join(self.relevant_commands[:3])}",
                source="repo_triage",
            )
        if self.unknowns:
            state.add_repository_fact(
                category="uncertainty",
                fact=f"Triage unknowns: {', '.join(self.unknowns[:3])}",
                source="repo_triage",
            )
