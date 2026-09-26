"""Code graph neighbor controller and Policy V1 implementation for IMPULSE (Stage 13)."""

from __future__ import annotations

from typing import Any, Callable

from local.graph.models import (
    CodeNeighborsResponse,
    NeighborCallRecord,
    NeighborReconContext,
)
from local.task_state.models import TaskState

# Authoritative tool contract constants (HARNESS_README.md Section 6.3)
TOOL_NAME = "get_code_neighbors"
DEFAULT_CONTRACT_MAX_NEIGHBORS = 50

# Policy v1 decisions (PLAN.md Stage 13)
DEFAULT_MAX_RETAINED_NEIGHBORS = 5


class NeighborPolicyV1:
    """Stage 13 Graph Neighbor Policy V1.

    Enforces disciplined, selective relational exploration:
    - Never expands symbols automatically or blindly.
    - Requires an established promising candidate symbol.
    - Requires that direct source inspection alone is insufficient.
    - Limits retained neighbors to prevent context explosion.
    - Records relations into TaskState without raw graph dumps.
    - Blocks recursive expansion and consecutive neighbor requests.
    """

    def __init__(
        self,
        default_max_neighbors: int = DEFAULT_CONTRACT_MAX_NEIGHBORS,
        max_retained: int = DEFAULT_MAX_RETAINED_NEIGHBORS,
    ) -> None:
        if default_max_neighbors <= 0:
            raise ValueError(f"default_max_neighbors must be positive, got {default_max_neighbors}")
        self.default_max_neighbors = default_max_neighbors
        self.max_retained = max_retained
        self.retrieval_history: list[NeighborCallRecord] = []
        self.expanded_nodes: set[str] = set()

    def should_retrieve(self, context: NeighborReconContext) -> tuple[bool, str]:
        """Evaluates whether get_code_neighbors should be called for a candidate symbol.

        Returns (should_retrieve: bool, rationale: str).
        """
        if context.phase != "localization":
            return False, f"Neighbor retrieval disabled in '{context.phase}' phase."

        if not context.target_symbol:
            return False, "Target symbol must be specified before expanding neighbors."

        if not context.is_promising_candidate:
            return False, f"Symbol '{context.target_symbol}' has not been established as a promising candidate."

        if context.direct_source_sufficient:
            return False, "Direct source inspection is sufficient; graph neighbor exploration not needed."

        if context.last_tool_was_neighbor:
            return False, "Consecutive neighbor retrieval blocked: inspect previously returned relations first."

        if (
            context.target_symbol in context.already_expanded_nodes
            or context.target_symbol in self.expanded_nodes
        ):
            return False, f"Symbol '{context.target_symbol}' has already been expanded."

        if context.needs_relationship_exploration:
            return True, f"Promising symbol '{context.target_symbol}' requires relationship exploration."

        return False, "Relational exploration criteria not satisfied."

    def integrate_results(
        self,
        response: CodeNeighborsResponse,
        state: TaskState,
        edge_type: str | None = None,
        max_neighbors: int | None = None,
        relevance_filter: Callable[[str], bool] | None = None,
    ) -> NeighborCallRecord:
        """Processes get_code_neighbors output and updates TaskState concisely.

        Guarantees:
        - No raw graph structures or code dumps in TaskState.
        - Selected neighbors recorded concisely into candidates and evidence.
        - Audit trail appended to retrieval history.
        """
        active_max = max_neighbors if max_neighbors is not None else self.default_max_neighbors
        self.expanded_nodes.add(response.node)

        if not response.is_ok() or len(response.neighbors) == 0:
            state.add_evidence(
                observation=f"Graph neighbors query for '{response.node}' returned 0 relations; continuing direct source reading.",
                source=f"{TOOL_NAME}(node='{response.node}')",
                supports_hypothesis=None,
            )
            record = NeighborCallRecord(
                source_node=response.node,
                edge_type=edge_type,
                max_neighbors=active_max,
                result_count=0,
                retained_count=0,
                retained_neighbors=[],
                rationale="Empty or failed graph neighbor response.",
            )
            self.retrieval_history.append(record)
            return record

        # Filter and select relevant neighbors
        candidates_to_filter = response.neighbors
        if relevance_filter is not None:
            filtered_candidates = [n for n in candidates_to_filter if relevance_filter(n)]
        else:
            filtered_candidates = candidates_to_filter

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for n in filtered_candidates:
            if n not in seen and n != response.node:
                seen.add(n)
                deduped.append(n)

        retained = deduped[: self.max_retained]

        # Add to TaskState candidates and evidence
        for neighbor in retained:
            edge_suffix = f" (edge_type: '{edge_type}')" if edge_type else ""
            state.add_candidate(
                path=neighbor,
                symbol=neighbor,
                line_number=None,
                rationale=f"Graph neighbor of '{response.node}'{edge_suffix}",
            )
            state.add_evidence(
                observation=f"Graph relationship discovered: '{response.node}' -> '{neighbor}'{edge_suffix}",
                source=f"{TOOL_NAME}(node='{response.node}')",
                supports_hypothesis=None,
            )

        record = NeighborCallRecord(
            source_node=response.node,
            edge_type=edge_type,
            max_neighbors=active_max,
            result_count=len(response.neighbors),
            retained_count=len(retained),
            retained_neighbors=retained,
            rationale=f"Retained {len(retained)} relevant neighbor(s) out of {len(response.neighbors)} returned.",
        )
        self.retrieval_history.append(record)
        return record
