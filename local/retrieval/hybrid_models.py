"""Data models and representations for the Hybrid Localization Policy (Stage 15)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LocalizationAction(str, Enum):
    """Possible localization operations evaluated by the hybrid controller."""

    EXACT_SEARCH = "EXACT_SEARCH"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    INSPECT_SOURCE = "INSPECT_SOURCE"
    GRAPH_NEIGHBORS = "GRAPH_NEIGHBORS"
    SUBGRAPH = "SUBGRAPH"
    STOP_RETRIEVAL = "STOP_RETRIEVAL"


class DecisionState(str, Enum):
    """Explicit decision states governing the hybrid localization policy transitions."""

    EXACT_STRONG = "EXACT_STRONG"
    EXACT_AMBIGUOUS = "EXACT_AMBIGUOUS"
    SEMANTIC_NEEDED = "SEMANTIC_NEEDED"
    PROMISING_SYMBOL_FOUND = "PROMISING_SYMBOL_FOUND"
    RELATIONSHIP_NEEDED = "RELATIONSHIP_NEEDED"
    MULTI_SYMBOL_INTERACTION = "MULTI_SYMBOL_INTERACTION"
    SOURCE_SUFFICIENT = "SOURCE_SUFFICIENT"
    RETRIEVAL_BUDGET_EXHAUSTED = "RETRIEVAL_BUDGET_EXHAUSTED"
    NON_LOCALIZATION_PHASE = "NON_LOCALIZATION_PHASE"


@dataclass
class HybridReconContext:
    """Consolidated reconnaissance context evaluated by HybridLocalizationPolicy."""

    phase: str = "localization"  # "localization", "edit", "verify", "review"
    exact_matches_found: int = 0
    has_subsystem_ambiguity: bool = False
    exact_terms_mismatch: bool = False
    text_search_weak: bool = False
    candidate_symbols: list[str] = field(default_factory=list)
    inspected_symbols: set[str] = field(default_factory=set)
    promising_symbol: str | None = None
    needs_relationship_exploration: bool = False
    spans_multiple_symbols: bool = False
    direct_source_sufficient: bool = False
    single_neighbor_sufficient: bool = False


@dataclass
class HybridDecisionRecord:
    """Lightweight, auditable decision record for a hybrid localization decision."""

    action: LocalizationAction
    state: DecisionState
    reason: str
    candidate_count: int = 0
    inspected_candidate_count: int = 0
    evidence_sufficient: bool = False
    previous_action: LocalizationAction | None = None
    semantic_calls: int = 0
    neighbor_calls: int = 0
    subgraph_calls: int = 0
    total_calls: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Converts the record into a JSON-serializable dictionary."""
        return {
            "action": self.action.value if isinstance(self.action, LocalizationAction) else str(self.action),
            "state": self.state.value if isinstance(self.state, DecisionState) else str(self.state),
            "reason": self.reason,
            "candidate_count": self.candidate_count,
            "inspected_candidate_count": self.inspected_candidate_count,
            "evidence_sufficient": self.evidence_sufficient,
            "previous_action": (
                self.previous_action.value
                if isinstance(self.previous_action, LocalizationAction)
                else (str(self.previous_action) if self.previous_action is not None else None)
            ),
            "semantic_calls": self.semantic_calls,
            "neighbor_calls": self.neighbor_calls,
            "subgraph_calls": self.subgraph_calls,
            "total_calls": self.total_calls,
            "timestamp": self.timestamp,
        }
