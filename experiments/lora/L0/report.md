# Stage 37 — LoRA Feasibility / Readiness Study (L0)

## 1. Executive Result
- **L0 Readiness Decision:** **`CONDITIONALLY_READY_FOR_STAGE_38`**
- **Primary Proposed Objective:** `OBJ-TOOL-DISCIPLINE` (Reduce Repeated Failing Commands & Improve Tool Invocation Correctness)
- **Infrastructure Feasibility:** `EXTERNAL_GPU_REQUIRED`
- **Base Model:** `gemma-4-31b-it-qat-w4a16-ct` (frozen competition standard)
- **Zero Adapter Training Affirmation:** Confirmed. No LoRA adapter was trained, downloaded, or attached during Stage 37.

## 2. Frozen Baseline
- **Parent Frozen Commit:** `bad6390b8f2b26cd1125d0e14a7fa615b7987714` (Stage 36 completion)
- **Root Prompt Hash (P0):** `2360d4bf64dd`
- **Retrieval Policy Version:** `R0`
- **Testing Strategy Policy Version:** `T0`
- **Recovery Policy Version:** `REC0`
- **Topology Configuration:** `root_only` (M0 baseline)
- **Frozen Stage 24 Artifacts:** 14/14 MATCH verified

## 3. Architecture Stability
- **Overall Stability Status:** `STABLE`
- **Root Prompt:** `STABLE`
- **Topology:** `STABLE`
- **Retrieval Subsystem:** `STABLE`
- **Testing Policy:** `STABLE`
- **Recovery Policy:** `STABLE`
- **Tool Contracts:** `STABLE`
- **Canonical Skills:** `STABLE`
- **Benchmark Definition:** `STABLE`

## 4. Benchmark Stability
- **Benchmark Status:** `BENCHMARK_STABLE`
- **Source Dataset SHA-256:** `e4b3fd60f69d`
- **Split Manifest SHA-256:** `6fcba533870c`
- **Total Task Count:** 129 (dev: 67, validation: 48, held_out: 14)
- **Held-Out Lock (held_out.lock):** `80fbcabf1942` (LOCKED & VERIFIED)

## 5. Failure-Taxonomy Readiness
| Category | Definition | Observable Signal | Live Count | Fixture Count | LoRA Learnable? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Host environment constraints, missing runtime/depe... | Command exit code 127, ModuleN... | 0 | 25 | `NO` |
| `COMMAND` | Invalid command syntax, malformed CLI options, bad... | CLI syntax error message, unre... | 0 | 25 | `YES` |
| `PRE_EXISTING_FAILURE` | Test was already failing in baseline verification ... | Clean baseline test execution ... | 0 | 25 | `NO` |
| `REGRESSION` | Test passed in baseline, but failed after changes ... | Passing test switches to faili... | 0 | 25 | `YES` |
| `INCOMPLETE_FIX` | Fix is directionally aligned with hypothesis, but ... | Reproduction test passes, but ... | 0 | 25 | `YES` |
| `WRONG_HYPOTHESIS` | Failure evidence contradicts the root-cause hypoth... | Test failure persists unchange... | 0 | 25 | `YES` |
| `NEW_EDGE_CASE` | Core fix functional, but an unconsidered boundary ... | New assertion failure on bound... | 0 | 25 | `YES` |
| `UNKNOWN` | Available evidence is ambiguous or insufficient to... | Inconclusive diagnostics, corr... | 0 | 25 | `NO` |

- **Live Data Status:** `NO_ACTIONABLE_LIVE_DATA` (local environment cannot run Gemma 4 31B GPU inference; zero fabricated observations asserted).

## 6. Root-Prompt Stability
- **Current Hash:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`
- **Stability Status:** `STABLE`
- **Revision History:** Established at Stage 24 commit `8871ba4` and unmodified across 13 consecutive stages.

## 7. Tool-Contract Stability
- **Predefined Tools Audited:** 9 tools (`run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`)
- **Status:** `STABLE` across all 9 tool contracts.

## 8. Infrastructure Feasibility
- **Host OS:** `Windows-10-10.0.26300-SP0`
- **Python Version:** `3.10.11`
- **CUDA Available:** `NO`
- **GPU Model:** `Intel(R) Iris(R) Xe Graphics` (0 device(s))
- **Total Host RAM:** 7.68 GB
- **Free Disk:** 41.4 GB
- **PyTorch Installed:** `NO`
- **PEFT Installed:** `NO`
- **Classification:** **`EXTERNAL_GPU_REQUIRED`**
- **Rationale:** Host environment has integrated graphics (Intel(R) Iris(R) Xe Graphics) with 7.68 GB RAM and 0 NVIDIA CUDA devices. Gemma 4 31B weights (~23.3 GB) exceed host capacity. External GPU infrastructure (4x NVIDIA L4 or equivalent) is required for LoRA training/evaluation.

## 9. Candidate Training Objectives Considered
### `OBJ-TOOL-DISCIPLINE`: Reduce Repeated Failing Commands & Improve Tool Invocation Correctness
- **Problem Definition:** Agent repeatedly executes identical failing shell or test commands (FailureClass.COMMAND and Stage 19 REPEATED_COMMAND_FAILURE) without inspecting error traces or adjusting arguments.
- **Target Failure Classes:** COMMAND
- **Observable Input:** Command execution failure output (non-zero exit code or stderr) in agent context.
- **Desired Behavior:** Inspect failure trace and immediately adjust arguments, fix syntax, or choose alternative verification.
- **Evaluation Metric:** `command_redundancy_count and repeated_command_loop_rate`
- **Status:** **`PRIMARY_SELECTED`**

### `OBJ-TARGETED-TEST-SELECTION`: Improve Targeted Test Selection After Code Edits
- **Problem Definition:** Agent executes broad repository test sweeps or irrelevant test files after a localized edit, exhausting tool call and execution time budgets.
- **Target Failure Classes:** COMMAND, REGRESSION
- **Observable Input:** Source code diff and repository test directory structure.
- **Desired Behavior:** Formulate narrow test command targeting the specific test module exercising modified symbols.
- **Evaluation Metric:** `targeted_test_selection_accuracy and irrelevant_tests_executed_count`
- **Status:** **`SECONDARY_CANDIDATE`**

### `OBJ-GENERIC-SWE-AGENT`: General Autonomous Software Engineering Capability
- **Problem Definition:** Make the agent generically smarter and solve more SWE-bench repository defects.
- **Target Failure Classes:** ALL
- **Observable Input:** Complete issue statement and entire repository tree.
- **Desired Behavior:** Solve all tasks correctly without error.
- **Evaluation Metric:** `overall_pass_rate`
- **Status:** **`REJECTED_TOO_BROAD`**

## 10. Selected Objective
- **Primary Selected Objective:** `OBJ-TOOL-DISCIPLINE`
- **Justification:** Agent repeatedly executes identical failing shell or test commands (FailureClass.COMMAND and Stage 19 REPEATED_COMMAND_FAILURE) without inspecting error traces or adjusting arguments.

## 11. Controlled Experiment Contract
- **Baseline Candidate:** `M0`
- **Experimental Candidate:** `L1`
- **Target Model:** `gemma-4-31b-it-qat-w4a16-ct`
- **Primary Metric:** `command_redundancy_count`
- **Promotion Gate:** `VALIDATION_IMPROVEMENT_AND_NO_HELD_OUT_REGRESSION`
- **Stop Conditions:** HELD_OUT_REGRESSION, TOOL_SCHEMA_VIOLATION, NON_TARGET_BEHAVIOR_COLLATERAL_DROP, COLLATERAL_PASS_TO_FAIL_REGRESSION

## 12. No-Adapter Control Definition
The future experiment compares:
- **Control (A):** Frozen baseline (M0 root_only, P0 prompt, R0 retrieval, T0 testing, REC0 recovery, frozen skills, no adapter).
- **Candidate (B):** Same baseline + exactly ONE LoRA adapter targeting `OBJ-TOOL-DISCIPLINE`.
- Invariant: Same prompt, same tools, same retrieval, same testing strategy, same recovery, same topology, same tasks, same model.

## 13. Measurement Protocol
- **Validation Gate:** Improved primary metric on validation split without degrading task success.
- **Held-Out Protection:** Zero regression permitted on held-out tasks.
- **Clean-Copy Evaluation:** Evaluated strictly via Stage 28 clean-copy isolated workspaces.

## 14. Known Blockers
- Local Windows host lacks NVIDIA CUDA hardware for Gemma 4 31B inference/training.
- Live benchmark failure data is unavailable locally (`NO_ACTIONABLE_LIVE_DATA`).
- Stage 39 adapter execution requires remote 4x NVIDIA L4 or equivalent GPU environment.

## 15. Final L0 Decision
**`CONDITIONALLY_READY_FOR_STAGE_38`**

## 16. Explicit Affirmation: No Adapter Trained
It is explicitly affirmed that zero LoRA adapter training was executed during Stage 37. No weights were downloaded, generated, or integrated into the production agent.
