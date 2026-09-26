"""Retrieval package for IMPULSE (Stage 12 Semantic + Stage 15 Hybrid Localization)."""

from local.retrieval.controller import (
    DEFAULT_CONTRACT_K,
    DEFAULT_INITIAL_K,
    MAX_RETAINED_CANDIDATES,
    MAX_SUPPORTED_K,
    MIN_SIMILARITY_THRESHOLD,
    MIN_SUPPORTED_K,
    TOOL_NAME,
    RetrievalPolicyV1,
)
from local.retrieval.hybrid_controller import (
    DEFAULT_MAX_CONSECUTIVE_REPEATS,
    DEFAULT_MAX_NEIGHBOR_CALLS,
    DEFAULT_MAX_SEMANTIC_CALLS,
    DEFAULT_MAX_SUBGRAPH_CALLS,
    DEFAULT_MAX_TOTAL_RETRIEVAL_CALLS,
    HybridLocalizationPolicy,
)
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
    SemanticSearchResultItem,
)

__all__ = [
    # Semantic Search (Stage 12)
    "DEFAULT_CONTRACT_K",
    "DEFAULT_INITIAL_K",
    "MAX_RETAINED_CANDIDATES",
    "MAX_SUPPORTED_K",
    "MIN_SIMILARITY_THRESHOLD",
    "MIN_SUPPORTED_K",
    "TOOL_NAME",
    "ReconContext",
    "RetrievalCallRecord",
    "RetrievalPolicyV1",
    "SemanticSearchResponse",
    "SemanticSearchResultItem",
    # Hybrid Localization (Stage 15)
    "DEFAULT_MAX_CONSECUTIVE_REPEATS",
    "DEFAULT_MAX_NEIGHBOR_CALLS",
    "DEFAULT_MAX_SEMANTIC_CALLS",
    "DEFAULT_MAX_SUBGRAPH_CALLS",
    "DEFAULT_MAX_TOTAL_RETRIEVAL_CALLS",
    "HybridLocalizationPolicy",
    "DecisionState",
    "HybridDecisionRecord",
    "HybridReconContext",
    "LocalizationAction",
]
