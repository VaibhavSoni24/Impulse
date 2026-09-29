"""IMPULSE Lightweight Failure Dashboard (Stage 30).

Provides deterministic evaluation reporting, failure aggregation,
and metrics export without web servers or interactive UIs.
"""

from __future__ import annotations

from local.dashboard.generator import DashboardGenerator, verify_dashboard_artifacts
from local.dashboard.integrity import SplitIntegrityError, verify_split_before_dashboard
from local.dashboard.metrics import aggregate_dashboard_report, calculate_metric_stats
from local.dashboard.models import (
    DashboardReport,
    EvidenceMode,
    FailureCategorySummary,
    MetricStats,
    ReportStatus,
    RepositoryMetrics,
    RunSummary,
    TaskTypeMetrics,
)
from local.dashboard.queries import (
    build_tasks_lookup,
    fetch_runs_from_db,
    load_runs_from_jsonl,
    run_row_to_summary,
)

__all__ = [
    "DashboardGenerator",
    "DashboardReport",
    "EvidenceMode",
    "FailureCategorySummary",
    "MetricStats",
    "ReportStatus",
    "RepositoryMetrics",
    "RunSummary",
    "SplitIntegrityError",
    "TaskTypeMetrics",
    "aggregate_dashboard_report",
    "build_tasks_lookup",
    "calculate_metric_stats",
    "fetch_runs_from_db",
    "load_runs_from_jsonl",
    "run_row_to_summary",
    "verify_dashboard_artifacts",
    "verify_split_before_dashboard",
]
