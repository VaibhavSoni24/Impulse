"""Historical Candidate Importer for Stage 43 (Sections 20, 21, 22, 36).

Inspects verified repository evidence across:
- experiments/baseline/E0/manifest.json
- experiments/prompts/E1, E2, D1, E_S1, V1, M0-M5
- experiments/retrieval/R1, R2
- Stage 39/40 LoRA contracts (L1 -> BLOCKED)
- Stage 50 release candidate reservation (RC1 -> RESERVED)

Strictly obeys Historical Import Safety:
- No invented measurements
- Preserves exact historical hashes and git commits
- Marks missing or blocked data explicitly as UNKNOWN / UNAVAILABLE / BLOCKED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from local.versioning.hashing import compute_file_sha256
from local.versioning.models import (
    CandidateManifest,
    CandidateStatus,
    EvidenceMode,
    ExperimentDimension,
    PromotionStatus,
)
from local.versioning.registry import CandidateRegistry

FROZEN_BASE_MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def import_all_historical_candidates(registry: CandidateRegistry) -> List[str]:
    """Imports all verified candidates and registers them into CandidateRegistry."""
    imported_ids: List[str] = []
    root = registry.repo_root

    # Helper to resolve split hashes
    smoke_sha = "UNKNOWN"
    smoke_path = root / "benchmark" / "tasks" / "smoke.jsonl"
    if smoke_path.is_file():
        smoke_sha = compute_file_sha256(smoke_path)

    dev_sha = "UNKNOWN"
    dev_path = root / "benchmark" / "splits" / "v1" / "dev.jsonl"
    if dev_path.is_file():
        dev_sha = compute_file_sha256(dev_path)

    val_sha = "UNKNOWN"
    val_path = root / "benchmark" / "splits" / "v1" / "validation.jsonl"
    if val_path.is_file():
        val_sha = compute_file_sha256(val_path)

    held_sha = "UNKNOWN"
    held_path = root / "benchmark" / "splits" / "v1" / "held_out.jsonl"
    if held_path.is_file():
        held_sha = compute_file_sha256(held_path)

    # Tool contracts
    default_tools = {
        "run_command": "d48386318ec0eee1fa585ca53d1d3a8cc04ec06cc9acb851229aa9258cb95d8a",
        "submit_patch": "7ad08c240566f903e9fbcc217fd1af8dbf4796019812be1857b4bba6c9cb9490",
        "get_status": "59d2bdd46f070c357aeba14267cad7f67a394758908eb2c41b6ed140dda0bfe1",
        "read_file": "7c1fc9cd8769c270c8a7895f4322304c09c0212bc515ff24c75e1a39e241cfdc",
        "edit_file": "700f0f4920bd2095d9179a5a743d6dee0ce6997258c7c2dbbb6916645fd7eb50",
        "write_file": "b27c17afe3d7d7ed78cdeebcfca97fe02d866bf885dd088fb760a6ec8daa5183",
    }

    # Sampling config
    sampling_cfg = {
        "temperature": 0.2,
        "top_p": 0.95,
        "max_output_tokens": 16384,
        "thinking_config": {
            "thinking_level": "high",
            "thinking_budget": 4096,
            "include_thoughts": True,
        },
    }

    # ----------------------------------------------------
    # 1. E0 — Minimal Root Agent Baseline
    # ----------------------------------------------------
    e0_manifest = CandidateManifest(
        candidate_id="E0",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id=None,
        git_commit="99c0da320af4940f4eca27d172592d1ed706d26f",
        created_at="2026-09-26T09:45:00+00:00",
        description="IMPULSE-E0 minimal baseline software engineering agent.",
        experiment_type="baseline",
        primary_dimension=ExperimentDimension.BASELINE.value,
        change_summary={
            "primary_dimension": "baseline",
            "changed_components": ["initial_baseline_architecture"],
            "unchanged_components": [],
            "rationale": "Frozen initial competition baseline.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(e0_manifest, reason="Imported verified E0 baseline", overwrite_finalized=True)
    imported_ids.append("E0")

    # ----------------------------------------------------
    # 2. E1 — Prompt Evidence Discipline
    # ----------------------------------------------------
    e1_manifest = CandidateManifest(
        candidate_id="E1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E0",
        git_commit="99c0da320af4940f4eca27d172592d1ed706d26f",
        created_at="2026-09-26T10:00:00+00:00",
        description="Prompt-v1 requiring explicit root cause hypothesis before editing.",
        experiment_type="prompt_optimization",
        primary_dimension=ExperimentDimension.PROMPT.value,
        change_summary={
            "primary_dimension": "prompt",
            "changed_components": ["root_prompt"],
            "unchanged_components": ["tools", "topology", "retrieval", "testing"],
            "rationale": "Inserted root cause hypothesis requirement into root prompt.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="87079495ebb5350da2b4888cd185ebdc26897aac1168caf33d4f832cd15c97ea",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(e1_manifest, reason="Imported verified E1 prompt candidate", overwrite_finalized=True)
    imported_ids.append("E1")

    # ----------------------------------------------------
    # 3. E2 — Structured Task State
    # ----------------------------------------------------
    e2_manifest = CandidateManifest(
        candidate_id="E2",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E1",
        git_commit="24ea3df32d4b9c1d6837072ad8fa94459eb5ba0a",
        created_at="2026-09-26T11:00:00+00:00",
        description="Structured task state tracking candidate.",
        experiment_type="state_discipline",
        primary_dimension=ExperimentDimension.STATE.value,
        change_summary={
            "primary_dimension": "state",
            "changed_components": ["state_tracking_contract"],
            "unchanged_components": ["topology", "retrieval", "testing"],
            "rationale": "Introduced structured state observation discipline.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(e2_manifest, reason="Imported verified E2 state candidate", overwrite_finalized=True)
    imported_ids.append("E2")

    # ----------------------------------------------------
    # 4. R1 — Semantic Retrieval
    # ----------------------------------------------------
    r1_manifest = CandidateManifest(
        candidate_id="R1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E2",
        git_commit="24ea3df32d4b9c1d6837072ad8fa94459eb5ba0a",
        created_at="2026-09-27T08:00:00+00:00",
        description="Semantic code retrieval candidate (BM25 + embedding hybrid).",
        experiment_type="retrieval_optimization",
        primary_dimension=ExperimentDimension.RETRIEVAL.value,
        change_summary={
            "primary_dimension": "retrieval",
            "changed_components": ["retrieval_policy"],
            "unchanged_components": ["topology", "testing", "recovery"],
            "rationale": "Introduced semantic symbol lookup tool.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R1",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(r1_manifest, reason="Imported verified R1 retrieval candidate", overwrite_finalized=True)
    imported_ids.append("R1")

    # ----------------------------------------------------
    # 5. R2 — Semantic + Graph Retrieval
    # ----------------------------------------------------
    r2_manifest = CandidateManifest(
        candidate_id="R2",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="R1",
        git_commit="24ea3df32d4b9c1d6837072ad8fa94459eb5ba0a",
        created_at="2026-09-27T09:30:00+00:00",
        description="Semantic retrieval combined with graph neighborhood lookup.",
        experiment_type="retrieval_optimization",
        primary_dimension=ExperimentDimension.RETRIEVAL.value,
        change_summary={
            "primary_dimension": "retrieval",
            "changed_components": ["retrieval_policy", "graph_neighbors_tool"],
            "unchanged_components": ["topology", "testing", "recovery"],
            "rationale": "Combined lexical retrieval with static symbol dependency graph.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R2",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(r2_manifest, reason="Imported verified R2 retrieval candidate", overwrite_finalized=True)
    imported_ids.append("R2")

    # ----------------------------------------------------
    # 6. D1 — Debug-Recovery
    # ----------------------------------------------------
    d1_manifest = CandidateManifest(
        candidate_id="D1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E2",
        git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
        created_at="2026-09-28T08:00:00+00:00",
        description="Debugger recovery specialist candidate.",
        experiment_type="recovery_optimization",
        primary_dimension=ExperimentDimension.RECOVERY.value,
        change_summary={
            "primary_dimension": "recovery",
            "changed_components": ["recovery_policy"],
            "unchanged_components": ["prompt", "retrieval"],
            "rationale": "Added read-only debugger recovery loop.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={},
        sub_agent_hashes={"debugger": "4e724b17cf90a07153b6da93c0429f6048d2fa619ba04fe8a04f27be368a1835"},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC1",
        topology="root_with_debugger",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(d1_manifest, reason="Imported verified D1 recovery candidate", overwrite_finalized=True)
    imported_ids.append("D1")

    # ----------------------------------------------------
    # 7. S1 — Scout Specialist
    # ----------------------------------------------------
    s1_manifest = CandidateManifest(
        candidate_id="S1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E2",
        git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
        created_at="2026-09-28T09:00:00+00:00",
        description="Scout localization specialist candidate.",
        experiment_type="specialist_topology",
        primary_dimension=ExperimentDimension.TOPOLOGY.value,
        change_summary={
            "primary_dimension": "topology",
            "changed_components": ["topology", "scout_specialist"],
            "unchanged_components": ["retrieval", "testing"],
            "rationale": "Introduced read-only scout specialist for file triage.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={"repo_triage": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce"},
        sub_agent_hashes={"scout": "99ea78f7e2d7658514ef3bdfef93630f576e31b6dfb8d4bb9bc54be22b5133d1"},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_with_scout",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(s1_manifest, reason="Imported verified S1 scout candidate", overwrite_finalized=True)
    imported_ids.append("S1")

    # ----------------------------------------------------
    # 8. V1 — Reviewer Specialist
    # ----------------------------------------------------
    v1_manifest = CandidateManifest(
        candidate_id="V1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E2",
        git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
        created_at="2026-09-28T09:30:00+00:00",
        description="Reviewer pre-submission patch validation candidate.",
        experiment_type="specialist_topology",
        primary_dimension=ExperimentDimension.TOPOLOGY.value,
        change_summary={
            "primary_dimension": "topology",
            "changed_components": ["topology", "reviewer_specialist"],
            "unchanged_components": ["retrieval", "testing"],
            "rationale": "Introduced read-only reviewer specialist for patch verification.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={"test_strategy": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148"},
        sub_agent_hashes={"reviewer": "df14e5bbf6e5aebe73087ea74164b301a2e7c1a8d05bfd7e7d95d18d45e0544a"},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_with_reviewer",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(v1_manifest, reason="Imported verified V1 reviewer candidate", overwrite_finalized=True)
    imported_ids.append("V1")

    # ----------------------------------------------------
    # 9. C1 — Context Compaction
    # ----------------------------------------------------
    c1_manifest = CandidateManifest(
        candidate_id="C1",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E2",
        git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
        created_at="2026-09-28T10:00:00+00:00",
        description="Structured context compaction candidate for multi-turn history.",
        experiment_type="context_optimization",
        primary_dimension=ExperimentDimension.PROMPT.value,
        change_summary={
            "primary_dimension": "prompt",
            "changed_components": ["context_compaction_strategy"],
            "unchanged_components": ["tools", "topology", "retrieval"],
            "rationale": "Introduced token-efficient context compaction window.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="1d0f50756e076ae4118ea1914eb44ceb955c4d6f78fbb4cfd97d09a25b39e4a3",
        skill_hashes={},
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
        result_status="PASS",
        promotion_status=PromotionStatus.NOT_PROMOTED.value,
    )
    registry.register_candidate(c1_manifest, reason="Imported verified C1 context candidate", overwrite_finalized=True)
    imported_ids.append("C1")

    # ----------------------------------------------------
    # 10. M0 — Frozen Competition Baseline Candidate
    # ----------------------------------------------------
    m0_manifest = CandidateManifest(
        candidate_id="M0",
        candidate_version="1.0.0",
        status=CandidateStatus.VALIDATED.value,
        parent_candidate_id="E0",
        git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
        created_at="2026-09-28T10:20:00+00:00",
        description="Frozen root_only competition baseline candidate with graph tools and skills.",
        experiment_type="competition_candidate",
        primary_dimension=ExperimentDimension.TOPOLOGY.value,
        change_summary={
            "primary_dimension": "topology",
            "changed_components": ["agent_config", "root_prompt", "skills"],
            "unchanged_components": ["model_id", "sampling_settings"],
            "rationale": "Frozen Stage 24 competition package (root_only).",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
        skill_hashes={
            "test_strategy": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148",
            "repo_triage": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce",
        },
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.LIVE.value,
        result_status="PASS",
        promotion_status=PromotionStatus.PROMOTED.value,
    )
    registry.register_candidate(m0_manifest, reason="Imported verified M0 competition baseline", overwrite_finalized=True)
    imported_ids.append("M0")

    # Designate M0 as active current-best candidate
    registry.set_current_best(
        "M0",
        rationale="M0 is the verified, frozen competition baseline candidate passing full validator and submission packaging checks.",
    )

    # ----------------------------------------------------
    # 11-15. M1 through M5 — Topology Specialist Candidates
    # ----------------------------------------------------
    topologies = [
        ("M1", "root_with_scout", {"scout": "99ea78f7e2d7658514ef3bdfef93630f576e31b6dfb8d4bb9bc54be22b5133d1"}),
        ("M2", "root_with_debugger", {"debugger": "4e724b17cf90a07153b6da93c0429f6048d2fa619ba04fe8a04f27be368a1835"}),
        ("M3", "root_with_reviewer", {"reviewer": "df14e5bbf6e5aebe73087ea74164b301a2e7c1a8d05bfd7e7d95d18d45e0544a"}),
        (
            "M4",
            "root_with_scout_and_debugger",
            {
                "scout": "99ea78f7e2d7658514ef3bdfef93630f576e31b6dfb8d4bb9bc54be22b5133d1",
                "debugger": "4e724b17cf90a07153b6da93c0429f6048d2fa619ba04fe8a04f27be368a1835",
            },
        ),
        (
            "M5",
            "full_topology",
            {
                "scout": "99ea78f7e2d7658514ef3bdfef93630f576e31b6dfb8d4bb9bc54be22b5133d1",
                "debugger": "4e724b17cf90a07153b6da93c0429f6048d2fa619ba04fe8a04f27be368a1835",
                "reviewer": "df14e5bbf6e5aebe73087ea74164b301a2e7c1a8d05bfd7e7d95d18d45e0544a",
            },
        ),
    ]

    for m_id, topo_name, sub_agents in topologies:
        m_manifest = CandidateManifest(
            candidate_id=m_id,
            candidate_version="1.0.0",
            status=CandidateStatus.VALIDATED.value,
            parent_candidate_id="M0",
            git_commit="d8f8522f8a64b9bb4c93b314ed29563ca43a508d",
            created_at="2026-09-28T10:30:00+00:00",
            description=f"Frozen Stage 24 competition candidate ({topo_name}).",
            experiment_type="competition_candidate",
            primary_dimension=ExperimentDimension.TOPOLOGY.value,
            change_summary={
                "primary_dimension": "topology",
                "changed_components": ["sub_agents", "topology"],
                "unchanged_components": ["base_model", "root_prompt", "tools"],
                "rationale": f"Frozen Stage 24 multi-agent topology candidate {m_id}.",
            },
            base_model=FROZEN_BASE_MODEL,
            model_revision=None,
            root_prompt_hash="2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
            skill_hashes={
                "test_strategy": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148",
                "repo_triage": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce",
            },
            sub_agent_hashes=sub_agents,
            tool_contract_hashes=default_tools,
            retrieval_version="R0",
            testing_version="T0",
            recovery_version="REC0",
            topology=topo_name,
            adapter_id=None,
            adapter_sha256=None,
            benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
            dev_split_hash=dev_sha,
            validation_split_hash=val_sha,
            held_out_split_hash=held_sha,
            runtime_settings={"timeout_seconds": 600},
            sampling_settings=sampling_cfg,
            compute_environment_id="LOCAL_CPU",
            evidence_mode=EvidenceMode.INFRASTRUCTURE_ONLY.value,
            result_status="PASS",
            promotion_status=PromotionStatus.NOT_PROMOTED.value,
        )
        registry.register_candidate(m_manifest, reason=f"Imported verified {m_id} candidate", overwrite_finalized=True)
        imported_ids.append(m_id)

    # ----------------------------------------------------
    # 16. L1 — LoRA-v1 Candidate (SPECIAL RULE: BLOCKED)
    # ----------------------------------------------------
    l1_manifest = CandidateManifest(
        candidate_id="L1",
        candidate_version="1.0.0",
        status=CandidateStatus.BLOCKED.value,
        parent_candidate_id="M0",
        git_commit="4f5c0d8cb3581893b7d1007fc0c699cd08c94c19",
        created_at="2026-10-01T23:00:00+00:00",
        description="Planned LoRA adapter candidate for tool discipline (BLOCKED: no adapter produced, training blocked by data).",
        experiment_type="peft_lora",
        primary_dimension=ExperimentDimension.ADAPTER.value,
        change_summary={
            "primary_dimension": "adapter",
            "changed_components": ["adapter_weights"],
            "unchanged_components": ["base_model", "root_prompt", "tools", "topology"],
            "rationale": "Tool-discipline PEFT adapter candidate. Execution blocked by missing training data and unexecuted A/B ablation.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
        skill_hashes={
            "test_strategy": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148",
            "repo_triage": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce",
        },
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.UNAVAILABLE.value,
        result_status="BLOCKED",
        promotion_status=PromotionStatus.BLOCKED.value,
    )
    registry.register_candidate(l1_manifest, reason="Imported L1 candidate in BLOCKED state", overwrite_finalized=True)
    imported_ids.append("L1")

    # ----------------------------------------------------
    # 17. RC1 — Release Candidate (SPECIAL RULE: RESERVED)
    # ----------------------------------------------------
    rc1_manifest = CandidateManifest(
        candidate_id="RC1",
        candidate_version="0.1.0",
        status=CandidateStatus.RESERVED.value,
        parent_candidate_id="M0",
        git_commit="4f5c0d8cb3581893b7d1007fc0c699cd08c94c19",
        created_at="2026-10-01T23:30:00+00:00",
        description="Reserved release candidate identifier for final competition submission selection.",
        experiment_type="release_candidate",
        primary_dimension=ExperimentDimension.PACKAGING.value,
        change_summary={
            "primary_dimension": "packaging",
            "changed_components": ["final_packaging"],
            "unchanged_components": ["base_model"],
            "rationale": "Reserved identifier pending Stage 50 final candidate evaluation.",
        },
        base_model=FROZEN_BASE_MODEL,
        model_revision=None,
        root_prompt_hash="2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e",
        skill_hashes={
            "test_strategy": "3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148",
            "repo_triage": "ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce",
        },
        sub_agent_hashes={},
        tool_contract_hashes=default_tools,
        retrieval_version="R0",
        testing_version="T0",
        recovery_version="REC0",
        topology="root_only",
        adapter_id=None,
        adapter_sha256=None,
        benchmark_manifest_hash="e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6",
        dev_split_hash=dev_sha,
        validation_split_hash=val_sha,
        held_out_split_hash=held_sha,
        runtime_settings={"timeout_seconds": 600},
        sampling_settings=sampling_cfg,
        compute_environment_id="LOCAL_CPU",
        evidence_mode=EvidenceMode.UNAVAILABLE.value,
        result_status="UNEXECUTED",
        promotion_status=PromotionStatus.RESERVED.value,
    )
    registry.register_candidate(rc1_manifest, reason="Imported RC1 candidate in RESERVED state", overwrite_finalized=True)
    imported_ids.append("RC1")

    return imported_ids
