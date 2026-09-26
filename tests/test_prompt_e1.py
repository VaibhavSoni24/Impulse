"""Tests for Stage 10 Prompt Candidate IMPULSE-E1."""

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

E0_YAML_PATH = Path("agent/agent.yaml")
E0_PROMPT_PATH = Path("agent/prompts/root.md")

E1_CANDIDATE_DIR = Path("experiments/candidates/E1")
E1_YAML_PATH = E1_CANDIDATE_DIR / "agent.yaml"
E1_PROMPT_PATH = E1_CANDIDATE_DIR / "prompts/root.md"

E1_EXP_DIR = Path("experiments/prompts/E1")
E1_CANONICAL_PROMPT_PATH = E1_EXP_DIR / "root.md"
E1_MANIFEST_PATH = E1_EXP_DIR / "manifest.json"
E1_REPORT_PATH = E1_EXP_DIR / "report.md"

EXPECTED_E0_YAML_SHA = "617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261"
EXPECTED_E0_PROMPT_SHA = "62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431"


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestPromptCandidateE1(unittest.TestCase):
    """Validates structural correctness, baseline isolation, and anti-fabrication for E1."""

    def test_e0_files_frozen_and_hashes_match_stage8(self) -> None:
        """Verifies E0 files remain completely untouched and match Stage 8 recorded hashes."""
        self.assertTrue(E0_YAML_PATH.exists())
        self.assertTrue(E0_PROMPT_PATH.exists())

        actual_yaml_sha = compute_sha256(E0_YAML_PATH)
        actual_prompt_sha = compute_sha256(E0_PROMPT_PATH)

        self.assertEqual(
            actual_yaml_sha,
            EXPECTED_E0_YAML_SHA,
            "E0 agent.yaml hash must match Stage 8 recorded hash",
        )
        self.assertEqual(
            actual_prompt_sha,
            EXPECTED_E0_PROMPT_SHA,
            "E0 root.md hash must match Stage 8 recorded hash",
        )

    def test_e1_candidate_configuration_parity_with_e0(self) -> None:
        """Verifies E1 agent.yaml has identical model, tools, and generation parameters to E0."""
        self.assertTrue(E1_YAML_PATH.exists())

        e0_text = E0_YAML_PATH.read_text(encoding="utf-8")
        e1_text = E1_YAML_PATH.read_text(encoding="utf-8")

        # Parse basic fields
        def extract_field(content: str, key: str) -> str:
            for line in content.splitlines():
                if line.strip().startswith(f"{key}:"):
                    return line.split(f"{key}:", 1)[1].strip()
            return ""

        self.assertEqual(
            extract_field(e0_text, "model"),
            extract_field(e1_text, "model"),
            "Model ID must be identical across E0 and E1",
        )
        self.assertEqual(extract_field(e1_text, "model"), "gemma-4-31b-it-qat-w4a16-ct")

        # Verify generation config parameters are identical
        for param in ["temperature: 0.2", "top_p: 0.95", "max_output_tokens: 16384", "thinking_level: high", "thinking_budget: 4096", "include_thoughts: true"]:
            self.assertIn(param, e0_text)
            self.assertIn(param, e1_text)

        # Verify exact same tools declared
        tools = ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"]
        for tool in tools:
            self.assertIn(f"- {tool}", e0_text)
            self.assertIn(f"- {tool}", e1_text)

    def test_prompt_delta_is_strictly_targeted(self) -> None:
        """Verifies the single prompt intervention in E1 is the pre-edit hypothesis requirement."""
        self.assertTrue(E1_PROMPT_PATH.exists())
        self.assertTrue(E1_CANONICAL_PROMPT_PATH.exists())

        # Candidate prompt and canonical prompt record must be identical
        self.assertEqual(
            compute_sha256(E1_PROMPT_PATH),
            compute_sha256(E1_CANONICAL_PROMPT_PATH),
        )

        e0_prompt = E0_PROMPT_PATH.read_text(encoding="utf-8")
        e1_prompt = E1_PROMPT_PATH.read_text(encoding="utf-8")

        # E1 must contain the targeted Step 5
        target_intervention = "Formulate Root Cause Hypothesis"
        self.assertNotIn(target_intervention, e0_prompt)
        self.assertIn(target_intervention, e1_prompt)
        self.assertIn("Before applying any code modifications, articulate an explicit, evidence-backed hypothesis", e1_prompt)

    def test_e1_manifest_integrity_and_anti_fabrication(self) -> None:
        """Verifies manifest.json records factual metadata, hashes, and no fabricated metrics."""
        self.assertTrue(E1_MANIFEST_PATH.exists())
        with open(E1_MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["candidate_id"], "E1")
        self.assertEqual(manifest["parent_candidate"], "E0")
        self.assertEqual(
            manifest["parent_git_commit"],
            "99c0da320af4940f4eca27d172592d1ed706d26f",
        )
        self.assertEqual(manifest["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest["validation_status"], "pending_live_inference")
        self.assertEqual(manifest["evidence_status"], "hypothesis_only")

        # Zero fabrication
        self.assertFalse(manifest["benchmark_scores_asserted"])
        self.assertIsNone(manifest["pass_rate"])
        self.assertIsNone(manifest["fail_rate"])

        # Cryptographic hash verification
        self.assertEqual(manifest["prompt_sha256"], compute_sha256(E1_PROMPT_PATH))
        self.assertEqual(manifest["agent_config_sha256"], compute_sha256(E1_YAML_PATH))

    def test_e1_runner_and_database_compatibility(self) -> None:
        """Verifies candidate E1 is accepted by local runner and can be registered in database."""
        with tempfile.TemporaryDirectory() as td:
            # Runner test (dry-run)
            spec = RunSpec(
                task_id="fastapi_14786",
                candidate_id="E1",
                candidate_dir=E1_CANDIDATE_DIR,
                output_dir=Path(td),
                backend_name="dry-run",
            )
            meta = run_task(spec, Path("data/competition/tasks.jsonl"))
            self.assertEqual(meta.candidate_id, "E1")
            self.assertEqual(meta.status, "dry_run_completed")
            self.assertEqual(meta.model_id, "gemma-4-31b-it-qat-w4a16-ct")

            # Database test (manifest ingestion)
            db_path = Path(td) / "eval.db"
            init_database(db_path)
            conn = get_connection(db_path)
            cid = ingest_manifest(conn, E1_MANIFEST_PATH)
            self.assertEqual(cid, "E1")
            cands = list_candidates(conn)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["candidate_id"], "E1")
            conn.close()

    def test_report_md_exists_and_contains_required_sections(self) -> None:
        """Verifies E1 report.md documents hypothesis, prompt delta, and evidence boundaries."""
        self.assertTrue(E1_REPORT_PATH.exists())
        content = E1_REPORT_PATH.read_text(encoding="utf-8")

        self.assertIn("EXP-PROMPT-E1", content)
        self.assertIn("gemma-4-31b-it-qat-w4a16-ct", content)
        self.assertIn("Hypothesis Only", content)
        self.assertIn("Formulate Root Cause Hypothesis", content)
        self.assertIn("No conclusion regarding E1 superiority", content)

    def test_no_secret_patch_or_credential_leakage(self) -> None:
        """Verifies no forbidden competition secrets or test patches were copied into E1."""
        for path in [E1_YAML_PATH, E1_PROMPT_PATH, E1_CANONICAL_PROMPT_PATH, E1_MANIFEST_PATH, E1_REPORT_PATH]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("test_patch", content)
            self.assertNotIn("golden_patch", content)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", content)


if __name__ == "__main__":
    unittest.main()
