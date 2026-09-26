"""Retrieval controller and Policy V1 implementation for IMPULSE (Stage 12)."""

from __future__ import annotations

from typing import Any

from local.retrieval.models import (
    ReconContext,
    RetrievalCallRecord,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from local.task_state.models import TaskState

# Authoritative tool contract constants (HARNESS_README.md Section 6.3)
TOOL_NAME = "search_similar_code"
DEFAULT_CONTRACT_K = 10
MIN_SUPPORTED_K = 1
MAX_SUPPORTED_K = 50

# Policy v1 decisions (PLAN.md Stage 12)
DEFAULT_INITIAL_K = 5
MIN_SIMILARITY_THRESHOLD = 0.50
MAX_RETAINED_CANDIDATES = 3


class RetrievalPolicyV1:
    """Stage 12 Retrieval Policy V1.

    Enforces disciplined, selective semantic retrieval:
    - Never invokes semantic search blindly on every turn.
    - Evaluates ambiguity, term mismatch, and weak candidate signals.
    - Limits initial k to prevent context bloat.
    - Concisely updates TaskState without raw code dumping.
    - Falls back to exact search when semantic results are weak or empty.
    """

    def __init__(
        self,
        initial_k: int = DEFAULT_INITIAL_K,
        similarity_threshold: float = MIN_SIMILARITY_THRESHOLD,
        max_retained: int = MAX_RETAINED_CANDIDATES,
    ) -> None:
        if not (MIN_SUPPORTED_K <= initial_k <= MAX_SUPPORTED_K):
            raise ValueError(
                f"initial_k must be between {MIN_SUPPORTED_K} and {MAX_SUPPORTED_K}, got {initial_k}"
            )
        self.initial_k = initial_k
        self.similarity_threshold = similarity_threshold
        self.max_retained = max_retained
        self.retrieval_history: list[RetrievalCallRecord] = []

    def should_retrieve(self, context: ReconContext) -> tuple[bool, str]:
        """Evaluates whether search_similar_code should be invoked.

        Returns (should_retrieve: bool, rationale: str).
        """
        if context.phase != "localization":
            return False, f"Semantic retrieval disabled in '{context.phase}' phase."

        if context.last_tool_was_retrieval:
            return False, "Consecutive semantic retrieval blocked: inspect candidate context first."

        # Condition 1: Normal text search returns zero matches
        if context.exact_matches_found == 0:
            return True, "No exact candidate matches found during initial reconnaissance."

        # Condition 2: Multiple candidate subsystems create ambiguity
        if context.has_subsystem_ambiguity:
            return True, "Multiple candidate subsystems detected; semantic disambiguation required."

        # Condition 3: Exact issue terms unlikely to match implementation names
        if context.exact_terms_mismatch:
            return True, "Issue terminology diverges from codebase symbol names."

        # Condition 4: Exact search candidates are weak or inconclusive
        if context.text_search_weak:
            return True, "Exact text search returned low-relevance or weak candidate matches."

        return False, "Unambiguous exact matches identified; semantic retrieval not required."

    def integrate_results(
        self,
        response: SemanticSearchResponse,
        state: TaskState,
        k: int | None = None,
    ) -> RetrievalCallRecord:
        """Processes search_similar_code output and updates TaskState concisely.

        Guarantees:
        - No raw multi-KB code payloads dumped into TaskState.
        - Fallback triggered if results are empty, failed, or below similarity threshold.
        - Full provenance recorded for auditing.
        """
        active_k = k if k is not None else self.initial_k

        if not response.is_ok() or len(response.results) == 0:
            state.add_evidence(
                observation=f"Semantic search for '{response.query}' yielded no candidates; falling back to exact search.",
                source=f"{TOOL_NAME}(query='{response.query}', k={active_k})",
                supports_hypothesis=None,
            )
            record = RetrievalCallRecord(
                query=response.query,
                k=active_k,
                result_count=0,
                fallback_triggered=True,
                rationale="Empty or failed semantic response; fallback triggered.",
            )
            self.retrieval_history.append(record)
            return record

        # Filter by similarity threshold
        sorted_results = sorted(response.results, key=lambda x: x.similarity, reverse=True)
        top_sim = sorted_results[0].similarity
        qualified = [r for r in sorted_results if r.similarity >= self.similarity_threshold]

        if not qualified:
            state.add_evidence(
                observation=(
                    f"Semantic search for '{response.query}' returned weak candidates "
                    f"(top similarity {top_sim:.4f} < {self.similarity_threshold:.2f}); falling back to exact search."
                ),
                source=f"{TOOL_NAME}(query='{response.query}', k={active_k})",
                supports_hypothesis=None,
            )
            record = RetrievalCallRecord(
                query=response.query,
                k=active_k,
                result_count=len(response.results),
                top_similarity=top_sim,
                retained_count=0,
                fallback_triggered=True,
                rationale="Top similarity below threshold; fallback triggered.",
            )
            self.retrieval_history.append(record)
            return record

        # Retain top candidates up to max_retained
        retained = qualified[: self.max_retained]
        for item in retained:
            target_path = item.file_path or item.node_name
            state.add_candidate(
                path=target_path,
                symbol=item.node_name,
                line_number=None,
                rationale=f"Semantic match for query '{response.query}' (similarity: {item.similarity:.4f})",
            )
            state.add_evidence(
                observation=f"Semantic retrieval identified candidate node '{item.node_name}' (similarity: {item.similarity:.4f})",
                source=f"{TOOL_NAME}(query='{response.query}', k={active_k})",
                supports_hypothesis=None,
            )

        record = RetrievalCallRecord(
            query=response.query,
            k=active_k,
            result_count=len(response.results),
            top_similarity=top_sim,
            retained_count=len(retained),
            fallback_triggered=False,
            rationale=f"Retained {len(retained)} candidate(s) above {self.similarity_threshold:.2f} similarity.",
        )
        self.retrieval_history.append(record)
        return record
