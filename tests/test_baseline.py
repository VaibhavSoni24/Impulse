"""Integrity tests for Stage 8 E0 baseline evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest

BASELINE_DIR = Path("experiments/baseline/E0")
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
RESULTS_PATH = BASELINE_DIR / "results.jsonl"
REPORT_PATH = BASELINE_DIR / "report.md"
SMOKE_TASKS_PATH = Path("benchmark/tasks/smoke.jsonl")

SHA256_REGEX = re.compile(r"^[a-f0-9]{64}$")


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 digest of a given file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestBaselineArtifacts(unittest.TestCase):
    """Validates structure, integrity, and anti-fabrication rules for E0 artifacts."""

    def test_manifest_structure_and_hashes(self) -> None:
        """Verifies manifest.json exists, parses cleanly, and records factual hashes."""
        self.assertTrue(MANIFEST_PATH.exists(), f"Missing manifest: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("candidate_id"), "E0")
        self.assertEqual(manifest.get("git_tag"), "E0-baseline")
        self.assertEqual(
            manifest.get("git_commit"),
            "99c0da320af4940f4eca27d172592d1ed706d26f",
        )
        self.assertEqual(manifest.get("model_id"), "gemma-4-31b-it-qat-w4a16-ct")
        self.assertEqual(manifest.get("smoke_tasks_count"), 5)
        self.assertEqual(manifest.get("total_development_tasks"), 129)

        # Anti-fabrication assertions
        self.assertFalse(manifest.get("benchmark_scores_asserted"))
        self.assertIsNone(manifest.get("pass_rate"))
        self.assertIsNone(manifest.get("fail_rate"))
        self.assertEqual(manifest.get("execution_status"), "execution_unavailable_local_host")

        # Verify cryptographic checksums against live filesystem
        agent_config_path = Path(manifest["agent_config_reference"])
        self.assertTrue(agent_config_path.exists())
        self.assertEqual(
            manifest["agent_config_sha256"],
            compute_file_sha256(agent_config_path),
        )

        prompt_path = Path(manifest["prompt_reference"])
        self.assertTrue(prompt_path.exists())
        self.assertEqual(
            manifest["prompt_sha256"],
            compute_file_sha256(prompt_path),
        )

        smoke_path = Path(manifest["smoke_benchmark_path"])
        self.assertTrue(smoke_path.exists())
        self.assertEqual(
            manifest["smoke_benchmark_sha256"],
            compute_file_sha256(smoke_path),
        )

        dev_tasks_path = Path(manifest["development_tasks_manifest_path"])
        self.assertTrue(dev_tasks_path.exists())
        self.assertEqual(
            manifest["development_tasks_manifest_sha256"],
            compute_file_sha256(dev_tasks_path),
        )

    def test_results_jsonl_integrity_and_anti_fabrication(self) -> None:
        """Verifies results.jsonl contains 5 smoke task records with strict null metrics."""
        self.assertTrue(RESULTS_PATH.exists(), f"Missing results: {RESULTS_PATH}")

        # Extract expected smoke task IDs
        with open(SMOKE_TASKS_PATH, "r", encoding="utf-8") as f:
            expected_ids = [
                json.loads(line)["instance_id"] for line in f if line.strip()
            ]

        self.assertEqual(len(expected_ids), 5)

        recorded_records: list[dict] = []
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                recorded_records.append(json.loads(stripped))

        self.assertEqual(len(recorded_records), 5)
        recorded_ids = [r["task_id"] for r in recorded_records]
        self.assertEqual(recorded_ids, expected_ids)

        for record in recorded_records:
            self.assertEqual(record["candidate_id"], "E0")
            self.assertEqual(record["model_id"], "gemma-4-31b-it-qat-w4a16-ct")
            self.assertEqual(record["execution_backend"], "local-unavailable")
            self.assertEqual(record["status"], "execution_unavailable_local_host")
            self.assertFalse(record["inference_executed"])
            self.assertFalse(record["verification_executed"])
            self.assertFalse(record["patch_generated"])

            # Critical anti-fabrication assertions: metrics MUST be null, not 0 or fabricated
            self.assertIsNone(
                record["resolved"],
                "resolved must be null when inference was not executed",
            )
            self.assertIsNone(
                record["tool_calls"],
                "tool_calls must be null when inference was not executed",
            )
            self.assertIsNone(
                record["turns"],
                "turns must be null when inference was not executed",
            )
            self.assertIsNone(record["files_read"])
            self.assertIsNone(record["files_changed"])
            self.assertIsNone(record["diff_bytes"])

            # Verify no golden solution or secret test patch is leaked
            self.assertNotIn("test_patch", record)
            self.assertNotIn("patch_data", record)

    def test_report_md_completeness(self) -> None:
        """Verifies report.md exists and covers all required sections."""
        self.assertTrue(REPORT_PATH.exists(), f"Missing report: {REPORT_PATH}")
        content = REPORT_PATH.read_text(encoding="utf-8")

        self.assertIn("gemma-4-31b-it-qat-w4a16-ct", content)
        self.assertIn("99c0da320af4940f4eca27d172592d1ed706d26f", content)
        self.assertIn("E0-baseline", content)
        self.assertIn("FROZEN", content)
        self.assertIn("Zero Fabrication", content)
        self.assertIn("local-unavailable", content)
        self.assertIn("NVIDIA L4", content)


if __name__ == "__main__":
    unittest.main()
