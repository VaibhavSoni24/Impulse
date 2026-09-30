"""Deterministic Retrieval Experiment Fixtures A through T (Stage 33 Section 31).

Provides clean, reproducible synthetic data for verifying the retrieval optimization machinery
without fabricating live Gemma 4 model inference:
A. R0 baseline
B. R1 finds relevant semantic candidate
C. R1 returns irrelevant candidates
D. R2 finds useful neighbor
E. R2 adds redundant neighbors
F. R3 finds necessary dependency path
G. R3 over-expands
H. R4 stops early because evidence is sufficient
I. R4 expands because evidence remains insufficient
J. Retrieval budget exhausted
K. Retrieval tool failure fallback
L. Cache hit
M. Duplicate retrieval
N. Retrieval improves target failure
O. Retrieval does not improve target failure
P. Retrieval improves target but causes collateral regression
Q. Deterministic candidate comparison
R. Mixed evidence modes
S. No actionable live results
T. Manifest/hash mismatch

All fixtures explicitly enforce evidence_mode = "FIXTURE".
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from local.fdd.models import FailureRecord
from local.retrieval_opt.models import (
    DynamicRoundTrace,
    RetrievalCandidateManifest,
    RetrievalEvent,
    RetrievalHypothesis,
    RetrievalPolicy,
    RetrievalType,
    RetrievalVariant,
)
from local.retrieval_opt.policy import (
    build_r0_baseline_policy,
    build_r1_semantic_policy,
    build_r2_neighbors_policy,
    build_r3_subgraph_policy,
    build_r4_dynamic_policy,
)


def get_fixture_a_r0_baseline() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture A: R0 Baseline (No semantic/graph retrieval, exact search only)."""
    policy = build_r0_baseline_policy()
    records = [
        FailureRecord(
            run_id="run-a",
            candidate_id="R0",
            task_id=f"astropy__astropy-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=(i % 3 == 0),
            failure_category="WRONG_FILE_LOCALIZATION" if i % 3 != 0 else None,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 10)
    ]
    # In R0, zero semantic or graph retrieval events occur
    events: List[RetrievalEvent] = []
    return policy, records, events


def get_fixture_b_r1_relevant() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture B: R1 finds relevant semantic candidate."""
    policy = build_r1_semantic_policy()
    records = [
        FailureRecord(
            run_id="run-b",
            candidate_id="R1",
            task_id=f"astropy__astropy-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 10)
    ]
    events = [
        RetrievalEvent(
            run_id="run-b",
            task_id="astropy__astropy-1",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="FITS header card parsing error",
            returned_count=3,
            unique_returned_count=3,
            selected_count=1,
            inspected_count=1,
            retrieval_duration_ms=45.0,
            returned_entities=["fits.Header", "fits.Card", "fits.util"],
            source_files_exposed=["astropy/io/fits/header.py"],
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_c_r1_irrelevant() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture C: R1 returns irrelevant candidates and falls back."""
    policy = build_r1_semantic_policy()
    records = [
        FailureRecord(
            run_id="run-c",
            candidate_id="R1",
            task_id="astropy__astropy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        RetrievalEvent(
            run_id="run-c",
            task_id="astropy__astropy-1",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="quantum gravity simulator",
            returned_count=2,
            unique_returned_count=2,
            selected_count=0,
            inspected_count=0,
            retrieval_duration_ms=60.0,
            returned_entities=["unrelated.foo", "unrelated.bar"],
            source_files_exposed=["astropy/misc.py"],
            evidence_mode="FIXTURE",
            metadata={"misleading_retrieval": True},
        )
    ]
    return policy, records, events


def get_fixture_d_r2_useful_neighbor() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture D: R2 finds useful neighbor after semantic search."""
    policy = build_r2_neighbors_policy()
    records = [
        FailureRecord(
            run_id="run-d",
            candidate_id="R2",
            task_id="astropy__astropy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        RetrievalEvent(
            run_id="run-d",
            task_id="astropy__astropy-1",
            candidate_id="R2",
            retrieval_variant="R2",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="TimeISO parser",
            returned_count=1,
            unique_returned_count=1,
            selected_count=1,
            inspected_count=1,
            returned_entities=["astropy.time.TimeISO"],
            source_files_exposed=["astropy/time/formats.py"],
            evidence_mode="FIXTURE",
        ),
        RetrievalEvent(
            run_id="run-d",
            task_id="astropy__astropy-1",
            candidate_id="R2",
            retrieval_variant="R2",
            retrieval_type=RetrievalType.NEIGHBORS.value,
            query="neighbors of TimeISO",
            seed_nodes=["astropy.time.TimeISO"],
            returned_count=2,
            unique_returned_count=2,
            selected_count=1,
            inspected_count=1,
            returned_entities=["astropy.time.TimeUnique", "astropy.time.parse_iso"],
            source_files_exposed=["astropy/time/core.py"],
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, records, events


def get_fixture_e_r2_redundant_neighbors() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture E: R2 adds redundant neighbors already known."""
    policy = build_r2_neighbors_policy()
    records = [
        FailureRecord(
            run_id="run-e",
            candidate_id="R2",
            task_id="astropy__astropy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        RetrievalEvent(
            run_id="run-e",
            task_id="astropy__astropy-1",
            candidate_id="R2",
            retrieval_variant="R2",
            retrieval_type=RetrievalType.NEIGHBORS.value,
            query="neighbors of foo",
            seed_nodes=["foo"],
            returned_count=3,
            unique_returned_count=0,
            duplicate_count=3,
            returned_entities=["foo_child1", "foo_child2", "foo_child3"],
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_f_r3_dependency_path() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture F: R3 finds necessary dependency path via subgraph."""
    policy = build_r3_subgraph_policy()
    records = [
        FailureRecord(
            run_id="run-f",
            candidate_id="R3",
            task_id="sympy__sympy-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        RetrievalEvent(
            run_id="run-f",
            task_id="sympy__sympy-1",
            candidate_id="R3",
            retrieval_variant="R3",
            retrieval_type=RetrievalType.SUBGRAPH.value,
            query="subgraph around Matrix and Expr",
            seed_nodes=["sympy.Matrix", "sympy.Expr"],
            requested_depth=1,
            returned_count=4,
            unique_returned_count=4,
            selected_count=2,
            inspected_count=2,
            returned_entities=["sympy.MatrixBase", "sympy.ImmutableMatrix", "sympy.DenseMatrix", "sympy.Basic"],
            source_files_exposed=["sympy/matrices/common.py", "sympy/core/basic.py"],
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_g_r3_over_expansion() -> Tuple[RetrievalPolicy, List[FailureRecord], List[RetrievalEvent]]:
    """Fixture G: R3 over-expands with large subgraph and negligible usage."""
    policy = build_r3_subgraph_policy()
    records = [
        FailureRecord(
            run_id="run-g",
            candidate_id="R3",
            task_id="sympy__sympy-2",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="TOOL_TIMEOUT",
            evidence_mode="FIXTURE",
        )
    ]
    events = [
        RetrievalEvent(
            run_id="run-g",
            task_id="sympy__sympy-2",
            candidate_id="R3",
            retrieval_variant="R3",
            retrieval_type=RetrievalType.SUBGRAPH.value,
            query="large subgraph",
            seed_nodes=["sympy.Basic"],
            requested_depth=2,
            returned_count=15,
            unique_returned_count=15,
            selected_count=1,
            inspected_count=0,
            returned_entities=[f"sympy.node_{i}" for i in range(15)],
            source_files_exposed=[f"sympy/file_{i}.py" for i in range(5)],
            evidence_mode="FIXTURE",
        )
    ]
    return policy, records, events


def get_fixture_h_r4_stops_early() -> Tuple[RetrievalPolicy, List[DynamicRoundTrace]]:
    """Fixture H: R4 stops early at round 1 because evidence is sufficient."""
    policy = build_r4_dynamic_policy()
    traces = [
        DynamicRoundTrace(
            round_index=1,
            current_evidence_state={"candidate_count": 2, "evidence_sufficient": True, "uncertainty": 0.1},
            action_taken="SEMANTIC_SEARCH",
            new_evidence_gained=["astropy.io.fits.Card"],
            duplicate_evidence=[],
            decision="STOP",
            decision_rationale="Evidence sufficient: exact target symbol located with high confidence.",
            budget_remaining=7,
        )
    ]
    return policy, traces


def get_fixture_i_r4_expands() -> Tuple[RetrievalPolicy, List[DynamicRoundTrace]]:
    """Fixture I: R4 expands multiple rounds because evidence remains insufficient."""
    policy = build_r4_dynamic_policy()
    traces = [
        DynamicRoundTrace(
            round_index=1,
            current_evidence_state={"candidate_count": 1, "evidence_sufficient": False, "uncertainty": 0.8},
            action_taken="SEMANTIC_SEARCH",
            new_evidence_gained=["sympy.core.Basic"],
            duplicate_evidence=[],
            decision="CONTINUE",
            decision_rationale="Target ambiguous; caller relationships required.",
            budget_remaining=7,
        ),
        DynamicRoundTrace(
            round_index=2,
            current_evidence_state={"candidate_count": 3, "evidence_sufficient": True, "uncertainty": 0.2},
            action_taken="GRAPH_NEIGHBORS",
            new_evidence_gained=["sympy.core.Expr", "sympy.core.Symbol"],
            duplicate_evidence=[],
            decision="STOP",
            decision_rationale="Caller-callee dependency path resolved.",
            budget_remaining=6,
        ),
    ]
    return policy, traces


def get_fixture_j_budget_exhausted() -> Tuple[RetrievalPolicy, List[RetrievalEvent]]:
    """Fixture J: Retrieval stops because configured call budget is reached."""
    policy = build_r1_semantic_policy()
    policy.max_retrieval_calls = 2
    events = [
        RetrievalEvent(
            run_id="run-j",
            task_id="task-j",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query=f"query {i}",
            evidence_mode="FIXTURE",
        )
        for i in range(2)
    ]
    return policy, events


def get_fixture_k_tool_failure_fallback() -> Tuple[RetrievalPolicy, List[RetrievalEvent]]:
    """Fixture K: Semantic retrieval raises error; policy falls back to text search."""
    policy = build_r1_semantic_policy()
    events = [
        RetrievalEvent(
            run_id="run-k",
            task_id="task-k",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="failing query",
            metadata={"status": "error", "error": "EmbeddingServiceUnavailable", "fallback_action": "EXACT_SEARCH"},
            evidence_mode="FIXTURE",
        ),
        RetrievalEvent(
            run_id="run-k",
            task_id="task-k",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.EXACT_SEARCH.value,
            query="exact search fallback",
            returned_count=1,
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, events


def get_fixture_l_cache_hit() -> Tuple[RetrievalPolicy, List[RetrievalEvent]]:
    """Fixture L: Repeated query is served from BoundedToolCache."""
    policy = build_r1_semantic_policy()
    events = [
        RetrievalEvent(
            run_id="run-l",
            task_id="task-l",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="fits header parsing",
            returned_count=2,
            unique_returned_count=2,
            retrieval_duration_ms=50.0,
            cache_hit=False,
            evidence_mode="FIXTURE",
        ),
        RetrievalEvent(
            run_id="run-l",
            task_id="task-l",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="fits header parsing",
            returned_count=2,
            unique_returned_count=0,
            duplicate_count=2,
            retrieval_duration_ms=0.5,
            cache_hit=True,
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, events


def get_fixture_m_duplicate_retrieval() -> Tuple[RetrievalPolicy, List[RetrievalEvent]]:
    """Fixture M: Duplicate query issued within the same run."""
    policy = build_r1_semantic_policy()
    events = [
        RetrievalEvent(
            run_id="run-m",
            task_id="task-m",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="identical search",
            returned_count=2,
            duplicate_count=0,
            evidence_mode="FIXTURE",
        ),
        RetrievalEvent(
            run_id="run-m",
            task_id="task-m",
            candidate_id="R1",
            retrieval_variant="R1",
            retrieval_type=RetrievalType.SEMANTIC.value,
            query="identical search",
            returned_count=2,
            duplicate_count=2,
            evidence_mode="FIXTURE",
        ),
    ]
    return policy, events


def get_fixture_n_target_improvement() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture N: Retrieval intervention reduces targeted failure from 5 to 1."""
    base_records = [
        FailureRecord(
            run_id="run-base",
            candidate_id="R0",
            task_id=f"task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 6)
    ]
    cand_records = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id="task-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
    ] + [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id=f"task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(2, 6)
    ]
    return base_records, cand_records


def get_fixture_o_target_unchanged() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture O: Retrieval intervention does not improve target failure (4 -> 4)."""
    base_records = [
        FailureRecord(
            run_id="run-base",
            candidate_id="R0",
            task_id=f"task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    cand_records = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id=f"task-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    return base_records, cand_records


def get_fixture_p_collateral_regression() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture P: Targeted failure improves (4 -> 1), but collateral regression occurs (0 -> 4 regressions)."""
    base_records = [
        FailureRecord(
            run_id="run-base",
            candidate_id="R0",
            task_id=f"target-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ] + [
        FailureRecord(
            run_id="run-base",
            candidate_id="R0",
            task_id=f"other-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    cand_records = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id="target-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="WRONG_FILE_LOCALIZATION",
            evidence_mode="FIXTURE",
        )
    ] + [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id=f"target-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
        for i in range(2, 5)
    ] + [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id=f"other-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            failure_category="TOOL_TIMEOUT",
            evidence_mode="FIXTURE",
        )
        for i in range(1, 5)
    ]
    return base_records, cand_records


def get_fixture_q_deterministic_comparison() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture Q: Deterministic candidate comparison dataset."""
    base = [
        FailureRecord(
            run_id="run-base",
            candidate_id="R0",
            task_id=f"t-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=(i % 2 == 0),
            failure_category="WRONG_FILE_LOCALIZATION" if i % 2 != 0 else None,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 11)
    ]
    cand = [
        FailureRecord(
            run_id="run-cand",
            candidate_id="R1",
            task_id=f"t-{i}",
            run_status="COMPLETED",
            is_actionable=True,
            success=True if i in (1, 3) else (i % 2 == 0),
            failure_category="WRONG_FILE_LOCALIZATION" if i not in (1, 3) and i % 2 != 0 else None,
            evidence_mode="FIXTURE",
        )
        for i in range(1, 11)
    ]
    return base, cand


def get_fixture_r_mixed_evidence_modes() -> Tuple[List[FailureRecord], List[FailureRecord]]:
    """Fixture R: Candidate attempts to mix FIXTURE and LIVE evidence modes (should be rejected)."""
    base = [
        FailureRecord(
            run_id="run-live",
            candidate_id="R0",
            task_id="task-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=False,
            evidence_mode="LIVE",
        )
    ]
    cand = [
        FailureRecord(
            run_id="run-fix",
            candidate_id="R1",
            task_id="task-1",
            run_status="COMPLETED",
            is_actionable=True,
            success=True,
            evidence_mode="FIXTURE",
        )
    ]
    return base, cand


def get_fixture_s_no_actionable_live_results() -> List[FailureRecord]:
    """Fixture S: Current real local baseline state where all runs are infrastructure/unavailable."""
    return [
        FailureRecord(
            run_id="run-unavail",
            candidate_id="R0",
            task_id=f"task-{i}",
            run_status="UNKNOWN",
            is_actionable=False,
            success=False,
            failure_category="INFRASTRUCTURE_UNAVAILABLE",
            evidence_mode="UNAVAILABLE",
        )
        for i in range(1, 5)
    ]


def get_fixture_t_manifest_hash_mismatch() -> Tuple[RetrievalCandidateManifest, RetrievalPolicy]:
    """Fixture T: Manifest records a tampered or invalid policy hash."""
    policy = build_r1_semantic_policy()
    manifest = RetrievalCandidateManifest(
        candidate_id="R1",
        parent_candidate_id="R0",
        retrieval_variant="R1",
        retrieval_policy_hash="0000000000000000000000000000000000000000000000000000000000000000",
        hypothesis=RetrievalHypothesis(
            target_failure="WRONG_FILE_LOCALIZATION",
            observation="Observed symbol mismatch",
            hypothesis="Semantic search locates symbol",
            retrieval_change="Enable search_similar_code",
            expected_signal="Reduce wrong localization",
            rejection_condition="No improvement",
        ),
        evidence_mode="FIXTURE",
    )
    return manifest, policy
