"""Unit and regression tests for Candidate E8 and Repository Triage Skill (Stage 17)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.task_state.models import TaskState
from local.triage.models import RepoTriageSummary
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E7)
E0_AGENT_SHA256 = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
E0_PROMPT_SHA256 = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"
E1_AGENT_SHA256 = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
E1_PROMPT_SHA256 = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"
E2_AGENT_SHA256 = "cefb9297917626ba10f07b39a2769a668246b6a3d13f4f6e1ffde08f0c62df04"
E2_PROMPT_SHA256 = "f8358618a67353d0a456ece8dc037bbdaefe108d99fa4f997e5daf4fb354fd4e"
E3_AGENT_SHA256 = "2cf03011fc03c37292a1b0cdd74ae9d512f97bd8f1a5148939410e96c5e6b783"
E3_PROMPT_SHA256 = "6925be383fbbdd0f58a885a82c02b5e9fefe434d8cb7f91d6b5107ada9e120cf"
E4_AGENT_SHA256 = "ec3cddcf88d5e04a2415dac7a59aed6464ce0e379f301ae4df24e507368953ca"
E4_PROMPT_SHA256 = "4a7eefeb785bf1334e2f6f85a2f6b9ebeb5349f42b0acb3327d19bbd9ad7008d"
E5_AGENT_SHA256 = "137e26ebcd7018bdad4b488f71d1221b06f979f2b3f5d8ac9179f89c95f6cf28"
E5_PROMPT_SHA256 = "d4128a6dc3d016422370cb6354a355971408463399196dcaf97e7ce04ec83756"
E6_AGENT_SHA256 = "c2dec89c9df91bc9c0324ab43c379f7ef9fc6a79ae35af3bdd09e13e0d093724"
E6_PROMPT_SHA256 = "fe9805fc39ef2e4861aa4ea9b0956985080012acef70397b3f485f083733278e"
E7_AGENT_SHA256 = "92021a5379f36c7eeacca0962f666494efe028c973148f8e0f412812479692a0"
E7_PROMPT_SHA256 = "d1195b317a475a2411b99b49d701d16e71bedd9b3c6c035d800970e15914950d"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"

EXPECTED_E8_TOOLS = [
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
]


class TestRepoTriageSkillE8(unittest.TestCase):
    """35+ focused verification tests for Stage 17 Candidate E8 and repo_triage skill."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # 1-4: Submission Validation & Parity with E7
    # -------------------------------------------------------------
    def test_01_e8_submission_configuration_passes_validation(self) -> None:
        """1. E8 candidate directory satisfies all submission rules."""
        e8_dir = PROJECT_ROOT / "experiments" / "candidates" / "E8"
        validator = SubmissionValidator(e8_dir)
        valid = validator.validate()
        self.assertTrue(valid, f"E8 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    def test_02_e8_preserves_e7_model(self) -> None:
        """2. E8 preserves the exact model gemma-4-31b-it-qat-w4a16-ct."""
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e8_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e8_yaml["model"], e7_yaml["model"])

    def test_03_e8_preserves_e7_generation_settings(self) -> None:
        """3. E8 preserves identical sampling configuration."""
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e8_yaml["generate_content_config"], e7_yaml["generate_content_config"])

    def test_04_e8_preserves_all_9_e7_competition_tools(self) -> None:
        """4. E8 preserves all 9 competition tools without additions or removals."""
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e8_yaml["tools"], EXPECTED_E8_TOOLS)
        self.assertEqual(len(e8_yaml["tools"]), 9)

    # -------------------------------------------------------------
    # 5-12: Invariance of Prior Candidates (E0–E7)
    # -------------------------------------------------------------
    def test_05_e0_remains_unchanged(self) -> None:
        """5. E0 files remain strictly invariant."""
        self.assertEqual(self._hash_file("agent/agent.yaml"), E0_AGENT_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/root.md"), E0_PROMPT_SHA256)

    def test_06_e1_remains_unchanged(self) -> None:
        """6. E1 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E1/agent.yaml"), E1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E1/prompts/root.md"), E1_PROMPT_SHA256)

    def test_07_e2_remains_unchanged(self) -> None:
        """7. E2 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E2/agent.yaml"), E2_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E2/prompts/root.md"), E2_PROMPT_SHA256)

    def test_08_e3_remains_unchanged(self) -> None:
        """8. E3 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E3/agent.yaml"), E3_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E3/prompts/root.md"), E3_PROMPT_SHA256)

    def test_09_e4_remains_unchanged(self) -> None:
        """9. E4 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E4/agent.yaml"), E4_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E4/prompts/root.md"), E4_PROMPT_SHA256)

    def test_10_e5_remains_unchanged(self) -> None:
        """10. E5 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E5/agent.yaml"), E5_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E5/prompts/root.md"), E5_PROMPT_SHA256)

    def test_11_e6_remains_unchanged(self) -> None:
        """11. E6 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E6/agent.yaml"), E6_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E6/prompts/root.md"), E6_PROMPT_SHA256)

    def test_12_e7_remains_unchanged(self) -> None:
        """12. E7 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E7/agent.yaml"), E7_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E7/prompts/root.md"), E7_PROMPT_SHA256)

    # -------------------------------------------------------------
    # 13-16: Skill Presence, Parity & Dual Skill Declaration
    # -------------------------------------------------------------
    def test_13_canonical_repo_triage_skill_exists(self) -> None:
        """13. Canonical repo_triage SKILL.md exists at required path."""
        path = PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md"
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 500)

    def test_14_packaged_repo_triage_skill_exists(self) -> None:
        """14. Packaged repo_triage SKILL.md exists and matches canonical."""
        canonical = self._hash_file("agent/skills/repo_triage/SKILL.md")
        packaged = self._hash_file("experiments/candidates/E8/skills/repo_triage/SKILL.md")
        self.assertEqual(canonical, packaged)

    def test_15_test_strategy_skill_remains_present_and_unchanged(self) -> None:
        """15. Stage 16 test_strategy skill remains present and unchanged."""
        canonical_test_strategy = self._hash_file("agent/skills/test_strategy/SKILL.md")
        self.assertEqual(canonical_test_strategy, CANONICAL_TEST_STRATEGY_SHA256)
        e8_packaged_test_strategy = self._hash_file("experiments/candidates/E8/skills/test_strategy/SKILL.md")
        self.assertEqual(e8_packaged_test_strategy, CANONICAL_TEST_STRATEGY_SHA256)

    def test_16_both_skills_are_correctly_declared_in_e8(self) -> None:
        """16. Both test_strategy and repo_triage are declared in E8 agent.yaml."""
        e8_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E8/agent.yaml").read_text(encoding="utf-8"))
        self.assertIn("skills", e8_yaml)
        self.assertIn("skills/test_strategy", e8_yaml["skills"])
        self.assertIn("skills/repo_triage", e8_yaml["skills"])
        self.assertEqual(len(e8_yaml["skills"]), 2)

    # -------------------------------------------------------------
    # 17-23: Seven Triage Dimensions
    # -------------------------------------------------------------
    def test_17_skill_contains_language_discovery_guidance(self) -> None:
        """17. Skill teaches language and polyglot discovery from evidence."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("language", text)
        self.assertIn("polyglot", text)
        self.assertIn("file extensions", text)

    def test_18_skill_contains_framework_discovery_guidance(self) -> None:
        """18. Skill teaches framework and ecosystem discovery."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("framework", text)
        self.assertIn("dependencies", text)
        self.assertIn("ecosystem", text)

    def test_19_skill_contains_package_and_build_manager_discovery(self) -> None:
        """19. Skill teaches package manager and build tooling discovery."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("package manager", text)
        self.assertIn("build", text)
        self.assertIn("pyproject.toml", text)
        self.assertIn("package.json", text)
        self.assertIn("cargo.toml", text)

    def test_20_skill_contains_entry_point_discovery(self) -> None:
        """20. Skill teaches locating application and package entry points."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("entry point", text)
        self.assertIn("__main__", text)
        self.assertIn("console script", text)

    def test_21_skill_contains_test_layout_discovery(self) -> None:
        """21. Skill teaches identifying test topology and layout."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("test topology", text)
        self.assertIn("test directories", text)
        self.assertIn("test_strategy", text)

    def test_22_skill_contains_ci_and_build_convention_discovery(self) -> None:
        """22. Skill teaches extracting conventions from CI workflows and Makefiles."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn(".github/workflows", text)
        self.assertIn("makefile", text)
        self.assertIn("conventions", text)

    def test_23_skill_contains_repository_layout_mapping(self) -> None:
        """23. Skill teaches constructing a compact repository structural map."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("source directories", text)
        self.assertIn("repository layout", text)
        self.assertIn("compact structural", text)

    # -------------------------------------------------------------
    # 24-28: Evidence, Anti-Fabrication & Bounded Reconnaissance Rules
    # -------------------------------------------------------------
    def test_24_skill_requires_evidence_before_conclusions(self) -> None:
        """24. Skill forbids guessing and requires evidence for conclusions."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("verify before asserting", text)
        self.assertIn("evidence", text)

    def test_25_skill_supports_explicit_unknowns(self) -> None:
        """25. Skill explicitly supports recording unknowns rather than fabricating."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("unknowns", text)
        self.assertIn("unknown", text)

    def test_26_skill_forbids_secrets_in_triage_summaries(self) -> None:
        """26. Skill forbids copying credentials, tokens, or private keys into task state."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("secrets", text)
        self.assertIn("credentials", text)

    def test_27_skill_avoids_huge_recursive_repository_dumps(self) -> None:
        """27. Skill explicitly prohibits recursive whole-tree dumps and vendor scanning."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("never recursively dump", text)
        self.assertIn("node_modules", text)
        self.assertIn("vendor", text)

    def test_28_skill_specifies_bounded_high_value_reconnaissance_order(self) -> None:
        """28. Skill establishes strict priority order for reconnaissance."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("bounded reconnaissance protocol", text)
        self.assertIn("root directory listing", text)
        self.assertIn("root configuration & manifests", text)

    # -------------------------------------------------------------
    # 29-33: Anti-Hardcoding & Stage Boundaries
    # -------------------------------------------------------------
    def test_29_skill_contains_no_benchmark_task_ids(self) -> None:
        """29. Skill contains zero benchmark task IDs."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        for forbidden in ["fastapi_14479", "fastapi_14786", "requests_6629", "requests_7505", "rich_4070"]:
            self.assertNotIn(forbidden, text)

    def test_30_skill_contains_no_repository_specific_answers(self) -> None:
        """30. Skill contains no repository-specific answers for FastAPI, Requests, Rich."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        for forbidden in [
            "fastapi source is in",
            "requests source is in",
            "rich source is in",
            "for this benchmark task",
        ]:
            self.assertNotIn(forbidden, text)

    def test_31_skill_does_not_contain_stage_18_failure_classification(self) -> None:
        """31. Skill does not contain Stage 18 failure classification."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("failure classification", text)
        self.assertNotIn("failureclassifier", text)

    def test_32_skill_does_not_contain_stage_19_no_progress_instructions(self) -> None:
        """32. Skill does not contain Stage 19 no-progress instructions."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("no-progress detector", text)
        self.assertNotIn("no_progress_detector", text)

    def test_33_skill_does_not_contain_stage_20_recovery_logic(self) -> None:
        """33. Skill does not contain Stage 20 recovery logic."""
        text = (PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("recovery path", text)
        self.assertNotIn("recovery a", text)
        self.assertNotIn("recovery b", text)

    # -------------------------------------------------------------
    # 34-37: Prompt Integration, TaskState & Secrets
    # -------------------------------------------------------------
    def test_34_e8_prompt_contains_minimal_repo_triage_integration(self) -> None:
        """34. E8 prompt integrates repo_triage under Operational Workflow and Step 2."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E8/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("repo_triage", prompt)
        self.assertIn("skills/repo_triage/SKILL.md", prompt)
        self.assertIn("2. **Inspect Repository State**: Follow the `repo_triage` skill", prompt)

    def test_35_e8_prompt_preserves_e7_localization_and_testing_guidance(self) -> None:
        """35. E8 prompt preserves all of E7's hybrid localization and testing strategy guidance."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E8/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("## Hybrid Localization Strategy", prompt)
        self.assertIn("search_similar_code", prompt)
        self.assertIn("get_code_neighbors", prompt)
        self.assertIn("get_code_subgraph", prompt)
        self.assertIn("test_strategy", prompt)
        self.assertIn("7. **Run Targeted Verification**", prompt)

    def test_36_repo_triage_summary_model_and_task_state_integration(self) -> None:
        """36. RepoTriageSummary formats clean summaries and integrates into TaskState without bloat."""
        summary = RepoTriageSummary(
            language="Python",
            framework="FastAPI",
            package_manager="flit",
            entry_points=["fastapi.cli:main"],
            source_layout="fastapi/",
            test_layout="tests/ (pytest)",
            ci_convention="pytest tests/",
            relevant_commands=["pytest"],
            important_config=["pyproject.toml"],
            unknowns=["Packaging backend flags"],
        )
        formatted = summary.format_summary()
        self.assertIn("Language(s):          Python", formatted)
        self.assertIn("Framework:            FastAPI", formatted)
        self.assertIn("Entry Point(s):       fastapi.cli:main", formatted)

        state = TaskState()
        summary.integrate_into_task_state(state)
        state.validate()

        self.assertGreaterEqual(len(state.repository_facts), 3)
        self.assertLessEqual(len(state.repository_facts), 10)
        # Ensure no raw file dumps
        for fact in state.repository_facts:
            self.assertLess(len(fact.fact), 200)

    def test_37_no_secrets_committed_in_stage_17_artifacts(self) -> None:
        """37. No API keys, credentials, or session tokens exist in Stage 17 artifacts."""
        for path in [
            PROJECT_ROOT / "agent/skills/repo_triage/SKILL.md",
            PROJECT_ROOT / "experiments/candidates/E8/agent.yaml",
            PROJECT_ROOT / "experiments/candidates/E8/prompts/root.md",
            PROJECT_ROOT / "experiments/candidates/E8/skills/repo_triage/SKILL.md",
            PROJECT_ROOT / "experiments/prompts/E8/manifest.json",
            PROJECT_ROOT / "experiments/prompts/E8/report.md",
            PROJECT_ROOT / "docs/decisions/repo_triage_skill.md",
            PROJECT_ROOT / "local/triage/models.py",
        ]:
            text = path.read_text(encoding="utf-8").lower()
            for secret_pattern in ["api_key", "secret_key", "bearer ", "ghp_", "sk-proj-", "sk-live-"]:
                self.assertNotIn(
                    secret_pattern,
                    text,
                    f"Potential credential pattern '{secret_pattern}' found in {path.name}",
                )


if __name__ == "__main__":
    unittest.main()
