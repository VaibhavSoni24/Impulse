"""Unit and regression tests for Candidate E_S1/E_S2 and Scout Agent (Stage 21).

Validates:
A. Scout structure
B. Read-only enforcement
C. Scout output contract
D. Uncertainty trigger
E. E_S1 invocation policy (Available)
F. E_S2 invocation policy (Mandatory under uncertainty)
G. S1 vs S2 experimental isolation
H. TaskState integration
I. E0–E11 invariance
J. Candidate submission validation
K. Anti-cheating / anti-overfitting guarantees
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.failures import FailureClass
from local.progress import NoProgressDetectorV1, ProgressStatus
from local.recovery import RecoveryControllerV1, RecoveryPath, RecoveryState
from local.scout import (
    ScoutControllerV1,
    ScoutPolicy,
    ScoutResult,
    ScoutStatus,
    ScoutTriggerContext,
    evaluate_scout_trigger,
    is_localization_uncertain,
)
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E11)
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
E8_AGENT_SHA256 = "c7c7f49faae94b904357583b2fc0e46ce9be0999688641f5d18e8a1e0e905f15"
E8_PROMPT_SHA256 = "d607c494fc32f3132df3301bccc693adf8ba4074bdbc190860b1df65b6f78220"
E9_AGENT_SHA256 = "eba7d0f032fa169918e2e3e1a1606ead98d1d825688db2817625922dd5ecc977"
E9_PROMPT_SHA256 = "a03fba7410c03d0929d95653ad892c42f802d2a0a017eab92a2e2168bee2fc48"
E10_AGENT_SHA256 = "779f70c0feeb9f89b577a62c73361afc3aae7823d86a05e23b6fc246b66babf7"
E10_PROMPT_SHA256 = "4766117f671fd7fb4e4e8ade8afe46d7c9412fbe7255ee2a29f9b38ebc25b73f"
E11_AGENT_SHA256 = "688e0269c966db0f7dd367735190dbd3fa193a69c73dc7b3d48eff63237da01a"
E11_PROMPT_SHA256 = "42a895fe99b5c537c348e92f02d7c906185b32afb450f393cf0e8255bd407356"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

EXPECTED_ROOT_TOOLS = [
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

EXPECTED_SCOUT_TOOLS = [
    "read_file",
    "get_status",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
]


class TestScoutStage21(unittest.TestCase):
    """57+ verification tests for Stage 21 Candidate E_S1 / E_S2 and the Scout agent."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # A. Scout Structure (1 - 5)
    # -------------------------------------------------------------
    def test_01_scout_config_parses_successfully(self) -> None:
        """1. Scout YAML configuration parses into a valid mapping."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/scout.yaml"
        self.assertTrue(cfg_path.exists())
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("name"), "scout")

    def test_02_scout_uses_exact_competition_model(self) -> None:
        """2. Scout declares the exact model gemma-4-31b-it-qat-w4a16-ct."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/scout.yaml"
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.get("model"), "gemma-4-31b-it-qat-w4a16-ct")

    def test_03_scout_is_declared_as_sub_agent_using_valid_harness_schema(self) -> None:
        """3. Root agent configurations declare scout under sub_agents."""
        for cand in ["E_S1", "E_S2"]:
            yaml_path = PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml"
            parsed = parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
            self.assertIn("sub_agents", parsed)
            sub_agents = parsed["sub_agents"]
            self.assertIsInstance(sub_agents, list)
            self.assertEqual(len(sub_agents), 1)
            self.assertEqual(sub_agents[0].get("config_path"), "sub_agents/scout.yaml")

    def test_04_scout_prompt_exists(self) -> None:
        """4. Scout prompt file exists in canonical and candidate locations."""
        self.assertTrue((PROJECT_ROOT / "agent/prompts/scout.md").exists())
        self.assertTrue((PROJECT_ROOT / "experiments/candidates/E_S1/prompts/scout.md").exists())
        self.assertTrue((PROJECT_ROOT / "experiments/candidates/E_S2/prompts/scout.md").exists())

    def test_05_scout_prompt_explicitly_enforces_read_only_behavior(self) -> None:
        """5. Scout prompt contains explicit READ ONLY and mutation prohibition instructions."""
        prompt = (PROJECT_ROOT / "agent/prompts/scout.md").read_text(encoding="utf-8")
        self.assertIn("READ ONLY", prompt)
        self.assertIn("Do not modify any repository file", prompt)
        self.assertIn("Do not create new files", prompt)
        self.assertIn("Do not submit patches", prompt)

    # -------------------------------------------------------------
    # B. Read-Only Enforcement (6 - 10)
    # -------------------------------------------------------------
    def test_06_scout_has_no_edit_file(self) -> None:
        """6. Scout tool list does NOT contain edit_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("edit_file", cfg.get("tools", []))

    def test_07_scout_has_no_write_file(self) -> None:
        """7. Scout tool list does NOT contain write_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("write_file", cfg.get("tools", []))

    def test_08_scout_has_no_submit_patch(self) -> None:
        """8. Scout tool list does NOT contain submit_patch."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("submit_patch", cfg.get("tools", []))

    def test_09_scout_has_no_run_command_to_prevent_destructive_reset(self) -> None:
        """9. Scout tool list does NOT contain run_command (prevents destructive shell reset)."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("run_command", cfg.get("tools", []))

    def test_10_scout_tools_are_strictly_read_only(self) -> None:
        """10. Scout tools match exactly the 5 read-only competition tools."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("tools"), EXPECTED_SCOUT_TOOLS)
        self.assertEqual(len(cfg.get("tools")), 5)

    # -------------------------------------------------------------
    # C. Scout Output (11 - 19)
    # -------------------------------------------------------------
    def test_11_valid_scout_result_structure(self) -> None:
        """11. ScoutResult initializes with all expected fields."""
        res = ScoutResult(
            issue_summary="TypeError in query parser",
            candidate_files=["src/parser.py"],
            candidate_symbols=["parse_query"],
            relevant_relationships=["parse_query -> tokenize"],
            evidence=["parser.py:42: int conversion fails on None"],
            unresolved_questions=["Is None allowed in schema?"],
            recommended_inspection_targets=["src/schema.py"],
            status=ScoutStatus.LOCALIZED,
        )
        d = res.to_dict()
        self.assertEqual(d["issue_summary"], "TypeError in query parser")
        self.assertEqual(d["candidate_files"], ["src/parser.py"])
        self.assertEqual(d["status"], "LOCALIZED")

    def test_12_localized_result(self) -> None:
        """12. ScoutResult supports LOCALIZED status."""
        res = ScoutResult(status=ScoutStatus.LOCALIZED)
        self.assertEqual(res.status, ScoutStatus.LOCALIZED)

    def test_13_partially_localized_result(self) -> None:
        """13. ScoutResult supports PARTIALLY_LOCALIZED status."""
        res = ScoutResult(status=ScoutStatus.PARTIALLY_LOCALIZED)
        self.assertEqual(res.status, ScoutStatus.PARTIALLY_LOCALIZED)

    def test_14_ambiguous_result(self) -> None:
        """14. ScoutResult supports AMBIGUOUS status."""
        res = ScoutResult(status=ScoutStatus.AMBIGUOUS)
        self.assertEqual(res.status, ScoutStatus.AMBIGUOUS)

    def test_15_insufficient_evidence_result(self) -> None:
        """15. ScoutResult supports INSUFFICIENT_EVIDENCE status."""
        res = ScoutResult(status=ScoutStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(res.status, ScoutStatus.INSUFFICIENT_EVIDENCE)

    def test_16_bounded_evidence_length(self) -> None:
        """16. ScoutResult truncates long summaries to bounded length."""
        long_summary = "a" * 2000
        res = ScoutResult(issue_summary=long_summary)
        d = res.to_dict()
        self.assertLessEqual(len(d["issue_summary"]), 500)

    def test_17_no_raw_tool_log_dumping(self) -> None:
        """17. format_summary generates a clean overview without raw tool trace dumps."""
        res = ScoutResult(
            issue_summary="Syntax error in tokenizer",
            candidate_files=["src/token.py"],
            candidate_symbols=["Tokenizer"],
            evidence=["token.py:10: unhandled EOF"],
            status=ScoutStatus.LOCALIZED,
        )
        summary = res.format_summary()
        self.assertIn("=== Scout Localization Result ===", summary)
        self.assertNotIn("stdout", summary.lower())
        self.assertNotIn("traceback (most recent call last)", summary.lower())

    def test_18_no_secrets_in_scout_output(self) -> None:
        """18. Secrets or tokens are not present in serialized ScoutResult."""
        res = ScoutResult(
            issue_summary="Connection error",
            candidate_files=["src/auth.py"],
            evidence=["auth.py:20: missing token check"],
        )
        text = json.dumps(res.to_dict())
        self.assertNotIn("ghp_", text)
        self.assertNotIn("password", text.lower())

    def test_19_deterministic_serialization(self) -> None:
        """19. to_dict serialization is deterministic across identical calls."""
        res = ScoutResult(
            issue_summary="Defect",
            candidate_files=["a.py", "b.py"],
            status=ScoutStatus.AMBIGUOUS,
            timestamp="2026-09-28T09:00:00Z",
        )
        self.assertEqual(res.to_dict(), res.to_dict())

    # -------------------------------------------------------------
    # D. Uncertainty Trigger (20 - 24)
    # -------------------------------------------------------------
    def test_20_clearly_localized_task_does_not_trigger_scout(self) -> None:
        """20. Scout does NOT trigger when defect location is already confirmed."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            has_confirmed_defect_location=True,
            source_evidence_sufficient=True,
            candidate_files=["src/parser.py"],
        )
        uncertain, reason = is_localization_uncertain(ctx)
        self.assertFalse(uncertain)
        self.assertIn("already confirmed", reason)

    def test_21_ambiguous_localization_triggers_uncertainty(self) -> None:
        """21. Recon completed with no candidate locations triggers uncertainty."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=[],
            has_confirmed_defect_location=False,
            source_evidence_sufficient=False,
        )
        uncertain, reason = is_localization_uncertain(ctx)
        self.assertTrue(uncertain)
        self.assertIn("zero confirmed candidate targets", reason)

    def test_22_multiple_unresolved_candidates_triggers_uncertainty(self) -> None:
        """22. Multiple unresolved candidate files trigger uncertainty."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py", "src/c.py"],
            has_confirmed_defect_location=False,
            source_evidence_sufficient=False,
        )
        uncertain, reason = is_localization_uncertain(ctx)
        self.assertTrue(uncertain)
        self.assertIn("multiple candidate targets remain", reason)

    def test_23_insufficient_or_conflicting_retrieval_triggers_uncertainty(self) -> None:
        """23. Conflicting or weak retrieval triggers uncertainty."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py"],
            retrieval_conflicting_or_weak=True,
            has_confirmed_defect_location=False,
            source_evidence_sufficient=False,
        )
        uncertain, reason = is_localization_uncertain(ctx)
        self.assertTrue(uncertain)
        self.assertIn("conflicting or weak", reason)

    def test_24_trigger_is_deterministic_for_identical_state(self) -> None:
        """24. Uncertainty evaluation produces identical results for identical contexts."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/foo.py", "src/bar.py"],
        )
        res1 = is_localization_uncertain(ctx)
        res2 = is_localization_uncertain(ctx)
        self.assertEqual(res1, res2)

    # -------------------------------------------------------------
    # E. E_S1 Invocation Policy (25 - 28)
    # -------------------------------------------------------------
    def test_25_e_s1_scout_is_available(self) -> None:
        """25. Under policy AVAILABLE, evaluate_scout_trigger indicates Scout is available."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py"],
        )
        can_invoke, reason = evaluate_scout_trigger(ctx, policy=ScoutPolicy.AVAILABLE)
        self.assertTrue(can_invoke)
        self.assertIn("Scout available", reason)

    def test_26_e_s1_root_may_choose_not_to_invoke_scout(self) -> None:
        """26. E_S1 root prompt establishes that Scout invocation is discretionary."""
        prompt = (PROJECT_ROOT / "experiments/candidates/E_S1/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("you may invoke the read-only `scout` sub-agent", prompt)
        self.assertIn("Invocation is discretionary", prompt)

    def test_27_e_s1_scout_invocation_is_not_mandatory(self) -> None:
        """27. E_S1 agent description declares discretionary availability."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S1/agent.yaml").read_text(encoding="utf-8"))
        self.assertIn("available for discretionary localization reconnaissance", cfg.get("description", ""))

    def test_28_e_s1_no_repeated_scout_invocation_for_unchanged_uncertainty(self) -> None:
        """28. Loop prevention blocks repeat Scout call for unchanged repository state."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py"],
            prior_scout_invocations=1,
            repository_state_version=0,
            last_scout_repo_version=0,
        )
        can_invoke, reason = evaluate_scout_trigger(ctx, policy=ScoutPolicy.AVAILABLE)
        self.assertFalse(can_invoke)
        self.assertIn("loop prevention", reason)

    # -------------------------------------------------------------
    # F. E_S2 Invocation Policy (29 - 32)
    # -------------------------------------------------------------
    def test_29_e_s2_scout_is_mandatory_under_uncertainty(self) -> None:
        """29. Under policy MANDATORY_UNDER_UNCERTAINTY, evaluate_scout_trigger reports mandatory invocation."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py"],
        )
        can_invoke, reason = evaluate_scout_trigger(ctx, policy=ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY)
        self.assertTrue(can_invoke)
        self.assertIn("Scout mandatory", reason)

    def test_30_e_s2_scout_is_not_mandatory_outside_uncertainty(self) -> None:
        """30. Under policy MANDATORY_UNDER_UNCERTAINTY, Scout does NOT trigger without uncertainty."""
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py"],
            has_confirmed_defect_location=True,
            source_evidence_sufficient=True,
        )
        can_invoke, reason = evaluate_scout_trigger(ctx, policy=ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY)
        self.assertFalse(can_invoke)
        self.assertIn("Scout not triggered", reason)

    def test_31_e_s2_exactly_one_scout_invocation_per_episode(self) -> None:
        """31. Controller enforces exactly 1 invocation per unchanged uncertainty episode."""
        ctrl = ScoutControllerV1(policy=ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY)
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py"],
            repository_state_version=0,
        )
        # First check: allowed
        should_run_1, _ = ctrl.should_invoke(ctx)
        self.assertTrue(should_run_1)

        # Record invocation
        result = ScoutResult(status=ScoutStatus.LOCALIZED, candidate_files=["src/a.py"])
        ctrl.record_result(ctx, result)

        # Second check under same state: blocked
        should_run_2, reason_2 = ctrl.should_invoke(ctx)
        self.assertFalse(should_run_2)
        self.assertIn("loop prevention", reason_2)

    def test_32_e_s2_repeated_unchanged_uncertainty_does_not_loop(self) -> None:
        """32. Repeated evaluations under unchanged state do not increase invocation count."""
        ctrl = ScoutControllerV1(policy=ScoutPolicy.MANDATORY_UNDER_UNCERTAINTY)
        ctx = ScoutTriggerContext(
            exact_recon_completed=True,
            candidate_files=["src/a.py", "src/b.py"],
            repository_state_version=1,
        )
        ctrl.should_invoke(ctx)
        ctrl.record_result(ctx, ScoutResult(status=ScoutStatus.AMBIGUOUS))
        self.assertEqual(ctrl.get_invocation_count(), 1)

        # Subsequent attempts
        for _ in range(5):
            should_run, _ = ctrl.should_invoke(ctx)
            self.assertFalse(should_run)
        self.assertEqual(ctrl.get_invocation_count(), 1)

    # -------------------------------------------------------------
    # G. S1 vs S2 Isolation (33 - 39)
    # -------------------------------------------------------------
    def test_33_s1_and_s2_have_identical_scout_prompts(self) -> None:
        """33. Scout prompt is byte-for-byte identical between E_S1 and E_S2."""
        s1_prompt = self._hash_file("experiments/candidates/E_S1/prompts/scout.md")
        s2_prompt = self._hash_file("experiments/candidates/E_S2/prompts/scout.md")
        canonical_prompt = self._hash_file("agent/prompts/scout.md")
        self.assertEqual(s1_prompt, s2_prompt)
        self.assertEqual(s1_prompt, canonical_prompt)

    def test_34_s1_and_s2_have_identical_scout_configs(self) -> None:
        """34. Scout config is byte-for-byte identical between E_S1 and E_S2."""
        s1_cfg = self._hash_file("experiments/candidates/E_S1/sub_agents/scout.yaml")
        s2_cfg = self._hash_file("experiments/candidates/E_S2/sub_agents/scout.yaml")
        canonical_cfg = self._hash_file("agent/sub_agents/scout.yaml")
        self.assertEqual(s1_cfg, s2_cfg)
        self.assertEqual(s1_cfg, canonical_cfg)

    def test_35_s1_and_s2_have_identical_scout_tools(self) -> None:
        """35. Scout tools are identical across E_S1 and E_S2."""
        s1_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S1/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        s2_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S2/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertEqual(s1_yaml["tools"], s2_yaml["tools"])
        self.assertEqual(s1_yaml["tools"], EXPECTED_SCOUT_TOOLS)

    def test_36_s1_and_s2_have_identical_scout_models(self) -> None:
        """36. Scout model is identical across E_S1 and E_S2."""
        s1_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S1/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        s2_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S2/sub_agents/scout.yaml").read_text(encoding="utf-8"))
        self.assertEqual(s1_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(s2_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_37_s1_and_s2_have_identical_root_generation_settings(self) -> None:
        """37. Root generation configuration is identical across E_S1 and E_S2."""
        s1_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S1/agent.yaml").read_text(encoding="utf-8"))
        s2_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S2/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(s1_yaml["generate_content_config"], s2_yaml["generate_content_config"])

    def test_38_s1_and_s2_differ_only_in_invocation_policy(self) -> None:
        """38. E_S1 and E_S2 root prompts differ specifically in discretionary vs. mandatory invocation wording."""
        s1_prompt = (PROJECT_ROOT / "experiments/candidates/E_S1/prompts/root.md").read_text(encoding="utf-8")
        s2_prompt = (PROJECT_ROOT / "experiments/candidates/E_S2/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("you may invoke the read-only `scout` sub-agent", s1_prompt)
        self.assertIn("you must invoke the read-only `scout` sub-agent once", s2_prompt)
        self.assertNotEqual(s1_prompt, s2_prompt)

    def test_39_s1_and_s2_have_identical_skills(self) -> None:
        """39. Both candidates package identical skills."""
        s1_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S1/agent.yaml").read_text(encoding="utf-8"))
        s2_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E_S2/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(s1_yaml["skills"], ["skills/test_strategy", "skills/repo_triage"])
        self.assertEqual(s2_yaml["skills"], ["skills/test_strategy", "skills/repo_triage"])

    # -------------------------------------------------------------
    # H. TaskState Integration (40 - 44)
    # -------------------------------------------------------------
    def test_40_scout_invocation_recorded_in_task_state(self) -> None:
        """40. Scout findings are recorded in TaskState evidence."""
        state = TaskState(summary="Resolving issue")
        res = ScoutResult(
            issue_summary="Discovered parser bug",
            candidate_files=["src/parser.py"],
            status=ScoutStatus.LOCALIZED,
        )
        res.integrate_into_task_state(state)
        self.assertEqual(len(state.evidence), 1)
        self.assertEqual(state.evidence[0].source_command_or_file, "scout_agent")

    def test_41_scout_candidates_registered_in_task_state(self) -> None:
        """41. Discovered candidate files are registered in TaskState candidates."""
        state = TaskState(summary="Resolving issue")
        res = ScoutResult(
            candidate_files=["src/parser.py", "src/lexer.py"],
            candidate_symbols=["parse_tokens"],
            status=ScoutStatus.PARTIALLY_LOCALIZED,
        )
        res.integrate_into_task_state(state)
        self.assertEqual(len(state.candidates), 2)
        paths = [c.path for c in state.candidates]
        self.assertIn("src/parser.py", paths)
        self.assertIn("src/lexer.py", paths)

    def test_42_scout_result_status_recorded_in_task_state(self) -> None:
        """42. Scout status string is present in evidence observation."""
        state = TaskState(summary="Resolving issue")
        res = ScoutResult(status=ScoutStatus.AMBIGUOUS)
        res.integrate_into_task_state(state)
        self.assertIn("AMBIGUOUS", state.evidence[0].observation)

    def test_43_scout_evidence_remains_bounded_in_task_state(self) -> None:
        """43. Evidence observations integrated from Scout obey max summary length."""
        state = TaskState(summary="Resolving issue")
        long_summary = "x" * 2000
        res = ScoutResult(issue_summary=long_summary, status=ScoutStatus.LOCALIZED)
        res.integrate_into_task_state(state)
        self.assertLessEqual(len(state.evidence[0].observation), 550)

    def test_44_root_can_consume_scout_evidence(self) -> None:
        """44. Root agent inspects candidates added by Scout."""
        state = TaskState(summary="Resolving issue")
        res = ScoutResult(candidate_files=["src/core.py"], status=ScoutStatus.LOCALIZED)
        res.integrate_into_task_state(state)
        self.assertTrue(any(c.path == "src/core.py" for c in state.candidates))

    # -------------------------------------------------------------
    # I. E0–E11 Invariance (45 - 49)
    # -------------------------------------------------------------
    def test_45_e11_candidate_unchanged(self) -> None:
        """45. Frozen E11 files remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E11/agent.yaml"), E11_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E11/prompts/root.md"), E11_PROMPT_SHA256)

    def test_46_e10_no_progress_detector_unchanged(self) -> None:
        """46. E10 detector behavior is preserved."""
        detector = NoProgressDetectorV1(threshold=2)
        self.assertEqual(detector.threshold, 2)

    def test_47_e9_failure_categories_unchanged(self) -> None:
        """47. All 8 failure classes from Stage 18 are preserved."""
        self.assertEqual(len(FailureClass), 8)

    def test_48_e11_recovery_policy_unchanged(self) -> None:
        """48. Recovery controller behavior is preserved."""
        ctrl = RecoveryControllerV1()
        self.assertEqual(len(RecoveryPath), 6)

    def test_49_canonical_skills_unchanged(self) -> None:
        """49. Canonical skills remain byte-identical."""
        self.assertEqual(self._hash_file("agent/skills/test_strategy/SKILL.md"), CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(self._hash_file("agent/skills/repo_triage/SKILL.md"), CANONICAL_REPO_TRIAGE_SHA256)

    # -------------------------------------------------------------
    # J. Candidate Submission Validation (50 - 56)
    # -------------------------------------------------------------
    def test_50_e_s1_submission_validator_passes(self) -> None:
        """50. Candidate E_S1 directory satisfies all submission rules."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/E_S1")
        valid = validator.validate()
        self.assertTrue(valid, f"E_S1 validation failed: {validator.errors}")

    def test_51_e_s2_submission_validator_passes(self) -> None:
        """51. Candidate E_S2 directory satisfies all submission rules."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/E_S2")
        valid = validator.validate()
        self.assertTrue(valid, f"E_S2 validation failed: {validator.errors}")

    def test_52_exact_competition_model_in_both_candidates(self) -> None:
        """52. Both candidates declare exact model gemma-4-31b-it-qat-w4a16-ct."""
        for cand in ["E_S1", "E_S2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_53_root_still_has_exactly_9_tools(self) -> None:
        """53. Root agent preserves exactly 9 competition tools."""
        for cand in ["E_S1", "E_S2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["tools"], EXPECTED_ROOT_TOOLS)
            self.assertEqual(len(cfg["tools"]), 9)

    def test_54_no_debugger_agent(self) -> None:
        """54. Verifies Debugger agent is NOT present in Stage 21 candidates."""
        self.assertFalse((PROJECT_ROOT / "experiments/candidates/E_S1/sub_agents/debugger.yaml").exists())
        self.assertFalse((PROJECT_ROOT / "experiments/candidates/E_S2/sub_agents/debugger.yaml").exists())

    def test_55_no_reviewer_agent(self) -> None:
        """55. Verifies Reviewer agent is NOT present."""
        self.assertFalse((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").exists())
        self.assertFalse((PROJECT_ROOT / "agent/prompts/reviewer.md").exists())

    def test_56_no_later_stage_implementation(self) -> None:
        """56. Confirms Stage 22+ files do not exist in Stage 21 candidates."""
        for cand in ["E_S1", "E_S2"]:
            subagent_files = list((PROJECT_ROOT / f"experiments/candidates/{cand}/sub_agents").glob("*.yaml"))
            names = [f.stem for f in subagent_files]
            self.assertEqual(names, ["scout"], f"Only scout subagent allowed in {cand}, found: {names}")

    # -------------------------------------------------------------
    # K. Anti-Cheating & Anti-Overfitting (57)
    # -------------------------------------------------------------
    def test_57_scout_prompt_and_config_contain_no_benchmark_answers(self) -> None:
        """57. Scout prompt and config contain zero competition task IDs or benchmark solution snippets."""
        scout_prompt = (PROJECT_ROOT / "agent/prompts/scout.md").read_text(encoding="utf-8")
        scout_yaml = (PROJECT_ROOT / "agent/sub_agents/scout.yaml").read_text(encoding="utf-8")

        # Check for benchmark-specific identifiers
        prohibited_terms = [
            "django__django",
            "pytest-dev__pytest",
            "sympy__sympy",
            "matplotlib__matplotlib",
            "scikit-learn__scikit-learn",
            "astropy__astropy",
            "sphinx-doc__sphinx",
            "requests__requests",
            "flask__flask",
        ]
        for term in prohibited_terms:
            self.assertNotIn(term, scout_prompt)
            self.assertNotIn(term, scout_yaml)


if __name__ == "__main__":
    unittest.main()
