"""Canonical topology matrix definitions and validation for Stage 24.

Defines the six experimental topologies (M0 to M5) and functions to inspect
and validate candidate configurations.
"""

from __future__ import annotations

from local.topology.models import TopologyDefinition, TopologyID

# Authoritative matrix mapping for Stage 24
CANONICAL_TOPOLOGY_MATRIX: dict[str, TopologyDefinition] = {
    TopologyID.M0.value: TopologyDefinition(
        topology_id="M0",
        name="root_only",
        description="Baseline topology containing the Root agent with full core capabilities and no specialist sub-agents.",
        specialists=(),
    ),
    TopologyID.M1.value: TopologyDefinition(
        topology_id="M1",
        name="root_plus_scout",
        description="Root agent accompanied by the read-only Scout specialist for pre-edit localization.",
        specialists=("scout",),
    ),
    TopologyID.M2.value: TopologyDefinition(
        topology_id="M2",
        name="root_plus_debugger",
        description="Root agent accompanied by the read-only Debugger specialist for post-failure diagnostic analysis.",
        specialists=("debugger",),
    ),
    TopologyID.M3.value: TopologyDefinition(
        topology_id="M3",
        name="root_plus_reviewer",
        description="Root agent accompanied by the read-only Reviewer specialist for pre-submission patch assessment.",
        specialists=("reviewer",),
    ),
    TopologyID.M4.value: TopologyDefinition(
        topology_id="M4",
        name="root_plus_scout_debugger",
        description="Root agent with both Scout and Debugger specialists (localization and failure diagnosis).",
        specialists=("scout", "debugger"),
    ),
    TopologyID.M5.value: TopologyDefinition(
        topology_id="M5",
        name="root_full_specialists",
        description="Root agent with all three specialists: Scout, Debugger, and Reviewer.",
        specialists=("scout", "debugger", "reviewer"),
    ),
}


def get_canonical_topology_matrix() -> dict[str, TopologyDefinition]:
    """Returns a copy of the canonical topology definitions for M0–M5."""
    return dict(CANONICAL_TOPOLOGY_MATRIX)


def get_topology_definition(topology_id: str) -> TopologyDefinition:
    """Retrieves a topology definition by ID. Raises KeyError if invalid."""
    normalized = topology_id.upper()
    if normalized not in CANONICAL_TOPOLOGY_MATRIX:
        raise KeyError(f"Unknown topology '{topology_id}'. Expected one of {list(CANONICAL_TOPOLOGY_MATRIX.keys())}")
    return CANONICAL_TOPOLOGY_MATRIX[normalized]


def validate_topology_composition(
    topology_id: str,
    declared_subagents: list[str],
) -> tuple[bool, str]:
    """Validates that a candidate's declared subagents strictly match its canonical topology definition."""
    try:
        expected_def = get_topology_definition(topology_id)
    except KeyError as e:
        return False, str(e)

    # Clean stems (e.g., 'sub_agents/scout.yaml' -> 'scout')
    normalized_subagents = []
    for sa in declared_subagents:
        stem = sa.split("/")[-1].replace(".yaml", "").replace(".yml", "")
        normalized_subagents.append(stem)

    declared_set = set(normalized_subagents)
    expected_set = set(expected_def.specialists)

    if declared_set != expected_set:
        return False, (
            f"Topology {topology_id} declared specialists {sorted(declared_set)}, "
            f"but canonical definition requires {sorted(expected_set)}."
        )

    return True, f"Topology {topology_id} composition matches canonical specification exactly."
