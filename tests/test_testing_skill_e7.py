"""Unit and regression tests for Candidate E7 and Systematic Testing Strategy Skill (Stage 16)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E6)
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

EXPECTED_E7_TOOLS = [
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


class TestTestingSkillE7(unittest.TestCase):
    """Focused verification tests for Stage 16 Candidate E7 and the test_strategy skill."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # 1-4: Submission Validation & Parity with E6
    # -------------------------------------------------------------
    def test_01_e7_submission_configuration_passes_validation(self) -> None:
        """1. E7 candidate directory satisfies all submission rules."""
        e7_dir = PROJECT_ROOT / "experiments" / "candidates" / "E7"
        validator = SubmissionValidator(e7_dir)
        valid = validator.validate()
        self.assertTrue(valid, f"E7 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    def test_02_e7_preserves_e6_model(self) -> None:
        """2. E7 preserves the exact model gemma-4-31b-it-qat-w4a16-ct."""
        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        e6_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E6/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e7_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e7_yaml["model"], e6_yaml["model"])

    def test_03_e7_preserves_e6_generation_settings(self) -> None:
        """3. E7 preserves identical sampling configuration."""
        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        e6_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E6/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e7_yaml["generate_content_config"], e6_yaml["generate_content_config"])

    def test_04_e7_preserves_all_9_e6_competition_tools(self) -> None:
        """4. E7 preserves all 9 competition tools without additions or removals."""
        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e7_yaml["tools"], EXPECTED_E7_TOOLS)
        self.assertEqual(len(e7_yaml["tools"]), 9)

    # -------------------------------------------------------------
    # 5-11: Invariance of Prior Candidates (E0–E6)
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

    # -------------------------------------------------------------
    # 12-17: Skill Location, Structure, Contents & Boundaries
    # -------------------------------------------------------------
    def test_12_skill_md_exists_at_canonical_location(self) -> None:
        """12. SKILL.md exists at required canonical path agent/skills/test_strategy/SKILL.md."""
        canonical_path = PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md"
        self.assertTrue(canonical_path.exists(), f"Missing canonical skill file at {canonical_path}")
        self.assertGreater(canonical_path.stat().st_size, 500)

    def test_13_skill_is_discoverable_and_declared_in_candidate(self) -> None:
        """13. Skill is declared in E7 agent.yaml and packaged in candidate directory."""
        candidate_skill_path = PROJECT_ROOT / "experiments/candidates/E7/skills/test_strategy/SKILL.md"
        self.assertTrue(candidate_skill_path.exists())
        self.assertEqual(
            self._hash_file("agent/skills/test_strategy/SKILL.md"),
            self._hash_file("experiments/candidates/E7/skills/test_strategy/SKILL.md"),
        )

        e7_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E7/agent.yaml").read_text(encoding="utf-8"))
        self.assertIn("skills", e7_yaml)
        self.assertIn("skills/test_strategy", e7_yaml["skills"])

    def test_14_skill_contains_all_seven_core_behaviors(self) -> None:
        """14. SKILL.md contains all seven required testing strategy workflow concepts."""
        skill_text = (PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md").read_text(encoding="utf-8").lower()

        required_concepts = [
            ("discover test framework", ["discover", "framework"]),
            ("identify relevant test area", ["relevant", "test area"]),
            ("reproduce narrowly", ["reproduce", "narrow"]),
            ("run targeted verification", ["targeted", "smallest"]),
            ("broaden coverage intelligently", ["broaden", "intelligent"]),
            ("interpret results soundly", ["interpret", "exit code"]),
            ("avoid unnecessary full suites", ["avoid", "full-suite", "redundant"]),
        ]

        for concept_name, keywords in required_concepts:
            for kw in keywords:
                self.assertIn(
                    kw,
                    skill_text,
                    f"Required keyword '{kw}' for concept '{concept_name}' missing from SKILL.md",
                )

    def test_15_skill_does_not_contain_benchmark_task_specific_instructions(self) -> None:
        """15. Skill contains no task-specific answers or benchmark hard-coding."""
        skill_text = (PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md").read_text(encoding="utf-8").lower()

        forbidden_task_strings = [
            "fastapi_14479",
            "fastapi_14786",
            "requests_6629",
            "requests_7505",
            "rich_4070",
            "fastapi tests usually live in",
            "requests tests are under",
            "for this benchmark",
        ]

        for forbidden in forbidden_task_strings:
            self.assertNotIn(
                forbidden,
                skill_text,
                f"Found prohibited task-specific string '{forbidden}' in SKILL.md",
            )

    def test_16_skill_does_not_contain_fake_results_or_claims(self) -> None:
        """16. Skill contains zero fabricated pass rates, benchmark scores, or fake test output."""
        skill_text = (PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md").read_text(encoding="utf-8").lower()
        manifest_text = (PROJECT_ROOT / "experiments/prompts/E7/manifest.json").read_text(encoding="utf-8").lower()

        for forbidden in ["pass rate:", "100% reliable", "verified benchmark score", "empirically superior"]:
            self.assertNotIn(forbidden, skill_text)
            self.assertNotIn(forbidden, manifest_text)

    def test_17_skill_does_not_introduce_stage_17_plus_concepts(self) -> None:
        """17. Stage 17+ concepts (triage skill, failure classifier, recovery, sub-agents) are absent."""
        skill_text = (PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md").read_text(encoding="utf-8").lower()
        prompt_text = (PROJECT_ROOT / "experiments/candidates/E7/prompts/root.md").read_text(encoding="utf-8").lower()

        for forbidden in [
            "repository triage skill",
            "failure classification",
            "no-progress detector",
            "recovery path",
            "scout agent",
            "debugger agent",
            "reviewer agent",
            "repo_triage",
        ]:
            self.assertNotIn(forbidden, skill_text)
            self.assertNotIn(forbidden, prompt_text)

    # -------------------------------------------------------------
    # 18-20: Prompt Minimal Delta, Hygiene & Secrets
    # -------------------------------------------------------------
    def test_18_e7_prompt_delta_is_minimal_and_relevant_to_skill(self) -> None:
        """18. E7 prompt extends E6 only with test_strategy skill references."""
        e6_prompt = (PROJECT_ROOT / "experiments/candidates/E6/prompts/root.md").read_text(encoding="utf-8")
        e7_prompt = (PROJECT_ROOT / "experiments/candidates/E7/prompts/root.md").read_text(encoding="utf-8")

        self.assertIn("test_strategy", e7_prompt)
        self.assertIn("skills/test_strategy/SKILL.md", e7_prompt)
        self.assertNotIn("test_strategy", e6_prompt)

        # Ensure core process steps 1-6 and 8-10 remain unchanged
        self.assertIn("1. **Understand the Issue**", e7_prompt)
        self.assertIn("5. **Formulate Root Cause Hypothesis**", e7_prompt)
        self.assertIn("6. **Make the Smallest Justified Change**", e7_prompt)
        self.assertIn("10. **Submit Patch**", e7_prompt)

    def test_19_manifest_and_no_unrelated_configuration_changes(self) -> None:
        """19. Manifest accurately records null empirical metrics and parent commit."""
        manifest_path = PROJECT_ROOT / "experiments/prompts/E7/manifest.json"
        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["candidate_id"], "E7")
        self.assertEqual(data["parent_candidate"], "E6")
        self.assertEqual(data["parent_git_commit"], "36be03bdfc98937c3eb727ceb22a264c03935c87")
        self.assertIsNone(data["pass_rate"])
        self.assertIsNone(data["redundant_test_command_count"])
        self.assertIsNone(data["full_suite_invocations"])
        self.assertFalse(data["benchmark_scores_asserted"])

    def test_20_no_secrets_committed(self) -> None:
        """20. No API keys, credentials, or session tokens exist in Stage 16 artifacts."""
        for path in [
            PROJECT_ROOT / "agent/skills/test_strategy/SKILL.md",
            PROJECT_ROOT / "experiments/candidates/E7/agent.yaml",
            PROJECT_ROOT / "experiments/candidates/E7/prompts/root.md",
            PROJECT_ROOT / "experiments/prompts/E7/manifest.json",
            PROJECT_ROOT / "experiments/prompts/E7/report.md",
            PROJECT_ROOT / "docs/decisions/testing_skill.md",
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
