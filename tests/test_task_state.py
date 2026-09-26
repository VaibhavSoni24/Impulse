"""Comprehensive tests for Stage 11 Structured Task State and Candidate E2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.evaluation.db import get_connection, init_database
from local.evaluation.ingestion import ingest_manifest
from local.evaluation.queries import list_candidates
from local.runner.cli import run_task
from local.runner.models import RunSpec
from local.task_state import (
    MAX_COLLECTION_SIZE,
    CandidateLocation,
    EditRecord,
    EvidenceItem,
    FailureRecord,
    FinalReviewRecord,
    RepositoryFact,
    TaskState,
    TaskStateManager,
    TestRecord,
    render_model_context,
)

E0_YAML_PATH = Path("agent/agent.yaml")
E0_PROMPT_PATH = Path("agent/prompts/root.md")

E1_YAML_PATH = Path("experiments/candidates/E1/agent.yaml")
E1_PROMPT_PATH = Path("experiments/candidates/E1/prompts/root.md")

E2_CANDIDATE_DIR = Path("experiments/candidates/E2")
E2_YAML_PATH = E2_CANDIDATE_DIR / "agent.yaml"
E2_PROMPT_PATH = E2_CANDIDATE_DIR / "prompts/root.md"

E2_EXP_DIR = Path("experiments/prompts/E2")
E2_MANIFEST_PATH = E2_EXP_DIR / "manifest.json"
E2_REPORT_PATH = E2_EXP_DIR / "report.md"

# Recorded hashes from Stage 8 and Stage 10
RECORDED_E0_YAML_SHA = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
RECORDED_E0_PROMPT_SHA = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"
RECORDED_E1_YAML_SHA = "299cc4edc60e4ad7e6aa064c5604fa9306f4ac17ce6b890cafa37df7566da801"
RECORDED_E1_PROMPT_SHA = "87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestTaskStateCore(unittest.TestCase):
    """Unit tests for TaskState models, serialization, bounds, and rendering."""

    def test_default_construction_and_all_required_fields_exist(self) -> None:
        """Requirement 1 & 2: Verify TaskState default creation and presence of all 11 fields."""
        state = TaskState()
        state.validate()

        # All 11 required PLAN.md conceptual fields
        self.assertEqual(state.summary, "")
        self.assertEqual(state.repository_facts, [])
        self.assertEqual(state.candidates, [])
        self.assertIsNone(state.hypothesis)
        self.assertEqual(state.evidence, [])
        self.assertEqual(state.plan, [])
        self.assertEqual(state.edits, [])
        self.assertEqual(state.tests, [])
        self.assertEqual(state.failures, [])
        self.assertEqual(state.no_progress_count, 0)
        self.assertIsInstance(state.final_review, FinalReviewRecord)

    def test_typed_records_and_updates(self) -> None:
        """Requirement 3 & 8: Verify typed records accept valid inputs and update state."""
        state = TaskState(summary="Fix authentication header stripping")

        state.add_repository_fact("framework", "FastAPI uses Starlette request handlers", "fastapi/security")
        state.add_candidate("fastapi/security/utils.py", "get_authorization_scheme_param", 12, "RFC 6750 whitespace")
        state.set_hypothesis("Authorization header credentials contain leading/trailing whitespace")
        state.add_evidence("AssertionError on whitespace token", "pytest", supports_hypothesis=True)
        state.set_plan(["Inspect utils.py", "Strip token string", "Run targeted pytest"])
        state.add_edit("fastapi/security/utils.py", "Added .strip() to credentials extraction")
        state.add_test("pytest tests/test_security.py", "PASS", "All 4 security tests passed")
        state.add_failure("AssertionError", "Expected token 'foo' got ' foo '", resolved=True)
        state.increment_no_progress()
        self.assertEqual(state.no_progress_count, 1)
        state.reset_no_progress()
        self.assertEqual(state.no_progress_count, 0)

        state.update_final_review(diff_inspected=True, scratch_files_removed=True, intended_files_only=True)
        state.validate()

        self.assertEqual(len(state.repository_facts), 1)
        self.assertEqual(len(state.candidates), 1)
        self.assertEqual(len(state.evidence), 1)
        self.assertEqual(len(state.plan), 3)
        self.assertEqual(len(state.edits), 1)
        self.assertEqual(len(state.tests), 1)
        self.assertEqual(len(state.failures), 1)
        self.assertTrue(state.final_review.diff_inspected)

    def test_invariants_and_validation(self) -> None:
        """Requirement 4 & 9: Verify invariant checks (negative counters, invalid types)."""
        state = TaskState()

        # no_progress_count cannot be negative
        state.no_progress_count = -1
        with self.assertRaises(ValueError):
            state.validate()

        state.no_progress_count = 0
        state.summary = 123  # type: ignore
        with self.assertRaises(TypeError):
            state.validate()

        state.summary = "valid summary"
        state.hypothesis = 456  # type: ignore
        with self.assertRaises(TypeError):
            state.validate()

    def test_serialization_and_deserialization_round_trip(self) -> None:
        """Requirement 4 & 7: Verify lossless deterministic JSON round-trip."""
        state1 = TaskState(summary="Round-trip test", hypothesis="Causal hypothesis")
        state1.add_repository_fact("testing", "pytest configured via pytest.ini")
        state1.add_candidate("src/core.py", "process", 42)
        state1.add_evidence("Reproduced stacktrace", supports_hypothesis=True)
        state1.set_plan(["Step 1", "Step 2"])
        state1.add_edit("src/core.py", "Fixed off-by-one")
        state1.add_test("pytest", "PASS")
        state1.add_failure("IndexError", "Out of bounds", resolved=True)
        state1.increment_no_progress()

        json_str1 = state1.to_json(indent=2)
        state2 = TaskState.from_json(json_str1)
        json_str2 = state2.to_json(indent=2)

        self.assertEqual(json_str1, json_str2, "Serialization must be strictly deterministic")
        self.assertEqual(state1.summary, state2.summary)
        self.assertEqual(state1.hypothesis, state2.hypothesis)
        self.assertEqual(state1.no_progress_count, state2.no_progress_count)
        self.assertEqual(len(state1.evidence), len(state2.evidence))
        self.assertEqual(state1.final_review.diff_inspected, state2.final_review.diff_inspected)

    def test_bounded_collection_growth(self) -> None:
        """Requirement 6: Verify collections enforce upper capacity bounds without unbounded growth."""
        state = TaskState()
        for i in range(MAX_COLLECTION_SIZE + 10):
            state.add_evidence(f"Observation {i}")
            state.add_edit("file.py", f"Edit {i}")
            state.add_test("pytest", "PASS", f"Test {i}")

        self.assertEqual(len(state.evidence), MAX_COLLECTION_SIZE)
        self.assertEqual(len(state.edits), MAX_COLLECTION_SIZE)
        self.assertEqual(len(state.tests), MAX_COLLECTION_SIZE)
        # Most recent items preserved
        self.assertEqual(state.evidence[-1].observation, f"Observation {MAX_COLLECTION_SIZE + 9}")

    def test_null_preservation(self) -> None:
        """Requirement 5 & 10: Verify unobserved/null fields remain distinctly None."""
        state = TaskState()
        self.assertIsNone(state.hypothesis)

        state.add_evidence("Neutral observation", supports_hypothesis=None)
        self.assertIsNone(state.evidence[0].supports_hypothesis)

        d = state.to_dict()
        self.assertIsNone(d["hypothesis"])
        self.assertIsNone(d["evidence"][0]["supports_hypothesis"])

        restored = TaskState.from_dict(d)
        self.assertIsNone(restored.hypothesis)
        self.assertIsNone(restored.evidence[0].supports_hypothesis)

    def test_model_facing_rendering_is_deterministic_and_bounded(self) -> None:
        """Requirement 10 & 11: Verify model context rendering is concise, deterministic, and bounded."""
        state = TaskState(summary="Bug in parameter parsing", hypothesis="Regex lacks boundary anchor")
        state.add_evidence("Test failed with error code 1", "pytest -k test_parse", supports_hypothesis=True)
        state.set_plan(["Add ^ and $ anchors to pattern", "Re-run test_parse"])
        state.add_edit("parser.py", "Updated regex pattern")
        state.add_test("pytest -k test_parse", "PASS", "Assertion ok")

        rendered1 = render_model_context(state)
        rendered2 = render_model_context(state)

        self.assertEqual(rendered1, rendered2, "Rendering must be strictly deterministic")
        self.assertIn("## Active Task State", rendered1)
        self.assertIn("Bug in parameter parsing", rendered1)
        self.assertIn("Regex lacks boundary anchor", rendered1)
        self.assertIn("Supports", rendered1)
        self.assertIn("Add ^ and $ anchors to pattern", rendered1)
        self.assertIn("No-Progress Count: 0", rendered1)

    def test_state_manager_persistence_in_temp_path(self) -> None:
        """Requirement 4: Verify TaskStateManager stores state in isolated temp paths outside /workspace."""
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "test_task_state.json"
            mgr = TaskStateManager(state_file)

            # Initially clean
            state = mgr.load_or_create()
            self.assertEqual(state.summary, "")

            # Mutate and save
            state.summary = "Persisted task summary"
            state.add_candidate("app.py", "main")
            mgr.save(state)
            self.assertTrue(state_file.exists())

            # Reload
            mgr2 = TaskStateManager(state_file)
            loaded = mgr2.load_or_create()
            self.assertEqual(loaded.summary, "Persisted task summary")
            self.assertEqual(len(loaded.candidates), 1)

            # Clear
            mgr2.clear()
            self.assertFalse(state_file.exists())


class TestCandidateE2Integrity(unittest.TestCase):
    """Integrity and isolation tests for candidate E2 and frozen baselines."""

    def test_e0_and_e1_remain_completely_unmodified(self) -> None:
        """Requirement 14 & 15: Verify E0 and E1 input hashes match prior recorded values."""
        self.assertEqual(compute_sha256(E0_YAML_PATH), RECORDED_E0_YAML_SHA)
        self.assertEqual(compute_sha256(E0_PROMPT_PATH), RECORDED_E0_PROMPT_SHA)
        self.assertEqual(compute_sha256(E1_YAML_PATH), RECORDED_E1_YAML_SHA)
        self.assertEqual(compute_sha256(E1_PROMPT_PATH), RECORDED_E1_PROMPT_SHA)

    def test_e2_candidate_parity_with_e1_and_e0(self) -> None:
        """Requirement 13: Verify E2 uses identical model, tools, and generation configuration."""
        self.assertTrue(E2_YAML_PATH.exists())

        e0_text = E0_YAML_PATH.read_text(encoding="utf-8")
        e2_text = E2_YAML_PATH.read_text(encoding="utf-8")

        def extract_field(content: str, key: str) -> str:
            for line in content.splitlines():
                if line.strip().startswith(f"{key}:"):
                    return line.split(f"{key}:", 1)[1].strip()
            return ""

        self.assertEqual(extract_field(e2_text, "model"), "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(extract_field(e0_text, "model"), extract_field(e2_text, "model"))

        # Verify generation parameters are identical
        for param in ["temperature: 0.2", "top_p: 0.95", "max_output_tokens: 16384", "thinking_level: high", "thinking_budget: 4096", "include_thoughts: true"]:
            self.assertIn(param, e2_text)

        # Verify exact same 6 tools
        tools = ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"]
        for tool in tools:
            self.assertIn(f"- {tool}", e2_text)

    def test_prompt_delta_is_strictly_targeted_to_state_continuity(self) -> None:
        """Verify prompt delta from E1 to E2 is strictly limited to state continuity instructions."""
        self.assertTrue(E2_PROMPT_PATH.exists())

        e1_prompt = E1_PROMPT_PATH.read_text(encoding="utf-8")
        e2_prompt = E2_PROMPT_PATH.read_text(encoding="utf-8")

        # State instruction present in E2, absent in E1
        state_directive = "Maintain structured task state across turns to ensure continuity"
        self.assertNotIn(state_directive, e1_prompt)
        self.assertIn(state_directive, e2_prompt)

        # Both contain the root cause hypothesis step from E1
        self.assertIn("Formulate Root Cause Hypothesis", e1_prompt)
        self.assertIn("Formulate Root Cause Hypothesis", e2_prompt)

    def test_e2_manifest_integrity_and_anti_fabrication(self) -> None:
        """Verify E2 manifest records parent linkage, state fields, and null performance metrics."""
        self.assertTrue(E2_MANIFEST_PATH.exists())
        with open(E2_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["candidate_id"], "E2")
        self.assertEqual(manifest["parent_candidate"], "E1")
        self.assertEqual(manifest["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest["validation_status"], "pending_live_inference")
        self.assertEqual(manifest["evidence_status"], "structural_only")

        # Zero fabrication
        self.assertFalse(manifest["benchmark_scores_asserted"])
        self.assertIsNone(manifest["pass_rate"])
        self.assertIsNone(manifest["fail_rate"])

        # Checksum checks
        self.assertEqual(manifest["prompt_sha256"], compute_sha256(E2_PROMPT_PATH))
        self.assertEqual(manifest["agent_config_sha256"], compute_sha256(E2_YAML_PATH))

        # Check all 11 fields declared in manifest
        expected_fields = [
            "summary", "repository_facts", "candidates", "hypothesis",
            "evidence", "plan", "edits", "tests", "failures",
            "no_progress_count", "final_review",
        ]
        self.assertEqual(manifest["exact_fields"], expected_fields)

    def test_e2_runner_and_database_compatibility(self) -> None:
        """Verify E2 candidate is recognized by local runner and can be registered in database."""
        with tempfile.TemporaryDirectory() as td:
            # Runner dry-run
            spec = RunSpec(
                task_id="fastapi_14786",
                candidate_id="E2",
                candidate_dir=E2_CANDIDATE_DIR,
                output_dir=Path(td),
                backend_name="dry-run",
            )
            meta = run_task(spec, Path("data/competition/tasks.jsonl"))
            self.assertEqual(meta.candidate_id, "E2")
            self.assertEqual(meta.status, "dry_run_completed")
            self.assertEqual(meta.model_id, "gemma-4-31b-it-qat-w4a16-ct")

            # Database registration
            db_path = Path(td) / "eval.db"
            init_database(db_path)
            conn = get_connection(db_path)
            cid = ingest_manifest(conn, E2_MANIFEST_PATH)
            self.assertEqual(cid, "E2")
            cands = list_candidates(conn)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["candidate_id"], "E2")
            conn.close()

    def test_no_secret_patch_or_credential_leakage(self) -> None:
        """Requirement 16: Verify no secret competition patches or credentials in E2 artifacts."""
        for path in [E2_YAML_PATH, E2_PROMPT_PATH, E2_MANIFEST_PATH, E2_REPORT_PATH]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("test_patch", content)
            self.assertNotIn("golden_patch", content)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", content)


if __name__ == "__main__":
    unittest.main()
