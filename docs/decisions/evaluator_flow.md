# Evaluator Flow & Harness Architecture — IMPULSE

This document records the exact evaluator pipeline, sandbox lifecycle, tool implementations, and grading flow established by the Google / Kaggle competition source of truth.

---

## 1. Authoritative Source Documents Inspected

- **Live Kaggle Competition Pages:**
  - Overview: `https://www.kaggle.com/competitions/gemma-4-developer-agent`
  - Data Specification & Files: `https://www.kaggle.com/competitions/gemma-4-developer-agent/data`
  - Competition Rules: `https://www.kaggle.com/competitions/gemma-4-developer-agent/rules`
  - Model Card: `https://www.kaggle.com/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct`
- **Downloaded Competition Package Artifacts (`data/competition/`):**
  - Primary Technical Guide: `HARNESS_README.md` (654 lines, 46.29 kB — Complete evaluation harness & competitor guide)
  - Task Manifest: `tasks.jsonl` (129 public development tasks, 1.98 MB)
  - Sandbox Specifications: `docker/Dockerfile.sandbox`, `docker/Dockerfile.public`, `docker/imp.py`, `docker/telnetlib.py`, `sandbox/setup.py` (397 lines)
  - Sample Submission: `sample_submission/agent.yaml`, `sample_submission/eval_config.yaml`, `sample_submission/configs/sampling.yaml`, `sample_submission/sub_agents/code_analyzer.yaml`
  - Wheelhouse Manifest: `wheels_manifest.json` (124 offline Python wheels in `/wheels/`)
- **Core Cooperating Harness Libraries:**
  - **`swegemma`**: Central SWE-bench harness, scoring engine, two-container lifecycle manager, and tool bindings.
  - **`adk-submission`**: Declarative agent compiler (`compile_submission`), security sandbox validator, and vLLM server manager.
  - **`adk-eval-core`**: Task/result data models, 3-tier resilient string replacement engine (`apply_replacement`), token/cost tracking, and ATIF v1.7 tracing.

---

## 2. Hardware Environment & Serving Infrastructure

The evaluation environment runs on a dedicated host equipped with **4 × NVIDIA L4 GPUs** (24 GB GDDR6 per GPU, **96 GB total VRAM**):

- **Inference Server (`VllmServer` on `127.0.0.1:8000/v1`):**
  - Base model: `gemma-4-31b-it-qat-w4a16-ct` (INT4 quantized, W4A16, ~16–18 GB weight footprint across 4 GPUs, leaving ~68 GB for 32k KV cache and LoRAs).
  - Tensor parallelism: `tensor_parallel_size = 4` (sharded across all 4 L4 GPUs).
  - GPU memory utilization: `gpu_memory_utilization = 0.90` (~86.4 GB usable across 4 GPUs).
  - Context window ceiling: `max_model_len = 32768` (32,768 tokens maximum combined prompt, reasoning, and output).
  - LoRA serving: `enable_lora = True`, `max_loras = 8`, `max_lora_rank = 128`.
  - Parsers: `tool_call_parser = 'gemma4'`, `reasoning_parser = 'gemma4'`.
- **The Single Base Model Rule:**
  - All agents in a submission hierarchy (root agent, sub-agents, `agent_tool` delegates) **must declare the exact same base model**. Declaring multiple distinct base models causes immediate validation failure (`ParticipantVisibleError`).
- **LoRA Adapter Support (`adapters/`):**
  - Different agents can use different LoRA adapters (e.g., `adapter: main_lora` on root agent, `adapter: tool_lora` on code analyzer).
  - Formats: Strictly `.safetensors` PEFT LoRA directories (`adapter_config.json` + `adapter_model.safetensors`).
  - Total unpacked submission size limit: **`< 3 GiB`** (`3,221,225,472` bytes), including all adapter weights.

---

## 3. Submission Compilation Pipeline (`adk-submission`)

When a competitor submission is unpacked and compiled by the scoring runner, it proceeds through the following deterministic pipeline:

```text
submission.zip
    ↓ (Extraction & Size Check: < 3 GiB unpacked, safe relative paths)
agent.yaml (or submission/agent.yaml root discovery)
    ↓
include/resource resolution (!include YAML/Markdown/text with path sandboxing)
    ↓
schema validation (required fields: model, instruction, tools; prohibited fields check)
    ↓
agent tree compilation (recursive agent/sub-agent/tool compilation; Single Base Model enforcement)
    ↓
tool binding (predefined 9 tools bound to SwegemmaContext; agent_tool bound to sub-agents)
    ↓
adapter validation (if present: verify adapter_config.json + adapter_model.safetensors)
    ↓
runtime-ready representation (instantiated ADK Agent hierarchy bound to vLLM client)
```

1. **Extraction & Size Check:**
   - Uncompressed size must not exceed **`< 3 GiB`** (3,221,225,472 bytes).
   - All extracted paths are verified to remain within the submission root (directory traversal attempts like `../` trigger immediate error).
2. **Root Configuration Discovery:**
   - The harness searches for `agent.yaml` or `submission/agent.yaml` as the entry point.
3. **Resource & `!include` Resolution:**
   - Custom YAML loader resolves `!include <relative-path>`.
   - Files can include `.yaml`, `.yml`, `.md`, `.txt`, `.json`.
   - All targets must resolve strictly within the submission directory tree.
4. **Declarative Schema Validation:**
   - Checks presence of required top-level keys (`model`, `instruction`, `tools`).
   - Verifies the **Single Base Model Rule**: Root agent and any child agents must declare identical `model` strings (e.g. `gemma-4-31b-it-qat-w4a16-ct`).
   - Checks prohibited fields: `generate_content_config` must not declare reserved agent-level fields (`system_instruction`, `tools`, `response_schema`).
5. **Agent Tree Compilation:**
   - Compiles hierarchical agent structure (`sub_agents` and `agent_tool` references).
   - Validates that recursion / sub-agent loops do not violate tree invariants.
6. **Tool Binding:**
   - Matches declared tool names against predefined tool contracts (`run_command`, `read_file`, `edit_file`, `write_file`, `submit_patch`, `get_status`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`).
   - Unrecognized tools are rejected unless explicitly declared as custom tool extensions with schema.
7. **Adapter Validation:**
   - Any referenced adapter directory is inspected for valid PEFT LoRA files (`adapter_config.json`, `adapter_model.safetensors`).
   - Maximum active LoRAs must not exceed vLLM capacity (`max_loras = 8`, `max_lora_rank = 128`).
8. **Runtime-Ready Representation:**
   - The compiled agent hierarchy is bound to the live vLLM inference endpoint (`http://127.0.0.1:8000/v1`) and `SwegemmaContext` tools, ready to receive task prompts.

---

## 4. Two-Container Architecture & Isolation

The competition strictly separates agent execution from verification using two independent sandboxes:

| Component | Container A (Agent Sandbox) | Container B (Verification Sandbox) |
|---|---|---|
| **Role** | Executes agent tool calls, explorations, and code edits | Applies extracted patch, test patch, and runs `pytest` |
| **Base Image** | `swebench-sandbox:latest` (built from `Dockerfile.sandbox`) | `swebench-sandbox:latest` |
| **Python Version** | Python 3.13-slim | Python 3.13-slim |
| **Resources** | 4 GiB RAM (`-m 4g`), 2 vCPUs (`cpu_quota=200_000`) | 4 GiB RAM, 2 vCPUs |
| **Network** | `network_mode="none"` (completely air-gapped, no PyPI/internet) | `network_mode="none"` (completely air-gapped) |
| **Mounts** | `/workspace` (repository snapshot), `/wheels` (124 wheels) | `/workspace` (fresh snapshot), `/wheels` |
| **Lifecycle** | Created at task start, destroyed/wiped after patch extraction | Created fresh for Phase 2 verification |

---

## 5. Detailed Evaluator Execution Sequence

### Phase 1: Agent Execution & Patch Extraction
```text
1. Task Selection & Metadata Load
   ├── Read benchmark task from tasks.jsonl (instance_id, repo, base_commit, problem_statement, hints_text)
   └── Verify pre-computed graph (graphs/<repo>.json) and embeddings (embeddings/<repo>.npz)
       ↓
2. Container A Bootstrap Sequence (container_setup.py)
   ├── Extract snapshot archive into /workspace at base_commit (zero future git history)
   ├── Append ignore patterns to /workspace/.git/info/exclude (__pycache__, *.pyc, .pytest_cache, build, dist)
   ├── Run offline editable install: pip install --no-index --find-links=/wheels --no-deps -e /workspace
   ├── Stream cached test dependencies & execute /sandbox/setup.py --fast-path <repo>
   ├── Write hermetic /workspace/pytest.ini and prepend hook to /workspace/conftest.py
   └── Commit baseline: git add -A && git commit -m "baseline" --allow-empty -q
       ↓
3. Agent Session Initialization
   ├── adk-submission compiles submission directory (agent.yaml, sub-agents, prompts, adapters)
   ├── Validate single base model and < 3 GiB total size constraint
   ├── Start agent timer (context.start_agent_session() — container setup excluded from budget)
   └── Send structured initial user prompt (build_agent_prompt):
       ├── Problem Statement & Hints
       ├── Task Budget (time allowance, tool calls allowance, max turns)
       ├── Execution Environment Rules (offline, 300s command timeout, 5000 chars output limit)
       ├── Code Intelligence Tool descriptions (if graphs/embeddings exist)
       └── Workspace directory layout (first 150 entries of find . -maxdepth 3)
       ↓
4. Multi-Turn Agent Loop & Continuation Nudges
   ├── Agent invokes tools (run_command, read_file, edit_file, etc.)
   ├── Budget gate updates tool_calls_used and remaining wall-clock time
   ├── If turn finishes WITHOUT submit_patch() and without tool calls:
   │   ├── Increment consecutive_nudges (max 3)
   │   └── Inject specific nudge prompt (unclosed <|tool_call|>, MAX_TOKENS cutoff, or normal continuation)
   └── If turn executes at least one tool call: consecutive_nudges resets to 0
       ↓
5. Patch Extraction & Container A Teardown
   ├── If agent called submit_patch(): captures git add -N . && git diff HEAD
   ├── Fallback: if agent terminated without submit_patch(), harness automatically runs git add -N . && git diff HEAD
   └── Container A is wiped and stopped; proceed to Phase 2 if patch is non-empty
```

### Phase 2: Hermetic Verification & Scoring (Container B)

```text
1. Fresh Container B Instantiation
   └── Perform identical bootstrap sequence 1–7 to create eval_baseline commit (HEAD)
       ↓
2. 4-Pass Resilient Patch Application (apply_patch_in_container)
   ├── Pass 1: git apply --unsafe-paths -p1 (-3, --ignore-space-change, --recount)
   ├── Pass 2: Symlink-normalized git apply --unsafe-paths -p1
   ├── Pass 3: Prefixless git apply --unsafe-paths -p0
   └── Pass 4: GNU patch -p1 / patch -p0 (--batch --forward -l)
       ↓
3. Anti-Tampering Test Target Reset
   ├── Parse all file paths referenced in task.test_patch (+++ b/<path>)
   └── Forcefully reset targets: git checkout HEAD -- <targets> && git clean -f -- <targets>
       ↓
4. Verification Test Application & pytest Execution
   ├── Apply official task.test_patch
   └── Execute hermetic pytest:
       PYTHONSAFEPATH=1 python3 -m pytest <pytest_targets> \
         -p no:anyio -o timeout=0 -o norecursedirs=".* build dist venv" \
         -o python_classes="Test* *Test" -q
       ↓
5. Resolution Determination
   ├── resolved = True (score = 1.0) IF AND ONLY IF test_res.exit_code == 0
   └── Record metrics to task_results.jsonl and output /kaggle/working/submission.parquet
```

---

## 6. Built-In Tools Reference & Behavioral Boundaries

The 9 predefined tools in `SwegemmaContext` conform to the following verified specifications:

| Tool | Signature | Budget-Gated? | Key Behavioral Constraints |
|---|---|:---:|---|
| **`run_command`** | `run_command(command: str) -> str` | **Yes** | `/bin/bash -c` in `/workspace`. Timeout: 300s (or remaining session time). Output truncated at 5,000 chars. Timeout does NOT kill session. |
| **`submit_patch`** | `submit_patch() -> str` | **No** (`count_tool_call=False`) | Runs `git add -N . && git diff HEAD`. Sets `patch_submitted=True`. Once current turn completes, harness terminates agent loop. |
| **`get_status`** | `get_status() -> str` | **No** (un-gated) | Returns JSON with `tool_calls_used`, `tool_calls_remaining`, `time_seconds_remaining`, etc. Never fails on budget exhaustion. |
| **`read_file`** | `read_file(filepath, start_line, end_line) -> str` | **Yes** | 1-indexed line slicing. Dual truncation: max 150 lines AND max 10,000 chars. `..` traversal prohibited. |
| **`edit_file`** | `edit_file(filepath, old_string, new_string, allow_multiple) -> str` | **Yes** | **3-Tier Resilient Engine**: (1) `exact` -> (2) `flexible` (whitespace stripped, auto re-indent) -> (3) `regex` (code delimiter tokenization). Fails if `old_string` not unique and `allow_multiple=False`. |
| **`write_file`** | `write_file(filepath: str, content: str) -> str` | **Yes** | Creates or overwrites `/workspace/<filepath>`. Automatically creates parent directories (`mkdir -p`). |
| **`get_code_neighbors`** | `get_code_neighbors(node, edge_type, max_neighbors=50) -> str` | **Yes** | Queries in-memory NetworkX call graph. 4-tier symbol resolution (exact -> suffix -> case-insensitive -> substring). |
| **`search_similar_code`** | `search_similar_code(query: str, k=10) -> str` | **Yes** | Queries precomputed `.npz` cosine similarity. Requires symbol/identifier query (not conversational natural language). |
| **`get_code_subgraph`** | `get_code_subgraph(nodes: list[str]) -> str` | **Yes** | Extracts induced subgraph of interconnecting edges between symbols. |

---

## 7. Resolved Specifications & Architectural Guarantees

1. **Wheelhouse Composition:**
   - 124 pre-compiled offline wheels in `/wheels/` (cataloged in `data/competition/wheels_manifest.json`), covering repository dependencies for Flask, Starlette, SQLModel, SQLAlchemy, Pytest, FastAPI, Typer, Pydantic, Click, Jinja2, etc.
2. **Context Window Ceiling:**
   - Operational context limit is **32,768 tokens**, matching vLLM's `max_model_len=32768`. Google ADK's `EventsCompactionConfig` compacts events every 15 turns with token threshold 32,768.
3. **Local Evaluation Command:**
   - Evaluations can be executed locally via `swegemma eval` with either `--sandbox docker` (default, using `Dockerfile.sandbox`) or `--sandbox subprocess` (for environments without Docker).
4. **Temporary Reproduction Scripts:**
   - Any scratch files created under `/workspace` are captured by `git add -N . && git diff HEAD` and contaminate the patch. Reproduction scripts must be written to **`/tmp/`** or deleted before calling `submit_patch()`.
5. **No Architectural Revisions Required:**
   - IMPULSE's planned architecture (hierarchical orchestrator, code analyzer specialist, progressive reproduction, 3-tier editing alignment) matches the competition harness in every respect.

