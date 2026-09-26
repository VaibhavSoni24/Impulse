"""Hybrid localization controller and policy implementation for IMPULSE (Stage 15)."""

from __future__ import annotations

from typing import Any, Callable

from local.graph.controller import NeighborPolicyV1
from local.graph.models import (
    CodeNeighborsResponse,
    NeighborCallRecord,
    NeighborReconContext,
)
from local.retrieval.controller import RetrievalPolicyV1
from local.retrieval.hybrid_models import (
    DecisionState,
    HybridDecisionRecord,
    HybridReconContext,
    LocalizationAction,
)
from local.retrieval.models import (
    ReconContext,
    RetrievalCallRecord,
    SemanticSearchResponse,
)
from local.subgraph.controller import SubgraphPolicyV1
from local.subgraph.models import (
    CodeSubgraphResponse,
    SubgraphCallRecord,
    SubgraphReconContext,
)
from local.task_state.models import TaskState

# Default budget and safety bounds (PLAN.md Section 17)
DEFAULT_MAX_SEMANTIC_CALLS = 2
DEFAULT_MAX_NEIGHBOR_CALLS = 3
DEFAULT_MAX_SUBGRAPH_CALLS = 2
DEFAULT_MAX_TOTAL_RETRIEVAL_CALLS = 6
DEFAULT_MAX_CONSECUTIVE_REPEATS = 1

VALID_LOCALIZATION_PHASES = {"localization", "reconnaissance"}
NON_RETRIEVAL_PHASES = {"edit", "verify", "review"}


class HybridLocalizationPolicy:
    """Stage 15 Hybrid Localization Policy V1.

    Enforces disciplined, information-gain retrieval:
    1. Exact reconnaissance before semantic retrieval.
    2. Semantic retrieval only when exact search is ambiguous or weak.
    3. Direct source inspection before graph expansion.
    4. Graph neighbors only for an established promising symbol with unresolved relations.
    5. Subgraph retrieval only when multiple inspected symbols interact.
    6. Immediate cessation of retrieval once direct source evidence explains the defect.
    7. Strict budget, repeat, and loop bounds.
    """

    def __init__(
        self,
        semantic_policy: RetrievalPolicyV1 | None = None,
        neighbor_policy: NeighborPolicyV1 | None = None,
        subgraph_policy: SubgraphPolicyV1 | None = None,
        max_semantic_calls: int = DEFAULT_MAX_SEMANTIC_CALLS,
        max_neighbor_calls: int = DEFAULT_MAX_NEIGHBOR_CALLS,
        max_subgraph_calls: int = DEFAULT_MAX_SUBGRAPH_CALLS,
        max_total_calls: int = DEFAULT_MAX_TOTAL_RETRIEVAL_CALLS,
        max_consecutive_repeats: int = DEFAULT_MAX_CONSECUTIVE_REPEATS,
    ) -> None:
        self.semantic_policy = semantic_policy or RetrievalPolicyV1()
        self.neighbor_policy = neighbor_policy or NeighborPolicyV1()
        self.subgraph_policy = subgraph_policy or SubgraphPolicyV1()

        self.max_semantic_calls = max_semantic_calls
        self.max_neighbor_calls = max_neighbor_calls
        self.max_subgraph_calls = max_subgraph_calls
        self.max_total_calls = max_total_calls
        self.max_consecutive_repeats = max_consecutive_repeats

        # Tracking state
        self.semantic_call_count = 0
        self.neighbor_call_count = 0
        self.subgraph_call_count = 0
        self.total_call_count = 0
        self.last_action: LocalizationAction | None = None
        self.consecutive_repeats = 0
        self.is_converged = False
        self.decision_history: list[HybridDecisionRecord] = []

    def choose_next_localization_action(
        self, context: HybridReconContext
    ) -> HybridDecisionRecord:
        """Determines the next justified localization action given current reconnaissance evidence."""
        # 1. Phase Guard Check
        if context.phase not in VALID_LOCALIZATION_PHASES:
            record = self._build_record(
                action=LocalizationAction.STOP_RETRIEVAL,
                state=DecisionState.NON_LOCALIZATION_PHASE,
                reason=f"Retrieval operations disabled in '{context.phase}' phase.",
                context=context,
            )
            self._finalize_decision(record)
            return record

        # 2. Source Evidence Sufficiency Check
        if context.direct_source_sufficient:
            self.is_converged = True
            record = self._build_record(
                action=LocalizationAction.STOP_RETRIEVAL,
                state=DecisionState.SOURCE_SUFFICIENT,
                reason="Direct source inspection explains the defect; stopping retrieval.",
                context=context,
            )
            self._finalize_decision(record)
            return record

        # 3. Global Budget Exhaustion Check
        if self.total_call_count >= self.max_total_calls:
            self.is_converged = True
            record = self._build_record(
                action=LocalizationAction.STOP_RETRIEVAL,
                state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                reason=f"Total retrieval call limit ({self.max_total_calls}) reached; stopping retrieval.",
                context=context,
            )
            self._finalize_decision(record)
            return record

        # 4. Multi-Symbol Interaction Check (Subgraph)
        # Evaluated before single-symbol neighbors if multiple established & inspected candidates interact
        candidate_count = len(context.candidate_symbols)
        inspected_candidates = set(context.candidate_symbols).intersection(context.inspected_symbols)
        if (
            candidate_count >= 2
            and len(inspected_candidates) >= 2
            and context.spans_multiple_symbols
            and not context.single_neighbor_sufficient
        ):
            if self.subgraph_call_count >= self.max_subgraph_calls:
                record = self._build_record(
                    action=LocalizationAction.STOP_RETRIEVAL,
                    state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                    reason=f"Subgraph retrieval budget ({self.max_subgraph_calls}) exhausted; stopping retrieval.",
                    context=context,
                )
            else:
                # Validate with composed SubgraphPolicyV1
                subgraph_recon = SubgraphReconContext(
                    candidate_symbols=context.candidate_symbols,
                    inspected_symbols=context.inspected_symbols,
                    spans_multiple_symbols=context.spans_multiple_symbols,
                    direct_source_sufficient=context.direct_source_sufficient,
                    single_neighbor_sufficient=context.single_neighbor_sufficient,
                    phase=context.phase,
                    last_tool_was_subgraph=(self.last_action == LocalizationAction.SUBGRAPH),
                )
                should_call, specialized_reason = self.subgraph_policy.should_retrieve(subgraph_recon)
                if should_call:
                    record = self._build_record(
                        action=LocalizationAction.SUBGRAPH,
                        state=DecisionState.MULTI_SYMBOL_INTERACTION,
                        reason=specialized_reason,
                        context=context,
                    )
                else:
                    record = self._build_record(
                        action=LocalizationAction.STOP_RETRIEVAL,
                        state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                        reason=f"Subgraph policy rejected retrieval: {specialized_reason}",
                        context=context,
                    )
            record = self._apply_repetition_guard(record, context)
            self._finalize_decision(record)
            return record

        # 5. Promising Candidate Established: Inspect Source First or Expand Neighbors
        if context.promising_symbol is not None:
            # Rule: Always inspect actual source BEFORE expanding graph neighbors
            if context.promising_symbol not in context.inspected_symbols:
                record = self._build_record(
                    action=LocalizationAction.INSPECT_SOURCE,
                    state=DecisionState.PROMISING_SYMBOL_FOUND,
                    reason=f"Promising candidate symbol '{context.promising_symbol}' identified; inspect source before graph expansion.",
                    context=context,
                )
                self._finalize_decision(record)
                return record

            # If symbol inspected and relationship exploration is needed
            if context.needs_relationship_exploration:
                if self.neighbor_call_count >= self.max_neighbor_calls:
                    record = self._build_record(
                        action=LocalizationAction.STOP_RETRIEVAL,
                        state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                        reason=f"Graph neighbor retrieval budget ({self.max_neighbor_calls}) exhausted; stopping retrieval.",
                        context=context,
                    )
                else:
                    # Validate with composed NeighborPolicyV1
                    neighbor_recon = NeighborReconContext(
                        target_symbol=context.promising_symbol,
                        is_promising_candidate=True,
                        needs_relationship_exploration=context.needs_relationship_exploration,
                        direct_source_sufficient=context.direct_source_sufficient,
                        already_expanded_nodes=set(),
                        last_tool_was_neighbor=(self.last_action == LocalizationAction.GRAPH_NEIGHBORS),
                        phase=context.phase,
                    )
                    should_call, specialized_reason = self.neighbor_policy.should_retrieve(neighbor_recon)
                    if should_call:
                        record = self._build_record(
                            action=LocalizationAction.GRAPH_NEIGHBORS,
                            state=DecisionState.RELATIONSHIP_NEEDED,
                            reason=specialized_reason,
                            context=context,
                        )
                    else:
                        record = self._build_record(
                            action=LocalizationAction.STOP_RETRIEVAL,
                            state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                            reason=f"Neighbor policy rejected retrieval: {specialized_reason}",
                            context=context,
                        )
                record = self._apply_repetition_guard(record, context)
                self._finalize_decision(record)
                return record

        # 6. Exact Reconnaissance vs. Semantic Retrieval
        # Check if exact search produced a single strong candidate
        if (
            context.exact_matches_found == 1
            and not context.has_subsystem_ambiguity
            and not context.exact_terms_mismatch
            and not context.text_search_weak
        ):
            record = self._build_record(
                action=LocalizationAction.INSPECT_SOURCE,
                state=DecisionState.EXACT_STRONG,
                reason="Unambiguous exact match identified during reconnaissance; inspecting source directly without semantic search.",
                context=context,
            )
            self._finalize_decision(record)
            return record

        # Check if semantic retrieval is justified (ambiguity, term mismatch, weak exact search, or 0 matches)
        is_semantic_justified = (
            context.has_subsystem_ambiguity
            or context.exact_terms_mismatch
            or context.text_search_weak
            or (context.exact_matches_found == 0 and len(context.candidate_symbols) == 0)
        )

        if is_semantic_justified:
            if self.semantic_call_count >= self.max_semantic_calls:
                record = self._build_record(
                    action=LocalizationAction.STOP_RETRIEVAL,
                    state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                    reason=f"Semantic retrieval budget ({self.max_semantic_calls}) exhausted; stopping retrieval.",
                    context=context,
                )
            else:
                # Validate with composed RetrievalPolicyV1
                semantic_recon = ReconContext(
                    exact_matches_found=context.exact_matches_found,
                    has_subsystem_ambiguity=context.has_subsystem_ambiguity,
                    exact_terms_mismatch=context.exact_terms_mismatch,
                    text_search_weak=context.text_search_weak,
                    last_tool_was_retrieval=(self.last_action == LocalizationAction.SEMANTIC_SEARCH),
                    phase=context.phase,
                )
                should_call, specialized_reason = self.semantic_policy.should_retrieve(semantic_recon)
                if should_call:
                    state = (
                        DecisionState.SEMANTIC_NEEDED
                        if context.exact_terms_mismatch
                        else DecisionState.EXACT_AMBIGUOUS
                    )
                    record = self._build_record(
                        action=LocalizationAction.SEMANTIC_SEARCH,
                        state=state,
                        reason=specialized_reason,
                        context=context,
                    )
                else:
                    record = self._build_record(
                        action=LocalizationAction.STOP_RETRIEVAL,
                        state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                        reason=f"Semantic policy blocked invocation: {specialized_reason}",
                        context=context,
                    )
            record = self._apply_repetition_guard(record, context)
            self._finalize_decision(record)
            return record

        # 7. Default Safe Fallback
        record = self._build_record(
            action=LocalizationAction.STOP_RETRIEVAL,
            state=DecisionState.SOURCE_SUFFICIENT,
            reason="No further retrieval operations justified by reconnaissance evidence; stopping retrieval.",
            context=context,
        )
        self._finalize_decision(record)
        return record

    def _apply_repetition_guard(
        self, record: HybridDecisionRecord, context: HybridReconContext
    ) -> HybridDecisionRecord:
        """Blocks consecutive identical retrieval operations to avoid looping."""
        retrieval_actions = {
            LocalizationAction.SEMANTIC_SEARCH,
            LocalizationAction.GRAPH_NEIGHBORS,
            LocalizationAction.SUBGRAPH,
        }
        if record.action in retrieval_actions and record.action == self.last_action:
            if self.consecutive_repeats >= self.max_consecutive_repeats:
                return self._build_record(
                    action=LocalizationAction.STOP_RETRIEVAL,
                    state=DecisionState.RETRIEVAL_BUDGET_EXHAUSTED,
                    reason=f"Consecutive repeated retrieval action '{record.action.value}' blocked; stopping retrieval.",
                    context=context,
                )
        return record

    def _build_record(
        self,
        action: LocalizationAction,
        state: DecisionState,
        reason: str,
        context: HybridReconContext,
    ) -> HybridDecisionRecord:
        """Constructs an auditable decision record."""
        return HybridDecisionRecord(
            action=action,
            state=state,
            reason=reason,
            candidate_count=len(context.candidate_symbols),
            inspected_candidate_count=len(context.inspected_symbols),
            evidence_sufficient=context.direct_source_sufficient,
            previous_action=self.last_action,
            semantic_calls=self.semantic_call_count,
            neighbor_calls=self.neighbor_call_count,
            subgraph_calls=self.subgraph_call_count,
            total_calls=self.total_call_count,
        )

    def _finalize_decision(self, record: HybridDecisionRecord) -> None:
        """Updates internal audit history and repeat counters."""
        if record.action == LocalizationAction.STOP_RETRIEVAL:
            self.is_converged = True

        if record.action == self.last_action:
            self.consecutive_repeats += 1
        else:
            self.consecutive_repeats = 0

        self.decision_history.append(record)

    def record_semantic_call(self) -> None:
        """Updates counters following a semantic retrieval tool execution."""
        self.semantic_call_count += 1
        self.total_call_count += 1
        self.last_action = LocalizationAction.SEMANTIC_SEARCH

    def record_neighbor_call(self) -> None:
        """Updates counters following a graph neighbor tool execution."""
        self.neighbor_call_count += 1
        self.total_call_count += 1
        self.last_action = LocalizationAction.GRAPH_NEIGHBORS

    def record_subgraph_call(self) -> None:
        """Updates counters following a subgraph tool execution."""
        self.subgraph_call_count += 1
        self.total_call_count += 1
        self.last_action = LocalizationAction.SUBGRAPH

    def integrate_semantic_results(
        self,
        response: SemanticSearchResponse,
        state: TaskState,
        k: int | None = None,
    ) -> RetrievalCallRecord:
        """Delegates to composed RetrievalPolicyV1 and updates hybrid tracking."""
        record = self.semantic_policy.integrate_results(response, state, k=k)
        self.record_semantic_call()
        return record

    def integrate_neighbor_results(
        self,
        response: CodeNeighborsResponse,
        state: TaskState,
        edge_type: str | None = None,
        max_neighbors: int | None = None,
        relevance_filter: Callable[[str], bool] | None = None,
    ) -> NeighborCallRecord:
        """Delegates to composed NeighborPolicyV1 and updates hybrid tracking."""
        record = self.neighbor_policy.integrate_results(
            response,
            state,
            edge_type=edge_type,
            max_neighbors=max_neighbors,
            relevance_filter=relevance_filter,
        )
        self.record_neighbor_call()
        return record

    def integrate_subgraph_results(
        self,
        response: CodeSubgraphResponse,
        state: TaskState,
        seed_nodes: list[str],
        breadth_k: int | None = None,
    ) -> SubgraphCallRecord:
        """Delegates to composed SubgraphPolicyV1 and updates hybrid tracking."""
        record = self.subgraph_policy.integrate_results(
            response, state, seed_nodes=seed_nodes, breadth_k=breadth_k
        )
        self.record_subgraph_call()
        return record
