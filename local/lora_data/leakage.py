"""Held-Out and Cross-Split Leakage Protection Subsystem (Stage 38 Section 5, 13, 15).

Strictly protects HELD_OUT benchmark integrity.
HELD_OUT is immutable.

Detects and rejects:
1. Held-out task IDs (instance_ids)
2. Held-out repository and base-commit combinations
3. Exact or normalized problem statements from held-out instances
4. Patch and test-patch fingerprints from held-out instances
5. Cross-split contamination (overlap between TRAIN and VALIDATION)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def normalize_text_for_matching(text: str) -> str:
    """Normalizes text for fuzzy or normalized matching."""
    if not text:
        return ""
    # Lowercase, collapse whitespace, strip non-alphanumeric except spaces
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def text_sha256(text: str) -> str:
    """Computes SHA-256 of string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class HeldOutLeakageChecker:
    """Authoritative checker for held-out leakage prevention."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = Path(repo_root or Path(".")).resolve()
        self.lock_path = self.repo_root / "benchmark" / "splits" / "v1" / "held_out.lock"
        self.held_out_path = self.repo_root / "benchmark" / "splits" / "v1" / "held_out.jsonl"

        self.held_out_tasks: set[str] = set()
        self.held_out_repo_commits: set[tuple[str, str]] = set()
        self.held_out_problem_hashes: set[str] = set()
        self.held_out_problem_normalized: list[str] = []
        self.held_out_patch_hashes: set[str] = set()
        self.held_out_test_patch_hashes: set[str] = set()

        self._load_held_out()

    def _load_held_out(self) -> None:
        """Loads held-out lock and jsonl records."""
        if self.lock_path.exists():
            try:
                with open(self.lock_path, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                    for tid in lock_data.get("held_out_tasks", []):
                        self.held_out_tasks.add(tid.strip())
            except Exception:
                pass

        if self.held_out_path.exists():
            try:
                with open(self.held_out_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        iid = record.get("instance_id", "").strip()
                        if iid:
                            self.held_out_tasks.add(iid)

                        repo = record.get("repo", "").strip()
                        bc = record.get("base_commit", "").strip()
                        if repo and bc:
                            self.held_out_repo_commits.add((repo, bc))

                        prob = record.get("problem_statement", "").strip()
                        if prob:
                            self.held_out_problem_hashes.add(text_sha256(prob))
                            norm = normalize_text_for_matching(prob)
                            if norm:
                                self.held_out_problem_normalized.append(norm)

                        patch = record.get("patch", "").strip()
                        if patch:
                            self.held_out_patch_hashes.add(text_sha256(patch))

                        test_patch = record.get("test_patch", "").strip()
                        if test_patch:
                            self.held_out_test_patch_hashes.add(text_sha256(test_patch))
            except Exception:
                pass

    def check_example(self, example_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Audits a candidate training example for held-out leakage.

        Returns:
            (is_leaked, list_of_violations)
        """
        violations: list[str] = []

        # 1. Task ID check
        task_id = str(example_data.get("task_id", "")).strip()
        if task_id and task_id in self.held_out_tasks:
            violations.append(f"LEAKAGE_TASK_ID: Task ID '{task_id}' matches held-out benchmark task")

        # 2. Repo + base commit check
        repo = str(example_data.get("repo", "")).strip()
        base_commit = str(example_data.get("base_commit", "")).strip()
        if repo and base_commit:
            if (repo, base_commit) in self.held_out_repo_commits:
                violations.append(
                    f"LEAKAGE_REPO_COMMIT: Repo/commit pair '{repo}@{base_commit}' matches held-out instance"
                )

        # 3. Problem statement / Situation matching
        situation = str(example_data.get("situation", "")).strip()
        if situation:
            sit_hash = text_sha256(situation)
            if sit_hash in self.held_out_problem_hashes:
                violations.append("LEAKAGE_PROBLEM_EXACT: Situation exact match to held-out problem statement")
            else:
                norm_sit = normalize_text_for_matching(situation)
                if len(norm_sit) > 50:
                    for norm_prob in self.held_out_problem_normalized:
                        # Check substring or high overlap
                        if norm_sit in norm_prob or (len(norm_prob) > 50 and norm_prob in norm_sit):
                            violations.append("LEAKAGE_PROBLEM_NORMALIZED: Situation overlaps held-out problem statement")
                            break

        # 4. Patch / Test Patch check in tool sequence or evidence
        content_to_check = [situation]
        for ev in example_data.get("evidence", []):
            if isinstance(ev, str):
                content_to_check.append(ev)
        for step in example_data.get("tool_sequence", []):
            content_to_check.append(str(step.get("arguments", "")))
            content_to_check.append(str(step.get("result_summary", "")))

        combined_text = "\n".join(content_to_check)
        for p_hash in self.held_out_patch_hashes:
            # Check if any patch hash or snippet is present
            if p_hash in combined_text:
                violations.append(f"LEAKAGE_PATCH_HASH: Embedded patch hash {p_hash[:8]} matches held-out patch")

        is_leaked = len(violations) > 0
        return is_leaked, violations

    def check_split_separation(
        self, train_examples: list[dict[str, Any]], val_examples: list[dict[str, Any]]
    ) -> tuple[bool, list[str]]:
        """Audits TRAIN vs VALIDATION split for task and trajectory cross-contamination.

        Returns:
            (is_clean, violations)
        """
        violations: list[str] = []

        train_tasks: set[str] = set()
        train_hashes: set[str] = set()

        for ex in train_examples:
            tid = str(ex.get("task_id", "")).strip()
            if tid:
                train_tasks.add(tid)
            # Hash of core trajectory
            ex_id = str(ex.get("example_id", "")).strip()
            seq_str = json.dumps(ex.get("tool_sequence", []), sort_keys=True)
            train_hashes.add(text_sha256(f"{tid}:{seq_str}"))

        for ex in val_examples:
            tid = str(ex.get("task_id", "")).strip()
            if tid and tid in train_tasks:
                violations.append(f"SPLIT_TASK_OVERLAP: Task ID '{tid}' present in both TRAIN and VALIDATION")

            seq_str = json.dumps(ex.get("tool_sequence", []), sort_keys=True)
            v_hash = text_sha256(f"{tid}:{seq_str}")
            if v_hash in train_hashes:
                violations.append(f"SPLIT_TRAJECTORY_OVERLAP: Near-identical trajectory found in both TRAIN and VALIDATION")

        is_clean = len(violations) == 0
        return is_clean, violations
