"""Comprehensive tests for Stage 13 Code Graph Neighbors and Candidate E4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_manifest
from local.evaluation.queries import list_candidates
from local.graph import (
    DEFAULT_CONTRACT_MAX_NEIGHBORS,
    DEFAULT_MAX_RETAINED_NEIGHBORS,
    TOOL_NAME,
    CodeNeighborItem,
    CodeNeighborsResponse,
    NeighborCallRecord,
    NeighborPolicyV1,
    NeighborReconContext,
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

E4_EXP_DIR = Path("experiments/prompts/E4")
E4_MANIFEST_PATH = E4_EXP_DIR / "manifest.json"
E4_REPORT_PATH = E4_EXP_DIR / "report.md"

# Recorded frozen checksums
RECORDED_E0_YAML_SHA = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
RECORDED_E0_PROMPT_SHA = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"

RECORDED_E1_YAML_SHA = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
RECORDED_E1_PROMPT_SHA = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"

RECORDED_E2_YAML_SHA = "cefb9297917626ba10f07b39a2769a668246b6a3d13f4f6e1ffde08f0c62df04"
RECORDED_E2_PROMPT_SHA = "f8358618a67353d0a456ece8dc037bbdaefe108d99fa4f997e5daf4fb354fd4e"

RECORDED_E3_YAML_SHA = "2cf03011fc03c37292a1b0cdd74ae9d512f97bd8f1a5148939410e96c5e6b783"
RECORDED_E3_PROMPT_SHA = "6925be383fbbdd0f58a885a82c02b5e9fefe434d8cb7f91d6b5107ada9e120cf"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestGraphNeighborsE4(unittest.TestCase):
    """Test suite validating Stage 13 Candidate E4 and Code Graph Neighbor Policy V1."""

    # -------------------------------------------------------------------------
    # Requirement 1: E4 submission configuration validates
    # -------------------------------------------------------------------------
    def test_e4_config_is_valid(self) -> None:
        validator = SubmissionValidator(E4_CANDIDATE_DIR)
        valid = validator.validate()
        self.assertTrue(valid, f"E4 validation failed: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    # -------------------------------------------------------------------------
    # Requirements 2, 3, 4, 5: Architecture Parity with E3
    # -------------------------------------------------------------------------
    def test_e4_preserves_model_generation_and_all_e3_tools(self) -> None:
        with open(E3_YAML_PATH, "r", encoding="utf-8") as f:
            e3_text = f.read()
        with open(E4_YAML_PATH, "r", encoding="utf-8") as f:
            e4_text = f.read()

        def parse_kv(text: str) -> dict[str, str]:
            res = {}
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("-") and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res

        e3_kv = parse_kv(e3_text)
        e4_kv = parse_kv(e4_text)

        # Requirement 2: Preserves E3 model
        self.assertEqual(e4_kv["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e4_kv["model"], e3_kv["model"])

        # Requirement 3: Preserves E3 generation configuration
        self.assertEqual(e4_kv["temperature"], e3_kv["temperature"])
        self.assertEqual(e4_kv["top_p"], e3_kv["top_p"])
        self.assertEqual(e4_kv["max_output_tokens"], e3_kv["max_output_tokens"])
        self.assertEqual(e4_kv["thinking_level"], e3_kv["thinking_level"])
        self.assertEqual(e4_kv["thinking_budget"], e3_kv["thinking_budget"])
        self.assertEqual(e4_kv["include_thoughts"], e3_kv["include_thoughts"])

        # Requirement 4 & 5: Preserves all 7 E3 tools and adds exactly get_code_neighbors
        e3_tools = [
            "run_command", "read_file", "edit_file", "write_file", "get_status",
            "submit_patch", "search_similar_code"
        ]
        e4_expected_tools = e3_tools + ["get_code_neighbors"]

        declared_tools = [line.strip()[2:] for line in e4_text.splitlines() if line.strip().startswith("- ")]
        self.assertEqual(declared_tools, e4_expected_tools)
        self.assertEqual(len(declared_tools), 8)

    # -------------------------------------------------------------------------
    # Requirements 6, 7, 8, 9: Invariance of E0, E1, E2, E3
    # -------------------------------------------------------------------------
    def test_e0_e1_e2_e3_remain_unchanged(self) -> None:
        self.assertEqual(compute_sha256(E0_YAML_PATH), RECORDED_E0_YAML_SHA, "E0 YAML modified!")
        self.assertEqual(compute_sha256(E0_PROMPT_PATH), RECORDED_E0_PROMPT_SHA, "E0 prompt modified!")

        self.assertEqual(compute_sha256(E1_YAML_PATH), RECORDED_E1_YAML_SHA, "E1 YAML modified!")
        self.assertEqual(compute_sha256(E1_PROMPT_PATH), RECORDED_E1_PROMPT_SHA, "E1 prompt modified!")

        self.assertEqual(compute_sha256(E2_YAML_PATH), RECORDED_E2_YAML_SHA, "E2 YAML modified!")
        self.assertEqual(compute_sha256(E2_PROMPT_PATH), RECORDED_E2_PROMPT_SHA, "E2 prompt modified!")

        self.assertEqual(compute_sha256(E3_YAML_PATH), RECORDED_E3_YAML_SHA, "E3 YAML modified!")
        self.assertEqual(compute_sha256(E3_PROMPT_PATH), RECORDED_E3_PROMPT_SHA, "E3 prompt modified!")

    # -------------------------------------------------------------------------
    # Requirement 10: Official get_code_neighbors contract representation
    # -------------------------------------------------------------------------
    def test_get_code_neighbors_contract(self) -> None:
        self.assertEqual(TOOL_NAME, "get_code_neighbors")
        self.assertEqual(DEFAULT_CONTRACT_MAX_NEIGHBORS, 50)
        self.assertEqual(DEFAULT_MAX_RETAINED_NEIGHBORS, 5)

        # Response deserialization
        resp_data = {
            "status": "ok",
            "node": "fastapi.applications.FastAPI",
            "neighbors": ["fastapi.routing.APIRoute", "fastapi.datastructures.Default"],
            "count": 2,
        }
        resp = CodeNeighborsResponse.from_dict(resp_data)
        self.assertTrue(resp.is_ok())
        self.assertEqual(resp.node, "fastapi.applications.FastAPI")
        self.assertEqual(len(resp.neighbors), 2)
        self.assertEqual(resp.neighbors[0], "fastapi.routing.APIRoute")

    # -------------------------------------------------------------------------
    # Requirement 11: Neighbor retrieval not allowed without promising symbol
    # -------------------------------------------------------------------------
    def test_neighbor_retrieval_requires_promising_symbol(self) -> None:
        policy = NeighborPolicyV1()

        # Missing target symbol
        ctx_no_sym = NeighborReconContext(target_symbol=None, is_promising_candidate=True)
        should_run, reason = policy.should_retrieve(ctx_no_sym)
        self.assertFalse(should_run)
        self.assertIn("target symbol must be specified", reason.lower())

        # Target symbol not established as promising
        ctx_unpromising = NeighborReconContext(
            target_symbol="some.module.func",
            is_promising_candidate=False,
            needs_relationship_exploration=True,
        )
        should_run, reason = policy.should_retrieve(ctx_unpromising)
        self.assertFalse(should_run)
        self.assertIn("not been established as a promising candidate", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 12: Neighbor retrieval not invoked blindly for every candidate
    # -------------------------------------------------------------------------
    def test_neighbor_retrieval_not_invoked_blindly(self) -> None:
        policy = NeighborPolicyV1()

        # Case 1: Direct source inspection is already sufficient
        ctx_suff = NeighborReconContext(
            target_symbol="requests.models.Request",
            is_promising_candidate=True,
            direct_source_sufficient=True,
            needs_relationship_exploration=True,
        )
        should_run, reason = policy.should_retrieve(ctx_suff)
        self.assertFalse(should_run)
        self.assertIn("direct source inspection is sufficient", reason.lower())

        # Case 2: Consecutive neighbor retrieval (anti-spam / anti-loop)
        ctx_consec = NeighborReconContext(
            target_symbol="requests.models.Request",
            is_promising_candidate=True,
            needs_relationship_exploration=True,
            last_tool_was_neighbor=True,
        )
        should_run, reason = policy.should_retrieve(ctx_consec)
        self.assertFalse(should_run)
        self.assertIn("consecutive", reason.lower())

        # Case 3: Already expanded node
        ctx_dup = NeighborReconContext(
            target_symbol="requests.models.Request",
            is_promising_candidate=True,
            needs_relationship_exploration=True,
            already_expanded_nodes={"requests.models.Request"},
        )
        should_run, reason = policy.should_retrieve(ctx_dup)
        self.assertFalse(should_run)
        self.assertIn("already been expanded", reason.lower())

        # Case 4: Non-localization phase
        ctx_edit = NeighborReconContext(
            target_symbol="requests.models.Request",
            is_promising_candidate=True,
            needs_relationship_exploration=True,
            phase="edit",
        )
        should_run, reason = policy.should_retrieve(ctx_edit)
        self.assertFalse(should_run)
        self.assertIn("disabled in 'edit' phase", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 13, 14, 15: Parsing, TaskState integration, no payload dumping
    # -------------------------------------------------------------------------
    def test_integrate_neighbors_into_taskstate_without_payload_dumping(self) -> None:
        policy = NeighborPolicyV1(max_retained=3)
        state = TaskState()

        # Simulated 15 neighbors from get_code_neighbors
        neighbors_list = [f"pkg.submodule.func_{i}" for i in range(15)]
        resp = CodeNeighborsResponse(
            status="ok",
            node="pkg.main.Entrypoint",
            neighbors=neighbors_list,
            count=15,
        )

        record = policy.integrate_results(resp, state, edge_type="CALLS")
        self.assertEqual(record.result_count, 15)
        self.assertEqual(record.retained_count, 3)
        self.assertEqual(len(record.retained_neighbors), 3)

        # Candidates recorded in TaskState
        self.assertEqual(len(state.candidates), 3)
        self.assertEqual(state.candidates[0].symbol, "pkg.submodule.func_0")
        self.assertIn("pkg.main.Entrypoint", state.candidates[0].rationale)
        self.assertIn("CALLS", state.candidates[0].rationale)

        # Evidence recorded in TaskState
        self.assertEqual(len(state.evidence), 3)
        self.assertIn("pkg.main.Entrypoint", state.evidence[0].observation)
        self.assertEqual(state.evidence[0].source_command_or_file, "get_code_neighbors(node='pkg.main.Entrypoint')")

        # Invariant 15: No oversized raw payloads in TaskState
        state_json = state.to_json()
        self.assertNotIn("func_14", state_json, "Unretained neighbors must not pollute TaskState!")
        self.assertLess(len(state_json), 2500, "TaskState serialization must remain bounded and concise.")

    # -------------------------------------------------------------------------
    # Requirement 16: Distinguish useful vs irrelevant relations
    # -------------------------------------------------------------------------
    def test_distinguish_relevant_neighbor_relations(self) -> None:
        policy = NeighborPolicyV1(max_retained=5)
        state = TaskState()

        resp = CodeNeighborsResponse(
            status="ok",
            node="requests.sessions.Session",
            neighbors=[
                "builtins.object",
                "typing.Optional",
                "requests.adapters.HTTPAdapter",
                "requests.models.Request",
                "builtins.dict",
            ],
            count=5,
        )

        # Relevance filter filtering out standard library builtins
        def domain_filter(node: str) -> bool:
            return not node.startswith("builtins.") and not node.startswith("typing.")

        record = policy.integrate_results(resp, state, relevance_filter=domain_filter)
        self.assertEqual(record.retained_count, 2)
        self.assertEqual(record.retained_neighbors, [
            "requests.adapters.HTTPAdapter",
            "requests.models.Request",
        ])

    # -------------------------------------------------------------------------
    # Requirements 17, 18: No subgraph or recursive expansion in E4
    # -------------------------------------------------------------------------
    def test_no_subgraph_or_stage14_leakage(self) -> None:
        # Check E4 agent YAML
        with open(E4_YAML_PATH, "r", encoding="utf-8") as f:
            e4_yaml = f.read()
        self.assertNotIn("get_code_subgraph", e4_yaml)

        # Check E4 prompt
        with open(E4_PROMPT_PATH, "r", encoding="utf-8") as f:
            e4_prompt = f.read()
        self.assertNotIn("get_code_subgraph", e4_prompt)
        self.assertNotIn("subgraph", e4_prompt.lower())

        # Check local/graph files for subgraph
        for py_file in Path("local/graph").glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            self.assertNotIn("get_code_subgraph", content)

    # -------------------------------------------------------------------------
    # Requirement 19: No golden patch / test patch / secret leakage
    # -------------------------------------------------------------------------
    def test_no_secret_patch_or_credential_leakage(self) -> None:
        for path in [E4_YAML_PATH, E4_PROMPT_PATH, E4_MANIFEST_PATH, E4_REPORT_PATH]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("test_patch", content)
            self.assertNotIn("golden_patch", content)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", content)

    # -------------------------------------------------------------------------
    # Requirement 20: Candidate manifest hashes are correct
    # -------------------------------------------------------------------------
    def test_manifest_metadata_and_hashes(self) -> None:
        self.assertTrue(E4_MANIFEST_PATH.exists())
        with open(E4_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["candidate_id"], "E4")
        self.assertEqual(manifest["parent_candidate"], "E3")
        self.assertEqual(manifest["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest["new_tool_name"], "get_code_neighbors")
        self.assertEqual(manifest["neighbor_policy_version"], "v1")
        self.assertEqual(manifest["validation_status"], "structural_only")
        self.assertEqual(manifest["evidence_status"], "unvalidated")

        self.assertFalse(manifest["benchmark_scores_asserted"])
        self.assertIsNone(manifest["pass_rate"])
        self.assertIsNone(manifest["fail_rate"])

        # Check exact file hashes
        self.assertEqual(manifest["prompt_sha256"], compute_sha256(E4_PROMPT_PATH))
        self.assertEqual(manifest["agent_config_sha256"], compute_sha256(E4_YAML_PATH))
        self.assertEqual(manifest["parent_prompt_sha256"], RECORDED_E3_PROMPT_SHA)

    # -------------------------------------------------------------------------
    # Local Runner and Database Integration
    # -------------------------------------------------------------------------
    def test_e4_runner_and_database_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Local runner dry run
            spec = RunSpec(
                task_id="fastapi_14786",
                candidate_id="E4",
                candidate_dir=E4_CANDIDATE_DIR,
                output_dir=Path(td),
                backend_name="dry-run",
            )
            meta = run_task(spec, Path("data/competition/tasks.jsonl"))
            self.assertEqual(meta.candidate_id, "E4")
            self.assertEqual(meta.status, "dry_run_completed")
            self.assertEqual(meta.model_id, "gemma-4-31b-it-qat-w4a16-ct")

            # Database registration acceptance
            db_path = Path(td) / "eval.db"
            init_database(db_path)
            conn = get_connection(db_path)
            cid = ingest_manifest(conn, E4_MANIFEST_PATH)
            self.assertEqual(cid, "E4")
            cands = list_candidates(conn)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["candidate_id"], "E4")
            self.assertEqual(cands[0]["prompt_sha256"], compute_sha256(E4_PROMPT_PATH))
            conn.close()


if __name__ == "__main__":
    unittest.main()
