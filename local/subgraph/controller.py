"""Code graph selective subgraph controller and Policy V1 for IMPULSE (Stage 14)."""

from __future__ import annotations

from typing import Any

from local.subgraph.models import (
    CodeSubgraphResponse,
    SubgraphCallRecord,
    SubgraphEdge,
    SubgraphReconContext,
)
from local.task_state.models import TaskState

# Authoritative tool contract constants (HARNESS_README.md Section 6.3)
TOOL_NAME = "get_code_subgraph"

# Policy v1 decisions (PLAN.md Stage 14)
SUPPORTED_BREADTH_CONFIGS = (2, 4, 8)
DEFAULT_BREADTH_K = 4
MAX_RETAINED_NODES = 8
MAX_RETAINED_EDGES = 12


class SubgraphPolicyV1:
    """Stage 14 Selective Subgraph Policy V1.

    Enforces bounded, evidence-driven induced subgraph retrieval:
    - Never invokes subgraph retrieval indiscriminately.
    - Requires pre-established relevant candidate symbol set (>= 2).
    - Requires prior inspection of candidate symbols.
    - Bounded candidate breadth (k in {2, 4, 8}).
    - Prevents consecutive calls and recursive graph crawling.
    - Updates TaskState concisely without dumping raw adjacency payloads.
    """

    def __init__(
        self,
        default_breadth_k: int = DEFAULT_BREADTH_K,
        max_retained_nodes: int = MAX_RETAINED_NODES,
        max_retained_edges: int = MAX_RETAINED_EDGES,
    ) -> None:
        if default_breadth_k not in SUPPORTED_BREADTH_CONFIGS:
            raise ValueError(
                f"default_breadth_k must be one of {SUPPORTED_BREADTH_CONFIGS}, got {default_breadth_k}"
            )
        self.default_breadth_k = default_breadth_k
        self.max_retained_nodes = max_retained_nodes
        self.max_retained_edges = max_retained_edges
        self.retrieval_history: list[SubgraphCallRecord] = []
        self.queried_seed_sets: list[set[str]] = []

    def should_retrieve(
        self, context: SubgraphReconContext, breadth_k: int | None = None
    ) -> tuple[bool, str]:
        """Evaluates whether get_code_subgraph should be invoked.

        Returns (should_retrieve: bool, rationale: str).
        """
        active_k = breadth_k if breadth_k is not None else self.default_breadth_k
        if active_k not in SUPPORTED_BREADTH_CONFIGS:
            return False, f"breadth_k {active_k} not in supported configurations {SUPPORTED_BREADTH_CONFIGS}."

        if context.phase != "localization":
            return False, f"Subgraph retrieval disabled in '{context.phase}' phase."

        if context.last_tool_was_subgraph:
            return False, "Consecutive subgraph retrieval blocked: inspect previously returned subgraph first."

        if len(context.candidate_symbols) < 2:
            return False, "Subgraph retrieval requires at least 2 pre-identified candidate symbols."

        if not context.spans_multiple_symbols:
            return False, "Defect mechanism has not been identified as spanning multiple related symbols."

        if context.direct_source_sufficient:
            return False, "Direct source reading is sufficient; subgraph retrieval not needed."

        if context.single_neighbor_sufficient:
            return False, "Single-node neighbor inspection is sufficient; subgraph retrieval not needed."

        # Verify prior inspection of at least 2 candidate symbols
        inspected_candidates = set(context.candidate_symbols).intersection(context.inspected_symbols)
        if len(inspected_candidates) < 2:
            return (
                False,
                f"Prior inspection required for at least 2 candidates; inspected {len(inspected_candidates)}.",
            )

        # Check duplicate seed sets
        seed_set = set(context.candidate_symbols[:active_k])
        if seed_set in self.queried_seed_sets:
            return False, f"Subgraph for seed set {sorted(seed_set)} has already been retrieved."

        return (
            True,
            f"Multi-symbol interaction identified across {len(seed_set)} candidate symbols (k={active_k}).",
        )

    def select_seed_nodes(
        self, candidate_symbols: list[str], breadth_k: int | None = None
    ) -> list[str]:
        """Selects and deduplicates seed nodes bounded by breadth_k."""
        active_k = breadth_k if breadth_k is not None else self.default_breadth_k
        seen = set()
        deduped = []
        for s in candidate_symbols:
            if s and s not in seen:
                seen.add(s)
                deduped.append(s)
                if len(deduped) >= active_k:
                    break
        return deduped

    def integrate_results(
        self,
        response: CodeSubgraphResponse,
        state: TaskState,
        seed_nodes: list[str],
        breadth_k: int | None = None,
    ) -> SubgraphCallRecord:
        """Processes get_code_subgraph response and updates TaskState concisely.

        Guarantees:
        - Bounded nodes and edges.
        - Zero raw serialized subgraphs or multi-KB graph payloads in TaskState.
        - Audit trail appended to retrieval history.
        """
        active_k = breadth_k if breadth_k is not None else self.default_breadth_k
        self.queried_seed_sets.append(set(seed_nodes))

        if not response.is_ok() or len(response.nodes) == 0:
            state.add_evidence(
                observation=f"Subgraph query for {seed_nodes} returned no interconnected nodes; continuing direct source reading.",
                source=f"{TOOL_NAME}(nodes={seed_nodes})",
                supports_hypothesis=None,
            )
            record = SubgraphCallRecord(
                seed_nodes=seed_nodes,
                breadth_k=active_k,
                result_node_count=0,
                result_edge_count=0,
                retained_nodes=[],
                retained_edges=[],
                fallback_triggered=True,
                rationale="Empty or failed subgraph response; fallback triggered.",
            )
            self.retrieval_history.append(record)
            return record

        # Retain nodes up to max_retained_nodes (seed nodes first, then additional nodes)
        retained_nodes: list[str] = []
        for s in seed_nodes:
            if s in response.nodes and s not in retained_nodes:
                retained_nodes.append(s)
        for n in response.nodes:
            if n not in retained_nodes:
                retained_nodes.append(n)
                if len(retained_nodes) >= self.max_retained_nodes:
                    break

        # Retain edges connecting retained nodes
        retained_node_set = set(retained_nodes)
        retained_edges: list[SubgraphEdge] = []
        for e in response.edges:
            if e.from_node in retained_node_set and e.to_node in retained_node_set:
                retained_edges.append(e)
                if len(retained_edges) >= self.max_retained_edges:
                    break

        # Update TaskState candidates
        for node in retained_nodes:
            # Count connected edges for this node
            node_edges = [
                e for e in retained_edges if e.from_node == node or e.to_node == node
            ]
            state.add_candidate(
                path=node,
                symbol=node,
                line_number=None,
                rationale=f"Induced subgraph node connected via {len(node_edges)} relation(s)",
            )

        # Update TaskState evidence with concise edge summary
        edge_summaries = [
            f"{e.from_node} -[{e.edge_type or 'CONNECTS'}]-> {e.to_node}"
            for e in retained_edges[:3]
        ]
        summary_str = ", ".join(edge_summaries) if edge_summaries else "No internal edges"
        state.add_evidence(
            observation=(
                f"Induced subgraph ({len(response.nodes)} nodes, {len(response.edges)} edges, k={active_k}): "
                f"{summary_str}"
            ),
            source=f"{TOOL_NAME}(nodes={seed_nodes})",
            supports_hypothesis=None,
        )

        record = SubgraphCallRecord(
            seed_nodes=seed_nodes,
            breadth_k=active_k,
            result_node_count=len(response.nodes),
            result_edge_count=len(response.edges),
            retained_nodes=retained_nodes,
            retained_edges=[e.to_dict() for e in retained_edges],
            fallback_triggered=False,
            rationale=(
                f"Retained {len(retained_nodes)} node(s) and {len(retained_edges)} edge(s) "
                f"across {len(seed_nodes)} seed symbol(s)."
            ),
        )
        self.retrieval_history.append(record)
        return record
