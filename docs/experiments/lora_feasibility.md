# LoRA Feasibility and Readiness Study (L0)

## 1. Why LoRA Is Being Considered Only Now
Throughout Stages 24–36, IMPULSE systematically optimized every orthogonal non-weight dimension of autonomous repository-level engineering:
- Multi-agent topology (Stage 24)
- Context compaction (Stage 25)
- Tool-call budgeting (Stage 26)
- Benchmark splits and leakage protection (Stage 29)
- Failure taxonomy and Failure-Driven Development (Stages 30–31)
- Root prompt optimization (Stage 32)
- Code graph retrieval optimization (Stage 33)
- Multi-stage test execution policy (Stage 34)
- Deterministic recovery state machine (Stage 35)
- Canonical skill optimization (Stage 36)

Only after freezing and verifying that all prompting, retrieval, tool, recovery, and test-selection boundaries are stable can an adapter experiment be causally isolated. Attempting LoRA earlier would have confounded weight adjustments with moving architectural targets.

## 2. What L0 Verifies
Stage 37 (L0) establishes a deterministic readiness gate auditing 6 governing conditions:
1. **Baseline Architecture Stability:** Multi-agent topology (`root_only`), retrieval (`R0`), testing policy (`T0`), recovery policy (`REC0`), canonical skills, and frozen Stage 24 artifacts (14/14 MATCH).
2. **Benchmark Split Stability:** Frozen v1 benchmark splits (`dev`: 67, `validation`: 48, `held_out`: 14) and cryptographic held-out lock integrity (`held_out.lock`).
3. **Failure Taxonomy Readiness:** Audit of 8 canonical failure categories and identification of learnable behavioral targets (`COMMAND`, `REGRESSION`, `INCOMPLETE_FIX`).
4. **Tool Contract Stability:** Invariance of all 9 competition tool interfaces (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`).
5. **Root Prompt Stability:** Root prompt P0 (`2360d4bf...`) verified unchanged since Stage 24 across 13 consecutive stages.
6. **Narrow Training Objective:** Selection of a behaviorally specific, measurable target (`OBJ-TOOL-DISCIPLINE`).

## 3. What Is Intentionally NOT Implemented
Stage 37 is strictly an analytical and readiness feasibility study:
- **NO adapter weights** are trained, downloaded, or attached.
- **NO dataset construction** is performed (reserved for Stage 38).
- **NO training scripts** or PEFT orchestration pipelines are created.
- **NO production configuration** or prompt is altered.
- **NO hyperparameters** (rank, alpha, learning rate) are preselected.

## 4. Candidate and Selected Objective
- **Selected Primary Objective:** `OBJ-TOOL-DISCIPLINE`
  - *Problem:* Agent repeatedly issues identical failing shell commands (`FailureClass.COMMAND` and repeated command loops) without inspecting error traces or adjusting arguments.
  - *Desired Behavior:* Inspect stderr/exit code and immediately adjust arguments, correct syntax, or select alternative verification.
  - *Metric:* `command_redundancy_count` and `repeated_command_loop_rate`.
- **Secondary Candidate:** `OBJ-TARGETED-TEST-SELECTION`
  - *Problem:* Exhausting tool call budgets on broad repository test sweeps instead of localized test selectors.
- **Rejected Objective:** `OBJ-GENERIC-SWE-AGENT`
  - *Problem:* "Make the agent smarter" is rejected as structurally unmeasurable and causally confounded across multiple subsystems.

## 5. The No-Adapter Control
Future evaluation requires an explicit, invariant control:
- **Control (A):** Frozen baseline (M0 root_only, P0 prompt, R0 retrieval, T0 testing, REC0 recovery, frozen skills, 9 tools, no adapter).
- **Candidate (B):** Same baseline + exactly ONE LoRA adapter targeting `OBJ-TOOL-DISCIPLINE`.
- **Invariance Rule:** The adapter is the *sole* experimental dimension. No prompt, tool, or policy changes may be bundled into the adapter comparison.

## 6. Known Blockers and Infrastructure Findings
- **Local Host Infrastructure:** The local development host runs Windows 10 with integrated graphics (`Intel(R) Iris(R) Xe Graphics`) and 0 NVIDIA CUDA devices.
- **Model Footprint:** Gemma 4 31B QAT W4A16 base weights occupy ~23.3 GB, exceeding local host memory.
- **External Compute Requirement:** LoRA fine-tuning and evaluation requires external GPU compute (4x NVIDIA L4 or equivalent A100 environment).
- **Live Failure Data:** Reported honestly as `NO_ACTIONABLE_LIVE_DATA`. No live benchmark distributions were fabricated.

## 7. Decision and Next Steps
- **L0 Gate Decision:** **`CONDITIONALLY_READY_FOR_STAGE_38`**
- **Stage 38 Scope:** Authorize trajectory dataset construction specifically formatted for `OBJ-TOOL-DISCIPLINE`.
- **Stage 39 Scope:** Execute controlled fine-tuning and clean-copy paired evaluation against Control A on external GPU infrastructure.
