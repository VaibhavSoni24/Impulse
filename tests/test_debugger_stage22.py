"""Unit and regression tests for Candidate D1/D2 and Debugger Agent (Stage 22).

Validates:
A. Debugger configuration
B. Read-only enforcement
C. Debugger output contract
D. Difficult-failure trigger
E. Invocation and loop prevention
F. Subsystem integration (E9, E10, E11, TaskState)
G. D1 vs D2 experimental isolation
H. Stage 21 invariance
I. Candidate submission validation and anti-overfitting
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.debugger import (
    DebuggerControllerV1,
    DebuggerPolicy,
    DebuggerResult,
    DebuggerStatus,
    DebuggerTriggerContext,
    evaluate_debugger_trigger,
    is_difficult_failure,
)
from local.failures import FailureClass
from local.progress import NoProgressReason, ProgressStatus
from local.recovery import RecoveryControllerV1, RecoveryPath, RecoveryState
from local.scout import ScoutResult, ScoutStatus
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes (E0–E11 & Stage 21)
E11_AGENT_SHA256 = "688e0269c966db0f7dd367735190dbd3fa193a69c73dc7b3d48eff63237da01a"
E11_PROMPT_SHA256 = "42a895fe99b5c537c348e92f02d7c906185b32afb450f393cf0e8255bd407356"
E_S1_AGENT_SHA256 = "40c9da2300c8f6ef53df72208defeacf74b84d4b727f0a6b795a433f26efcc53"
E_S1_PROMPT_SHA256 = "1f800d8c0709f1ba2fc3b9771f189c4163e0a292928ec2cbd7be3a26ada37277"
E_S2_AGENT_SHA256 = "d91eab2b640108945ff3c1eb3de6ecbc41522f566159a0a9405a88bd04d03876"
E_S2_PROMPT_SHA256 = "e0cc66e573c3e961630fc11add52f53370cfee67d3319196b21a21ddcb4e21cd"

CANONICAL_SCOUT_YAML_SHA256 = "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877"
CANONICAL_SCOUT_MD_SHA256 = "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805"
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

EXPECTED_READONLY_TOOLS = [
    "read_file",
    "get_status",
    "search_similar_code",
    "get_code_neighbors",
    "get_code_subgraph",
]


class TestDebuggerStage22(unittest.TestCase):
    """55+ verification tests for Stage 22 Candidates D1 / D2 and the Debugger agent."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # A. Configuration (1 - 5)
    # -------------------------------------------------------------
    def test_01_debugger_config_parses_under_harness_schema(self) -> None:
        """1. Debugger YAML configuration parses into a valid mapping."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/debugger.yaml"
        self.assertTrue(cfg_path.exists())
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("name"), "debugger")

    def test_02_debugger_uses_exact_competition_model(self) -> None:
        """2. Debugger declares the exact model gemma-4-31b-it-qat-w4a16-ct."""
        cfg_path = PROJECT_ROOT / "agent/sub_agents/debugger.yaml"
        parsed = parse_simple_yaml(cfg_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.get("model"), "gemma-4-31b-it-qat-w4a16-ct")

    def test_03_debugger_valid_sub_agent_declaration(self) -> None:
        """3. Candidate D2 declares debugger under sub_agents."""
        yaml_path = PROJECT_ROOT / "experiments/candidates/D2/agent.yaml"
        parsed = parse_simple_yaml(yaml_path.read_text(encoding="utf-8"))
        self.assertIn("sub_agents", parsed)
        sub_agents = parsed["sub_agents"]
        config_paths = [sa["config_path"] for sa in sub_agents if isinstance(sa, dict)]
        self.assertIn("sub_agents/debugger.yaml", config_paths)

    def test_04_debugger_prompt_exists_and_forbids_mutations(self) -> None:
        """4. Debugger prompt exists and explicitly enforces read-only behavior."""
        prompt_path = PROJECT_ROOT / "agent/prompts/debugger.md"
        self.assertTrue(prompt_path.exists())
        content = prompt_path.read_text(encoding="utf-8")
        self.assertIn("READ ONLY", content)
        self.assertIn("Do not modify any repository file", content)
        self.assertIn("Do not submit patches", content)

    def test_05_debugger_included_only_in_d2(self) -> None:
        """5. Candidate D1 does NOT configure Debugger; D2 does."""
        d1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D1/agent.yaml").read_text(encoding="utf-8"))
        d1_sub = [sa["config_path"] for sa in d1_cfg.get("sub_agents", [])]
        self.assertNotIn("sub_agents/debugger.yaml", d1_sub)

        d2_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D2/agent.yaml").read_text(encoding="utf-8"))
        d2_sub = [sa["config_path"] for sa in d2_cfg.get("sub_agents", [])]
        self.assertIn("sub_agents/debugger.yaml", d2_sub)

    # -------------------------------------------------------------
    # B. Read-Only Enforcement (6 - 10)
    # -------------------------------------------------------------
    def test_06_debugger_has_no_edit_file(self) -> None:
        """6. Debugger does not expose edit_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/debugger.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("edit_file", cfg.get("tools", []))

    def test_07_debugger_has_no_write_file(self) -> None:
        """7. Debugger does not expose write_file."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/debugger.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("write_file", cfg.get("tools", []))

    def test_08_debugger_has_no_submit_patch(self) -> None:
        """8. Debugger does not expose submit_patch."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/debugger.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("submit_patch", cfg.get("tools", []))

    def test_09_debugger_has_no_destructive_commands(self) -> None:
        """9. Debugger does not expose run_command (strictly read-only tools)."""
        cfg = parse_simple_yaml((PROJECT_ROOT / "agent/sub_agents/debugger.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("run_command", cfg.get("tools", []))
        self.assertEqual(cfg.get("tools"), EXPECTED_READONLY_TOOLS)

    def test_10_structured_result_cannot_mutate_repository_state(self) -> None:
        """10. DebuggerResult integration mutates only task_state evidence, not filesystem."""
        state = TaskState(summary="Initial test")
        result = DebuggerResult(
            status=DebuggerStatus.DIAGNOSED,
            failure_class="REGRESSION",
            failure_summary="Off by one error in parser",
            likely_cause_candidates=["src/parser.py"],
            observed_evidence=["IndexError at line 42"],
            next_inspection_targets=["src/parser.py"],
        )
        result.integrate_into_task_state(state)
        # Verify evidence recorded
        self.assertEqual(len(state.evidence), 1)
        candidate_paths = [c.path for c in state.candidates]
        self.assertIn("src/parser.py", candidate_paths)

    # -------------------------------------------------------------
    # C. Output Contract (11 - 19)
    # -------------------------------------------------------------
    def test_11_diagnosed_result(self) -> None:
        """11. Produces valid DIAGNOSED result."""
        res = DebuggerResult(status=DebuggerStatus.DIAGNOSED, failure_summary="Diagnosed cause")
        d = res.to_dict()
        self.assertEqual(d["status"], "DIAGNOSED")

    def test_12_partially_diagnosed_result(self) -> None:
        """12. Produces valid PARTIALLY_DIAGNOSED result."""
        res = DebuggerResult(status=DebuggerStatus.PARTIALLY_DIAGNOSED)
        self.assertEqual(res.to_dict()["status"], "PARTIALLY_DIAGNOSED")

    def test_13_ambiguous_result(self) -> None:
        """13. Produces valid AMBIGUOUS result."""
        res = DebuggerResult(status=DebuggerStatus.AMBIGUOUS)
        self.assertEqual(res.to_dict()["status"], "AMBIGUOUS")

    def test_14_insufficient_evidence_result(self) -> None:
        """14. Produces valid INSUFFICIENT_EVIDENCE result."""
        res = DebuggerResult(status=DebuggerStatus.INSUFFICIENT_EVIDENCE)
        self.assertEqual(res.to_dict()["status"], "INSUFFICIENT_EVIDENCE")

    def test_15_bounded_evidence(self) -> None:
        """15. Large evidence lists are bounded in to_dict()."""
        huge_evidence = [f"evidence item {i}" for i in range(100)]
        res = DebuggerResult(observed_evidence=huge_evidence)
        d = res.to_dict()
        self.assertLessEqual(len(d["observed_evidence"]), 20)

    def test_16_bounded_hypothesis_data(self) -> None:
        """16. String summaries are capped at MAX_SUMMARY_LEN."""
        long_str = "x" * 2000
        res = DebuggerResult(failure_summary=long_str, hypothesis_update=long_str)
        d = res.to_dict()
        self.assertLessEqual(len(d["failure_summary"]), 500)
        self.assertLessEqual(len(d["hypothesis_update"]), 500)

    def test_17_observation_inference_separation(self) -> None:
        """17. Output explicitly maintains separate fields for observed vs inferred findings."""
        res = DebuggerResult(
            observed_evidence=["AssertionError: expected 200 got 500"],
            inferred_mechanisms=["Database connection timeout during request handling"],
        )
        d = res.to_dict()
        self.assertEqual(len(d["observed_evidence"]), 1)
        self.assertEqual(len(d["inferred_mechanisms"]), 1)
        self.assertNotEqual(d["observed_evidence"], d["inferred_mechanisms"])

    def test_18_no_raw_logs(self) -> None:
        """18. format_summary does not dump raw logs or stack traces."""
        res = DebuggerResult(
            status=DebuggerStatus.DIAGNOSED,
            likely_cause_candidates=["src/core.py"],
            observed_evidence=["KeyError on line 10"],
        )
        summary = res.format_summary()
        self.assertIn("=== Debugger Diagnostic Result ===", summary)
        self.assertNotIn("Traceback (most recent call last):", summary)

    def test_19_no_secrets(self) -> None:
        """19. DebuggerResult does not include secret or credential fields."""
        res = DebuggerResult()
        d = res.to_dict()
        for key in ["token", "secret", "password", "api_key", "credential"]:
            self.assertNotIn(key, d)

    # -------------------------------------------------------------
    # D. Difficult-Failure Trigger (20 - 26)
    # -------------------------------------------------------------
    def test_20_ordinary_single_test_failure_does_not_trigger(self) -> None:
        """20. Single ordinary test failure with clear single fix does NOT trigger Debugger."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            has_clear_single_targeted_fix=True,
            initial_investigation_bounded=True,
        )
        triggered, reason = is_difficult_failure(ctx)
        self.assertFalse(triggered)
        self.assertIn("clear single fix", reason)

    def test_21_unknown_failure_class_triggers(self) -> None:
        """21. FailureClass.UNKNOWN triggers difficult failure."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            initial_investigation_bounded=True,
        )
        triggered, reason = is_difficult_failure(ctx)
        self.assertTrue(triggered)
        self.assertIn("UNKNOWN", reason)

    def test_22_wrong_hypothesis_triggers(self) -> None:
        """22. FailureClass.WRONG_HYPOTHESIS triggers difficult failure."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.WRONG_HYPOTHESIS.value,
            initial_investigation_bounded=True,
        )
        triggered, reason = is_difficult_failure(ctx)
        self.assertTrue(triggered)
        self.assertIn("WRONG_HYPOTHESIS", reason)

    def test_23_incomplete_fix_triggers(self) -> None:
        """23. FailureClass.INCOMPLETE_FIX triggers difficult failure."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.INCOMPLETE_FIX.value,
            initial_investigation_bounded=True,
        )
        triggered, reason = is_difficult_failure(ctx)
        self.assertTrue(triggered)
        self.assertIn("INCOMPLETE_FIX", reason)

    def test_24_repeated_failure_or_no_progress_triggers(self) -> None:
        """24. Repeated failures or no-progress signals trigger difficult failure."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            repeated_failure_count=2,
            initial_investigation_bounded=True,
        )
        triggered, reason = is_difficult_failure(ctx)
        self.assertTrue(triggered)
        self.assertIn("repeated failure", reason)

    def test_25_clear_localized_failure_does_not_trigger(self) -> None:
        """25. Passing tests or tests without bounded investigation do not trigger."""
        # Case A: Passed test
        ctx_pass = DebuggerTriggerContext(test_result="PASSED")
        trig_pass, _ = is_difficult_failure(ctx_pass)
        self.assertFalse(trig_pass)

        # Case B: Initial investigation not bounded
        ctx_unbounded = DebuggerTriggerContext(test_result="FAILED", initial_investigation_bounded=False)
        trig_unbounded, _ = is_difficult_failure(ctx_unbounded)
        self.assertFalse(trig_unbounded)

    def test_26_trigger_is_deterministic(self) -> None:
        """26. Identical context evaluated multiple times produces identical outcome."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            initial_investigation_bounded=True,
        )
        t1, r1 = is_difficult_failure(ctx)
        t2, r2 = is_difficult_failure(ctx)
        self.assertEqual(t1, t2)
        self.assertEqual(r1, r2)

    # -------------------------------------------------------------
    # E. Invocation & Loop Prevention (27 - 32)
    # -------------------------------------------------------------
    def test_27_one_debugger_call_max_per_episode(self) -> None:
        """27. Controller allows first invocation and blocks second for unchanged state."""
        ctrl = DebuggerControllerV1(policy=DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE)
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            repository_state_version=1,
            current_failure_signature="test_err_sig",
        )
        should_run_1, _ = ctrl.should_invoke(ctx)
        self.assertTrue(should_run_1)

        result = DebuggerResult(status=DebuggerStatus.DIAGNOSED)
        ctrl.record_result(ctx, result)

        # Second check under identical state
        should_run_2, reason_2 = ctrl.should_invoke(ctx)
        self.assertFalse(should_run_2)
        self.assertIn("loop prevention", reason_2)

    def test_28_unchanged_ambiguous_result_does_not_loop(self) -> None:
        """28. If Debugger reports AMBIGUOUS, repeat invocation is suppressed."""
        ctrl = DebuggerControllerV1(policy=DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE)
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            repository_state_version=1,
            current_failure_signature="sig_a",
        )
        ctrl.record_result(ctx, DebuggerResult(status=DebuggerStatus.AMBIGUOUS))
        should_run, reason = ctrl.should_invoke(ctx)
        self.assertFalse(should_run)
        self.assertIn("loop prevention", reason)

    def test_29_unchanged_insufficient_evidence_does_not_loop(self) -> None:
        """29. If Debugger reports INSUFFICIENT_EVIDENCE, repeat invocation is suppressed."""
        ctrl = DebuggerControllerV1(policy=DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE)
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            repository_state_version=1,
            current_failure_signature="sig_b",
        )
        ctrl.record_result(ctx, DebuggerResult(status=DebuggerStatus.INSUFFICIENT_EVIDENCE))
        should_run, reason = ctrl.should_invoke(ctx)
        self.assertFalse(should_run)
        self.assertIn("loop prevention", reason)

    def test_30_repo_state_change_establishes_new_episode(self) -> None:
        """30. Incrementing repository state version initiates a new episode."""
        ctrl = DebuggerControllerV1(policy=DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE)
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
            repository_state_version=1,
            current_failure_signature="sig_c",
        )
        ctrl.record_result(ctx, DebuggerResult(status=DebuggerStatus.AMBIGUOUS))

        # Modifying repository state increments version
        ctx.repository_state_version = 2
        should_run, _ = ctrl.should_invoke(ctx)
        self.assertTrue(should_run)

    def test_31_d1_has_no_debugger(self) -> None:
        """31. Under D1 policy UNAVAILABLE, evaluate_debugger_trigger returns False."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
        )
        can_run, reason = evaluate_debugger_trigger(ctx, policy=DebuggerPolicy.UNAVAILABLE)
        self.assertFalse(can_run)
        self.assertIn("Debugger unavailable", reason)

    def test_32_d2_has_debugger_available(self) -> None:
        """32. Under D2 policy AVAILABLE_ON_DIFFICULT_FAILURE, trigger succeeds."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.UNKNOWN.value,
        )
        can_run, reason = evaluate_debugger_trigger(ctx, policy=DebuggerPolicy.AVAILABLE_ON_DIFFICULT_FAILURE)
        self.assertTrue(can_run)
        self.assertIn("Debugger triggered", reason)

    # -------------------------------------------------------------
    # F. Subsystem Integration (33 - 37)
    # -------------------------------------------------------------
    def test_33_e9_failure_classification_consumed_without_modification(self) -> None:
        """33. Debugger models and trigger consume the exact 8 canonical FailureClass values."""
        for fc in FailureClass:
            ctx = DebuggerTriggerContext(test_result="FAILED", failure_class=fc.value)
            # Evaluate without crashing
            is_diff, _ = is_difficult_failure(ctx)
            self.assertIsInstance(is_diff, bool)

    def test_34_e10_no_progress_state_consumed_without_duplication(self) -> None:
        """34. Debugger consumes NoProgressReason and ProgressStatus directly."""
        ctx = DebuggerTriggerContext(
            test_result="FAILED",
            failure_class=FailureClass.REGRESSION.value,
            no_progress_signal=NoProgressReason.REPEATED_FAILURE.value,
        )
        is_diff, reason = is_difficult_failure(ctx)
        self.assertTrue(is_diff)
        self.assertIn("REPEATED_FAILURE", reason)

    def test_35_e11_recovery_remains_downstream(self) -> None:
        """35. E11 RecoveryController operates independently after Debugger records findings."""
        state = TaskState()
        debugger_res = DebuggerResult(
            status=DebuggerStatus.DIAGNOSED,
            failure_class=FailureClass.WRONG_HYPOTHESIS.value,
            hypothesis_update="Update hypothesis to check parser bounds",
        )
        debugger_res.integrate_into_task_state(state)

        recovery_ctrl = RecoveryControllerV1()
        from local.recovery.models import RecoveryContext
        rec_ctx = RecoveryContext(
            test_result="FAILED",
            failure_classification=FailureClass.WRONG_HYPOTHESIS.value,
        )
        decision = recovery_ctrl.route_recovery(rec_ctx)
        self.assertEqual(decision.selected_path, RecoveryPath.TEST_FAILURE)

    def test_36_debugger_cannot_perform_recovery_itself(self) -> None:
        """36. DebuggerResult does not expose recovery execution or workspace mutation methods."""
        res = DebuggerResult()
        self.assertFalse(hasattr(res, "execute_recovery"))
        self.assertFalse(hasattr(res, "rollback"))
        self.assertFalse(hasattr(res, "apply_edit"))

    def test_37_root_remains_authoritative_over_edits(self) -> None:
        """37. Root prompt explicitly notes that Debugger findings must be verified before editing."""
        d2_root = (PROJECT_ROOT / "experiments/candidates/D2/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("Do not treat Debugger conclusions as automatically proven", d2_root)

    # -------------------------------------------------------------
    # G. D1 vs D2 Isolation (38 - 45)
    # -------------------------------------------------------------
    def test_38_same_root_model(self) -> None:
        """38. Both candidates declare exact model gemma-4-31b-it-qat-w4a16-ct."""
        for cand in ["D1", "D2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_39_same_root_tools(self) -> None:
        """39. Both candidates provide the exact 9 competition tools to the Root agent."""
        for cand in ["D1", "D2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["tools"], EXPECTED_ROOT_TOOLS)

    def test_40_same_generation_settings(self) -> None:
        """40. Both candidates preserve identical root generation settings."""
        d1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D1/agent.yaml").read_text(encoding="utf-8"))
        d2_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D2/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(d1_cfg["generate_content_config"], d2_cfg["generate_content_config"])

    def test_41_same_scout_implementation(self) -> None:
        """41. Scout configuration and prompt in D1 and D2 match canonical Scout exactly."""
        for cand in ["D1", "D2"]:
            scout_yaml_hash = self._hash_file(f"experiments/candidates/{cand}/sub_agents/scout.yaml")
            scout_md_hash = self._hash_file(f"experiments/candidates/{cand}/prompts/scout.md")
            self.assertEqual(scout_yaml_hash, CANONICAL_SCOUT_YAML_SHA256)
            self.assertEqual(scout_md_hash, CANONICAL_SCOUT_MD_SHA256)

    def test_42_same_scout_tools(self) -> None:
        """42. Scout preserves exactly 5 read-only tools across candidates."""
        for cand in ["D1", "D2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/sub_agents/scout.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["tools"], EXPECTED_READONLY_TOOLS)

    def test_43_same_scout_model(self) -> None:
        """43. Scout uses gemma-4-31b-it-qat-w4a16-ct across both candidates."""
        for cand in ["D1", "D2"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{cand}/sub_agents/scout.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_44_same_skills(self) -> None:
        """44. Both candidates package identical canonical test_strategy and repo_triage skills."""
        for cand in ["D1", "D2"]:
            ts_hash = self._hash_file(f"experiments/candidates/{cand}/skills/test_strategy/SKILL.md")
            rt_hash = self._hash_file(f"experiments/candidates/{cand}/skills/repo_triage/SKILL.md")
            self.assertEqual(ts_hash, CANONICAL_TEST_STRATEGY_SHA256)
            self.assertEqual(rt_hash, CANONICAL_REPO_TRIAGE_SHA256)

    def test_45_only_debugger_availability_differs(self) -> None:
        """45. D1 configures only scout; D2 configures scout and debugger."""
        d1_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D1/agent.yaml").read_text(encoding="utf-8"))
        d2_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D2/agent.yaml").read_text(encoding="utf-8"))
        d1_subs = [sa["config_path"] for sa in d1_cfg["sub_agents"]]
        d2_subs = [sa["config_path"] for sa in d2_cfg["sub_agents"]]
        self.assertEqual(d1_subs, ["sub_agents/scout.yaml"])
        self.assertEqual(d2_subs, ["sub_agents/scout.yaml", "sub_agents/debugger.yaml"])

    # -------------------------------------------------------------
    # H. Stage 21 Invariance (46 - 48)
    # -------------------------------------------------------------
    def test_46_scout_canonical_artifacts_unchanged(self) -> None:
        """46. Canonical Scout artifacts in agent/ match Stage 21 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/scout.yaml"), CANONICAL_SCOUT_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/scout.md"), CANONICAL_SCOUT_MD_SHA256)

    def test_47_e_s1_e_s2_frozen_artifacts_unchanged(self) -> None:
        """47. Stage 21 candidate artifacts remain strictly unchanged."""
        self.assertEqual(self._hash_file("experiments/candidates/E_S1/agent.yaml"), E_S1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E_S1/prompts/root.md"), E_S1_PROMPT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E_S2/agent.yaml"), E_S2_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E_S2/prompts/root.md"), E_S2_PROMPT_SHA256)

    def test_48_canonical_skills_unchanged(self) -> None:
        """48. Canonical skill artifacts in agent/skills/ match frozen hashes."""
        self.assertEqual(self._hash_file("agent/skills/test_strategy/SKILL.md"), CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(self._hash_file("agent/skills/repo_triage/SKILL.md"), CANONICAL_REPO_TRIAGE_SHA256)

    # -------------------------------------------------------------
    # I. Candidate Validation & Anti-Overfitting (49 - 55)
    # -------------------------------------------------------------
    def test_49_d1_submission_validation_passes(self) -> None:
        """49. Candidate D1 passes submission validation."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/D1")
        valid = validator.validate()
        self.assertTrue(valid, f"D1 validation failed: {validator.errors}")

    def test_50_d2_submission_validation_passes(self) -> None:
        """50. Candidate D2 passes submission validation."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/D2")
        valid = validator.validate()
        self.assertTrue(valid, f"D2 validation failed: {validator.errors}")

    def test_51_d2_contains_exactly_one_new_specialist(self) -> None:
        """51. D2 sub_agents contains exactly scout and debugger."""
        d2_cfg = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/D2/agent.yaml").read_text(encoding="utf-8"))
        sub_paths = [sa["config_path"] for sa in d2_cfg["sub_agents"]]
        self.assertEqual(len(sub_paths), 2)
        self.assertIn("sub_agents/scout.yaml", sub_paths)
        self.assertIn("sub_agents/debugger.yaml", sub_paths)

    def test_52_no_reviewer_agent(self) -> None:
        """52. Confirms Reviewer agent is NOT present."""
        self.assertFalse((PROJECT_ROOT / "agent/sub_agents/reviewer.yaml").exists())
        self.assertFalse((PROJECT_ROOT / "agent/prompts/reviewer.md").exists())

    def test_53_no_later_stage_agents(self) -> None:
        """53. Only scout and debugger are present in agent/sub_agents/."""
        subagent_files = list((PROJECT_ROOT / "agent/sub_agents").glob("*.yaml"))
        names = sorted(f.stem for f in subagent_files)
        self.assertEqual(names, ["debugger", "scout"], f"Only scout and debugger allowed in Stage 22, found: {names}")

    def test_54_no_benchmark_specific_hardcoding(self) -> None:
        """54. Debugger prompt and config contain zero competition task IDs or benchmark solution snippets."""
        debugger_prompt = (PROJECT_ROOT / "agent/prompts/debugger.md").read_text(encoding="utf-8")
        debugger_yaml = (PROJECT_ROOT / "agent/sub_agents/debugger.yaml").read_text(encoding="utf-8")
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
            self.assertNotIn(term, debugger_prompt)
            self.assertNotIn(term, debugger_yaml)

    def test_55_e0_to_e11_invariance(self) -> None:
        """55. Baseline E11 agent and prompt remain strictly invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E11/agent.yaml"), E11_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E11/prompts/root.md"), E11_PROMPT_SHA256)


if __name__ == "__main__":
    unittest.main()
