# Stage 0 Reconciliation Report — IMPULSE

This document reconciles the authoritative live competition source of truth (from Kaggle, the downloaded competition package, and `HARNESS_README.md`) with the project specifications ([IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) and [PLAN.md](file:///e:/Projects/Impulse/PLAN.md)).

---

## 1. Verified Matching Facts

Inspection of the downloaded competition artifacts (`HARNESS_README.md`, `tasks.jsonl`, `sample_submission/*`, `sandbox/setup.py`, `docker/*`, and `wheels_manifest.json`) directly confirms the core architecture and assumptions defined in `IMPULSE.md` and `PLAN.md`:

| Dimension | Specification in IMPULSE.md / PLAN.md | Live Competition Source of Truth | Status |
|---|---|---|---|
| **Competition Slug** | `gemma-4-developer-agent` | `gemma-4-developer-agent` | Confirmed |
| **Primary Base Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` (mandatory for all agents/sub-agents) | Confirmed |
| **Submission Format** | `submission.zip` with root `agent.yaml` | `submission.zip` with root `agent.yaml` (or `root_agent.yaml`) | Confirmed |
| **Predefined Tools** | 9 exact tools (`run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) | Exactly identical 9 tool signatures, parameter types, and return JSON models | Confirmed |
| **Workspace Mount** | `/workspace` | `/workspace` (`TEST_TMPDIR=/tmp`) | Confirmed |
| **Patch Submission Mechanism** | `submit_patch()` stages via `git add -N .` and captures `git diff HEAD` | Identical: `git add -N .` followed by `git diff HEAD` from `/workspace` | Confirmed |
| **Global Budget** | 12 hours aggregate limit for all task patch submissions | 12 hours aggregate limit inclusive of sandbox setup, excluding patch validation | Confirmed |
| **Adapter Rules** | PEFT LoRA `.safetensors` format in `adapters/<name>/` (`adapter_config.json`, `adapter_model.safetensors`) | Identical; individual adapters assignable per agent; max 8 LoRAs, max rank 128 | Confirmed |
| **Skill Structure** | `SKILL.md` manifest with YAML frontmatter; executed via `run_skill_script` in Docker sandbox | Identical; debited against central budget; `load_skill_resource` supported | Confirmed |
| **Evaluation Output** | Patch strings applied to fresh repos; evaluated by pytest PASS/FAIL | Outputs `/kaggle/working/submission.parquet` (`id`, `prediction`); graded by PASS/FAIL | Confirmed |

---

## 2. Refined Facts & Newly Discovered Technical Details

Detailed inspection of `HARNESS_README.md` and the actual package code revealed critical operational parameters:

1. **Hardware & Serving Infrastructure:**
   - Evaluated on **4 × NVIDIA L4 GPUs** (24 GB per GPU, **96 GB aggregate VRAM**).
   - vLLM runs on `http://127.0.0.1:8000/v1` with `tensor_parallel_size = 4`, `gpu_memory_utilization = 0.90`, `max_model_len = 32768`, `enable_lora = True`, `max_loras = 8`, `max_lora_rank = 128`.
   - Tool call & reasoning parsers: `gemma4`.
   - Context window ceiling: strictly **32,768 tokens**.

2. **Submission Sizing & Constraints:**
   - Total unpacked submission size limit is **`< 3 GiB`** (`3,221,225,472` bytes) including all `adapters/`.
   - Model weights must strictly be in `.safetensors` format (pickle-based `.bin`, `.pt` are rejected).
   - **Single Base Model Rule**: Every agent in the compiled tree must declare the exact same base model (`gemma-4-31b-it-qat-w4a16-ct`). Declaring divergent base models raises `ParticipantVisibleError`.
   - Prohibited fields: `tools`, `system_instruction`, `http_options`, `safety_settings`, `response_schema` inside `generate_content_config` raise validation errors.

3. **Tool Execution & Budget Rules:**
   - `submit_patch()` is **free** (`count_tool_call=False`) and can be called even when tool calls budget is exhausted.
   - `get_status()` is **free and un-gated**.
   - `read_file` has dual truncation: **150 lines** AND **10,000 characters**.
   - `run_command` has a 300s timeout and truncates stdout/stderr at 5,000 characters. Timeout does NOT kill the agent session.
   - `edit_file` runs `adk-eval-core`'s 3-tier resilient string replacement: (1) `exact` -> (2) `flexible` (whitespace stripped, auto re-indent) -> (3) `regex` (code delimiter tokenization).

4. **Continuation Nudges & Automatic Fallback:**
   - Outer harness loop allows up to **3 consecutive nudges** if agent turn finishes without `submit_patch()`.
   - If a turn executes at least one tool call, `consecutive_nudges` resets to 0.
   - Automatic fallback: If the agent finishes, exhausts turns, or times out without calling `submit_patch()`, the harness automatically executes `git add -N . && git diff HEAD` and proceeds to Phase 2 if any diff exists.

5. **Sandbox Runtime & Wheelhouse:**
   - Sandbox base image: **Python 3.13-slim** (`Dockerfile.sandbox`).
   - Container limits: 4 GiB RAM, 2 vCPUs, air-gapped (`network_mode="none"`).
   - Offline wheelhouse: exactly **124 pre-compiled wheels** in `/wheels/` (cataloged in `data/competition/wheels_manifest.json`), providing dependencies for Flask, Starlette, SQLModel, SQLAlchemy, Pytest, FastAPI, Typer, Pydantic, etc.
   - In-sandbox testing: `enable_sandbox_testing = True` in `agent_runner.py` (line 285).

6. **Anti-Tampering Protocol:**
   - Before evaluating patches in Container B, the harness executes `git checkout HEAD -- <test_paths>` and `git clean -f` on all test files targeted by `task.test_patch`. Agent changes to test targets are discarded.

7. **Dataset Scale & Storage Strategy:**
   - Compressed archive: **21.93 GB** across 782 files (`tasks.jsonl`, 129 snapshots, 256 graphs, 256 embeddings, 124 wheels, docker, sandbox, sample submission).
   - Core competition metadata, manifests, docker files, setup scripts, and sample submissions are stored in `data/competition/` (~50 MB).
   - Snapshots (21.93 GB) can be fetched on demand per benchmark task or staged on the larger `D:` drive partition (101 GB free) to preserve headroom on `E:` drive (40.85 GB free).

---

## 3. Discrepancies & Resolutions

| Item | Specification Text | Live Source Observation | Resolution / Action |
|---|---|---|---|
| **Python Version** | General Python environment assumed in PLAN.md | Sandbox explicitly runs **Python 3.13-slim** with 124 wheels in `/wheels/` | Local testing and development container will target Python 3.13 |
| **Evaluation Output File** | Generic patch capture described | Exact output file is `/kaggle/working/submission.parquet` with `id` and `prediction` | Local evaluator produces identical Parquet format |
| **Competition Data Access** | Assumed direct CLI download via `kaggle competitions download` | Requires active Kaggle account login and acceptance of official competition rules | User authenticated; API token verified; core assets downloaded |
| **Kaggle API Token Format** | Legacy `kaggle.json` (`username`/`key`) assumed | Kaggle now issues Bearer token `KGAT_...` saved in `~/.kaggle/access_token` | Kaggle API REST calls use `Authorization: Bearer KGAT_...` directly |

---

## 4. Architectural Stability Verdict

**No architectural revisions to IMPULSE are required.**
The frozen architecture defined in `IMPULSE.md` (hierarchical root engineer, read-only specialists, hybrid retrieval, progressive validation, zero-secrets discipline) is completely compatible with and supported by the live competition harness.
Stage 0 is formally complete. Proceed to Stage 1.

