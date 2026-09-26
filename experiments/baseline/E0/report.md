# Baseline Evaluation Report — Candidate IMPULSE-E0

**Experiment ID:** EXP-BASELINE-E0-SMOKE  
**Candidate Identifier:** `E0`  
**Date:** 2026-09-26  
**Status:** Evaluation Record Established / Execution Unavailable on Local Workstation  
**Authoritative References:** [PLAN.md](file:///E:/Projects/Impulse/PLAN.md), [IMPULSE.md](file:///E:/Projects/Impulse/IMPULSE.md), [HARNESS_README.md](file:///E:/Projects/Impulse/data/competition/HARNESS_README.md), [manifest.json](file:///E:/Projects/Impulse/experiments/baseline/E0/manifest.json)

---

## 1. Candidate Identity & Version Control

- **Candidate ID:** `E0`
- **Git Commit:** `99c0da320af4940f4eca27d172592d1ed706d26f` (`99c0da3`)
- **Git Tag:** `E0-baseline`
- **Candidate Path:** `agent/`
- **Architecture Role:** Frozen, minimal, single-agent inference baseline. Designed to establish the zero-point for all future architectural ablations (retrieval, graph reasoning, sub-agents, skills, recovery loops, and LoRA).
- **Candidate Frozen Status:** **FROZEN**. `agent/agent.yaml` and `agent/prompts/root.md` are locked at `99c0da3`. No further modifications will be made to E0. All subsequent experiments will introduce new candidate identifiers (`E1`, `E2`, etc.).

---

## 2. Model & Generation Specification

- **Model Identifier:** `gemma-4-31b-it-qat-w4a16-ct`
  - Base Model: Gemma 4 31B Instruction-Tuned
  - Quantization: Quantization-Aware Training (QAT), 4-bit weights, 16-bit activations
  - Storage/Checkpoint Format: Compressed Tensors (`compressed-tensors`)
- **Sampling Parameters (`generate_content_config`):**
  - `temperature`: `0.2`
  - `top_p`: `0.95`
  - `max_output_tokens`: `16384`
  - `thinking_config.thinking_level`: `high`
  - `thinking_config.thinking_budget`: `4096`
  - `thinking_config.include_thoughts`: `true`
- **Active Predefined Tools:**
  1. `run_command`
  2. `read_file`
  3. `edit_file`
  4. `write_file`
  5. `get_status`
  6. `submit_patch`

---

## 3. Cryptographic Input Hashes & Reproducibility Matrix

All source files defining candidate E0 and the smoke benchmark are hashed with SHA-256:

| Artifact | Repository Path | SHA-256 Checksum |
|---|---|---|
| **Agent Configuration** | `agent/agent.yaml` | `617cc4e21b7b47974d76f4a53df52a2f7d1e8b1013c97efc0ba4bc8dfc6f5261` |
| **System Root Prompt** | `agent/prompts/root.md` | `62003214997e9231ed811bdf2faab7e0ba1234798313a4ef9743b601bc8ae431` |
| **Smoke Benchmark Set** | `benchmark/tasks/smoke.jsonl` | `4d240afe94590f3980f1e8b50dee21f3f54ca9831121b4fe0d2d3d7c0f53f0b4` |
| **Full Development Dataset** | `data/competition/tasks.jsonl` | `e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6` |

---

## 4. Benchmark Dataset Composition

- **Dataset Identifier:** `smoke`
- **Task Count:** 5 diverse development tasks extracted from `data/competition/tasks.jsonl` (total 129 tasks):
  1. `fastapi_14786` (repo: `fastapi/fastapi`, base_commit: `eacbce24c9d299c6a28110d9fc8ac50f53cddb08`, category: `easy_localization`)
  2. `rich_4070` (repo: `Textualize/rich`, base_commit: `fc41075a3206d2a5fd846c6f41c4d2becab814fa`, category: `multi_file`)
  3. `fastapi_14479` (repo: `fastapi/fastapi`, base_commit: `2b212ddd7604891d42e2ffbafe764c334230bdb7`, category: `test_driven`)
  4. `requests_6629` (repo: `psf/requests`, base_commit: `7a13c041dbef42f9f3feb14110f02626f6892e9a`, category: `misleading_surface_symptom`)
  5. `requests_7505` (repo: `psf/requests`, base_commit: `6f205ff422bccd5e4c4fc0b64c5f3e7df5181db6`, category: `graph_retrieval_candidate`)

---

## 5. Host Execution Environment & Verification Boundary

### 5.1. Local Workstation Profile
- **Operating System:** Windows 11 (`Windows-11-10.0.26200-SP0`)
- **Python Version:** 3.13.15 (`AMD64`)
- **GPU Hardware Detected:** 0 GPUs available (NVIDIA CUDA runtime absent)
- **Container Runtime:** Docker sandbox environment not locally active

### 5.2. What Was Actually Executed Locally
1. **Task Manifest & Record Loading:** Successfully verified parsing of both `benchmark/tasks/smoke.jsonl` and full `data/competition/tasks.jsonl` via `local.runner.TaskLoader`.
2. **Runner Plumbing & Pipeline Orchestration:** Successfully verified end-to-end task execution orchestration, argument parsing, candidate directory snapshotting, and `RunMetadata` generation using both `unavailable` and `dry-run` backends.
3. **Patch Capture Semantics:** Successfully proved Git-level intent staging (`git add -N .`) and unified diff capture (`git diff HEAD`) via isolated unit tests in `tests/packaging/test_patch_capture.py`.

### 5.3. What Could NOT Be Executed Locally
1. **Model Inference:** Live generation with `gemma-4-31b-it-qat-w4a16-ct` requires a high-throughput vLLM serving stack running on 4× NVIDIA L4 GPUs with `--tensor-parallel-size 4`. This infrastructure is not present on this local workstation.
2. **Interactive Sandbox Evaluation:** Running the agent loop against live repository codebases in Container A and verifying solutions in Container B requires the proprietary Linux Docker harness.

---

## 6. Per-Task Execution Status

The local task runner exercised the pipeline across all 5 smoke tasks using the `local-unavailable` backend. Results are captured in [`results.jsonl`](file:///E:/Projects/Impulse/experiments/baseline/E0/results.jsonl):

| Task ID | Candidate | Backend | Status | Inference Executed | Resolved |
|---|:---:|:---:|:---:|:---:|:---:|
| `fastapi_14786` | `E0` | `local-unavailable` | `execution_unavailable_local_host` | **No** (`false`) | `null` |
| `rich_4070` | `E0` | `local-unavailable` | `execution_unavailable_local_host` | **No** (`false`) | `null` |
| `fastapi_14479` | `E0` | `local-unavailable` | `execution_unavailable_local_host` | **No** (`false`) | `null` |
| `requests_6629` | `E0` | `local-unavailable` | `execution_unavailable_local_host` | **No** (`false`) | `null` |
| `requests_7505` | `E0` | `local-unavailable` | `execution_unavailable_local_host` | **No** (`false`) | `null` |

---

## 7. Absolute Anti-Fabrication Notice: Why No Pass Rate Is Reported

In strict accordance with the **IMPULSE Constitution (AGENTS.md Section 2.5: Zero Fabrication)**:
> *"Benchmark scores, latency measurements, and pass rates must never be fabricated or assumed. Final documentation and reports must only assert numbers and capabilities that were empirically measured and reproducible locally or on official platforms."*

- **Pass Rate:** **None reported** (`null`).
- **Fail Rate:** **None reported** (`null`).
- **Average Tool Calls:** **None reported** (`null`).
- **Average Turns:** **None reported** (`null`).

**Rationale:** Reporting 0% (or any other number) would falsely imply that inference was executed and that the agent failed on task logic. In truth, inference was never executed due to physical hardware constraints. All numeric task performance metrics remain explicitly recorded as `null` rather than `0`.

---

## 8. Requirements for First Live E0 Performance Measurement

To obtain the first genuine task-solving performance evaluation of IMPULSE-E0, the following remote environment must be provisioned:

1. **Hardware Compute:**
   - 4× NVIDIA L4 GPUs (24 GB VRAM each, 96 GB aggregate VRAM)
   - Host machine running Linux (x86_64, Ubuntu 22.04 LTS or compatible), CUDA 12.x, NVIDIA driver `>=535`
2. **Model Serving Stack:**
   - vLLM serving `gemma-4-31b-it-qat-w4a16-ct` with `--tensor-parallel-size 4`
   - Model weights mounted from competition storage
3. **Execution Runtime:**
   - Docker daemon running Container A (`Dockerfile.sandbox` / `Dockerfile.public`)
   - Pre-baked Python 3.13 wheel cache (`/wheels`)
   - Predefined tool bindings (`swegemma.tools`)
4. **Handoff Sequence for Remote Run:**
   - Run candidate E0 against `benchmark/tasks/smoke.jsonl`
   - Capture live turn logs, tool call traces, and extracted patches
   - Verify patches in Container B using `verify_task`
   - Append genuine measurements (`resolved`, `tool_calls`, `turns`, `elapsed_time_seconds`, `diff_bytes`) to `results.jsonl`
   - Update `report.md` with empirical pass rates and failure classifications
