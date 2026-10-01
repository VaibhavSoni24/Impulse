# Stage 38 — LoRA Training Data Curation Report
**Dataset ID:** `L0-TOOL-DISCIPLINE-DATA-v1` (Version `1.0.0`)  
**Target Objective:** `OBJ-TOOL-DISCIPLINE` (Reduce Repeated Failing Commands & Improve Tool Invocation Correctness)  
**Parent Frozen Git Commit:** `0d66dd9cf6b8e23289c3a92bda4d12268d2b8920`  
**Dataset Status:** `BLOCKED_BY_DATA`  
**Hardware Classification:** `EXTERNAL_GPU_REQUIRED`  

---

## 1. Status and Executive Summary
The Stage 38 data construction pipeline has been fully constructed, instrumented, and verified.
Per Section 21 & 22 of Stage 38 governance and the project constitution (AGENTS.md):
- Fixture data is strictly isolated under `experiments/lora/L1-data/fixtures/` and cannot enter the curated training partition.
- Infrastructure failures (`experiments/evaluation.db`) are excluded from training data (`REJECT_INFRASTRUCTURE_ONLY`).
- Zero synthetic examples were converted into real live training data.
- The curated partitions (`curated/train.jsonl` and `curated/validation.jsonl`) contain 0 eligible records.
- Consequently, dataset status is formally recorded as: **`BLOCKED_BY_DATA`**.

---

## 2. Parent Commit & Environment
- **Parent Stage 37 Commit:** `0d66dd9cf6b8e23289c3a92bda4d12268d2b8920`
- **Root Prompt SHA-256:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`
- **Held-Out Lock SHA-256:** `80fbcabf19423f1967879ced8efa761821da03327769ad7920ad1851c1a7ee31`
- **Held-Out Tasks SHA-256:** `8dae6b4c276bd880b06abdbac0f729b48c4fc818401f3e820b1a2b6f6f581fcd`

---

## 3. Dataset Identity and Objective
- **Dataset Identifier:** `L0-TOOL-DISCIPLINE-DATA-v1`
- **Objective:** `OBJ-TOOL-DISCIPLINE`
- **Target Behaviors:**
  - Selecting correct available tools from declarative schemas.
  - Avoiding repeated invocation of commands that just failed without new evidence.
  - Updating hypotheses when tool observations falsify prior assumptions.
  - Executing minimum useful tool calls rather than broad exploratory dumps.
  - Avoiding redundant status / check polls when repository state has not changed.

---

## 4. Source Inventory and Provenance
| Source Identifier | Path | Format | Raw Count | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `evaluation_db` | `experiments/evaluation.db` | SQLite | 5 runs | REJECT_INFRASTRUCTURE_ONLY | Local host lacked CUDA GPU; runs unexecuted |
| `baseline_e0` | `experiments/baseline/E0/results.jsonl` | JSONL | 5 entries | REJECT_INFRASTRUCTURE_ONLY | Baseline runs unexecuted on local CPU host |
| `recovery_rec1` | `experiments/recovery/REC1/recovery_trace.jsonl` | JSONL | 2 entries | REJECT_FIXTURE_ISOLATION | Labeled `evidence_mode=FIXTURE` |
| `pipeline_fixtures` | `experiments/lora/L1-data/fixtures/fixtures.jsonl` | JSONL | 5 entries | VERIFIED_FIXTURE | Used exclusively to verify data pipeline |

---

## 5. Provenance and Licensing
All pipeline fixtures and schema validators comply with permissive licenses (`Apache-2.0`, `BSD-3-Clause`).
No unknown or unpermitted sources were admitted into the dataset.

---

## 6. Raw-Source Counts & Quality Filtering Audit
- **Raw Discovered Trajectories:** 0 eligible live traces
- **Curated Eligible Training Examples:** 0
- **Curated Eligible Validation Examples:** 0
- **Total Curated Live Examples:** 0
- **Rejection Counts by Reason:**
  - `REJECT_INFRASTRUCTURE_ONLY`: 10
  - `REJECT_FIXTURE_ISOLATION`: 2
  - `REJECT_LEAKAGE`: 0
  - `REJECT_SECRET`: 0
  - `REJECT_DUPLICATE`: 0
  - `REJECT_UNSAFE`: 0
  - `REJECT_AMBIGUOUS`: 0
  - `REJECT_NOT_PERMITTED`: 0

---

## 7. Leakage and Held-Out Benchmark Audit
- **Held-Out Tasks Audited:** 14 tasks (`benchmark/splits/v1/held_out.lock`)
- **Held-Out Task Leakage Count:** 0
- **Repo / Base-Commit Leakage Count:** 0
- **Problem Statement Leakage Count:** 0
- **Patch / Test-Patch Leakage Count:** 0
- **Cross-Split (Train vs Validation) Contamination:** 0
- **Leakage Status:** **VERIFIED_ZERO_LEAKAGE**

---

## 8. Duplicate Audit
- **Exact Hash Collisions:** 0
- **Identical Normalized Tool Sequences:** 0
- **Near-Duplicate Groups:** 0
- **Duplicate Removal Count:** 0

---

## 9. Quality and Safety Audit
- **Safety Checker:** Checked against 7 dangerous command patterns (`rm -rf`, `chmod 777`, `mkfs`, fork bombs, etc.).
- **Unsafe Command Injections:** 0
- **Quality Vector Minimums:** Evidence $\ge 0.8$, Objective Alignment $\ge 0.95$, Safety = `SAFE`.

---

## 10. Privacy & Secret Sanitization Audit
- **Zero Secrets Policy:** Enforced via `SecretSanitizer`.
- **API Keys / Credentials Detected:** 0
- **Path Sanitization:** User paths (`C:\Users\...`) normalized to `[WORKSPACE_ROOT]/`.

---

## 11. Distribution Summary
| Dimension | Category | Natural Count | Curated Count |
| :--- | :--- | :--- | :--- |
| Split | TRAIN | 0 | 0 |
| Split | VALIDATION | 0 | 0 |
| Contrastive | PAIRED_CONTRASTIVE | 0 | 0 |
| Contrastive | UNPAIRED | 0 | 0 |
| Evidence Mode | LIVE | 0 | 0 |
| Evidence Mode | FIXTURE | 5 | 0 |
| Evidence Mode | INFRASTRUCTURE_ONLY | 10 | 0 |

---

## 12. Training Contract
A formal training contract linking this dataset to Stage 39 PEFT execution was generated at:
`experiments/lora/L1-data/training_contract.json`
- **Target Model:** `gemma-4-31b-it-qat-w4a16-ct`
- **Target Role:** `ROOT_AGENT_ADAPTER`
- **Primary Metric:** `command_redundancy_count`
- **Control Candidate:** `M0`
- **Hyperparameter Policy:** Fixed variables (model, prompt, tools, metrics) are locked; training hyperparameters (rank, alpha, lr, epochs) are deferred to Stage 39 optimization.

---

## 13. Data Availability Decision and Limitations
Due to the absence of external NVIDIA GPU infrastructure (4x L4) during previous evaluation stages, local live trajectory generation was constrained. Per Section 21 & 22 of the Stage 38 specification, no synthetic records were converted into live training data. The data pipeline is complete and verified, awaiting execution of live traces on target GPU infrastructure.

---

## 14. Explicit LoRA Training Declaration
**NO LORA TRAINING OCCURRED DURING STAGE 38.**
- No PEFT or PyTorch training loops were executed.
- No adapter weights (`adapter_model.safetensors`) were generated or downloaded.
- No adapter configuration was activated in `agent.yaml`.
