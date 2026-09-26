"""Unit tests validating the initial smoke benchmark set (smoke.jsonl)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

SMOKE_FILE = Path("benchmark/tasks/smoke.jsonl")
SOURCE_FILE = Path("data/competition/tasks.jsonl")

EXPECTED_CATEGORIES = {
    "easy_localization",
    "multi_file",
    "test_driven",
    "misleading_surface_symptom",
    "graph_retrieval_candidate",
}


class TestSmokeBenchmarkSet(unittest.TestCase):
    """Validation test suite for benchmark/tasks/smoke.jsonl."""

    def setUp(self) -> None:
        self.assertTrue(SMOKE_FILE.exists(), f"Smoke file missing: {SMOKE_FILE}")
        self.assertTrue(SOURCE_FILE.exists(), f"Source tasks missing: {SOURCE_FILE}")

        self.records: list[dict] = []
        with open(SMOKE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    self.records.append(json.loads(stripped))

        self.source_tasks: dict[str, dict] = {}
        with open(SOURCE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    item = json.loads(stripped)
                    self.source_tasks[item["instance_id"]] = item

    def test_record_count(self) -> None:
        self.assertEqual(len(self.records), 5, "Smoke set must contain exactly 5 tasks.")

    def test_unique_instance_ids(self) -> None:
        ids = [r["instance_id"] for r in self.records]
        self.assertEqual(len(ids), len(set(ids)), "Task IDs in smoke set must be unique.")

    def test_all_tasks_exist_in_source(self) -> None:
        for r in self.records:
            iid = r["instance_id"]
            self.assertIn(iid, self.source_tasks, f"Task '{iid}' not in competition tasks.jsonl.")
            self.assertEqual(r["repo"], self.source_tasks[iid]["repo"])
            self.assertEqual(r["base_commit"], self.source_tasks[iid]["base_commit"])

    def test_categories_and_rationales(self) -> None:
        found_categories = {r["category"] for r in self.records}
        self.assertEqual(
            found_categories,
            EXPECTED_CATEGORIES,
            f"Categories must match {EXPECTED_CATEGORIES}.",
        )
        for r in self.records:
            self.assertGreater(
                len(r.get("selection_rationale", "")),
                20,
                f"Selection rationale too brief for {r['instance_id']}.",
            )

    def test_no_solution_leakage(self) -> None:
        for r in self.records:
            self.assertNotIn("patch", r, f"Forbidden 'patch' field found in {r['instance_id']}")
            self.assertNotIn(
                "test_patch", r, f"Forbidden 'test_patch' field found in {r['instance_id']}"
            )

    def test_documentation_code_fences(self) -> None:
        doc_path = Path("docs/decisions/smoke_benchmark.md")
        self.assertTrue(doc_path.exists())
        doc_content = doc_path.read_text(encoding="utf-8")
        fences = [l for l in doc_content.splitlines() if l.strip().startswith("```")]
        self.assertEqual(len(fences) % 2, 0, "Code fences in smoke_benchmark.md must be balanced.")


if __name__ == "__main__":
    unittest.main()
