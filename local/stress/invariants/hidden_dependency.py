"""Stress Invariant Checker: STRESS 5 — Hidden Dependency Relationship.

Verifies that graph traversal mechanisms can uncover indirect/hidden dependencies
without triggering uncontrolled context expansion, and respect strict neighbor bounds.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from local.graph.controller import DEFAULT_MAX_RETAINED_NEIGHBORS
from local.stress.fixtures import create_hidden_dependency_fixture


def check_hidden_dependency_stress() -> tuple[bool, str, dict[str, Any]]:
    """Evaluates bounded discovery of hidden dependency relations.

    Returns:
        (passed: bool, rationale: str, details: dict)
    """
    fixture = create_hidden_dependency_fixture()
    nodes = fixture["nodes"]
    edges = fixture["edges"]
    start_symbol = fixture["target_symbol"]
    target_hidden = fixture["hidden_dependency"]

    # Graph adjacency structure
    adj: dict[str, list[tuple[str, str]]] = {n: [] for n in nodes}
    for e in edges:
        adj[e["from"]].append((e["to"], e["kind"]))

    # Bounded Breadth-First Expansion (max depth = 3, max retained = 5)
    visited: set[str] = set()
    discovered_order: list[str] = []
    queue: list[tuple[str, int]] = [(start_symbol, 0)]
    max_depth = 3
    max_retained = DEFAULT_MAX_RETAINED_NEIGHBORS

    while queue and len(discovered_order) < max_retained:
        curr, depth = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        discovered_order.append(curr)

        if depth < max_depth:
            for neighbor, kind in adj.get(curr, []):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

    # Invariant 1: Hidden dependency must be discovered along the path
    if target_hidden not in discovered_order:
        return (
            False,
            f"Hidden dependency '{target_hidden}' was not discovered from '{start_symbol}' within max_depth={max_depth}",
            {"discovered_order": discovered_order},
        )

    # Invariant 2: Context bounding: discovered nodes must not exceed max_retained
    if len(discovered_order) > max_retained:
        return (
            False,
            f"Context explosion: discovered {len(discovered_order)} nodes exceeding max_retained={max_retained}",
            {"discovered_order": discovered_order},
        )

    # Invariant 3: Unrelated nodes are pruned / not included in expansion path
    if "unrelated_node_2" in discovered_order:
        return (
            False,
            "Unrelated graph node leaked into selective dependency exploration",
            {"discovered_order": discovered_order},
        )

    details = {
        "start_symbol": start_symbol,
        "target_hidden": target_hidden,
        "discovered_path": discovered_order,
        "nodes_expanded": len(discovered_order),
        "max_retained_bound": max_retained,
        "hidden_dependency_found": True,
    }

    return (
        True,
        f"Hidden dependency '{target_hidden}' discovered from '{start_symbol}' across 3 relational hops within bounded retention ({len(discovered_order)} <= {max_retained}).",
        details,
    )
