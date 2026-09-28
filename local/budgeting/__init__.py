"""Tool-Call Budgeting subsystem for IMPULSE (Stage 26).

Provides deterministic analysis of tool call distributions, evidence novelty,
waste classification, observational success associations, and bounded state-keyed caching.
"""

from local.budgeting.analyzer import ToolBudgetAnalyzer
from local.budgeting.cache import BoundedToolCache, SAFE_CACHEABLE_TOOLS
from local.budgeting.models import (
    CacheEntry,
    CacheKey,
    EvidenceNovelty,
    InformationValue,
    TOOL_CATEGORY_MAP,
    ToolAssociation,
    ToolBudgetProfile,
    ToolCallCategory,
    ToolCallEvent,
    ToolDistributionMetrics,
    ToolSuccessAssociation,
    WasteClassification,
)
from local.budgeting.normalization import (
    classify_tool_category,
    compute_arguments_digest,
    normalize_arguments,
    normalize_command,
)
from local.budgeting.novelty import EvidenceHistoryTracker
from local.budgeting.waste_detector import WasteDetector

__all__ = [
    "ToolCallCategory",
    "EvidenceNovelty",
    "WasteClassification",
    "ToolAssociation",
    "TOOL_CATEGORY_MAP",
    "ToolCallEvent",
    "InformationValue",
    "ToolDistributionMetrics",
    "ToolSuccessAssociation",
    "ToolBudgetProfile",
    "CacheKey",
    "CacheEntry",
    "classify_tool_category",
    "normalize_arguments",
    "normalize_command",
    "compute_arguments_digest",
    "EvidenceHistoryTracker",
    "WasteDetector",
    "BoundedToolCache",
    "SAFE_CACHEABLE_TOOLS",
    "ToolBudgetAnalyzer",
]
