"""Unit and regression tests for Candidate E6 and Hybrid Localization Policy (Stage 15)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.validate_submission import SubmissionValidator, parse_simple_yaml

from local.graph.controller import NeighborPolicyV1
from local.graph.models import CodeNeighborsResponse
from local.retrieval.controller import RetrievalPolicyV1
from local.retrieval.hybrid_controller import (
    DEFAULT_MAX_CONSECUTIVE_REPEATS,
    DEFAULT_MAX_NEIGHBOR_CALLS,
    DEFAULT_MAX_SEMANTIC_CALLS,
    DEFAULT_MAX_SUBGRAPH_CALLS,
    DEFAULT_MAX_TOTAL_RETRIEVAL_CALLS,
    HybridLocalizationPolicy,
)
from local.retrieval.hybrid_models import (
    DecisionState,
    HybridDecisionRecord,
    HybridReconContext,
    LocalizationAction,
)
from local.retrieval.models import (
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from local.subgraph.controller import SubgraphPolicyV1
from local.subgraph.models import (
    CodeSubgraphResponse,
    SubgraphEdge,
)
from local.task_state.models import TaskState

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Frozen Reference Hashes
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

EXPECTED_E6_TOOLS = [
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


class TestHybridLocalizationE6(unittest.TestCase):
    """30+ focused verification tests for Stage 15 / Candidate E6."""

    def _hash_file(self, rel_path: str) -> str:
        content = (PROJECT_ROOT / rel_path).read_bytes()
        return hashlib.sha256(content).hexdigest()

    # -------------------------------------------------------------
    # 1-4: Submission Validation & Parity with E5
    # -------------------------------------------------------------
    def test_01_e6_submission_configuration_passes_validation(self) -> None:
        """1. E6 candidate directory satisfies all submission rules."""
        e6_dir = PROJECT_ROOT / "experiments" / "candidates" / "E6"
        validator = SubmissionValidator(e6_dir)
        valid = validator.validate()
        self.assertTrue(valid, f"E6 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    def test_02_e6_preserves_e5_model(self) -> None:
        """2. E6 preserves the exact model gemma-4-31b-it-qat-w4a16-ct."""
        e6_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E6/agent.yaml").read_text(encoding="utf-8"))
        e5_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E5/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e6_yaml["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e6_yaml["model"], e5_yaml["model"])

    def test_03_e6_preserves_e5_generation_settings(self) -> None:
        """3. E6 preserves identical sampling configuration."""
        e6_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E6/agent.yaml").read_text(encoding="utf-8"))
        e5_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E5/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e6_yaml["generate_content_config"], e5_yaml["generate_content_config"])

    def test_04_e6_preserves_all_9_e5_tools(self) -> None:
        """4. E6 preserves all 9 competition tools without additions or removals."""
        e6_yaml = parse_simple_yaml((PROJECT_ROOT / "experiments/candidates/E6/agent.yaml").read_text(encoding="utf-8"))
        self.assertEqual(e6_yaml["tools"], EXPECTED_E6_TOOLS)
        self.assertEqual(len(e6_yaml["tools"]), 9)

    # -------------------------------------------------------------
    # 5-10: Invariance of Prior Candidates (E0–E5)
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

    # -------------------------------------------------------------
    # 11-20: Hybrid Policy Routing & Decision Invariants
    # -------------------------------------------------------------
    def test_11_exact_strong_candidate_does_not_trigger_semantic_retrieval(self) -> None:
        """11. Exact strong match progresses directly to source inspection without semantic search."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            exact_matches_found=1,
            has_subsystem_ambiguity=False,
            exact_terms_mismatch=False,
            text_search_weak=False,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.INSPECT_SOURCE)
        self.assertEqual(decision.state, DecisionState.EXACT_STRONG)
        self.assertEqual(policy.semantic_call_count, 0)

    def test_12_exact_ambiguity_triggers_semantic_retrieval(self) -> None:
        """12. Exact search ambiguity triggers semantic retrieval."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            exact_matches_found=3,
            has_subsystem_ambiguity=True,
            exact_terms_mismatch=False,
            text_search_weak=False,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.SEMANTIC_SEARCH)
        self.assertEqual(decision.state, DecisionState.EXACT_AMBIGUOUS)

    def test_13_strong_semantic_result_progresses_to_source_inspection_without_auto_neighbors(self) -> None:
        """13. Identifying a promising symbol leads to source inspection first, not auto-neighbors."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            promising_symbol="requests.models.PreparedRequest",
            inspected_symbols=set(),  # Not yet inspected in source
            needs_relationship_exploration=True,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.INSPECT_SOURCE)
        self.assertEqual(decision.state, DecisionState.PROMISING_SYMBOL_FOUND)

    def test_14_neighbor_retrieval_requires_an_established_promising_symbol(self) -> None:
        """14. Neighbor retrieval requires an established, inspected promising symbol."""
        policy = HybridLocalizationPolicy()
        # Case A: No promising symbol
        context_no_symbol = HybridReconContext(
            promising_symbol=None,
            needs_relationship_exploration=True,
            candidate_symbols=[],
        )
        decision_a = policy.choose_next_localization_action(context_no_symbol)
        self.assertNotEqual(decision_a.action, LocalizationAction.GRAPH_NEIGHBORS)

        # Case B: Promising symbol established and inspected
        context_with_symbol = HybridReconContext(
            promising_symbol="requests.sessions.Session",
            inspected_symbols={"requests.sessions.Session"},
            needs_relationship_exploration=True,
            direct_source_sufficient=False,
        )
        decision_b = policy.choose_next_localization_action(context_with_symbol)
        self.assertEqual(decision_b.action, LocalizationAction.GRAPH_NEIGHBORS)
        self.assertEqual(decision_b.state, DecisionState.RELATIONSHIP_NEEDED)

    def test_15_neighbor_retrieval_is_skipped_when_source_evidence_is_sufficient(self) -> None:
        """15. Neighbor retrieval is bypassed once direct source evidence explains the defect."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            promising_symbol="requests.sessions.Session",
            inspected_symbols={"requests.sessions.Session"},
            needs_relationship_exploration=True,
            direct_source_sufficient=True,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.STOP_RETRIEVAL)
        self.assertEqual(decision.state, DecisionState.SOURCE_SUFFICIENT)

    def test_16_subgraph_retrieval_requires_multiple_relevant_symbols(self) -> None:
        """16. Subgraph retrieval requires >= 2 pre-identified and inspected candidate symbols."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            candidate_symbols=["requests.models.Request", "requests.adapters.HTTPAdapter"],
            inspected_symbols={"requests.models.Request", "requests.adapters.HTTPAdapter"},
            spans_multiple_symbols=True,
            direct_source_sufficient=False,
            single_neighbor_sufficient=False,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.SUBGRAPH)
        self.assertEqual(decision.state, DecisionState.MULTI_SYMBOL_INTERACTION)

    def test_17_subgraph_retrieval_does_not_occur_for_a_single_candidate(self) -> None:
        """17. Subgraph retrieval is strictly blocked when only 1 candidate symbol exists."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            candidate_symbols=["requests.models.Request"],
            inspected_symbols={"requests.models.Request"},
            promising_symbol="requests.models.Request",
            spans_multiple_symbols=True,
            direct_source_sufficient=False,
            needs_relationship_exploration=True,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertNotEqual(decision.action, LocalizationAction.SUBGRAPH)
        # Should route to 1-hop graph neighbors instead
        self.assertEqual(decision.action, LocalizationAction.GRAPH_NEIGHBORS)

    def test_18_subgraph_retrieval_does_not_occur_when_neighbor_inspection_is_sufficient(self) -> None:
        """18. Subgraph retrieval is skipped if single-node neighbor inspection is sufficient."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            candidate_symbols=["requests.models.Request", "requests.adapters.HTTPAdapter"],
            inspected_symbols={"requests.models.Request", "requests.adapters.HTTPAdapter"},
            spans_multiple_symbols=True,
            single_neighbor_sufficient=True,
            promising_symbol="requests.models.Request",
            needs_relationship_exploration=True,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertNotEqual(decision.action, LocalizationAction.SUBGRAPH)
        # Bypassed to graph neighbors or source
        self.assertEqual(decision.action, LocalizationAction.GRAPH_NEIGHBORS)

    def test_19_retrieval_is_disabled_during_non_localization_phases(self) -> None:
        """19. Retrieval tools are strictly disabled during edit, verify, and review phases."""
        policy = HybridLocalizationPolicy()
        for non_loc_phase in ("edit", "verify", "review"):
            context = HybridReconContext(
                phase=non_loc_phase,
                exact_matches_found=0,
                has_subsystem_ambiguity=True,
                promising_symbol="foo",
                needs_relationship_exploration=True,
            )
            decision = policy.choose_next_localization_action(context)
            self.assertEqual(decision.action, LocalizationAction.STOP_RETRIEVAL)
            self.assertEqual(decision.state, DecisionState.NON_LOCALIZATION_PHASE)

    def test_20_consecutive_redundant_retrieval_actions_are_blocked(self) -> None:
        """20. Anti-loop safeguard blocks consecutive identical retrieval operations."""
        policy = HybridLocalizationPolicy(max_consecutive_repeats=1)
        context = HybridReconContext(
            exact_matches_found=0,
            has_subsystem_ambiguity=True,
        )
        # First call: triggers semantic search
        dec1 = policy.choose_next_localization_action(context)
        self.assertEqual(dec1.action, LocalizationAction.SEMANTIC_SEARCH)
        policy.record_semantic_call()

        # Second call with same context: consecutive repeat blocked
        dec2 = policy.choose_next_localization_action(context)
        self.assertEqual(dec2.action, LocalizationAction.STOP_RETRIEVAL)
        self.assertEqual(dec2.state, DecisionState.RETRIEVAL_BUDGET_EXHAUSTED)

    # -------------------------------------------------------------
    # 21-30: Safeguards, Composition, Hygiene & Limits
    # -------------------------------------------------------------
    def test_21_retrieval_loop_terminates(self) -> None:
        """21. An unguided agent loop deterministically terminates at STOP_RETRIEVAL."""
        policy = HybridLocalizationPolicy(max_total_calls=4)
        context = HybridReconContext(has_subsystem_ambiguity=True)

        for _ in range(10):
            dec = policy.choose_next_localization_action(context)
            if dec.action == LocalizationAction.STOP_RETRIEVAL:
                break
            if dec.action == LocalizationAction.SEMANTIC_SEARCH:
                policy.record_semantic_call()
            elif dec.action == LocalizationAction.GRAPH_NEIGHBORS:
                policy.record_neighbor_call()
            elif dec.action == LocalizationAction.SUBGRAPH:
                policy.record_subgraph_call()

        self.assertTrue(policy.is_converged or policy.decision_history[-1].action == LocalizationAction.STOP_RETRIEVAL)

    def test_22_retrieval_budget_counter_state_is_bounded(self) -> None:
        """22. Controller enforces maximum call counts across all retrieval categories."""
        policy = HybridLocalizationPolicy(
            max_semantic_calls=2,
            max_neighbor_calls=2,
            max_subgraph_calls=1,
            max_total_calls=5,
        )
        self.assertEqual(policy.max_semantic_calls, 2)
        self.assertEqual(policy.max_neighbor_calls, 2)
        self.assertEqual(policy.max_subgraph_calls, 1)
        self.assertEqual(policy.max_total_calls, 5)

        # Fill semantic budget
        policy.record_semantic_call()
        policy.record_semantic_call()
        self.assertEqual(policy.semantic_call_count, 2)
        self.assertEqual(policy.total_call_count, 2)

        # Attempt further semantic search
        context = HybridReconContext(has_subsystem_ambiguity=True)
        dec = policy.choose_next_localization_action(context)
        self.assertNotEqual(dec.action, LocalizationAction.SEMANTIC_SEARCH)

    def test_23_hybrid_controller_composes_specialized_policies(self) -> None:
        """23. Hybrid controller composes and validates with E3, E4, E5 policies."""
        custom_semantic = RetrievalPolicyV1(initial_k=3, similarity_threshold=0.6)
        custom_neighbor = NeighborPolicyV1(max_retained=3)
        custom_subgraph = SubgraphPolicyV1(default_breadth_k=2)

        hybrid = HybridLocalizationPolicy(
            semantic_policy=custom_semantic,
            neighbor_policy=custom_neighbor,
            subgraph_policy=custom_subgraph,
        )

        self.assertIs(hybrid.semantic_policy, custom_semantic)
        self.assertIs(hybrid.neighbor_policy, custom_neighbor)
        self.assertIs(hybrid.subgraph_policy, custom_subgraph)

    def test_24_task_state_remains_bounded(self) -> None:
        """24. Integrating hybrid results into TaskState respects bounded capacity."""
        policy = HybridLocalizationPolicy()
        state = TaskState()

        # Integrate semantic results
        sem_resp = SemanticSearchResponse(
            status="ok",
            query="http_client",
            results=[
                SemanticSearchResultItem(node_name=f"node_{i}", similarity=0.9 - (i * 0.05))
                for i in range(10)
            ],
        )
        policy.integrate_semantic_results(sem_resp, state)

        # Integrate neighbor results
        nbr_resp = CodeNeighborsResponse(
            status="ok",
            node="node_0",
            neighbors=[f"neighbor_{i}" for i in range(10)],
        )
        policy.integrate_neighbor_results(nbr_resp, state)

        # Integrate subgraph results
        sub_resp = CodeSubgraphResponse(
            status="ok",
            nodes=["node_0", "neighbor_0"],
            edges=[SubgraphEdge(from_node="node_0", to_node="neighbor_0", edge_type="CALLS")],
        )
        policy.integrate_subgraph_results(sub_resp, state, seed_nodes=["node_0", "neighbor_0"])

        state.validate()
        self.assertLessEqual(len(state.candidates), 50)
        self.assertLessEqual(len(state.evidence), 50)

    def test_25_no_raw_graph_or_subgraph_payload_copied_into_hybrid_state(self) -> None:
        """25. TaskState and decision records store zero raw serialized adjacency structures."""
        policy = HybridLocalizationPolicy()
        state = TaskState()

        sub_resp = CodeSubgraphResponse(
            status="ok",
            nodes=["seed_a", "seed_b", "extra_c"],
            edges=[SubgraphEdge(from_node="seed_a", to_node="seed_b", edge_type="CALLS")],
        )
        policy.integrate_subgraph_results(sub_resp, state, seed_nodes=["seed_a", "seed_b"])

        # Check TaskState serialized JSON does not contain raw dict dumps of edge objects
        state_json = state.to_json()
        self.assertNotIn('"edge_count":', state_json)
        self.assertNotIn('"node_count":', state_json)

    def test_26_decision_records_are_concise_and_deterministic(self) -> None:
        """26. HybridDecisionRecord serializes deterministically to JSON."""
        record = HybridDecisionRecord(
            action=LocalizationAction.EXACT_SEARCH,
            state=DecisionState.EXACT_STRONG,
            reason="Unambiguous exact match identified.",
            candidate_count=1,
            inspected_candidate_count=0,
            evidence_sufficient=False,
            previous_action=None,
            semantic_calls=0,
            neighbor_calls=0,
            subgraph_calls=0,
            total_calls=0,
        )
        d = record.to_dict()
        self.assertEqual(d["action"], "EXACT_SEARCH")
        self.assertEqual(d["state"], "EXACT_STRONG")
        self.assertIn("timestamp", d)
        serialized = json.dumps(d)
        self.assertIn('"action": "EXACT_SEARCH"', serialized)

    def test_27_stop_retrieval_emitted_when_evidence_is_sufficient(self) -> None:
        """27. STOP_RETRIEVAL is immediately returned when direct_source_sufficient is True."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            direct_source_sufficient=True,
            candidate_symbols=["module.function"],
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.STOP_RETRIEVAL)
        self.assertEqual(decision.state, DecisionState.SOURCE_SUFFICIENT)

    def test_28_unsupported_unknown_state_produces_safe_fallback(self) -> None:
        """28. Unsupported/unknown phase safely stops retrieval instead of speculating."""
        policy = HybridLocalizationPolicy()
        context = HybridReconContext(
            phase="invalid_custom_phase",
            has_subsystem_ambiguity=True,
        )
        decision = policy.choose_next_localization_action(context)
        self.assertEqual(decision.action, LocalizationAction.STOP_RETRIEVAL)
        self.assertEqual(decision.state, DecisionState.NON_LOCALIZATION_PHASE)

    def test_29_e6_prompt_contains_hybrid_localization_instructions(self) -> None:
        """29. E6 root prompt contains explicit hybrid localization guidance."""
        prompt_text = (PROJECT_ROOT / "experiments/candidates/E6/prompts/root.md").read_text(encoding="utf-8")
        self.assertIn("## Hybrid Localization Strategy", prompt_text)
        self.assertIn("Start with cheap exact reconnaissance", prompt_text)
        self.assertIn("Do not chain retrieval tools mechanically", prompt_text)
        self.assertIn("search_similar_code", prompt_text)
        self.assertIn("get_code_neighbors", prompt_text)
        self.assertIn("get_code_subgraph", prompt_text)
        self.assertIn("Stop retrieval once direct source evidence explains the defect", prompt_text)

    def test_30_no_stage_16_plus_functionality_introduced(self) -> None:
        """30. Stage 16+ features (testing skill, triage skill, recovery, classifiers) are absent."""
        prompt_text = (PROJECT_ROOT / "experiments/candidates/E6/prompts/root.md").read_text(encoding="utf-8")
        manifest_text = (PROJECT_ROOT / "experiments/prompts/E6/manifest.json").read_text(encoding="utf-8")

        for forbidden in (
            "testing skill",
            "repository triage",
            "failure classification",
            "no-progress detector",
            "recovery path",
            "scout sub-agent",
            "debugger sub-agent",
            "reviewer sub-agent",
        ):
            self.assertNotIn(forbidden, prompt_text.lower())
            self.assertNotIn(forbidden, manifest_text.lower())


if __name__ == "__main__":
    unittest.main()
