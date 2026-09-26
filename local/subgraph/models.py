"""Data models and representations for code subgraph retrieval (Stage 14)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


@dataclass
class SubgraphEdge:
    """Individual edge in an induced subgraph."""

    from_node: str
    to_node: str
    edge_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "type": self.edge_type,
        }


@dataclass
class CodeSubgraphResponse:
    """Standardized response from get_code_subgraph."""

    status: str
    nodes: list[str] = field(default_factory=list)
    edges: list[SubgraphEdge] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    error_type: str | None = None
    error_message: str | None = None

    def is_ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "nodes": list(self.nodes),
            "edges": [e.to_dict() for e in self.edges],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeSubgraphResponse:
        raw_nodes = data.get("nodes", [])
        parsed_nodes = [str(n) for n in raw_nodes]

        raw_edges = data.get("edges", [])
        parsed_edges: list[SubgraphEdge] = []
        for e in raw_edges:
            if isinstance(e, dict):
                parsed_edges.append(
                    SubgraphEdge(
                        from_node=str(e.get("from", "")),
                        to_node=str(e.get("to", "")),
                        edge_type=str(e.get("type", "")),
                    )
                )

        return cls(
            status=data.get("status", "error"),
            nodes=parsed_nodes,
            edges=parsed_edges,
            node_count=int(data.get("node_count", len(parsed_nodes))),
            edge_count=int(data.get("edge_count", len(parsed_edges))),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> CodeSubgraphResponse:
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class SubgraphReconContext:
    """Context evaluated by SubgraphPolicyV1 before invoking get_code_subgraph."""

    candidate_symbols: list[str] = field(default_factory=list)
    inspected_symbols: set[str] = field(default_factory=set)
    spans_multiple_symbols: bool = False
    direct_source_sufficient: bool = False
    single_neighbor_sufficient: bool = False
    phase: str = "localization"  # "localization", "edit", "verify", "review"
    last_tool_was_subgraph: bool = False


@dataclass
class SubgraphCallRecord:
    """Audit record of a code subgraph retrieval call and its outcome."""

    seed_nodes: list[str]
    breadth_k: int
    result_node_count: int = 0
    result_edge_count: int = 0
    retained_nodes: list[str] = field(default_factory=list)
    retained_edges: list[dict[str, str]] = field(default_factory=list)
    fallback_triggered: bool = False
    rationale: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
