# Evaluator Flow & Harness Architecture — IMPULSE

This document records the exact evaluator pipeline, sandbox lifecycle, and grading flow established by the Google / Kaggle competition source of truth.

---

## 1. Authoritative Source Documents Inspected

- **Live Kaggle Competition Pages:**
  - Overview: `https://www.kaggle.com/competitions/gemma-4-developer-agent`
  - Data Specification & Files: `https://www.kaggle.com/competitions/gemma-4-developer-agent/data`
  - Competition Rules: `https://www.kaggle.com/competitions/gemma-4-developer-agent/rules`
  - Model Card: `https://www.kaggle.com/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct`
- **Harness & Benchmark Metadata:**
  - Primary Technical Guide: `HARNESS_README.md` (46.29 kB in competition dataset)
  - Core Libraries: `swegemma`, `adk-submission`, `adk-eval-core`
  - Sandbox Specifications: `Dockerfile.sandbox`, `Dockerfile.public`, `sandbox/setup.py`

---

## 2. Two-Container Architecture Overview

The competition implements a decoupled **Two-Container Sandbox Architecture**:

1. **Host / Evaluation Controller Container:**
   - Houses the evaluation orchestration runner (`swegemma`), submission compiler (`adk-submission`), and model inference bridge.
   - Manages model interaction with the primary base model (`gemma-4-31b-it-qat-w4a16-ct`) and routes optional `.safetensors` adapters.
   - Tracks global execution time (12-hour aggregate budget across all tasks).
   - Materializes the agent's patch intents and compiles `/kaggle/working/submission.parquet`.

2. **Isolated Task Sandbox Container (`swebench-sandbox:latest`):**
   - Air-gapped, isolated environment running **Python 3.13** and **Git**.
   - Contains repository build backends (`setuptools`, `hatchling`, `flit-core`, `poetry-core`, `pdm-backend`) and compatibility shims (`imp.py`, `telnetlib.py`).
   - Mounts pre-compiled binary wheels read-only at `/wheels/` (124 wheels) allowing offline `pip` installations.
   - Executes agent shell commands (`run_command`) and sandboxed skill scripts (`run_skill_script`) strictly inside `/workspace`.

---

## 3. Detailed Evaluator Execution Sequence

The evaluation pipeline proceeds through two distinct phases:

### Phase 1: Task Execution & Patch Extraction

```text
1. Task Selection & Metadata Load
   ├── Read benchmark task from tasks.jsonl (instance_id, repo, base_commit, problem_statement, hints_text)
   └── Load pre-computed graph (graphs/<instance_id>.json) and embeddings (embeddings/<instance_id>.npz)
       ↓
2. Sandbox Initialization
   ├── Unpack frozen repository snapshot from snapshots/<instance_id>.tgz into /workspace
   ├── Execute sandbox/setup.py inside /workspace
   │   ├── Inspect pyproject.toml / setup.cfg / requirements.txt
   │   ├── Perform offline editable install: pip install --no-index --find-links=/wheels -e .
   │   └── Create clean baseline Git commit (so git diff HEAD isolates agent edits)
   └── Verify /workspace is in a clean git status
       ↓
3. Agent Compilation & Invocation
   ├── adk-submission compiles submitted submission.zip (verifying agent.yaml at root)
   ├── Bind base model gemma-4-31b-it-qat-w4a16-ct and optional LoRA adapters
   └── Initialize agent turn loop with problem_statement and hints_text
       ↓
4. Tool Execution Loop (Governed by central 12-hour budget)
   ├── Filesystem / Shell:
   │   ├── run_command(command) -> executed via /bin/bash -c inside /workspace
   │   ├── read_file(filepath, start_line, end_line) -> 1-indexed line slicing
   │   ├── edit_file(filepath, old_string, new_string, allow_multiple)
   │   │   └── Powered by adk-eval-core 3-tier resilient string replacement (exact -> flexible -> regex)
   │   └── write_file(filepath, content) -> creates/overwrites file + mkdir -p
   ├── Graph & Semantic Intelligence:
   │   ├── search_similar_code(query, k=10) -> top-k cosine similarity over precomputed embeddings
   │   ├── get_code_neighbors(node, edge_type, max_neighbors=50) -> AST call/dependency edges
   │   └── get_code_subgraph(nodes) -> induced subgraph for specified symbols
   └── Status & Monitoring:
       └── get_status() -> live query of remaining budget and patch status
       ↓
5. Patch Extraction
   ├── Agent invokes submit_patch() (or task terminates / budget expires)
   ├── Harness executes git add -N . in /workspace (stages untracked file intents)
   ├── Harness executes git diff HEAD to capture unified patch string
   └── Record task output into /kaggle/working/submission.parquet:
       ├── id: instance_id
       └── prediction: git diff patch string (or "NO_PATCH" if no changes produced)
```

---

### Phase 2: Grading & Validation (Conducted post-task or post-submission)

```text
1. Fresh Snapshot Instantiation
   └── Instantiate a fresh, clean sandbox snapshot at base_commit
       ↓
2. Anti-Tampering Test Target Reset
   ├── Evaluator executes git checkout HEAD -- <test_paths> and git clean on test targets
   └── Discards any unauthorized modifications to unit tests or grading harnesses
       ↓
3. Patch Application
   └── Apply agent's generated prediction patch (git apply)
       ↓
4. Verification Test Application
   └── Apply official test_patch from benchmark solution
       ↓
5. Test Execution
   └── Execute pytest inside sandbox
       ↓
6. Two-Phase Outcome Determination
   ├── Fail-to-Pass Verification: Targeted test failed on baseline, must pass with patch
   ├── Pass-to-Pass Verification: Pre-existing test suite must continue to pass cleanly
   └── Grade: PASS (exit code 0) or FAIL (non-zero exit code)
```

---

## 4. Operational Boundaries & Constraints

1. **Strict 12-Hour Global Budget:** The agent has an aggregate limit of 12 hours to submit patches for all tasks. This time includes sandbox setup but excludes patch validation.
2. **Context Window & Management:** Gemma 4 31B supports up to 256K context, but the harness documentation identifies a 32,768-token operational target for active context compaction.
3. **No External Network Access:** Sandboxes are completely offline. Dependencies must resolve exclusively against the 124 wheels in `/wheels/`.
4. **Prohibited Directory Traversal:** `../` and symlinks pointing outside `/workspace` or outside `submission.zip` root are rejected by `adk-submission`.
5. **Anti-Tampering Enforcement:** Modifying test files does not allow an agent to pass; the grading runner resets all test targets before running verification.

---

## 5. Unresolved Questions & Action Items

1. **Exact Package Wheel Versions:** Numerical version strings of `swegemma`, `adk-submission`, and `adk-eval-core` reside inside the competition dataset archive; downloading requires Kaggle authentication and rules acceptance.
2. **Local Runner Emulation:** For local development on Windows or Linux, we will need to determine whether to run Docker containers matching `Dockerfile.sandbox` (Python 3.13) or run lightweight process isolation.
