"""Canonical Retrieval Policy Definitions (Stage 33 Sections 3, 6, 7-11).

Defines canonical configurations for:
- R0: Baseline (no semantic retrieval; exact text search / file inspection only)
- R1: Semantic Retrieval (search_similar_code enabled under controlled policy)
- R2: Semantic Retrieval + Code Neighbors (get_code_neighbors)
- R3: Semantic Retrieval + Selective Subgraph (get_code_subgraph)
- R4: Dynamic Retrieval Depth (adaptive expansion & early stopping)
"""

from __future__ import annotations

from typing import Union

from local.retrieval_opt.models import RetrievalPolicy, RetrievalVariant


def build_r0_baseline_policy() -> RetrievalPolicy:
    """Builds the canonical R0 Baseline policy.

    R0 disables semantic/graph retrieval optimization while preserving
    ordinary repository reconnaissance (exact grep, file inspection).
    """
    return RetrievalPolicy(
        variant=RetrievalVariant.R0.value,
        candidate_id="R0",
        semantic_retrieval_enabled=False,
        neighbor_retrieval_enabled=False,
        subgraph_retrieval_enabled=False,
        dynamic_depth_enabled=False,
        semantic_top_k=0,
        neighbor_depth=0,
        subgraph_depth=0,
        subgraph_breadth_k=0,
        max_retrieval_calls=0,
        max_semantic_calls=0,
        max_neighbor_calls=0,
        max_subgraph_calls=0,
        max_retrieved_items=0,
        expansion_policy="none",
        trigger_conditions={
            "allow_text_search": True,
            "allow_file_inspection": True,
            "semantic_enabled": False,
        },
        fallback_behavior={
            "on_semantic_failure": "EXACT_SEARCH",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        },
    )


def build_r1_semantic_policy() -> RetrievalPolicy:
    """Builds the canonical R1 Semantic Retrieval policy.

    Enables search_similar_code under controlled conditions:
    only triggers when exact reconnaissance reveals term mismatch or ambiguity.
    """
    return RetrievalPolicy(
        variant=RetrievalVariant.R1.value,
        candidate_id="R1",
        semantic_retrieval_enabled=True,
        neighbor_retrieval_enabled=False,
        subgraph_retrieval_enabled=False,
        dynamic_depth_enabled=False,
        semantic_top_k=5,
        neighbor_depth=0,
        subgraph_depth=0,
        subgraph_breadth_k=0,
        max_retrieval_calls=3,
        max_semantic_calls=3,
        max_neighbor_calls=0,
        max_subgraph_calls=0,
        max_retrieved_items=15,
        similarity_threshold=0.50,
        expansion_policy="semantic_only",
        trigger_conditions={
            "require_exact_ambiguity": True,
            "min_similarity": 0.50,
        },
        fallback_behavior={
            "on_semantic_failure": "EXACT_SEARCH",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        },
    )


def build_r2_neighbors_policy() -> RetrievalPolicy:
    """Builds the canonical R2 Semantic + Code Neighbors policy.

    Enables get_code_neighbors selectively after a promising symbol
    has been identified through semantic retrieval and inspected.
    """
    return RetrievalPolicy(
        variant=RetrievalVariant.R2.value,
        candidate_id="R2",
        semantic_retrieval_enabled=True,
        neighbor_retrieval_enabled=True,
        subgraph_retrieval_enabled=False,
        dynamic_depth_enabled=False,
        semantic_top_k=5,
        neighbor_depth=1,
        subgraph_depth=0,
        subgraph_breadth_k=0,
        max_retrieval_calls=5,
        max_semantic_calls=2,
        max_neighbor_calls=3,
        max_subgraph_calls=0,
        max_retrieved_items=20,
        similarity_threshold=0.50,
        expansion_policy="selective_neighbors",
        trigger_conditions={
            "require_exact_ambiguity": True,
            "require_promising_symbol": True,
            "min_similarity": 0.50,
        },
        fallback_behavior={
            "on_semantic_failure": "EXACT_SEARCH",
            "on_neighbor_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        },
    )


def build_r3_subgraph_policy() -> RetrievalPolicy:
    """Builds the canonical R3 Semantic + Selective Subgraph policy.

    Enables get_code_subgraph selectively when multiple promising symbols
    are identified and relational dependency paths require disambiguation.
    """
    return RetrievalPolicy(
        variant=RetrievalVariant.R3.value,
        candidate_id="R3",
        semantic_retrieval_enabled=True,
        neighbor_retrieval_enabled=True,
        subgraph_retrieval_enabled=True,
        dynamic_depth_enabled=False,
        semantic_top_k=5,
        neighbor_depth=1,
        subgraph_depth=1,
        subgraph_breadth_k=4,
        max_retrieval_calls=6,
        max_semantic_calls=2,
        max_neighbor_calls=2,
        max_subgraph_calls=2,
        max_retrieved_items=25,
        similarity_threshold=0.50,
        expansion_policy="selective_subgraph",
        trigger_conditions={
            "require_exact_ambiguity": True,
            "require_promising_symbol": True,
            "require_multi_symbol_relation": True,
            "min_similarity": 0.50,
        },
        fallback_behavior={
            "on_semantic_failure": "EXACT_SEARCH",
            "on_neighbor_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_subgraph_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        },
    )


def build_r4_dynamic_policy() -> RetrievalPolicy:
    """Builds the canonical R4 Dynamic Retrieval Depth policy.

    Adapts retrieval depth dynamically: starts small, checks evidence sufficiency,
    stops early if sufficient, expands only under remaining uncertainty, and terminates
    if redundant or budget-exhausted.
    """
    return RetrievalPolicy(
        variant=RetrievalVariant.R4.value,
        candidate_id="R4",
        semantic_retrieval_enabled=True,
        neighbor_retrieval_enabled=True,
        subgraph_retrieval_enabled=True,
        dynamic_depth_enabled=True,
        semantic_top_k=5,
        neighbor_depth=1,
        subgraph_depth=2,
        subgraph_breadth_k=4,
        max_retrieval_calls=8,
        max_semantic_calls=3,
        max_neighbor_calls=3,
        max_subgraph_calls=2,
        max_retrieved_items=30,
        similarity_threshold=0.50,
        expansion_policy="dynamic_adaptive",
        trigger_conditions={
            "require_exact_ambiguity": True,
            "adaptive_uncertainty": True,
            "min_similarity": 0.50,
        },
        dynamic_config={
            "min_depth": 1,
            "max_depth": 3,
            "max_rounds": 4,
            "redundancy_stop_threshold": 0.50,
            "early_stop_on_sufficient": True,
            "confidence_threshold": 0.75,
        },
        fallback_behavior={
            "on_semantic_failure": "EXACT_SEARCH",
            "on_neighbor_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_subgraph_failure": "INSPECT_CURRENT_SYMBOLS",
            "on_budget_exhausted": "STOP_RETRIEVAL",
        },
    )


def get_canonical_policy(variant: Union[RetrievalVariant, str]) -> RetrievalPolicy:
    """Retrieves the canonical policy instance for a variant name or enum."""
    val = variant.value if isinstance(variant, RetrievalVariant) else str(variant).upper()
    if val == RetrievalVariant.R0.value:
        return build_r0_baseline_policy()
    elif val == RetrievalVariant.R1.value:
        return build_r1_semantic_policy()
    elif val == RetrievalVariant.R2.value:
        return build_r2_neighbors_policy()
    elif val == RetrievalVariant.R3.value:
        return build_r3_subgraph_policy()
    elif val == RetrievalVariant.R4.value:
        return build_r4_dynamic_policy()
    raise ValueError(f"Unknown retrieval variant: {variant}")
