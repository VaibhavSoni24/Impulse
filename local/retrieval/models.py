"""Data models and representations for semantic retrieval (Stage 12)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any


@dataclass
class SemanticSearchResultItem:
    """Individual node result returned by search_similar_code."""

    node_name: str
    similarity: float
    code: str = ""
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticSearchResponse:
    """Standardized response from search_similar_code."""

    status: str
    query: str
    results: list[SemanticSearchResultItem] = field(default_factory=list)
    count: int = 0
    error_type: str | None = None
    error_message: str | None = None

    def is_ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "count": self.count,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticSearchResponse:
        results_data = data.get("results", [])
        items = []
        for item in results_data:
            items.append(
                SemanticSearchResultItem(
                    node_name=item.get("node_name", ""),
                    similarity=float(item.get("similarity", 0.0)),
                    code=item.get("code", ""),
                    file_path=item.get("file_path", ""),
                )
            )
        return cls(
            status=data.get("status", "error"),
            query=data.get("query", ""),
            results=items,
            count=int(data.get("count", len(items))),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> SemanticSearchResponse:
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class ReconContext:
    """Reconnaissance context evaluated by RetrievalPolicyV1."""

    exact_matches_found: int = 0
    has_subsystem_ambiguity: bool = False
    exact_terms_mismatch: bool = False
    text_search_weak: bool = False
    is_repo_large: bool = False
    last_tool_was_retrieval: bool = False
    phase: str = "localization"  # "localization", "edit", "verify", "review"


@dataclass
class RetrievalCallRecord:
    """Audit record of a semantic retrieval call and its outcome."""

    query: str
    k: int
    result_count: int
    top_similarity: float | None = None
    retained_count: int = 0
    fallback_triggered: bool = False
    rationale: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
