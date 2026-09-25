# Stage 0 Reconciliation Report — IMPULSE

This document reconciles the authoritative live competition source of truth (from Kaggle and official competition documentation) with the project specifications ([IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) and [PLAN.md](file:///e:/Projects/Impulse/PLAN.md)).

---

## 1. Verified Matching Facts

The live competition pages and harness metadata directly confirm the core architecture and assumptions defined in `IMPULSE.md` and `PLAN.md`:

| Dimension | Specification in IMPULSE.md / PLAN.md | Live Competition Source of Truth | Status |
|---|---|---|---|
| **Competition Slug** | `gemma-4-developer-agent` | `gemma-4-developer-agent` | Confirmed |
| **Primary Base Model** | `gemma-4-31b-it-qat-w4a16-ct` | `gemma-4-31b-it-qat-w4a16-ct` (mandatory for all agents/subagents) | Confirmed |
| **Submission Format** | `submission.zip` with root `agent.yaml` | `submission.zip` with root `agent.yaml` | Confirmed |
| **Predefined Tools** | 9 exact tools (`run_command`, `submit_patch`, `get_status`, `read_file`, `edit_file`, `write_file`, `get_code_neighbors`, `search_similar_code`, `get_code_subgraph`) | Exactly identical 9 tool signatures and parameter types | Confirmed |
| **Workspace Mount** | `/workspace` | `/workspace` | Confirmed |
| **Patch Submission Mechanism** | `submit_patch()` stages via `git add -N .` and captures `git diff HEAD` | Identical: `git add -N .` followed by `git diff HEAD` from `/workspace` | Confirmed |
| **Global Budget** | 12 hours aggregate limit for all task patch submissions | 12 hours aggregate limit inclusive of sandbox setup, excluding patch validation | Confirmed |
| **Adapter Rules** | PEFT LoRA `.safetensors` format in `adapters/<name>/` (`adapter_config.json`, `adapter_model.safetensors`) | Identical; individual adapters assignable per agent | Confirmed |
| **Skill Structure** | `SKILL.md` manifest with YAML frontmatter; executed via `run_skill_script` in Docker sandbox | Identical; debited against central budget; `load_skill_resource` supported | Confirmed |
| **Evaluation Output** | Patch strings applied to fresh repos; evaluated by pytest PASS/FAIL | Outputs `/kaggle/working/submission.parquet` (`id`, `prediction`); graded by PASS/FAIL | Confirmed |

---

## 2. Refined Facts & Newly Discovered Technical Details

The live dataset and harness specifications revealed exact operational parameters that were previously general in the specifications:

1. **Exact Dataset Scale & Composition:**
   - Total archive size: **22.42 GB** across **782 files**.
   - Public training tasks: exactly **129 tasks** in `tasks.jsonl`.
   - Hidden evaluation set: approximately **120 tasks** curated from private repositories.
   - Pre-computed AST graphs: 256 NetworkX AST JSON files in `graphs/`.
   - Pre-computed embeddings: 256 `.npz` float32 256-dimensional feature archives in `embeddings/`.
   - Snapshots: 129 compressed Git working trees in `snapshots/<instance_id>.tgz`.

2. **Sandbox Runtime & Backends:**
   - Sandbox base image: **Python 3.13** (`Dockerfile.sandbox`, `Dockerfile.public`).
   - Compatibility shims: Includes `imp.py` and `telnetlib.py` to restore deprecated standard library modules removed in Python 3.13 for older repository test suites.
   - Offline wheel repository: **124 pre-compiled offline Python wheels** mounted read-only at `/wheels/` in the container.
   - Sandbox setup script: `sandbox/setup.py` automatically inspects `pyproject.toml`, installs offline wheels in editable mode, and creates a clean baseline Git commit.

3. **Core Evaluation Libraries:**
   - **`swegemma`**: The central SWE-bench evaluation harness and scoring engine.
   - **`adk-submission`**: Validates declarative agent bundles and compiles `submission.zip`.
   - **`adk-eval-core`**: Implements benchmark data models and the **3-tier resilient string replacement engine** (exact -> flexible -> regex matching) powering `edit_file`.

4. **Anti-Tampering Verification Protocol:**
   - Before evaluating patches, the grading runner executes `git checkout HEAD -- <test_paths>` and `git clean` on all test files.
   - Any agent modification to unit tests is automatically wiped out, guaranteeing that solutions must be achieved purely through functional source edits.

5. **Context Window Management:**
   - While Gemma 4 31B supports a 256K token context window, the harness technical guide specifies an operational context target of **32,768 tokens** for active context compaction and prompt budgeting.

---

## 3. Discrepancies & Resolutions

| Item | Specification Text | Live Source Observation | Resolution / Action |
|---|---|---|---|
| **Python Version** | General Python environment assumed in PLAN.md | Sandbox explicitly runs **Python 3.13** with 124 wheels in `/wheels/` | Host local runner and container definitions must target Python 3.13 compatibility |
| **Evaluation Output File** | Generic patch capture described | Exact output file is `/kaggle/working/submission.parquet` with `id` and `prediction` | Local evaluator must produce/verify identical Parquet schema |
| **Competition Data Access** | Assumed direct CLI download via `kaggle competitions download` | Requires active Kaggle account login and acceptance of official competition rules | User must manually accept rules and configure credentials before automated dataset download can succeed |

---

## 4. Architectural Stability Verdict

**No architectural revisions to IMPULSE are required.**
The frozen architecture defined in `IMPULSE.md` (hierarchical root engineer, read-only specialists, hybrid retrieval, progressive validation, zero-secrets discipline) is completely compatible with and supported by the live competition harness.
