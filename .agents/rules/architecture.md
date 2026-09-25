# Architecture Rules — IMPULSE

This document specifies the architectural governance, component boundaries, and competition compliance standards for **IMPULSE**.

---

## 1. Architectural Authority

- **Specification Primacy:** [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) is the sole architectural authority. All system implementations, agent configurations, and tool designs must conform to it.
- **Sequence Primacy:** [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) dictates the sequential order of implementation, baseline establishment, ablation studies, and release candidate validation.
- **No Silent Deviations:** Experimental or opportunistic variations must not silently enter production configurations. Any architectural shift (model, topology, tool interfaces, retrieval strategy, state management) requires explicit documentation and evidence-backed justification.
- **Purpose-Driven Architecture:** Do not add components, agent layers, or tools merely because they are novel or technologically interesting. Every element must measurably improve autonomous issue resolution.

---

## 2. Core Architectural Invariants

### 2.1 Model Identity
- The primary and only supported base model across all agents and sub-agents is:
  ```text
  gemma-4-31b-it-qat-w4a16-ct
  ```
- Sub-agents must never declare alternative base models.
- Adapters (PEFT / LoRA in `.safetensors` format) are optional optimizations and may only be added after a validated, controlled ablation demonstrates measurable benefit over the base model.

### 2.2 Agent Topology & Ownership
- **Shallow Hierarchy:** IMPULSE employs a hierarchical, shallow multi-agent topology:
  - **IMPULSE Root (Autonomous Engineer):** Sole owner of the workspace and lifecycle. Decides plans, performs edits, runs tests, and executes `submit_patch()`.
  - **Scout Agent (Optional Specialist):** Read-only repository localization specialist. Identifies candidate symbols, files, and tests.
  - **Debugger Agent (Optional Specialist):** Read-only failure classification and root-cause analysis specialist. Activated on non-trivial test failures.
  - **Reviewer Agent (Optional Specialist):** Read-only pre-submission validation specialist. Checks diff cleanliness, scope discipline, and regression risks.
- **Specialist Boundary:** Specialist sub-agents are strictly advisory and read-only by default. They do not independently mutate the repository.
- **Baseline Discipline:** Development starts with a single Root Agent baseline (`E0`). Specialists are integrated incrementally (`S1`, `D1`, `V1`) only after the single-agent loop is fully baselined.

### 2.3 Tool Suite Discipline
Agents must only invoke tools exposed by the competition harness. Predefined tools comprise:
1. `run_command`: Shell commands inside `/workspace` (discovery, tests, builds).
2. `read_file`: Line-bounded exact file inspection.
3. `edit_file`: Surgical replacements in existing files.
4. `write_file`: Creation or full overwrite of files.
5. `get_status`: Live turn, budget, and workspace status inspection.
6. `submit_patch`: Final patch capture and submission.
7. `search_similar_code`: Semantic top-k code graph retrieval via embeddings.
8. `get_code_neighbors`: Call graph and dependency neighbor inspection.
9. `get_code_subgraph`: Induced subgraph retrieval for focused symbol sets.

Prompts and configurations must never advertise or attempt to invoke tools not present in the runtime toolset.

---

## 3. Strict Boundary: Submission vs. Development Infrastructure

The repository strictly isolates competition submission artifacts from local development infrastructure:

```text
IMPULSE Repository
├── agent/                  <-- COMPETITION FACING (Maps directly into submission.zip)
│   ├── agent.yaml          <-- Root configuration
│   ├── configs/            <-- Sampling / agent configs
│   ├── prompts/            <-- System and specialist prompts
│   ├── sub_agents/         <-- Sub-agent YAML declarations
│   ├── skills/             <-- Competition-compatible skills (SKILL.md, scripts)
│   └── adapters/           <-- Validated LoRA adapters (if selected)
│
├── local/                  <-- DEVELOPMENT ONLY (Excluded from submission)
│   ├── runner/             <-- Local task execution engine
│   ├── sandbox/            <-- Local container / environment runners
│   ├── evaluator/          <-- Local ground-truth patch evaluation
│   └── diagnostics/        <-- Log parsers and execution tracing
│
├── benchmark/              <-- DEVELOPMENT ONLY (Excluded from submission)
│   ├── tasks/              <-- Smoke, dev, validation, held-out manifests
│   └── results/            <-- Run outputs and performance metrics
│
├── experiments/            <-- DEVELOPMENT ONLY (Excluded from submission)
├── scripts/                <-- DEVELOPMENT ONLY (Packaging, validation, evaluation)
├── tests/                  <-- DEVELOPMENT ONLY (Unit, integration, packaging tests)
└── docs/                   <-- DEVELOPMENT ONLY (Architecture, decisions, release notes)
```

### Classification Rule
When introducing a new file or utility, classify it immediately:
- If it is required by the competition harness inside the Docker evaluation sandbox to solve issues -> place in `agent/`.
- If it is for local benchmarking, evaluation, packaging, or analysis -> place in `local/`, `scripts/`, `benchmark/`, `tests/`, or `experiments/`.
- Development utilities must never leak into `agent/` or `submission.zip`.

---

## 4. Competition Contract Compliance

All submission candidates must satisfy the Kaggle submission contract:
1. **Archive Root:** `agent.yaml` must reside at the root of `submission.zip`.
2. **Path Integrity:** Include paths in YAML must be relative, valid within the archive, and free from directory traversal (`../`).
3. **No Symlinks:** Archives must contain only regular files and directories; no symlinks.
4. **Standalone Packaging:** The submission must execute standalone within the competition sandbox without external API calls or network-dependent asset downloads.
5. **Budget Adherence:** The agent must operate strictly within the global execution budget (12 aggregate hours for all tasks) and adhere to memory and compute limitations.
