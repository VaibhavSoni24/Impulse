"""Candidate E5 graph interface re-exporting code graph neighbor and subgraph packages."""

from local.graph import (
    DEFAULT_CONTRACT_MAX_NEIGHBORS,
    DEFAULT_MAX_RETAINED_NEIGHBORS,
    TOOL_NAME as NEIGHBOR_TOOL_NAME,
    CodeNeighborItem,
    CodeNeighborsResponse,
    NeighborCallRecord,
    NeighborPolicyV1,
    NeighborReconContext,
)
from local.subgraph import (
    DEFAULT_BREADTH_K,
    MAX_RETAINED_EDGES,
    MAX_RETAINED_NODES,
    SUPPORTED_BREADTH_CONFIGS,
    TOOL_NAME as SUBGRAPH_TOOL_NAME,
    CodeSubgraphResponse,
    SubgraphCallRecord,
    SubgraphEdge,
    SubgraphPolicyV1,
    SubgraphReconContext,
)

__all__ = [
    # Neighbors
    "DEFAULT_CONTRACT_MAX_NEIGHBORS",
    "DEFAULT_MAX_RETAINED_NEIGHBORS",
    "NEIGHBOR_TOOL_NAME",
    "CodeNeighborItem",
    "CodeNeighborsResponse",
    "NeighborCallRecord",
    "NeighborPolicyV1",
    "NeighborReconContext",
    # Subgraph
    "DEFAULT_BREADTH_K",
    "MAX_RETAINED_EDGES",
    "MAX_RETAINED_NODES",
    "SUBGRAPH_TOOL_NAME",
    "SUPPORTED_BREADTH_CONFIGS",
    "CodeSubgraphResponse",
    "SubgraphCallRecord",
    "SubgraphEdge",
    "SubgraphPolicyV1",
    "SubgraphReconContext",
]
