"""Multi-Agent Topology Experiments subsystem for IMPULSE (Stage 24).

Provides:
- TopologyID, SpecialistName, SelectionStatus, TopologyDefinition, TaskRunRecord, TopologyAggregateMetrics (models.py)
- CANONICAL_TOPOLOGY_MATRIX, get_canonical_topology_matrix, get_topology_definition, validate_topology_composition (matrix.py)
- calculate_topology_metrics, summarize_topology_metrics (metrics.py)
- generate_topology_comparison_table, evaluate_topology_selection (comparator.py)
"""

from local.topology.comparator import (
    evaluate_topology_selection,
    generate_topology_comparison_table,
)
from local.topology.matrix import (
    CANONICAL_TOPOLOGY_MATRIX,
    get_canonical_topology_matrix,
    get_topology_definition,
    validate_topology_composition,
)
from local.topology.metrics import (
    calculate_topology_metrics,
    summarize_topology_metrics,
)
from local.topology.models import (
    SelectionStatus,
    SpecialistName,
    TaskRunRecord,
    TopologyAggregateMetrics,
    TopologyDefinition,
    TopologyID,
)

__all__ = [
    "CANONICAL_TOPOLOGY_MATRIX",
    "SelectionStatus",
    "SpecialistName",
    "TaskRunRecord",
    "TopologyAggregateMetrics",
    "TopologyDefinition",
    "TopologyID",
    "calculate_topology_metrics",
    "evaluate_topology_selection",
    "generate_topology_comparison_table",
    "get_canonical_topology_matrix",
    "get_topology_definition",
    "summarize_topology_metrics",
    "validate_topology_composition",
]
