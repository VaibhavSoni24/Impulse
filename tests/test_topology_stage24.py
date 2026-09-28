"""Unit and regression tests for Stage 24: Multi-Agent Topology Experiments.

Validates:
A. Topology matrix (1-8)
B. Candidate configuration & validator (9-14)
C. Model/tool consistency (15-19)
D. Specialist invariance (20-23)
E. Shared experiment controls (24-29)
F. Result schema & metrics (30-34)
G. Selection logic (35-39)
H. Security & hygiene (40-43)
I. Frozen invariance (44-54)
J. Anti-Confound Test (55)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from local.topology import (
    CANONICAL_TOPOLOGY_MATRIX,
    SelectionStatus,
    SpecialistName,
    TaskRunRecord,
    TopologyAggregateMetrics,
    TopologyDefinition,
    TopologyID,
    calculate_topology_metrics,
    evaluate_topology_selection,
    generate_topology_comparison_table,
    get_canonical_topology_matrix,
    get_topology_definition,
    validate_topology_composition,
)
from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Canonical Hashes
CANONICAL_SCOUT_YAML_SHA256 = "335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877"
CANONICAL_SCOUT_MD_SHA256 = "d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805"
CANONICAL_DEBUGGER_YAML_SHA256 = "07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199"
CANONICAL_DEBUGGER_MD_SHA256 = "a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f"
CANONICAL_REVIEWER_YAML_SHA256 = "facfcbb4fbc8d42a82f32a6979bf8b090de5857ba92b4641e4a45617b340200c"
CANONICAL_REVIEWER_MD_SHA256 = "d2432da56d07170989edbd83add7fe51323df1db6dd458b80f0d893cdb9264c6"
CANONICAL_TEST_STRATEGY_SHA256 = "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"
CANONICAL_REPO_TRIAGE_SHA256 = "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"

# Prior Candidate Hashes
E11_AGENT_SHA256 = "688e0269c966db0f7dd367735190dbd3fa193a69c73dc7b3d48eff63237da01a"
E11_PROMPT_SHA256 = "42a895fe99b5c537c348e92f02d7c906185b32afb450f393cf0e8255bd407356"
E_S1_AGENT_SHA256 = "40c9da2300c8f6ef53df72208defeacf74b84d4b727f0a6b795a433f26efcc53"
E_S1_PROMPT_SHA256 = "1f800d8c0709f1ba2fc3b9771f189c4163e0a292928ec2cbd7be3a26ada37277"
E_S2_AGENT_SHA256 = "d91eab2b640108945ff3c1eb3de6ecbc41522f566159a0a9405a88bd04d03876"
E_S2_PROMPT_SHA256 = "e0cc66e573c3e961630fc11add52f53370cfee67d3319196b21a21ddcb4e21cd"
D1_AGENT_SHA256 = "68cd2bafd0d4bde105273d62b888ebf651638ef619fea41c7b66a2a3706f236f"
D1_PROMPT_SHA256 = "c2242d13e97c944174921c261bffac7223077f27cd7692a7b40047a864660695"
D2_AGENT_SHA256 = "87694f1daad01a78b72e4b57766a49254f2284306df09076b6c573bd8ab90273"
D2_PROMPT_SHA256 = "1d2b329f94439c8b7f92cc21b00347c115f71b24444492afe79b7bc523f7fdb0"
V0_AGENT_SHA256 = "dbc19fe450687636bb2da1adfa65975b928a25f9345f3ebcf562292465673e36"
V0_PROMPT_SHA256 = "3aeecc3db73e07e699a76059dd847bca6fcf5d90145368b3fb9bf4a79fc2baca"
V1_AGENT_SHA256 = "a54f415753ee16311230296f3782b39b9abe19ffebcc83681093ebaeec39c35e"
V1_PROMPT_SHA256 = "fb875011407eab58e3e65ccfdbecc0e1d2c32b23e2faced41be578782670821e"

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


class TestTopologyStage24(unittest.TestCase):
    """Verification test suite for Stage 24 Multi-Agent Topology Experiments."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # A. Topology Matrix (1 - 8)
    # -------------------------------------------------------------
    def test_01_exactly_six_required_topologies_exist(self) -> None:
        """1. Matrix defines exactly six topologies: M0, M1, M2, M3, M4, M5."""
        matrix = get_canonical_topology_matrix()
        self.assertEqual(len(matrix), 6)
        self.assertEqual(set(matrix.keys()), {"M0", "M1", "M2", "M3", "M4", "M5"})

    def test_02_m0_has_no_specialists(self) -> None:
        """2. M0 is root-only and defines zero specialists."""
        m0 = get_topology_definition("M0")
        self.assertEqual(m0.specialists, ())
        self.assertEqual(m0.specialist_count, 0)

    def test_03_m1_has_scout_only(self) -> None:
        """3. M1 defines scout only."""
        m1 = get_topology_definition("M1")
        self.assertEqual(m1.specialists, ("scout",))
        self.assertEqual(m1.specialist_count, 1)

    def test_04_m2_has_debugger_only(self) -> None:
        """4. M2 defines debugger only."""
        m2 = get_topology_definition("M2")
        self.assertEqual(m2.specialists, ("debugger",))
        self.assertEqual(m2.specialist_count, 1)

    def test_05_m3_has_reviewer_only(self) -> None:
        """5. M3 defines reviewer only."""
        m3 = get_topology_definition("M3")
        self.assertEqual(m3.specialists, ("reviewer",))
        self.assertEqual(m3.specialist_count, 1)

    def test_06_m4_has_scout_and_debugger(self) -> None:
        """6. M4 defines scout and debugger."""
        m4 = get_topology_definition("M4")
        self.assertEqual(set(m4.specialists), {"scout", "debugger"})
        self.assertEqual(m4.specialist_count, 2)

    def test_07_m5_has_all_three_specialists(self) -> None:
        """7. M5 defines scout, debugger, and reviewer."""
        m5 = get_topology_definition("M5")
        self.assertEqual(set(m5.specialists), {"scout", "debugger", "reviewer"})
        self.assertEqual(m5.specialist_count, 3)

    def test_08_no_extra_specialists_exist_in_matrix(self) -> None:
        """8. No unexpected specialist names appear across the topology matrix."""
        allowed_specialists = {"scout", "debugger", "reviewer"}
        for tid, defn in get_canonical_topology_matrix().items():
            for spec in defn.specialists:
                self.assertIn(spec, allowed_specialists)

    # -------------------------------------------------------------
    # B. Candidate Configuration & Validator (9 - 14)
    # -------------------------------------------------------------
    def test_09_m0_validator_passes(self) -> None:
        """9. Candidate M0 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M0")
        self.assertTrue(validator.validate(), f"M0 validation failed: {validator.errors}")

    def test_10_m1_validator_passes(self) -> None:
        """10. Candidate M1 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M1")
        self.assertTrue(validator.validate(), f"M1 validation failed: {validator.errors}")

    def test_11_m2_validator_passes(self) -> None:
        """11. Candidate M2 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M2")
        self.assertTrue(validator.validate(), f"M2 validation failed: {validator.errors}")

    def test_12_m3_validator_passes(self) -> None:
        """12. Candidate M3 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M3")
        self.assertTrue(validator.validate(), f"M3 validation failed: {validator.errors}")

    def test_13_m4_validator_passes(self) -> None:
        """13. Candidate M4 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M4")
        self.assertTrue(validator.validate(), f"M4 validation failed: {validator.errors}")

    def test_14_m5_validator_passes(self) -> None:
        """14. Candidate M5 passes submission validator."""
        validator = SubmissionValidator(PROJECT_ROOT / "experiments/candidates/M5")
        self.assertTrue(validator.validate(), f"M5 validation failed: {validator.errors}")

    # -------------------------------------------------------------
    # C. Model / Tool Consistency (15 - 19)
    # -------------------------------------------------------------
    def test_15_exact_root_model_across_all_six(self) -> None:
        """15. All candidates M0–M5 declare the exact model gemma-4-31b-it-qat-w4a16-ct."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{tid}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_16_exact_specialist_model_where_present(self) -> None:
        """16. All declared specialists declare gemma-4-31b-it-qat-w4a16-ct."""
        for tid in ["M1", "M2", "M3", "M4", "M5"]:
            subagents_dir = PROJECT_ROOT / f"experiments/candidates/{tid}/sub_agents"
            for sa_file in subagents_dir.glob("*.yaml"):
                parsed = parse_simple_yaml(sa_file.read_text(encoding="utf-8"))
                self.assertEqual(parsed["model"], "gemma-4-31b-it-qat-w4a16-ct")

    def test_17_exactly_9_root_tools_across_all_six(self) -> None:
        """17. All candidates M0–M5 declare the exact 9 competition tools for Root."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{tid}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["tools"], EXPECTED_ROOT_TOOLS)

    def test_18_unchanged_root_generation_settings(self) -> None:
        """18. All candidates M0–M5 declare identical root sampling settings."""
        baseline_gen = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/M0/agent.yaml").read_text(encoding="utf-8"))["generate_content_config"]
        for tid in ["M1", "M2", "M3", "M4", "M5"]:
            gen = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{tid}/agent.yaml").read_text(encoding="utf-8"))["generate_content_config"]
            self.assertEqual(gen, baseline_gen)

    def test_19_same_skills_across_all_six(self) -> None:
        """19. All candidates M0–M5 declare test_strategy and repo_triage skills."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cfg = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{tid}/agent.yaml").read_text(encoding="utf-8"))
            self.assertEqual(cfg["skills"], ["skills/test_strategy", "skills/repo_triage"])

    # -------------------------------------------------------------
    # D. Specialist Invariance (20 - 23)
    # -------------------------------------------------------------
    def test_20_scout_artifact_identical_everywhere(self) -> None:
        """20. Scout config and prompt match canonical hashes in M1, M4, M5."""
        for tid in ["M1", "M4", "M5"]:
            yaml_hash = self._hash_file(f"experiments/candidates/{tid}/sub_agents/scout.yaml")
            md_hash = self._hash_file(f"experiments/candidates/{tid}/prompts/scout.md")
            self.assertEqual(yaml_hash, CANONICAL_SCOUT_YAML_SHA256)
            self.assertEqual(md_hash, CANONICAL_SCOUT_MD_SHA256)

    def test_21_debugger_artifact_identical_everywhere(self) -> None:
        """21. Debugger config and prompt match canonical hashes in M2, M4, M5."""
        for tid in ["M2", "M4", "M5"]:
            yaml_hash = self._hash_file(f"experiments/candidates/{tid}/sub_agents/debugger.yaml")
            md_hash = self._hash_file(f"experiments/candidates/{tid}/prompts/debugger.md")
            self.assertEqual(yaml_hash, CANONICAL_DEBUGGER_YAML_SHA256)
            self.assertEqual(md_hash, CANONICAL_DEBUGGER_MD_SHA256)

    def test_22_reviewer_artifact_identical_everywhere(self) -> None:
        """22. Reviewer config and prompt match canonical hashes in M3, M5."""
        for tid in ["M3", "M5"]:
            yaml_hash = self._hash_file(f"experiments/candidates/{tid}/sub_agents/reviewer.yaml")
            md_hash = self._hash_file(f"experiments/candidates/{tid}/prompts/reviewer.md")
            self.assertEqual(yaml_hash, CANONICAL_REVIEWER_YAML_SHA256)
            self.assertEqual(md_hash, CANONICAL_REVIEWER_MD_SHA256)

    def test_23_canonical_skills_identical_everywhere(self) -> None:
        """23. Skills in all candidate packages match canonical hashes."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            ts_hash = self._hash_file(f"experiments/candidates/{tid}/skills/test_strategy/SKILL.md")
            rt_hash = self._hash_file(f"experiments/candidates/{tid}/skills/repo_triage/SKILL.md")
            self.assertEqual(ts_hash, CANONICAL_TEST_STRATEGY_SHA256)
            self.assertEqual(rt_hash, CANONICAL_REPO_TRIAGE_SHA256)

    # -------------------------------------------------------------
    # E. Shared Experiment Controls (24 - 29)
    # -------------------------------------------------------------
    def test_24_identical_benchmark_references(self) -> None:
        """24. Stage 24 matrix points to uniform split references."""
        matrix_path = PROJECT_ROOT / "experiments/topology/stage24.json"
        self.assertTrue(matrix_path.exists())
        data = json.loads(matrix_path.read_text(encoding="utf-8"))
        protocol = data["benchmark_protocol"]
        self.assertEqual(protocol["dev_split_reference"], "benchmark/splits/dev.jsonl")
        self.assertEqual(protocol["validation_split_reference"], "benchmark/splits/validation.jsonl")
        self.assertEqual(protocol["held_out_split_reference"], "benchmark/splits/held_out.jsonl")

    def test_25_identical_timeout_policy(self) -> None:
        """25. Timeout ceiling is uniformly documented across candidates."""
        matrix_path = PROJECT_ROOT / "experiments/topology/stage24.json"
        data = json.loads(matrix_path.read_text(encoding="utf-8"))
        self.assertEqual(data["benchmark_protocol"]["timeout_per_task_seconds"], 900)

    def test_26_identical_evaluation_protocol(self) -> None:
        """26. Benchmark protocol requires clean repository snapshot."""
        matrix_path = PROJECT_ROOT / "experiments/topology/stage24.json"
        data = json.loads(matrix_path.read_text(encoding="utf-8"))
        self.assertEqual(data["benchmark_protocol"]["initial_environment"], "clean_repository_snapshot")

    def test_27_identical_root_prompt_across_m0_to_m5(self) -> None:
        """27. Single shared root prompt hash across all six candidates."""
        hashes = [self._hash_file(f"experiments/candidates/{tid}/prompts/root.md") for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]]
        self.assertEqual(len(set(hashes)), 1, f"Multiple root prompt hashes found: {hashes}")

    def test_28_no_topology_specific_prompt_hacks(self) -> None:
        """28. Root prompt is topology-neutral and contains no hardcoded candidate mentions."""
        prompt = (PROJECT_ROOT / "experiments/candidates/M0/prompts/root.md").read_text(encoding="utf-8")
        self.assertNotIn("IMPULSE-M0", prompt)
        self.assertNotIn("IMPULSE-M5", prompt)
        self.assertIn("Multi-Agent Topology Guidance", prompt)
        self.assertIn("Depending on the current candidate topology configuration", prompt)

    def test_29_identical_retrieval_recovery_test_policies(self) -> None:
        """29. Root prompt preserves E9, E10, E11, and hybrid localization identically."""
        prompt = (PROJECT_ROOT / "experiments/candidates/M0/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("Hybrid Localization Strategy", prompt)
        self.assertIn("Search Fallback", prompt)
        self.assertIn("Test-Failure Recovery", prompt)
        self.assertIn("Bad-Edit Recovery", prompt)
        self.assertIn("Tool-Failure Recovery", prompt)
        self.assertIn("Budget-Pressure Recovery", prompt)

    # -------------------------------------------------------------
    # F. Result Schema & Metrics (30 - 34)
    # -------------------------------------------------------------
    def test_30_valid_per_run_record(self) -> None:
        """30. TaskRunRecord serializes cleanly with all required fields."""
        rec = TaskRunRecord(
            topology_id="M4",
            task_id="task_123",
            success=True,
            elapsed_seconds=42.5,
            turns=8,
            tool_calls=12,
            root_turns=6,
            specialist_calls={"scout": 1, "debugger": 1},
            failure_class="REGRESSION",
            recovery_triggered=True,
            recovery_success=True,
        )
        d = rec.to_dict()
        self.assertEqual(d["topology_id"], "M4")
        self.assertEqual(d["specialist_calls"]["scout"], 1)
        self.assertTrue(d["recovery_success"])

    def test_31_valid_aggregate_record(self) -> None:
        """31. TopologyAggregateMetrics serializes cleanly."""
        metrics = TopologyAggregateMetrics(
            topology_id="M5",
            total_tasks=10,
            resolved_tasks=8,
            failed_tasks=2,
            pass_rate=0.8,
            avg_runtime_seconds=65.2,
            avg_turns=12.0,
            avg_tool_calls=18.4,
            avg_specialist_calls=2.4,
            total_specialist_calls=24,
            recovery_attempt_count=3,
            recovery_success_count=2,
            recovery_success_rate=0.6667,
            evidence_status="MEASURED",
        )
        d = metrics.to_dict()
        self.assertEqual(d["pass_rate"], 0.8)
        self.assertEqual(d["recovery_success_rate"], 0.6667)

    def test_32_missing_specialist_metrics_represented_consistently(self) -> None:
        """32. Empty records return unexecuted null metrics without crashing."""
        metrics = calculate_topology_metrics([], topology_id="M0")
        self.assertEqual(metrics.evidence_status, "UNEXECUTED")
        self.assertIsNone(metrics.pass_rate)
        self.assertIsNone(metrics.avg_runtime_seconds)

    def test_33_no_fabricated_values(self) -> None:
        """33. Summary report presents unexecuted candidates as null rather than zero or positive."""
        metrics_map = {
            "M0": TopologyAggregateMetrics(topology_id="M0", evidence_status="UNEXECUTED"),
            "M1": TopologyAggregateMetrics(topology_id="M1", evidence_status="UNEXECUTED"),
        }
        table = generate_topology_comparison_table(metrics_map)
        self.assertIn("`M0`", table)
        self.assertIn("null", table)
        self.assertNotIn("0.0%", table)

    def test_34_deterministic_aggregation(self) -> None:
        """34. calculate_topology_metrics deterministically computes averages and rates."""
        runs = [
            TaskRunRecord(topology_id="M1", task_id="t1", success=True, elapsed_seconds=10.0, turns=4, tool_calls=6, specialist_calls={"scout": 1}),
            TaskRunRecord(topology_id="M1", task_id="t2", success=False, elapsed_seconds=20.0, turns=6, tool_calls=8, specialist_calls={"scout": 1}, recovery_triggered=True, recovery_success=False),
        ]
        m = calculate_topology_metrics(runs)
        self.assertEqual(m.total_tasks, 2)
        self.assertEqual(m.resolved_tasks, 1)
        self.assertEqual(m.pass_rate, 0.5)
        self.assertEqual(m.avg_runtime_seconds, 15.0)
        self.assertEqual(m.avg_turns, 5.0)
        self.assertEqual(m.avg_tool_calls, 7.0)
        self.assertEqual(m.avg_specialist_calls, 1.0)
        self.assertEqual(m.recovery_success_rate, 0.0)

    # -------------------------------------------------------------
    # G. Selection Logic (35 - 39)
    # -------------------------------------------------------------
    def test_35_no_winner_with_missing_benchmark_data(self) -> None:
        """35. evaluate_topology_selection returns UNRESOLVED when metrics are unasserted."""
        status, reason, winner = evaluate_topology_selection({})
        self.assertEqual(status, SelectionStatus.UNRESOLVED)
        self.assertIsNone(winner)
        self.assertIn("No empirical benchmark results available", reason)

    def test_36_unresolved_selection_state_supported(self) -> None:
        """36. If held-out confirmation is missing, selection status is UNRESOLVED."""
        dummy_metrics = {
            "M0": TopologyAggregateMetrics(topology_id="M0", pass_rate=0.5, evidence_status="MEASURED"),
            "M1": TopologyAggregateMetrics(topology_id="M1", pass_rate=0.6, evidence_status="MEASURED"),
        }
        status, reason, winner = evaluate_topology_selection(dummy_metrics, has_held_out_evidence=False)
        self.assertEqual(status, SelectionStatus.UNRESOLVED)
        self.assertIsNone(winner)
        self.assertIn("held-out evaluation evidence is absent", reason)

    def test_37_fewer_specialists_preferred_when_comparable(self) -> None:
        """37. When outcomes are within tolerance, smaller topology (fewer specialists) is selected."""
        # M0 (0 specialists): 0.70; M5 (3 specialists): 0.72 (within 5% tolerance)
        dummy_metrics = {
            "M0": TopologyAggregateMetrics(topology_id="M0", pass_rate=0.70, evidence_status="MEASURED"),
            "M5": TopologyAggregateMetrics(topology_id="M5", pass_rate=0.72, evidence_status="MEASURED"),
        }
        status, reason, winner = evaluate_topology_selection(dummy_metrics, has_held_out_evidence=True, min_pass_rate_improvement=0.05)
        self.assertEqual(status, SelectionStatus.SELECTED)
        self.assertEqual(winner, "M0")
        self.assertIn("smallest topology", reason)

    def test_38_held_out_evidence_required_before_promotion(self) -> None:
        """38. True promotion requires has_held_out_evidence=True."""
        dummy_metrics = {
            "M0": TopologyAggregateMetrics(topology_id="M0", pass_rate=0.60, evidence_status="MEASURED"),
            "M1": TopologyAggregateMetrics(topology_id="M1", pass_rate=0.80, evidence_status="MEASURED"),
        }
        status_no, _, winner_no = evaluate_topology_selection(dummy_metrics, has_held_out_evidence=False)
        self.assertEqual(status_no, SelectionStatus.UNRESOLVED)
        self.assertIsNone(winner_no)

        status_yes, _, winner_yes = evaluate_topology_selection(dummy_metrics, has_held_out_evidence=True)
        self.assertEqual(status_yes, SelectionStatus.SELECTED)
        self.assertEqual(winner_yes, "M1")

    def test_39_selection_does_not_rely_on_arbitrary_ranking_without_evidence(self) -> None:
        """39. Selection does not promote M5 purely because it contains all specialists."""
        dummy_metrics = {
            "M0": TopologyAggregateMetrics(topology_id="M0", pass_rate=0.75, evidence_status="MEASURED"),
            "M5": TopologyAggregateMetrics(topology_id="M5", pass_rate=0.75, evidence_status="MEASURED"),
        }
        status, _, winner = evaluate_topology_selection(dummy_metrics, has_held_out_evidence=True)
        self.assertEqual(status, SelectionStatus.SELECTED)
        self.assertEqual(winner, "M0")

    # -------------------------------------------------------------
    # H. Security / Hygiene (40 - 43)
    # -------------------------------------------------------------
    def test_40_no_secrets_in_candidate_packages(self) -> None:
        """40. Zero credentials, private keys, or API tokens in candidate files."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand_dir = PROJECT_ROOT / f"experiments/candidates/{tid}"
            for p in cand_dir.rglob("*"):
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    self.assertNotIn("ghp_", content)
                    self.assertNotIn("AKIA", content)
                    self.assertNotIn("BEGIN RSA PRIVATE KEY", content)

    def test_41_no_benchmark_specific_hardcoded_solutions(self) -> None:
        """41. Zero competition task IDs or benchmark solution fragments in candidates."""
        prohibited = [
            "django__django", "pytest-dev__pytest", "sympy__sympy",
            "matplotlib__matplotlib", "scikit-learn__scikit-learn",
            "astropy__astropy", "sphinx-doc__sphinx", "requests__requests",
        ]
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            prompt = (PROJECT_ROOT / f"experiments/candidates/{tid}/prompts/root.md").read_text(encoding="utf-8")
            for term in prohibited:
                self.assertNotIn(term, prompt)

    def test_42_no_temporary_files_in_candidate_packages(self) -> None:
        """42. No temporary scripts, scratch files, or test outputs in candidate directories."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand_dir = PROJECT_ROOT / f"experiments/candidates/{tid}"
            for p in cand_dir.rglob("*"):
                self.assertNotIn(p.suffix, [".pyc", ".tmp", ".bak", ".log"])
                self.assertFalse(p.name.startswith("temp"))
                self.assertFalse(p.name.startswith("scratch"))

    def test_43_no_generated_logs_in_submission_candidates(self) -> None:
        """43. Candidates contain no log directories."""
        for tid in ["M0", "M1", "M2", "M3", "M4", "M5"]:
            cand_dir = PROJECT_ROOT / f"experiments/candidates/{tid}"
            log_dirs = list(cand_dir.glob("**/logs"))
            self.assertEqual(len(log_dirs), 0)

    # -------------------------------------------------------------
    # I. Frozen Invariance (44 - 54)
    # -------------------------------------------------------------
    def test_44_e11_unchanged(self) -> None:
        """44. Baseline E11 agent config and prompt match frozen hashes."""
        self.assertEqual(self._hash_file("experiments/candidates/E11/agent.yaml"), E11_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E11/prompts/root.md"), E11_PROMPT_SHA256)

    def test_45_scout_canonical_unchanged(self) -> None:
        """45. Canonical Scout artifacts in agent/ match frozen Stage 21 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/scout.yaml"), CANONICAL_SCOUT_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/scout.md"), CANONICAL_SCOUT_MD_SHA256)

    def test_46_debugger_canonical_unchanged(self) -> None:
        """46. Canonical Debugger artifacts in agent/ match frozen Stage 22 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/debugger.yaml"), CANONICAL_DEBUGGER_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/debugger.md"), CANONICAL_DEBUGGER_MD_SHA256)

    def test_47_reviewer_canonical_unchanged(self) -> None:
        """47. Canonical Reviewer artifacts in agent/ match frozen Stage 23 hashes."""
        self.assertEqual(self._hash_file("agent/sub_agents/reviewer.yaml"), CANONICAL_REVIEWER_YAML_SHA256)
        self.assertEqual(self._hash_file("agent/prompts/reviewer.md"), CANONICAL_REVIEWER_MD_SHA256)

    def test_48_e_s1_unchanged(self) -> None:
        """48. Stage 21 Candidate E_S1 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E_S1/agent.yaml"), E_S1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E_S1/prompts/root.md"), E_S1_PROMPT_SHA256)

    def test_49_e_s2_unchanged(self) -> None:
        """49. Stage 21 Candidate E_S2 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/E_S2/agent.yaml"), E_S2_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/E_S2/prompts/root.md"), E_S2_PROMPT_SHA256)

    def test_50_d1_unchanged(self) -> None:
        """50. Stage 22 Candidate D1 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/D1/agent.yaml"), D1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/D1/prompts/root.md"), D1_PROMPT_SHA256)

    def test_51_d2_unchanged(self) -> None:
        """51. Stage 22 Candidate D2 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/D2/agent.yaml"), D2_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/D2/prompts/root.md"), D2_PROMPT_SHA256)

    def test_52_v0_unchanged(self) -> None:
        """52. Stage 23 Candidate V0 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/V0/agent.yaml"), V0_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/V0/prompts/root.md"), V0_PROMPT_SHA256)

    def test_53_v1_unchanged(self) -> None:
        """53. Stage 23 Candidate V1 remains invariant."""
        self.assertEqual(self._hash_file("experiments/candidates/V1/agent.yaml"), V1_AGENT_SHA256)
        self.assertEqual(self._hash_file("experiments/candidates/V1/prompts/root.md"), V1_PROMPT_SHA256)

    def test_54_canonical_skills_unchanged(self) -> None:
        """54. Canonical skill artifacts in agent/skills/ match frozen hashes."""
        self.assertEqual(self._hash_file("agent/skills/test_strategy/SKILL.md"), CANONICAL_TEST_STRATEGY_SHA256)
        self.assertEqual(self._hash_file("agent/skills/repo_triage/SKILL.md"), CANONICAL_REPO_TRIAGE_SHA256)

    # -------------------------------------------------------------
    # J. Anti-Confound Test (55)
    # -------------------------------------------------------------
    def test_55_anti_confound_proving_only_specialist_availability_differs(self) -> None:
        """55. Explicit anti-confound test: confirms only specialist availability varies across M0–M5."""
        candidates = ["M0", "M1", "M2", "M3", "M4", "M5"]

        # 1. Root prompt hash must be identical across all candidates
        prompt_hashes = [self._hash_file(f"experiments/candidates/{c}/prompts/root.md") for c in candidates]
        self.assertEqual(len(set(prompt_hashes)), 1, "Confound detected: root prompts diverge across candidates!")

        # 2. Base model must be identical across all candidates
        models = [parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{c}/agent.yaml").read_text(encoding="utf-8"))["model"] for c in candidates]
        self.assertEqual(set(models), {"gemma-4-31b-it-qat-w4a16-ct"}, "Confound detected: model differs!")

        # 3. Generation config must be identical across all candidates
        gen_configs = [parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{c}/agent.yaml").read_text(encoding="utf-8"))["generate_content_config"] for c in candidates]
        self.assertEqual(len(set(json.dumps(gc, sort_keys=True) for gc in gen_configs)), 1, "Confound detected: generation config differs!")

        # 4. Root tools must be identical across all candidates
        tools_list = [parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{c}/agent.yaml").read_text(encoding="utf-8"))["tools"] for c in candidates]
        for tl in tools_list:
            self.assertEqual(tl, EXPECTED_ROOT_TOOLS, "Confound detected: root tools differ!")

        # 5. Skills must be identical across all candidates
        skills_list = [parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{c}/agent.yaml").read_text(encoding="utf-8"))["skills"] for c in candidates]
        for sl in skills_list:
            self.assertEqual(sl, ["skills/test_strategy", "skills/repo_triage"], "Confound detected: declared skills differ!")

        # 6. Specialist sub-agents must strictly match canonical matrix
        for c in candidates:
            parsed = parse_simple_yaml((PROJECT_ROOT / f"experiments/candidates/{c}/agent.yaml").read_text(encoding="utf-8"))
            sub_agents = parsed.get("sub_agents", [])
            sub_paths = [sa["config_path"] for sa in sub_agents if isinstance(sa, dict)]
            valid, msg = validate_topology_composition(c, sub_paths)
            self.assertTrue(valid, f"Anti-confound failure for {c}: {msg}")


if __name__ == "__main__":
    unittest.main()
