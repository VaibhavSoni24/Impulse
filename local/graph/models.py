"""Data models and representations for code graph neighbor retrieval (Stage 13)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


@dataclass
class CodeNeighborItem:
    """Individual graph neighbor relationship."""

    node: str
    relation_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodeNeighborsResponse:
    """Standardized response from get_code_neighbors."""

    status: str
    node: str
    neighbors: list[str] = field(default_factory=list)
    count: int = 0
    error_type: str | None = None
    error_message: str | None = None

    def is_ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "node": self.node,
            "neighbors": list(self.neighbors),
            "count": self.count,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeNeighborsResponse:
        raw_neighbors = data.get("neighbors", [])
        parsed_neighbors: list[str] = []
        for n in raw_neighbors:
            if isinstance(n, str):
                parsed_neighbors.append(n)
            elif isinstance(n, dict) and "node" in n:
                parsed_neighbors.append(str(n["node"]))
            else:
                parsed_neighbors.append(str(n))

        return cls(
            status=data.get("status", "error"),
            node=data.get("node", ""),
            neighbors=parsed_neighbors,
            count=int(data.get("count", len(parsed_neighbors))),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> CodeNeighborsResponse:
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class NeighborReconContext:
    """Context evaluated by NeighborPolicyV1 before invoking get_code_neighbors."""

    target_symbol: str | None = None
    is_promising_candidate: bool = False
    needs_relationship_exploration: bool = False
    direct_source_sufficient: bool = False
    already_expanded_nodes: set[str] = field(default_factory=set)
    last_tool_was_neighbor: bool = False
    phase: str = "localization"  # "localization", "edit", "verify", "review"


@dataclass
class NeighborCallRecord:
    """Audit record of a graph neighbor retrieval call and its outcome."""

    source_node: str
    edge_type: str | None = None
    max_neighbors: int = 50
    result_count: int = 0
    retained_count: int = 0
    retained_neighbors: list[str] = field(default_factory=list)
    rationale: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
