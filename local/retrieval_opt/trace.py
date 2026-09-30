"""Retrieval Trace Logging and Diagnostics Engine (Stage 33 Sections 13, 21, 26, 30).

Provides:
- Structured event logging (RetrievalEvent, DynamicRoundTrace)
- Bounded cache accounting (Stage 26 BoundedToolCache integration)
- Anomaly and pathology detection (redundancy, dead retrieval, over-expansion,
  late retrieval, misleading retrieval)
- Information-gain approximation tracking
- JSONL persistence and serialization
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from local.retrieval_opt.models import (
    DynamicRoundTrace,
    RetrievalDiagnostics,
    RetrievalEvent,
    RetrievalType,
)


class RetrievalTraceCollector:
    """Collects, analyzes, and serializes retrieval traces for a candidate run."""

    def __init__(self, candidate_id: str = "R0") -> None:
        self.candidate_id = candidate_id
        self.events: List[RetrievalEvent] = []
        self.dynamic_rounds: List[DynamicRoundTrace] = []
        self._inspected_entities: Set[str] = set()
        self._seen_queries: Set[str] = set()
        self._seen_entities: Set[str] = set()
        self._file_edit_occurred: bool = False

    def record_file_edit(self) -> None:
        """Notifies the collector that an edit mutation has occurred (for late-retrieval detection)."""
        self._file_edit_occurred = True

    def mark_entity_inspected(self, entity: str) -> None:
        """Marks a repository symbol or file path as inspected by the agent."""
        if entity:
            self._inspected_entities.add(entity.strip())

    def mark_inspected_entities(self, entities: List[str]) -> None:
        """Marks multiple entities as inspected."""
        for e in entities:
            self.mark_entity_inspected(e)

    def record_dynamic_round(self, round_trace: DynamicRoundTrace) -> None:
        """Records an R4 dynamic retrieval round trace."""
        self.dynamic_rounds.append(round_trace)

    def record_event(
        self,
        event: RetrievalEvent,
    ) -> RetrievalEvent:
        """Records a structured retrieval event and updates audit state."""
        # Check query redundancy
        norm_query = event.query.strip().lower()
        if norm_query and norm_query in self._seen_queries:
            event.duplicate_count += 1
        elif norm_query:
            self._seen_queries.add(norm_query)

        # Track entities
        unique_nodes = 0
        duplicate_nodes = 0
        for ent in event.returned_entities:
            clean_ent = ent.strip()
            if clean_ent in self._seen_entities:
                duplicate_nodes += 1
            else:
                unique_nodes += 1
                self._seen_entities.add(clean_ent)

        if event.unique_returned_count == 0 and event.returned_entities:
            event.unique_returned_count = unique_nodes
            event.duplicate_count += duplicate_nodes

        # Note late retrieval if edit has already occurred
        if self._file_edit_occurred:
            event.metadata["late_retrieval"] = True

        self.events.append(event)
        return event

    def compute_diagnostics(self) -> RetrievalDiagnostics:
        """Analyzes recorded events and detects retrieval pathologies (Section 26)."""
        diag = RetrievalDiagnostics()

        for event in self.events:
            # 1. Redundancy (duplicate query or duplicate entities)
            if event.duplicate_count > 0:
                diag.redundancy_count += event.duplicate_count
                diag.diagnostic_messages.append(
                    f"Task {event.task_id} turn {event.turn}: {event.duplicate_count} duplicate entities/queries in {event.retrieval_type}."
                )

            # 2. Dead retrieval (returned entities never inspected)
            if event.returned_entities:
                uninspected = [
                    ent for ent in event.returned_entities
                    if ent.strip() not in self._inspected_entities
                ]
                if len(uninspected) == len(event.returned_entities):
                    diag.dead_retrieval_count += 1
                    diag.diagnostic_messages.append(
                        f"Task {event.task_id} turn {event.turn}: All {len(uninspected)} entities from {event.retrieval_type} remained uninspected."
                    )

            # 3. Over-expansion (large returned set > 8, but inspected <= 1)
            if event.returned_count >= 8:
                inspected_from_event = [
                    ent for ent in event.returned_entities
                    if ent.strip() in self._inspected_entities
                ]
                if len(inspected_from_event) <= 1:
                    diag.over_expansion_count += 1
                    diag.diagnostic_messages.append(
                        f"Task {event.task_id} turn {event.turn}: Over-expansion in {event.retrieval_type} (returned {event.returned_count}, inspected {len(inspected_from_event)})."
                    )

            # 4. Late retrieval
            if event.metadata.get("late_retrieval", False):
                diag.late_retrieval_count += 1
                diag.diagnostic_messages.append(
                    f"Task {event.task_id} turn {event.turn}: Late retrieval executed after file modification."
                )

            # 5. Misleading retrieval
            if event.metadata.get("misleading_retrieval", False):
                diag.misleading_retrieval_count += 1
                diag.diagnostic_messages.append(
                    f"Task {event.task_id} turn {event.turn}: Misleading retrieval diverted localization away from target."
                )

        return diag

    def save_jsonl(self, file_path: Path | str) -> None:
        """Saves recorded events to JSONL."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for ev in self.events:
                f.write(json.dumps(ev.to_dict(), sort_keys=True) + "\n")

    @classmethod
    def load_jsonl(cls, file_path: Path | str) -> List[RetrievalEvent]:
        """Loads retrieval events from a JSONL file."""
        p = Path(file_path)
        if not p.is_file():
            return []
        events: List[RetrievalEvent] = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(RetrievalEvent.from_dict(json.loads(line)))
        return events
