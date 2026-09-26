"""Comprehensive tests for Stage 14 Code Graph Selective Subgraph and Candidate E5."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_manifest
from local.evaluation.queries import list_candidates
from local.subgraph import (
    DEFAULT_BREADTH_K,
    MAX_RETAINED_EDGES,
    MAX_RETAINED_NODES,
    SUPPORTED_BREADTH_CONFIGS,
    TOOL_NAME as SUBGRAPH_TOOL_NAME,
    CodeSubgraphResponse,
    SubgraphCallRecord,
    SubgraphEdge,
    SubgraphPolicyV1,
    SubgraphReconContext,
)
from local.runner.cli import run_task
from local.runner.models import RunSpec
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator

# Paths
E0_YAML_PATH = Path("agent/agent.yaml")
E0_PROMPT_PATH = Path("agent/prompts/root.md")

E1_CANDIDATE_DIR = Path("experiments/candidates/E1")
E1_YAML_PATH = E1_CANDIDATE_DIR / "agent.yaml"
E1_PROMPT_PATH = E1_CANDIDATE_DIR / "prompts/root.md"

E2_CANDIDATE_DIR = Path("experiments/candidates/E2")
E2_YAML_PATH = E2_CANDIDATE_DIR / "agent.yaml"
E2_PROMPT_PATH = E2_CANDIDATE_DIR / "prompts/root.md"

E3_CANDIDATE_DIR = Path("experiments/candidates/E3")
E3_YAML_PATH = E3_CANDIDATE_DIR / "agent.yaml"
E3_PROMPT_PATH = E3_CANDIDATE_DIR / "prompts/root.md"

E4_CANDIDATE_DIR = Path("experiments/candidates/E4")
E4_YAML_PATH = E4_CANDIDATE_DIR / "agent.yaml"
E4_PROMPT_PATH = E4_CANDIDATE_DIR / "prompts/root.md"

E5_CANDIDATE_DIR = Path("experiments/candidates/E5")
E5_YAML_PATH = E5_CANDIDATE_DIR / "agent.yaml"
E5_PROMPT_PATH = E5_CANDIDATE_DIR / "prompts/root.md"

E5_EXP_DIR = Path("experiments/prompts/E5")
E5_MANIFEST_PATH = E5_EXP_DIR / "manifest.json"
E5_REPORT_PATH = E5_EXP_DIR / "report.md"

# Recorded frozen checksums
RECORDED_E0_YAML_SHA = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
RECORDED_E0_PROMPT_SHA = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"

RECORDED_E1_YAML_SHA = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
RECORDED_E1_PROMPT_SHA = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"

RECORDED_E2_YAML_SHA = "cefb9297917626ba10f07b39a2769a668246b6a3d13f4f6e1ffde08f0c62df04"
RECORDED_E2_PROMPT_SHA = "f8358618a67353d0a456ece8dc037bbdaefe108d99fa4f997e5daf4fb354fd4e"

RECORDED_E3_YAML_SHA = "2cf03011fc03c37292a1b0cdd74ae9d512f97bd8f1a5148939410e96c5e6b783"
RECORDED_E3_PROMPT_SHA = "6925be383fbbdd0f58a885a82c02b5e9fefe434d8cb7f91d6b5107ada9e120cf"

RECORDED_E4_YAML_SHA = "ec3cddcf88d5e04a2415dac7a59aed6464ce0e379f301ae4df24e507368953ca"
RECORDED_E4_PROMPT_SHA = "4a7eefeb785bf1334e2f6f85a2f6b9ebeb5349f42b0acb3327d19bbd9ad7008d"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestSubgraphE5(unittest.TestCase):
    """Test suite validating Stage 14 Candidate E5 and Selective Subgraph Policy V1."""

    # -------------------------------------------------------------------------
    # Requirement 1: E5 submission validator passes
    # -------------------------------------------------------------------------
    def test_e5_config_is_valid(self) -> None:
        validator = SubmissionValidator(E5_CANDIDATE_DIR)
        valid = validator.validate()
        self.assertTrue(valid, f"E5 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    # -------------------------------------------------------------------------
    # Requirements 2, 3, 4, 5: Architecture Parity with E4
    # -------------------------------------------------------------------------
    def test_e5_preserves_model_generation_and_all_e4_tools(self) -> None:
        with open(E4_YAML_PATH, "r", encoding="utf-8") as f:
            e4_text = f.read()
        with open(E5_YAML_PATH, "r", encoding="utf-8") as f:
            e5_text = f.read()

        def parse_kv(text: str) -> dict[str, str]:
            res = {}
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("-") and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res

        e4_kv = parse_kv(e4_text)
        e5_kv = parse_kv(e5_text)

        # Requirement 2: Preserves E4 model
        self.assertEqual(e5_kv["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e5_kv["model"], e4_kv["model"])

        # Requirement 3: Preserves E4 generation configuration
        self.assertEqual(e5_kv["temperature"], e4_kv["temperature"])
        self.assertEqual(e5_kv["top_p"], e4_kv["top_p"])
        self.assertEqual(e5_kv["max_output_tokens"], e4_kv["max_output_tokens"])
        self.assertEqual(e5_kv["thinking_level"], e4_kv["thinking_level"])
        self.assertEqual(e5_kv["thinking_budget"], e4_kv["thinking_budget"])
        self.assertEqual(e5_kv["include_thoughts"], e4_kv["include_thoughts"])

        # Requirement 4 & 5: Preserves all 8 E4 tools and adds exactly get_code_subgraph
        e4_tools = [
            "run_command", "read_file", "edit_file", "write_file", "get_status",
            "submit_patch", "search_similar_code", "get_code_neighbors"
        ]
        e5_expected_tools = e4_tools + ["get_code_subgraph"]

        declared_tools = [line.strip()[2:] for line in e5_text.splitlines() if line.strip().startswith("- ")]
        self.assertEqual(declared_tools, e5_expected_tools)
        self.assertEqual(len(declared_tools), 9)

    # -------------------------------------------------------------------------
    # Requirements 6, 7, 8, 9, 10: Invariance of E0, E1, E2, E3, E4
    # -------------------------------------------------------------------------
    def test_e0_to_e4_remain_unchanged(self) -> None:
        self.assertEqual(compute_sha256(E0_YAML_PATH), RECORDED_E0_YAML_SHA, "E0 YAML modified!")
        self.assertEqual(compute_sha256(E0_PROMPT_PATH), RECORDED_E0_PROMPT_SHA, "E0 prompt modified!")

        self.assertEqual(compute_sha256(E1_YAML_PATH), RECORDED_E1_YAML_SHA, "E1 YAML modified!")
        self.assertEqual(compute_sha256(E1_PROMPT_PATH), RECORDED_E1_PROMPT_SHA, "E1 prompt modified!")

        self.assertEqual(compute_sha256(E2_YAML_PATH), RECORDED_E2_YAML_SHA, "E2 YAML modified!")
        self.assertEqual(compute_sha256(E2_PROMPT_PATH), RECORDED_E2_PROMPT_SHA, "E2 prompt modified!")

        self.assertEqual(compute_sha256(E3_YAML_PATH), RECORDED_E3_YAML_SHA, "E3 YAML modified!")
        self.assertEqual(compute_sha256(E3_PROMPT_PATH), RECORDED_E3_PROMPT_SHA, "E3 prompt modified!")

        self.assertEqual(compute_sha256(E4_YAML_PATH), RECORDED_E4_YAML_SHA, "E4 YAML modified!")
        self.assertEqual(compute_sha256(E4_PROMPT_PATH), RECORDED_E4_PROMPT_SHA, "E4 prompt modified!")

    # -------------------------------------------------------------------------
    # Requirement 11: Exact get_code_subgraph contract representation
    # -------------------------------------------------------------------------
    def test_get_code_subgraph_contract_representation(self) -> None:
        self.assertEqual(SUBGRAPH_TOOL_NAME, "get_code_subgraph")

        resp_dict = {
            "status": "ok",
            "nodes": ["node_a", "node_b"],
            "edges": [{"from": "node_a", "to": "node_b", "type": "CALLS"}],
            "node_count": 2,
            "edge_count": 1,
        }
        resp = CodeSubgraphResponse.from_dict(resp_dict)
        self.assertTrue(resp.is_ok())
        self.assertEqual(resp.nodes, ["node_a", "node_b"])
        self.assertEqual(len(resp.edges), 1)
        self.assertEqual(resp.edges[0].from_node, "node_a")
        self.assertEqual(resp.edges[0].to_node, "node_b")
        self.assertEqual(resp.edges[0].edge_type, "CALLS")
        self.assertEqual(resp.node_count, 2)
        self.assertEqual(resp.edge_count, 1)

    # -------------------------------------------------------------------------
    # Requirement 12: Missing candidate seed set blocks subgraph retrieval
    # -------------------------------------------------------------------------
    def test_missing_or_insufficient_candidates_blocks_retrieval(self) -> None:
        policy = SubgraphPolicyV1()

        # Case 1: Empty candidate list
        ctx_empty = SubgraphReconContext(candidate_symbols=[])
        should_run, reason = policy.should_retrieve(ctx_empty)
        self.assertFalse(should_run)
        self.assertIn("at least 2", reason.lower())

        # Case 2: Only 1 candidate symbol
        ctx_one = SubgraphReconContext(
            candidate_symbols=["module.ClassA"],
            inspected_symbols={"module.ClassA"},
            spans_multiple_symbols=True,
        )
        should_run, reason = policy.should_retrieve(ctx_one)
        self.assertFalse(should_run)
        self.assertIn("at least 2", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 13: Oversized candidate set is bounded according to policy
    # -------------------------------------------------------------------------
    def test_oversized_candidate_set_is_bounded(self) -> None:
        policy = SubgraphPolicyV1()
        candidates = [f"mod.func_{i}" for i in range(20)]

        # Select seed nodes with k=4
        selected_4 = policy.select_seed_nodes(candidates, breadth_k=4)
        self.assertEqual(len(selected_4), 4)
        self.assertEqual(selected_4, candidates[:4])

        # Select seed nodes with k=2
        selected_2 = policy.select_seed_nodes(candidates, breadth_k=2)
        self.assertEqual(len(selected_2), 2)
        self.assertEqual(selected_2, candidates[:2])

        # Select seed nodes with k=8
        selected_8 = policy.select_seed_nodes(candidates, breadth_k=8)
        self.assertEqual(len(selected_8), 8)
        self.assertEqual(selected_8, candidates[:8])

    # -------------------------------------------------------------------------
    # Requirement 14, 15: Subgraph retrieval requires localization phase
    # -------------------------------------------------------------------------
    def test_subgraph_retrieval_phase_gating(self) -> None:
        policy = SubgraphPolicyV1()

        for invalid_phase in ["edit", "verify", "review"]:
            ctx = SubgraphReconContext(
                candidate_symbols=["mod.A", "mod.B"],
                inspected_symbols={"mod.A", "mod.B"},
                spans_multiple_symbols=True,
                phase=invalid_phase,
            )
            should_run, reason = policy.should_retrieve(ctx)
            self.assertFalse(should_run, f"Must not run in phase '{invalid_phase}'")
            self.assertIn(invalid_phase, reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 16: Supported breadth configurations (2, 4, 8) accepted
    # -------------------------------------------------------------------------
    def test_breadth_configurations(self) -> None:
        policy = SubgraphPolicyV1()
        self.assertEqual(SUPPORTED_BREADTH_CONFIGS, (2, 4, 8))
        self.assertEqual(DEFAULT_BREADTH_K, 4)

        ctx = SubgraphReconContext(
            candidate_symbols=["mod.A", "mod.B", "mod.C", "mod.D", "mod.E"],
            inspected_symbols={"mod.A", "mod.B", "mod.C"},
            spans_multiple_symbols=True,
        )

        for k in (2, 4, 8):
            should_run, reason = policy.should_retrieve(ctx, breadth_k=k)
            self.assertTrue(should_run, f"Breadth k={k} must be accepted")

        # Unsupported breadth
        should_run, reason = policy.should_retrieve(ctx, breadth_k=16)
        self.assertFalse(should_run)
        self.assertIn("not in supported configurations", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 17: Duplicate seeds/results handled deterministically
    # -------------------------------------------------------------------------
    def test_duplicate_seeds_handling(self) -> None:
        policy = SubgraphPolicyV1()

        # Deduplication of input candidate symbols
        duplicated_input = ["mod.A", "mod.B", "mod.A", "mod.C", "mod.B"]
        deduped = policy.select_seed_nodes(duplicated_input, breadth_k=4)
        self.assertEqual(deduped, ["mod.A", "mod.B", "mod.C"])

        # Repeated retrieval on identical seed set blocked
        state = TaskState()
        resp = CodeSubgraphResponse(status="ok", nodes=["mod.A", "mod.B"], edges=[], node_count=2, edge_count=0)
        policy.integrate_results(resp, state, seed_nodes=["mod.A", "mod.B"])

        ctx = SubgraphReconContext(
            candidate_symbols=["mod.A", "mod.B"],
            inspected_symbols={"mod.A", "mod.B"},
            spans_multiple_symbols=True,
        )
        should_run, reason = policy.should_retrieve(ctx, breadth_k=2)
        self.assertFalse(should_run, "Must block duplicate seed set retrieval")
        self.assertIn("already been retrieved", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 18: Raw unbounded subgraph payload not stored in TaskState
    # -------------------------------------------------------------------------
    def test_taskstate_payload_hygiene(self) -> None:
        policy = SubgraphPolicyV1(max_retained_nodes=8, max_retained_edges=12)
        state = TaskState()

        # Simulated oversized response with 50 nodes and 100 edges
        nodes = [f"pkg.mod.Node_{i}" for i in range(50)]
        edges = [SubgraphEdge(from_node=f"pkg.mod.Node_{i}", to_node=f"pkg.mod.Node_{i+1}", edge_type="CALLS") for i in range(49)]
        resp = CodeSubgraphResponse(status="ok", nodes=nodes, edges=edges, node_count=50, edge_count=49)

        record = policy.integrate_results(resp, state, seed_nodes=["pkg.mod.Node_0", "pkg.mod.Node_1"])
        self.assertFalse(record.fallback_triggered)
        self.assertLessEqual(len(record.retained_nodes), 8)
        self.assertLessEqual(len(record.retained_edges), 12)

        # Candidates in TaskState
        self.assertLessEqual(len(state.candidates), 8)
        # Evidence in TaskState
        self.assertEqual(len(state.evidence), 1)

        # Check serialized TaskState size
        state_json = state.to_json()
        self.assertNotIn("Node_49", state_json, "Unretained nodes must not be dumped into TaskState!")
        self.assertLess(len(state_json), 3000, "TaskState serialization must remain compact.")

    # -------------------------------------------------------------------------
    # Requirement 19: Error/empty response handling is deterministic
    # -------------------------------------------------------------------------
    def test_error_and_empty_response_handling(self) -> None:
        policy = SubgraphPolicyV1()

        # Empty response
        state_empty = TaskState()
        resp_empty = CodeSubgraphResponse(status="ok", nodes=[], edges=[], node_count=0, edge_count=0)
        rec_empty = policy.integrate_results(resp_empty, state_empty, seed_nodes=["mod.A", "mod.B"])
        self.assertTrue(rec_empty.fallback_triggered)
        self.assertEqual(len(state_empty.candidates), 0)
        self.assertEqual(len(state_empty.evidence), 1)
        self.assertIn("returned no interconnected nodes", state_empty.evidence[0].observation)

        # Error response
        state_err = TaskState()
        resp_err = CodeSubgraphResponse(status="error", error_message="Graph offline")
        rec_err = policy.integrate_results(resp_err, state_err, seed_nodes=["mod.A", "mod.B"])
        self.assertTrue(rec_err.fallback_triggered)
        self.assertEqual(len(state_err.candidates), 0)
        self.assertEqual(len(state_err.evidence), 1)

    # -------------------------------------------------------------------------
    # Requirement 20: No automatic recursive subgraph expansion
    # -------------------------------------------------------------------------
    def test_no_recursive_subgraph_expansion(self) -> None:
        policy = SubgraphPolicyV1()
        ctx_consec = SubgraphReconContext(
            candidate_symbols=["mod.A", "mod.B"],
            inspected_symbols={"mod.A", "mod.B"},
            spans_multiple_symbols=True,
            last_tool_was_subgraph=True,
        )
        should_run, reason = policy.should_retrieve(ctx_consec)
        self.assertFalse(should_run)
        self.assertIn("consecutive", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 21, 22: Prompt and codebase free of Stage 15+ leaks
    # -------------------------------------------------------------------------
    def test_no_stage15_hybrid_controller_leakage(self) -> None:
        with open(E5_PROMPT_PATH, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        # Stage 15 keywords must not be present
        self.assertNotIn("hybrid localization", prompt_text.lower())
        self.assertNotIn("hybrid controller", prompt_text.lower())
        self.assertNotIn("triage", prompt_text.lower())
        self.assertNotIn("scout", prompt_text.lower())

        # Check local/graph and local/subgraph for Stage 15
        for folder in ["local/graph", "local/subgraph"]:
            for py_path in Path(folder).glob("*.py"):
                content = py_path.read_text(encoding="utf-8")
                self.assertNotIn("HybridLocalizationController", content)
                self.assertNotIn("hybrid_controller", content)

    # -------------------------------------------------------------------------
    # Secret protection
    # -------------------------------------------------------------------------
    def test_no_secret_patch_or_credential_leakage(self) -> None:
        for path in [E5_YAML_PATH, E5_PROMPT_PATH, E5_MANIFEST_PATH, E5_REPORT_PATH]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("test_patch", content)
            self.assertNotIn("golden_patch", content)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", content)

    # -------------------------------------------------------------------------
    # Manifest verification
    # -------------------------------------------------------------------------
    def test_manifest_metadata_and_hashes(self) -> None:
        self.assertTrue(E5_MANIFEST_PATH.exists())
        with open(E5_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["candidate_id"], "E5")
        self.assertEqual(manifest["parent_candidate"], "E4")
        self.assertEqual(manifest["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest["new_tool_name"], "get_code_subgraph")
        self.assertEqual(manifest["policy_version"], "v1")
        self.assertEqual(manifest["supported_breadth_configurations"], [2, 4, 8])
        self.assertEqual(manifest["validation_status"], "structural_only")
        self.assertEqual(manifest["evidence_status"], "unvalidated")

        self.assertFalse(manifest["benchmark_scores_asserted"])
        self.assertIsNone(manifest["pass_rate"])
        self.assertIsNone(manifest["fail_rate"])

        # Check hashes
        self.assertEqual(manifest["prompt_sha256"], compute_sha256(E5_PROMPT_PATH))
        self.assertEqual(manifest["agent_config_sha256"], compute_sha256(E5_YAML_PATH))
        self.assertEqual(manifest["parent_prompt_sha256"], RECORDED_E4_PROMPT_SHA)

    # -------------------------------------------------------------------------
    # Local Runner and Database Integration
    # -------------------------------------------------------------------------
    def test_e5_runner_and_database_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Runner dry run
            spec = RunSpec(
                task_id="fastapi_14786",
                candidate_id="E5",
                candidate_dir=E5_CANDIDATE_DIR,
                output_dir=Path(td),
                backend_name="dry-run",
            )
            meta = run_task(spec, Path("data/competition/tasks.jsonl"))
            self.assertEqual(meta.candidate_id, "E5")
            self.assertEqual(meta.status, "dry_run_completed")
            self.assertEqual(meta.model_id, "gemma-4-31b-it-qat-w4a16-ct")

            # Database registration
            db_path = Path(td) / "eval.db"
            init_database(db_path)
            conn = get_connection(db_path)
            cid = ingest_manifest(conn, E5_MANIFEST_PATH)
            self.assertEqual(cid, "E5")
            cands = list_candidates(conn)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["candidate_id"], "E5")
            self.assertEqual(cands[0]["prompt_sha256"], compute_sha256(E5_PROMPT_PATH))
            conn.close()


if __name__ == "__main__":
    unittest.main()
