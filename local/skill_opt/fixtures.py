"""Deterministic Test Fixtures for Skill Optimization Loop (Stage 36 Section 34).

Provides deterministic fixtures covering all 35 mandatory scenarios A through AI:
A. S0 immutable snapshot
B. S1 add one instruction
C. S1 remove one instruction
D. S1 reword one instruction
E. S1 reorder one instruction
F. duplicate root-prompt instruction detected
G. duplicate skill instruction detected
H. contradiction detected
I. scope leakage rejected
J. multiple skills changed rejected
K. non-skill file changed rejected
L. prompt changed rejected
M. retrieval changed rejected
N. testing policy changed rejected
O. recovery policy changed rejected
P. topology changed rejected
Q. target behavior improves
R. target behavior unchanged
S. target behavior worsens
T. collateral regression
U. context cost increases
V. redundancy decreases without task regression
W. redundancy decreases but task performance worsens
X. paired comparison
Y. ablation lineage
Z. held-out regression
AA. benchmark hash mismatch
AB. skill hash mismatch
AC. duplicate candidate ID
AD. deterministic report output
AE. candidate artifact verification
AF. no actionable LIVE skill failures
AG. infrastructure-only evidence
AH. fixture/live separation
AI. frozen Stage 24 artifact mutation attempt

All fixtures explicitly have evidence_mode = 'FIXTURE'.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from local.skill_opt.models import (
    SkillCandidateManifest,
    SkillChangeType,
    SkillContextCostMetrics,
    SkillHypothesis,
    SkillScopeType,
    SkillTaskPairOutcome,
    TaskBehaviorTransition,
)
from local.skill_opt.validator import (
    EXPECTED_MODEL_ID,
    EXPECTED_P0_PROMPT_SHA256,
    EXPECTED_R0_RETRIEVAL_POLICY_HASH,
    EXPECTED_REC0_RECOVERY_POLICY_HASH,
    EXPECTED_REPO_TRIAGE_SKILL_SHA256,
    EXPECTED_T0_TESTING_POLICY_HASH,
    EXPECTED_TEST_STRATEGY_SKILL_SHA256,
    EXPECTED_TOPOLOGY_ID,
)


def fixture_a_s0_snapshot() -> Tuple[str, SkillCandidateManifest]:
    """Fixture A: S0 immutable baseline snapshot."""
    content = "# Baseline Testing Skill\n\n- Inspect configuration.\n- Reproduce narrowly.\n"
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = SkillCandidateManifest(
        candidate_id="S0",
        parent_candidate_id="S0",
        skill_id="test_strategy",
        skill_version="1.0.0",
        skill_hash=sha,
        parent_skill_hash=sha,
        intervention_id="int_fx_a",
        scope=SkillScopeType.TESTING.value,
        change_type="NONE_BASELINE",
        changed_section="None",
        target_failure="None",
        hypothesis="Baseline snapshot",
        expected_behavior="Baseline behavior",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="BASELINE",
        decision="PROMOTED",
    )
    return content, manifest


def fixture_b_s1_add_instruction() -> Tuple[str, str, SkillCandidateManifest]:
    """Fixture B: S1 add one scoped instruction."""
    parent = "# Baseline Testing Skill\n\n- Inspect configuration.\n"
    cand = "# Baseline Testing Skill\n\n- Inspect configuration.\n- Verify exit code semantics.\n"
    p_sha = hashlib.sha256(parent.encode("utf-8")).hexdigest()
    c_sha = hashlib.sha256(cand.encode("utf-8")).hexdigest()
    manifest = SkillCandidateManifest(
        candidate_id="S1",
        parent_candidate_id="S0",
        skill_id="test_strategy",
        skill_version="1.1.0",
        skill_hash=c_sha,
        parent_skill_hash=p_sha,
        intervention_id="int_fx_b",
        scope=SkillScopeType.TESTING.value,
        change_type=SkillChangeType.ADD_INSTRUCTION.value,
        changed_section="Section 1: Verification",
        target_failure="Exit code ambiguity",
        hypothesis="Adding exit code check clarifies failure interpretation.",
        expected_behavior="Check exit codes explicitly.",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="EVALUATED",
        decision="PROMOTED",
    )
    return parent, cand, manifest


def fixture_c_s1_remove_instruction() -> Tuple[str, str, SkillCandidateManifest]:
    """Fixture C: S1 remove one redundant instruction."""
    parent = "# Baseline Testing Skill\n\n- Inspect configuration.\n- Redundant instruction here.\n"
    cand = "# Baseline Testing Skill\n\n- Inspect configuration.\n"
    p_sha = hashlib.sha256(parent.encode("utf-8")).hexdigest()
    c_sha = hashlib.sha256(cand.encode("utf-8")).hexdigest()
    manifest = SkillCandidateManifest(
        candidate_id="S1",
        parent_candidate_id="S0",
        skill_id="test_strategy",
        skill_version="1.1.0",
        skill_hash=c_sha,
        parent_skill_hash=p_sha,
        intervention_id="int_fx_c",
        scope=SkillScopeType.TESTING.value,
        change_type=SkillChangeType.REMOVE_INSTRUCTION.value,
        changed_section="Section 2",
        target_failure="Instruction bloat",
        hypothesis="Removing redundant instruction preserves quality while reducing tokens.",
        expected_behavior="Same behavior with fewer tokens.",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="EVALUATED",
        decision="PROMOTED",
    )
    return parent, cand, manifest


def fixture_d_s1_reword_instruction() -> Tuple[str, str, SkillCandidateManifest]:
    """Fixture D: S1 reword one instruction for clarity."""
    parent = "# Baseline Testing Skill\n\n- Run tests if needed.\n"
    cand = "# Baseline Testing Skill\n\n- Run targeted tests before editing source code.\n"
    p_sha = hashlib.sha256(parent.encode("utf-8")).hexdigest()
    c_sha = hashlib.sha256(cand.encode("utf-8")).hexdigest()
    manifest = SkillCandidateManifest(
        candidate_id="S1",
        parent_candidate_id="S0",
        skill_id="test_strategy",
        skill_version="1.1.0",
        skill_hash=c_sha,
        parent_skill_hash=p_sha,
        intervention_id="int_fx_d",
        scope=SkillScopeType.TESTING.value,
        change_type=SkillChangeType.REWORD_INSTRUCTION.value,
        changed_section="Section 1",
        target_failure="Vague timing guidance",
        hypothesis="Rewording instruction clarifies test timing.",
        expected_behavior="Run targeted test before editing.",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="EVALUATED",
        decision="PROMOTED",
    )
    return parent, cand, manifest


def fixture_e_s1_reorder_instruction() -> Tuple[str, str, SkillCandidateManifest]:
    """Fixture E: S1 reorder one instruction."""
    parent = "# Baseline Testing Skill\n\n- Step B: Execute tests.\n- Step A: Discover framework.\n"
    cand = "# Baseline Testing Skill\n\n- Step A: Discover framework.\n- Step B: Execute tests.\n"
    p_sha = hashlib.sha256(parent.encode("utf-8")).hexdigest()
    c_sha = hashlib.sha256(cand.encode("utf-8")).hexdigest()
    manifest = SkillCandidateManifest(
        candidate_id="S1",
        parent_candidate_id="S0",
        skill_id="test_strategy",
        skill_version="1.1.0",
        skill_hash=c_sha,
        parent_skill_hash=p_sha,
        intervention_id="int_fx_e",
        scope=SkillScopeType.TESTING.value,
        change_type=SkillChangeType.REORDER_INSTRUCTION.value,
        changed_section="Ordering",
        target_failure="Inverted execution order",
        hypothesis="Ordering discovery before execution avoids premature execution errors.",
        expected_behavior="Framework discovery precedes test execution.",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="EVALUATED",
        decision="PROMOTED",
    )
    return parent, cand, manifest


def fixture_f_duplicate_root_prompt() -> str:
    """Fixture F: skill content duplicating root prompt directive verbatim."""
    return (
        "# Duplicate Root Prompt Skill\n\n"
        "Never copy secrets, credentials, or large directory dumps into task state.\n"
    )


def fixture_g_duplicate_skill_instruction() -> str:
    """Fixture G: internal duplication within the same skill."""
    return (
        "# Internal Duplication Skill\n\n"
        "1. Inspect root configuration files before running tests.\n"
        "2. Inspect root configuration files before running tests.\n"
    )


def fixture_h_contradiction() -> str:
    """Fixture H: contradictory instructions within skill."""
    return (
        "# Contradictory Skill\n\n"
        "1. Always run the full repository suite on every step.\n"
        "2. Avoid executing broad test suites unless strictly necessary.\n"
    )


def fixture_i_scope_leakage() -> Tuple[str, List[str]]:
    """Fixture I: testing skill attempting cross-subsystem leakage."""
    skill_text = (
        "# Testing Skill with Leakage\n\n"
        "- Run pytest on test file.\n"
        "- Use search_similar_code to find code embeddings.\n"
        "- Invoke RecoveryController with max_same_action_retries = 3.\n"
        "- Call sub_agents/scout for reconnaissance.\n"
    )
    added_lines = [
        "Use search_similar_code to find code embeddings.",
        "Invoke RecoveryController with max_same_action_retries = 3.",
        "Call sub_agents/scout for reconnaissance.",
    ]
    return skill_text, added_lines


def fixture_j_multiple_skills_changed() -> List[str]:
    """Fixture J: multiple skills modified simultaneously (must be rejected)."""
    return ["test_strategy", "repo_triage"]


def fixture_k_non_skill_file_changed() -> List[str]:
    """Fixture K: non-skill file modified (must be rejected)."""
    return ["agent/agent.yaml", "experiments/candidates/M0/prompts/root.md"]


def fixture_l_prompt_changed() -> SkillCandidateManifest:
    """Fixture L: prompt hash changed (must be rejected)."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.prompt_hash = "bad_prompt_hash_12345"
    return m


def fixture_m_retrieval_changed() -> SkillCandidateManifest:
    """Fixture M: retrieval policy hash changed (must be rejected)."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.retrieval_policy_hash = "bad_retrieval_hash_12345"
    return m


def fixture_n_testing_policy_changed() -> SkillCandidateManifest:
    """Fixture N: testing policy hash changed (must be rejected)."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.testing_policy_hash = "bad_testing_hash_12345"
    return m


def fixture_o_recovery_policy_changed() -> SkillCandidateManifest:
    """Fixture O: recovery policy hash changed (must be rejected)."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.recovery_policy_hash = "bad_recovery_hash_12345"
    return m


def fixture_p_topology_changed() -> SkillCandidateManifest:
    """Fixture P: topology identity changed (must be rejected)."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.topology_identity = "triad_scout_reviewer"
    return m


def fixture_q_target_behavior_improves() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture Q: target behavior improves (fewer redundant commands, 100% pass)."""
    parent = [
        {"task_id": "task-1", "success": True, "target_failure_detected": True, "is_redundant_command": True},
        {"task_id": "task-2", "success": True, "target_failure_detected": True, "is_redundant_command": True},
    ]
    cand = [
        {"task_id": "task-1", "success": True, "target_failure_detected": False, "is_redundant_command": False},
        {"task_id": "task-2", "success": True, "target_failure_detected": False, "is_redundant_command": False},
    ]
    return parent, cand


def fixture_r_target_behavior_unchanged() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture R: target behavior unchanged."""
    parent = [{"task_id": "task-1", "success": True, "target_failure_detected": False}]
    cand = [{"task_id": "task-1", "success": True, "target_failure_detected": False}]
    return parent, cand


def fixture_s_target_behavior_worsens() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture S: target behavior worsens."""
    parent = [{"task_id": "task-1", "success": True, "target_failure_detected": False}]
    cand = [{"task_id": "task-1", "success": False, "target_failure_detected": True}]
    return parent, cand


def fixture_t_collateral_regression() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture T: target defect improves on task-1 but collateral regressions drop overall pass rate."""
    parent = [
        {"task_id": "task-1", "success": False, "target_failure_detected": True},
        {"task_id": "task-2", "success": True, "target_failure_detected": False},
        {"task_id": "task-3", "success": True, "target_failure_detected": False},
    ]
    cand = [
        {"task_id": "task-1", "success": True, "target_failure_detected": False},
        {"task_id": "task-2", "success": False, "target_failure_detected": False},  # regressed!
        {"task_id": "task-3", "success": False, "target_failure_detected": False},  # regressed!
    ]
    return parent, cand


def fixture_u_context_cost_increases() -> SkillContextCostMetrics:
    """Fixture U: context cost increases."""
    return SkillContextCostMetrics(
        char_count=5000,
        line_count=120,
        word_count=800,
        estimated_tokens=900,
        char_delta=1500,
        line_delta=30,
        word_delta=250,
        token_delta=280,
    )


def fixture_v_redundancy_decreases_without_task_regression() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture V: redundancy decreases while task performance holds."""
    parent = [{"task_id": "t1", "success": True, "is_redundant_command": True, "repeated_reconnaissance": True}]
    cand = [{"task_id": "t1", "success": True, "is_redundant_command": False, "repeated_reconnaissance": False}]
    return parent, cand


def fixture_w_redundancy_decreases_but_task_worsens() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fixture W: redundancy decreases but task breaks."""
    parent = [{"task_id": "t1", "success": True, "is_redundant_command": True}]
    cand = [{"task_id": "t1", "success": False, "is_redundant_command": False}]
    return parent, cand


def fixture_x_paired_comparison() -> List[SkillTaskPairOutcome]:
    """Fixture X: paired task outcomes across all transition categories."""
    return [
        SkillTaskPairOutcome("t1", "test_strategy", "S0", "S1", "PASS", "PASS", TaskBehaviorTransition.PASS_TO_PASS.value),
        SkillTaskPairOutcome("t2", "test_strategy", "S0", "S1", "FAIL", "PASS", TaskBehaviorTransition.FAIL_TO_PASS.value),
        SkillTaskPairOutcome("t3", "test_strategy", "S0", "S1", "PASS", "FAIL", TaskBehaviorTransition.PASS_TO_FAIL.value),
        SkillTaskPairOutcome("t4", "test_strategy", "S0", "S1", "FAIL", "FAIL", TaskBehaviorTransition.FAIL_UNCHANGED.value),
        SkillTaskPairOutcome("t5", "test_strategy", "S0", "S1", "PASS", "PASS", TaskBehaviorTransition.REDUNDANT_TO_NON_REDUNDANT.value),
    ]


def fixture_y_ablation_lineage() -> List[SkillCandidateManifest]:
    """Fixture Y: ablation lineage tracking S0 -> S1 -> S2."""
    m0 = fixture_a_s0_snapshot()[1]
    m1 = fixture_b_s1_add_instruction()[2]
    m2 = SkillCandidateManifest(
        candidate_id="S2",
        parent_candidate_id="S1",
        skill_id="test_strategy",
        skill_version="1.2.0",
        skill_hash="hash_s2",
        parent_skill_hash=m1.skill_hash,
        intervention_id="int_fx_y2",
        scope=SkillScopeType.TESTING.value,
        change_type=SkillChangeType.CLARIFY_CONDITION.value,
        changed_section="Section 3",
        target_failure="Edge case",
        hypothesis="Clarifying edge condition improves stability.",
        expected_behavior="Handle edge conditions.",
        prompt_hash=EXPECTED_P0_PROMPT_SHA256,
        retrieval_policy_hash=EXPECTED_R0_RETRIEVAL_POLICY_HASH,
        testing_policy_hash=EXPECTED_T0_TESTING_POLICY_HASH,
        recovery_policy_hash=EXPECTED_REC0_RECOVERY_POLICY_HASH,
        topology_identity=EXPECTED_TOPOLOGY_ID,
        model_id=EXPECTED_MODEL_ID,
        evidence_mode="FIXTURE",
        status="EVALUATED",
        decision="PROMOTED",
    )
    return [m0, m1, m2]


def fixture_z_held_out_regression() -> Tuple[float, float, str]:
    """Fixture Z: validation improves but held-out regresses."""
    val_delta = +0.25  # +25% on validation
    held_out_delta = -0.15  # -15% on held-out
    decision = "REJECTED_HELD_OUT_REGRESSION"
    return val_delta, held_out_delta, decision


def fixture_aa_benchmark_hash_mismatch() -> SkillCandidateManifest:
    """Fixture AA: manifest benchmark manifest hash mismatch."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.benchmark_manifest_hash = "tampered_benchmark_hash_999"
    return m


def fixture_ab_skill_hash_mismatch() -> Tuple[str, SkillCandidateManifest]:
    """Fixture AB: actual skill text hash doesn't match manifest skill_hash."""
    content = "# Skill Text\n"
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.skill_hash = "wrong_hash_00000000"
    return content, m


def fixture_ac_duplicate_candidate_id() -> SkillCandidateManifest:
    """Fixture AC: candidate_id equals parent_candidate_id for non-S0 candidate."""
    _, m = fixture_a_s0_snapshot()
    m.candidate_id = "S1"
    m.parent_candidate_id = "S1"  # Invalid! Must not match unless S0
    return m


def fixture_ad_deterministic_report_output() -> str:
    """Fixture AD: required report.md content header."""
    return "# Skill Optimization Experiment\n\n## Candidate\n- **Candidate ID:** `S1`"


def fixture_ae_candidate_artifact_verification() -> List[str]:
    """Fixture AE: all required candidate directory artifacts."""
    return [
        "SKILL.md",
        "manifest.json",
        "skill_diff.json",
        "skill_diff.md",
        "paired_results.jsonl",
        "paired_results.csv",
        "metrics.json",
        "report.md",
    ]


def fixture_af_no_actionable_live_data() -> Dict[str, Any]:
    """Fixture AF: honest recording of no actionable live benchmark data."""
    return {
        "status": "NO_ACTIONABLE_LIVE_SKILL_DATA",
        "evidence_mode": "UNAVAILABLE",
        "reason": "Host environment does not support local Gemma 4 31B GPU inference.",
        "fabricated_gains_asserted": False,
    }


def fixture_ag_infrastructure_only_evidence() -> Dict[str, Any]:
    """Fixture AG: infrastructure-only trace error."""
    return {
        "error_type": "INFRASTRUCTURE_UNAVAILABLE",
        "message": "CUDA out of memory or missing GPU device.",
        "classified_as_skill_failure": False,  # MUST NOT be blamed on skill!
    }


def fixture_ah_fixture_live_separation() -> Tuple[str, str]:
    """Fixture AH: strict isolation between FIXTURE and LIVE modes."""
    fixture_mode = "FIXTURE"
    live_mode = "LIVE"
    return fixture_mode, live_mode


def fixture_ai_frozen_stage24_mutation_attempt() -> Tuple[str, str]:
    """Fixture AI: illegal attempt to edit frozen Stage 24 skill in place."""
    forbidden_target = "agent/skills/test_strategy/SKILL.md"
    action = "EDIT_IN_PLACE_MUTATION"
    return forbidden_target, action
