# Stage 24: Multi-Agent Topology Experiments

## 1. Overview
Stage 24 systematically investigates the multi-agent topology design space for IMPULSE. Having developed three read-only specialists in previous stages:
- **Scout** (Stage 21: pre-edit localization)
- **Debugger** (Stage 22: post-failure diagnostic analysis)
- **Reviewer** (Stage 23: pre-submission patch assessment)

This experiment evaluates which specialist combinations materially improve problem-solving effectiveness over a pure single-agent root baseline, and whether the added token/latency cost of additional specialists is justified.

---

## 2. The Topology Matrix (M0 – M5)

| Topology | Name | Specialists Declared | Primary Role |
|---|---|---|---|
| **`M0`** | `root_only` | *(none)* | Single-agent baseline with full core tools, E9–E11 recovery, and skills. |
| **`M1`** | `root_plus_scout` | `scout` | Tests whether specialized localization assistance alone improves solving. |
| **`M2`** | `root_plus_debugger` | `debugger` | Tests whether causal failure diagnostics alone improves recovery. |
| **`M3`** | `root_plus_reviewer` | `reviewer` | Tests whether pre-submission assessment alone reduces regressions. |
| **`M4`** | `root_plus_scout_debugger` | `scout`, `debugger` | Tests combined localization + failure diagnosis without final review. |
| **`M5`** | `root_full_specialists` | `scout`, `debugger`, `reviewer` | Tests full three-specialist delegation architecture. |

*Constraint: No additional arbitrary topologies (e.g. Scout + Reviewer, 4-agent topologies) are introduced in Stage 24.*

---

## 3. Experimental Controls Held Constant

To ensure that differences in measured performance strictly reflect specialist availability rather than confounding variables:
1. **Base Model:** Exact single model `gemma-4-31b-it-qat-w4a16-ct` for Root and all specialists.
2. **Root Generation Settings:** `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096`.
3. **Root Tools:** Exact 9 competition tools across all six candidates.
4. **Specialist Tools:** Exact 5 read-only tools (`read_file`, `get_status`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`).
5. **Specialist Invariance:** Canonical byte-for-byte YAML configs and prompts for Scout, Debugger, and Reviewer.
6. **Canonical Skills:** Identical `test_strategy` and `repo_triage` across all candidates.
7. **Unified Root Prompt:** Identical byte-for-byte prompt across all candidates (`prompts/root.md`), using topology-neutral availability guidance.
8. **Downstream Subsystems:** Failure classification (E9), no-progress detection (E10), and bounded recovery (E11) remain identical.

---

## 4. Benchmark Evaluation Protocol

The evaluation protocol enforces a disciplined three-stage progression:
1. **DEV Split:** Initial multi-topology sweep to verify operational stability and collect baseline metrics.
2. **VALIDATION Split:** Controlled head-to-head comparison to evaluate pass rates and identify promising configurations.
3. **HELD_OUT Split:** Final confirmation of the leading candidate. The held-out split is never used for iterative tuning.

Each task run is subject to:
- Identical task order or recorded random seed.
- Identical 900-second per-task timeout ceiling.
- Clean repository snapshot initialization (no cross-task state leakage).

---

## 5. Metrics & Cost Accounting

Each run records:
- **Pass Rate:** Fraction of benchmark tasks resolved.
- **Runtime:** Total elapsed execution time per task.
- **Turns & Tool Calls:** Total agent turns and tool invocations.
- **Specialist Invocations:** Frequency and distribution of sub-agent calls.
- **Failure Recovery Rate:** Success rate when executing recovery paths following test failures.

---

## 6. Selection Rule

In accordance with PLAN.md Stage 24:
> *"Select the smallest topology that materially improves held-out performance."*

1. A topology can be promoted only with empirical validation and held-out confirmation.
2. If two topologies achieve statistically comparable performance (within 5% pass rate), the smaller topology (fewer specialists) is selected.
3. Candidate `M5` is never automatically selected simply because it has the most sub-agents.
4. If live benchmark execution cannot be performed, `selection_status` remains strictly **`UNRESOLVED`**.

---

## 7. Current Evidence Status

- **Candidate Submission Validation:** `PASSED` for M0, M1, M2, M3, M4, and M5.
- **Live Inference Execution:** `UNEXECUTED` (Full Gemma 4 31B local inference environment unavailable on host).
- **Benchmark Metrics:** `null` (Strict Zero-Fabrication policy in compliance with AGENTS.md §2.5).
- **Selection Status:** `UNRESOLVED`.
