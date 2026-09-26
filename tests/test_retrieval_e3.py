"""Comprehensive tests for Stage 12 Semantic Retrieval and Candidate E3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_manifest
from local.evaluation.queries import list_candidates
from local.retrieval import (
    DEFAULT_CONTRACT_K,
    DEFAULT_INITIAL_K,
    MAX_RETAINED_CANDIDATES,
    MAX_SUPPORTED_K,
    MIN_SIMILARITY_THRESHOLD,
    MIN_SUPPORTED_K,
    TOOL_NAME,
    ReconContext,
    RetrievalCallRecord,
    RetrievalPolicyV1,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from local.runner.cli import run_task
from local.runner.models import RunSpec
from local.task_state.models import TaskState
from scripts.validate_submission import SubmissionValidator

# Candidate paths
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

E3_EXP_DIR = Path("experiments/prompts/E3")
E3_MANIFEST_PATH = E3_EXP_DIR / "manifest.json"
E3_REPORT_PATH = E3_EXP_DIR / "report.md"

# Recorded frozen checksums
RECORDED_E0_YAML_SHA = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
RECORDED_E0_PROMPT_SHA = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"

RECORDED_E1_YAML_SHA = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
RECORDED_E1_PROMPT_SHA = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"

RECORDED_E2_YAML_SHA = "cefb9297917626ba10f07b39a2769a668246b6a3d13f4f6e1ffde08f0c62df04"
RECORDED_E2_PROMPT_SHA = "f8358618a67353d0a456ece8dc037bbdaefe108d99fa4f997e5daf4fb354fd4e"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestSemanticRetrievalE3(unittest.TestCase):
    """Test suite validating Stage 12 Candidate E3 and Semantic Retrieval Policy V1."""

    # -------------------------------------------------------------------------
    # Requirement 1: E3 config is valid
    # -------------------------------------------------------------------------
    def test_e3_config_is_valid(self) -> None:
        validator = SubmissionValidator(E3_CANDIDATE_DIR)
        valid = validator.validate()
        self.assertTrue(valid, f"E3 validation failed with errors: {validator.errors}")
        self.assertEqual(len(validator.errors), 0)

    # -------------------------------------------------------------------------
    # Requirements 2, 3, 4, 5: Architecture Parity with E2
    # -------------------------------------------------------------------------
    def test_e3_preserves_model_generation_and_tools_parity(self) -> None:
        # Load E2 and E3 configs
        with open(E2_YAML_PATH, "r", encoding="utf-8") as f:
            e2_text = f.read()
        with open(E3_YAML_PATH, "r", encoding="utf-8") as f:
            e3_text = f.read()

        # Parse simple lines
        def parse_kv(text: str) -> dict[str, str]:
            res = {}
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("-") and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res

        e2_kv = parse_kv(e2_text)
        e3_kv = parse_kv(e3_text)

        # Requirement 2: Preserves E2 model ID
        self.assertEqual(e3_kv["model"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(e3_kv["model"], e2_kv["model"])

        # Requirement 3: Preserves E2 generation configuration
        self.assertEqual(e3_kv["temperature"], e2_kv["temperature"])
        self.assertEqual(e3_kv["top_p"], e2_kv["top_p"])
        self.assertEqual(e3_kv["max_output_tokens"], e2_kv["max_output_tokens"])
        self.assertEqual(e3_kv["thinking_level"], e2_kv["thinking_level"])
        self.assertEqual(e3_kv["thinking_budget"], e2_kv["thinking_budget"])
        self.assertEqual(e3_kv["include_thoughts"], e2_kv["include_thoughts"])

        # Requirement 4 & 5: Preserves all 6 existing tools and adds ONLY search_similar_code
        e2_tools = [
            "run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"
        ]
        e3_tools = e2_tools + ["search_similar_code"]

        for tool in e2_tools:
            self.assertIn(f"- {tool}", e3_text, f"Missing original tool: {tool}")

        self.assertIn("- search_similar_code", e3_text, "Missing search_similar_code")

        # Verify exact 7 tools
        declared_tools = [line.strip()[2:] for line in e3_text.splitlines() if line.strip().startswith("- ")]
        self.assertEqual(declared_tools, e3_tools)
        self.assertEqual(len(declared_tools), 7)

    # -------------------------------------------------------------------------
    # Requirements 6, 7, 8: E0, E1, E2 Invariance
    # -------------------------------------------------------------------------
    def test_e0_e1_e2_remain_unchanged(self) -> None:
        # Check E0
        self.assertEqual(compute_sha256(E0_YAML_PATH), RECORDED_E0_YAML_SHA, "E0 YAML was modified!")
        self.assertEqual(compute_sha256(E0_PROMPT_PATH), RECORDED_E0_PROMPT_SHA, "E0 prompt was modified!")

        # Check E1
        self.assertEqual(compute_sha256(E1_YAML_PATH), RECORDED_E1_YAML_SHA, "E1 YAML was modified!")
        self.assertEqual(compute_sha256(E1_PROMPT_PATH), RECORDED_E1_PROMPT_SHA, "E1 prompt was modified!")

        # Check E2
        self.assertEqual(compute_sha256(E2_YAML_PATH), RECORDED_E2_YAML_SHA, "E2 YAML was modified!")
        self.assertEqual(compute_sha256(E2_PROMPT_PATH), RECORDED_E2_PROMPT_SHA, "E2 prompt was modified!")

    # -------------------------------------------------------------------------
    # Requirement 9: Retrieval policy does NOT invoke semantic search on every turn
    # -------------------------------------------------------------------------
    def test_retrieval_policy_does_not_invoke_blindly(self) -> None:
        policy = RetrievalPolicyV1()

        # Case 1: Unambiguous exact matches found
        ctx_exact = ReconContext(exact_matches_found=2, has_subsystem_ambiguity=False, text_search_weak=False)
        should_run, reason = policy.should_retrieve(ctx_exact)
        self.assertFalse(should_run, "Must not retrieve when unambiguous exact match exists.")
        self.assertIn("not required", reason.lower())

        # Case 2: Consecutive retrieval calls (anti-spam invariant)
        ctx_consecutive = ReconContext(exact_matches_found=0, last_tool_was_retrieval=True)
        should_run, reason = policy.should_retrieve(ctx_consecutive)
        self.assertFalse(should_run, "Must block consecutive retrieval calls.")
        self.assertIn("consecutive", reason.lower())

        # Case 3: Later phase (editing or verifying)
        ctx_edit = ReconContext(exact_matches_found=0, phase="edit")
        should_run, reason = policy.should_retrieve(ctx_edit)
        self.assertFalse(should_run, "Must not retrieve in edit phase.")

    # -------------------------------------------------------------------------
    # Requirement 10: Retrieval policy invokes semantic search under defined conditions
    # -------------------------------------------------------------------------
    def test_retrieval_policy_invokes_under_ambiguity_or_weak_search(self) -> None:
        policy = RetrievalPolicyV1()

        # Condition 1: Zero exact matches
        ctx_zero = ReconContext(exact_matches_found=0)
        should_run, reason = policy.should_retrieve(ctx_zero)
        self.assertTrue(should_run)
        self.assertIn("no exact candidate", reason.lower())

        # Condition 2: Subsystem ambiguity
        ctx_ambig = ReconContext(exact_matches_found=3, has_subsystem_ambiguity=True)
        should_run, reason = policy.should_retrieve(ctx_ambig)
        self.assertTrue(should_run)
        self.assertIn("subsystem", reason.lower())

        # Condition 3: Terminology mismatch
        ctx_mismatch = ReconContext(exact_matches_found=1, exact_terms_mismatch=True)
        should_run, reason = policy.should_retrieve(ctx_mismatch)
        self.assertTrue(should_run)
        self.assertIn("diverges", reason.lower())

        # Condition 4: Weak search candidates
        ctx_weak = ReconContext(exact_matches_found=1, text_search_weak=True)
        should_run, reason = policy.should_retrieve(ctx_weak)
        self.assertTrue(should_run)
        self.assertIn("weak", reason.lower())

    # -------------------------------------------------------------------------
    # Requirement 11: Initial k matches verified tool contract
    # -------------------------------------------------------------------------
    def test_initial_k_semantics(self) -> None:
        self.assertEqual(DEFAULT_INITIAL_K, 5)
        self.assertEqual(DEFAULT_CONTRACT_K, 10)
        self.assertEqual(MIN_SUPPORTED_K, 1)
        self.assertEqual(MAX_SUPPORTED_K, 50)

        # Policy should accept valid k within contract range
        policy = RetrievalPolicyV1(initial_k=5)
        self.assertEqual(policy.initial_k, 5)

        # Out of bounds k should raise ValueError
        with self.assertRaises(ValueError):
            RetrievalPolicyV1(initial_k=0)
        with self.assertRaises(ValueError):
            RetrievalPolicyV1(initial_k=51)

    # -------------------------------------------------------------------------
    # Requirement 12: Returned candidates representation
    # -------------------------------------------------------------------------
    def test_returned_candidates_representation(self) -> None:
        item = SemanticSearchResultItem(
            node_name="fastapi.routing.APIRoute",
            similarity=0.9234,
            code="class APIRoute(routing.BaseRoute): pass",
            file_path="fastapi/routing.py",
        )
        self.assertEqual(item.node_name, "fastapi.routing.APIRoute")
        self.assertAlmostEqual(item.similarity, 0.9234)

        resp_dict = {
            "status": "ok",
            "query": "APIRoute",
            "results": [item.to_dict()],
            "count": 1,
        }
        resp = SemanticSearchResponse.from_dict(resp_dict)
        self.assertTrue(resp.is_ok())
        self.assertEqual(resp.query, "APIRoute")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].node_name, "fastapi.routing.APIRoute")

    # -------------------------------------------------------------------------
    # Requirement 13: Retrieval results recorded in TaskState without payload dumping
    # -------------------------------------------------------------------------
    def test_taskstate_integration_without_payload_dumping(self) -> None:
        policy = RetrievalPolicyV1()
        state = TaskState()

        # Simulated search result with large code snippet
        large_code_snippet = "def large_fn():\n" + ("    x = 1\n" * 200)
        resp = SemanticSearchResponse(
            status="ok",
            query="HTTPAdapter",
            results=[
                SemanticSearchResultItem(
                    node_name="requests.adapters.HTTPAdapter",
                    similarity=0.9150,
                    code=large_code_snippet,
                    file_path="requests/adapters.py",
                ),
                SemanticSearchResultItem(
                    node_name="requests.sessions.Session.send",
                    similarity=0.7820,
                    code="def send(self): pass",
                    file_path="requests/sessions.py",
                ),
            ],
            count=2,
        )

        record = policy.integrate_results(resp, state)
        self.assertFalse(record.fallback_triggered)
        self.assertEqual(record.retained_count, 2)

        # Candidates recorded in TaskState
        self.assertEqual(len(state.candidates), 2)
        c0 = state.candidates[0]
        self.assertEqual(c0.symbol, "requests.adapters.HTTPAdapter")
        self.assertEqual(c0.path, "requests/adapters.py")
        self.assertIn("0.9150", c0.rationale)

        # Evidence recorded in TaskState
        self.assertEqual(len(state.evidence), 2)
        e0 = state.evidence[0]
        self.assertIn("requests.adapters.HTTPAdapter", e0.observation)
        self.assertEqual(e0.source_command_or_file, "search_similar_code(query='HTTPAdapter', k=5)")

        # CRITICAL: Verify large code snippet was NOT dumped into TaskState
        state_json = state.to_json()
        self.assertNotIn("x = 1", state_json, "Raw code payload must not be dumped into TaskState!")
        self.assertLess(len(state_json), 2000, "TaskState serialization should remain compact.")

    # -------------------------------------------------------------------------
    # Requirement 14: Fallback behavior on empty or weak results
    # -------------------------------------------------------------------------
    def test_fallback_on_empty_or_weak_results(self) -> None:
        policy = RetrievalPolicyV1(similarity_threshold=0.50)

        # Case 1: Empty results
        state_empty = TaskState()
        resp_empty = SemanticSearchResponse(status="ok", query="non_existent_symbol", results=[], count=0)
        rec_empty = policy.integrate_results(resp_empty, state_empty)
        self.assertTrue(rec_empty.fallback_triggered)
        self.assertEqual(len(state_empty.candidates), 0)
        self.assertEqual(len(state_empty.evidence), 1)
        self.assertIn("falling back", state_empty.evidence[0].observation.lower())

        # Case 2: Weak results below similarity threshold
        state_weak = TaskState()
        resp_weak = SemanticSearchResponse(
            status="ok",
            query="misleading_query",
            results=[
                SemanticSearchResultItem(node_name="unrelated.module", similarity=0.2100, code="..."),
            ],
            count=1,
        )
        rec_weak = policy.integrate_results(resp_weak, state_weak)
        self.assertTrue(rec_weak.fallback_triggered)
        self.assertEqual(rec_weak.retained_count, 0)
        self.assertEqual(len(state_weak.candidates), 0)
        self.assertEqual(len(state_weak.evidence), 1)
        self.assertIn("weak candidates", state_weak.evidence[0].observation.lower())

        # Case 3: Error response
        state_err = TaskState()
        resp_err = SemanticSearchResponse(status="error", query="error_query", error_message="Graph offline")
        rec_err = policy.integrate_results(resp_err, state_err)
        self.assertTrue(rec_err.fallback_triggered)
        self.assertIn("falling back", state_err.evidence[0].observation.lower())

    # -------------------------------------------------------------------------
    # Requirement 15: No neighbors or subgraph behavior implemented
    # -------------------------------------------------------------------------
    def test_no_neighbors_or_subgraph_behavior(self) -> None:
        # Check E3 agent.yaml
        with open(E3_YAML_PATH, "r", encoding="utf-8") as f:
            e3_yaml = f.read()
        self.assertNotIn("get_code_neighbors", e3_yaml)
        self.assertNotIn("get_code_subgraph", e3_yaml)

        # Check E3 root prompt
        with open(E3_PROMPT_PATH, "r", encoding="utf-8") as f:
            e3_prompt = f.read()
        self.assertNotIn("get_code_neighbors", e3_prompt)
        self.assertNotIn("get_code_subgraph", e3_prompt)

    # -------------------------------------------------------------------------
    # Requirement 16: No golden patch / test patch / secret leakage
    # -------------------------------------------------------------------------
    def test_no_secret_patch_or_credential_leakage(self) -> None:
        for path in [E3_YAML_PATH, E3_PROMPT_PATH, E3_MANIFEST_PATH, E3_REPORT_PATH]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("test_patch", content)
            self.assertNotIn("golden_patch", content)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", content)

    # -------------------------------------------------------------------------
    # Requirement 17: Candidate manifest hashes are correct
    # -------------------------------------------------------------------------
    def test_manifest_metadata_and_hashes(self) -> None:
        self.assertTrue(E3_MANIFEST_PATH.exists())
        with open(E3_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["candidate_id"], "E3")
        self.assertEqual(manifest["parent_candidate"], "E2")
        self.assertEqual(manifest["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest["retrieval_tool_name"], "search_similar_code")
        self.assertEqual(manifest["retrieval_policy_version"], "v1")
        self.assertEqual(manifest["validation_status"], "structural_only")
        self.assertEqual(manifest["evidence_status"], "unvalidated")

        # Anti-fabrication assertions
        self.assertFalse(manifest["benchmark_scores_asserted"])
        self.assertIsNone(manifest["pass_rate"])
        self.assertIsNone(manifest["fail_rate"])

        # Hashes match exactly
        self.assertEqual(manifest["prompt_sha256"], compute_sha256(E3_PROMPT_PATH))
        self.assertEqual(manifest["agent_config_sha256"], compute_sha256(E3_YAML_PATH))
        self.assertEqual(manifest["parent_prompt_sha256"], RECORDED_E2_PROMPT_SHA)

    # -------------------------------------------------------------------------
    # Local Runner and Database Integration
    # -------------------------------------------------------------------------
    def test_e3_runner_and_database_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Runner dry-run acceptance
            spec = RunSpec(
                task_id="fastapi_14786",
                candidate_id="E3",
                candidate_dir=E3_CANDIDATE_DIR,
                output_dir=Path(td),
                backend_name="dry-run",
            )
            meta = run_task(spec, Path("data/competition/tasks.jsonl"))
            self.assertEqual(meta.candidate_id, "E3")
            self.assertEqual(meta.status, "dry_run_completed")
            self.assertEqual(meta.model_id, "gemma-4-31b-it-qat-w4a16-ct")

            # Database registration acceptance
            db_path = Path(td) / "eval.db"
            init_database(db_path)
            conn = get_connection(db_path)
            cid = ingest_manifest(conn, E3_MANIFEST_PATH)
            self.assertEqual(cid, "E3")
            cands = list_candidates(conn)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["candidate_id"], "E3")
            self.assertEqual(cands[0]["prompt_sha256"], compute_sha256(E3_PROMPT_PATH))
            conn.close()


if __name__ == "__main__":
    unittest.main()
