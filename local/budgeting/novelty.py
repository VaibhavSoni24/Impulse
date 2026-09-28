"""Deterministic information-gain and evidence novelty assessment (Stage 26).

Computes information value without hindsight bias:
Measures empirical novelty at the moment of tool execution against accumulated
task evidence history (file content, symbols, search items, test results, failure classes).
"""

from __future__ import annotations

import hashlib
from typing import Any

from local.budgeting.models import EvidenceNovelty, InformationValue
from local.context_compaction.fingerprints import compute_content_sha256, normalize_path


class EvidenceHistoryTracker:
    """Maintains empirical observation history for a task run to calculate information novelty.
    
    Guarantees:
    - Purely deterministic; no LLM-based estimation.
    - Evaluates newness across 8 distinct evidence dimensions.
    """

    def __init__(self) -> None:
        # path -> set of observed content hashes
        self._observed_file_hashes: dict[str, set[str]] = {}
        # set of observed symbol identifiers (graph retrieval)
        self._observed_symbols: set[str] = set()
        # set of observed relation identifiers (graph retrieval)
        self._observed_relations: set[str] = set()
        # set of observed search result item identities
        self._observed_search_items: set[str] = set()
        # command -> last (exit_code, tuple(failing_tests), error_signature)
        self._observed_test_signatures: dict[str, tuple[int, tuple[str, ...], str]] = {}
        # last observed repo status digest
        self._last_repo_status_digest: str | None = None
        # set of observed failure classes
        self._observed_failure_classes: set[str] = set()
        # active hypothesis string
        self._active_hypothesis: str | None = None

    def evaluate_file_read(
        self,
        path: str,
        content: str | bytes,
    ) -> InformationValue:
        """Evaluates novelty of a file read observation."""
        norm_p = normalize_path(path)
        content_hash = compute_content_sha256(content)

        is_new_path = norm_p not in self._observed_file_hashes
        seen_hashes = self._observed_file_hashes.setdefault(norm_p, set())
        is_new_hash = content_hash not in seen_hashes

        new_files = 1 if is_new_path else 0
        changed_files = 1 if (not is_new_path and is_new_hash) else 0

        seen_hashes.add(content_hash)

        if is_new_path or is_new_hash:
            return InformationValue(
                evidence_units_new=1,
                evidence_units_total=1,
                novelty_ratio=1.0,
                novelty_class=EvidenceNovelty.NEW_EVIDENCE,
                new_files_count=new_files,
                changed_files_count=changed_files,
            )
        else:
            return InformationValue(
                evidence_units_new=0,
                evidence_units_total=1,
                novelty_ratio=0.0,
                novelty_class=EvidenceNovelty.NO_NEW_EVIDENCE,
            )

    def evaluate_status_observation(
        self,
        status_text: str,
    ) -> InformationValue:
        """Evaluates novelty of repository status / tree output."""
        status_digest = compute_content_sha256(status_text)
        is_new = self._last_repo_status_digest != status_digest
        self._last_repo_status_digest = status_digest

        if is_new:
            return InformationValue(
                evidence_units_new=1,
                evidence_units_total=1,
                novelty_ratio=1.0,
                novelty_class=EvidenceNovelty.NEW_EVIDENCE,
            )
        else:
            return InformationValue(
                evidence_units_new=0,
                evidence_units_total=1,
                novelty_ratio=0.0,
                novelty_class=EvidenceNovelty.NO_NEW_EVIDENCE,
            )

    def evaluate_graph_retrieval(
        self,
        symbols: list[str],
        relations: list[str] | None = None,
    ) -> InformationValue:
        """Evaluates novelty of code neighbor or subgraph retrieval."""
        rel_list = relations or []
        new_syms = 0
        for s in symbols:
            s_clean = s.strip()
            if s_clean and s_clean not in self._observed_symbols:
                self._observed_symbols.add(s_clean)
                new_syms += 1

        new_rels = 0
        for r in rel_list:
            r_clean = r.strip()
            if r_clean and r_clean not in self._observed_relations:
                self._observed_relations.add(r_clean)
                new_rels += 1

        total_items = max(len(symbols) + len(rel_list), 1)
        new_items = new_syms + new_rels
        ratio = new_items / total_items

        if new_items == total_items and new_items > 0:
            n_class = EvidenceNovelty.NEW_EVIDENCE
        elif new_items > 0:
            n_class = EvidenceNovelty.PARTIAL_NEW_EVIDENCE
        else:
            n_class = EvidenceNovelty.NO_NEW_EVIDENCE

        return InformationValue(
            evidence_units_new=new_items,
            evidence_units_total=total_items,
            novelty_ratio=round(ratio, 3),
            novelty_class=n_class,
            new_symbols_count=new_syms,
            new_relations_count=new_rels,
        )

    def evaluate_search_results(
        self,
        candidate_ids: list[str],
    ) -> InformationValue:
        """Evaluates novelty of semantic code search results."""
        new_items = 0
        for cid in candidate_ids:
            c_clean = cid.strip()
            if c_clean and c_clean not in self._observed_search_items:
                self._observed_search_items.add(c_clean)
                new_items += 1

        total_items = max(len(candidate_ids), 1)
        ratio = new_items / total_items

        if new_items == total_items and new_items > 0:
            n_class = EvidenceNovelty.NEW_EVIDENCE
        elif new_items > 0:
            n_class = EvidenceNovelty.PARTIAL_NEW_EVIDENCE
        else:
            n_class = EvidenceNovelty.NO_NEW_EVIDENCE

        return InformationValue(
            evidence_units_new=new_items,
            evidence_units_total=total_items,
            novelty_ratio=round(ratio, 3),
            novelty_class=n_class,
        )

    def evaluate_test_execution(
        self,
        command: str,
        exit_code: int,
        failing_tests: list[str] | None = None,
        error_signature: str = "",
        failure_class: str | None = None,
    ) -> InformationValue:
        """Evaluates novelty of a test command execution."""
        clean_cmd = command.strip()
        fails_tuple = tuple(sorted(failing_tests or []))
        clean_sig = error_signature.strip()
        current_sig = (exit_code, fails_tuple, clean_sig)

        prev_sig = self._observed_test_signatures.get(clean_cmd)
        self._observed_test_signatures[clean_cmd] = current_sig

        is_new_result = prev_sig != current_sig
        new_tests = 1 if is_new_result else 0

        # Check failure class novelty
        new_fc = 0
        if failure_class:
            clean_fc = failure_class.strip().upper()
            if clean_fc not in self._observed_failure_classes:
                self._observed_failure_classes.add(clean_fc)
                new_fc = 1

        new_units = (1 if is_new_result else 0) + new_fc
        total_units = 1 + (1 if failure_class else 0)
        ratio = new_units / max(total_units, 1)

        if new_units == total_units and new_units > 0:
            n_class = EvidenceNovelty.NEW_EVIDENCE
        elif new_units > 0:
            n_class = EvidenceNovelty.PARTIAL_NEW_EVIDENCE
        else:
            n_class = EvidenceNovelty.NO_NEW_EVIDENCE

        return InformationValue(
            evidence_units_new=new_units,
            evidence_units_total=total_units,
            novelty_ratio=round(ratio, 3),
            novelty_class=n_class,
            new_test_results_count=new_tests,
            new_failure_signatures_count=new_fc,
            recovery_relevant=(new_fc > 0 or is_new_result),
        )

    def evaluate_mutation(
        self,
        path: str,
        new_content: str | bytes,
    ) -> InformationValue:
        """Mutations (edit_file, write_file) generate new repository state."""
        norm_p = normalize_path(path)
        content_hash = compute_content_sha256(new_content)
        seen_hashes = self._observed_file_hashes.setdefault(norm_p, set())
        is_new = content_hash not in seen_hashes
        seen_hashes.add(content_hash)

        # Invalidate last repo status digest since file mutated
        self._last_repo_status_digest = None

        return InformationValue(
            evidence_units_new=1 if is_new else 0,
            evidence_units_total=1,
            novelty_ratio=1.0 if is_new else 0.0,
            novelty_class=EvidenceNovelty.NEW_EVIDENCE if is_new else EvidenceNovelty.NO_NEW_EVIDENCE,
            changed_files_count=1 if is_new else 0,
        )
