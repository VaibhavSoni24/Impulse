# IMPULSE

**Autonomous Software-Engineering Agent for Repository-Level Issue Resolution**

---

## 1. Project Purpose

IMPULSE is an autonomous software-engineering agent designed to solve complex, repository-level GitHub issues and pass rigorous regression test suites for the **Google Gemma 4 Developer Agent Competition**. Built on top of Google Agent Development Kit (ADK) conventions and targeted at the `gemma-4-31b-it-qat-w4a16-ct` model architecture, IMPULSE structures the reasoning, localization, patch editing, and validation process into a disciplined, reproducible engineering pipeline.

---

## 2. Current Project Status

- **Status:** **Project Foundation Phase (Stage 2 Skeleton Established)**
- **Completed Stages:**
  - **Stage 0 (Competition Source of Truth):** Competition rules, dataset manifests, sandbox specifications, and evaluation lifecycle verified from authoritative competition files.
  - **Stage 1 (Development Environment):** Host system inspected, Python 3.13.15 installed side-by-side, isolated `.venv` configured, and compute strategy established.
  - **Stage 2 (Project Skeleton):** Root directory structure and Python packaging metadata initialized.
- **Current Operational Reality:**
  - Implementation is strictly in the project-foundation phase.
  - No agent logic, `agent.yaml`, prompts, or sub-agents have been implemented yet.
  - No model weights are downloaded locally; GPU-dependent model serving is designated for competition-compatible cloud/Kaggle environments.
  - No benchmarks or evaluation scores have been executed yet.

---

## 3. Authoritative Architecture & Planning Documents

The project's architectural integrity and development discipline are governed by authoritative specifications:

- **[IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md):** The authoritative architectural and system specification (Single Source of Truth for agent topology, tools, and operational models).
- **[PLAN.md](file:///e:/Projects/Impulse/PLAN.md):** The complete implementation and execution plan (Single Source of Truth for construction sequence, validation stages, and release gates).
- **[AGENTS.md](file:///e:/Projects/Impulse/AGENTS.md):** The project constitution and governance rules governing all agents and engineers.

---

## 4. Development Philosophy

1. **Evidence-Based Decisions:** All modifications and hypotheses are grounded in verifiable observation and source facts.
2. **Zero Fabrication:** Benchmark metrics, pass rates, and capabilities are never claimed without empirical measurement.
3. **Strict Reproducibility:** Fixed prompt templates, deterministic configurations, and explicit version pinning.
4. **Clean Repository Hygiene:** Clear separation between development tools, evaluation sandboxes, and the final `< 3 GiB` competition submission package.
5. **Zero Secrets Discipline:** Credentials and API tokens are never committed or stored within the repository.

---

## 5. Repository Structure

```text
IMPULSE/
├── IMPULSE.md                # System architectural specification
├── PLAN.md                   # Construction plan and release gates
├── AGENTS.md                 # Project constitution & governance
├── LICENSE                   # Custom source-available license
├── README.md                 # Project overview and current status
├── pyproject.toml            # Python project metadata foundation
├── agent/                    # Declarative agent bundle (prompts, sub-agents, skills, adapters)
│   ├── prompts/              # Modular instruction prompts
│   ├── sub_agents/           # Specialized delegate agent configurations
│   ├── skills/               # Reusable procedural skills
│   └── adapters/             # PEFT LoRA adapter weights (.safetensors)
├── local/                    # Local environment facts, manifests, and runner scaffolding
│   ├── runner/               # Local execution harness
│   ├── evaluator/            # Local evaluation routines
│   └── sandbox/              # Sandbox execution helpers
├── benchmark/                # Curated benchmark datasets and task manifests
│   └── tasks/                # SWE-bench task subsets
├── experiments/              # Experiment logs and ablation traces
├── scripts/                  # Packaging, validation, and maintenance utilities
├── tests/                    # Unit and regression test suites
└── docs/                     # Technical decision logs and environment documentation
    ├── decisions/            # Evaluator flow and Stage 0 reconciliation reports
    └── environment/          # Machine, Python, Docker, and GPU environment specs
```

---

## 6. Environment & Hardware Profile

- **Host Workstation:** Windows 11 Home Single Language (64-bit, 12th Gen Intel Core i5-1235U, 8 GB RAM, Intel Iris Xe Graphics).
- **Active Development Runtime:** Hermetic virtual environment (`.venv`) running **Python 3.13.15** (matching the competition's `python:3.13-slim` container sandbox).
- **Compute Allocation Policy:** GPU-dependent inference (requiring 4x NVIDIA L4 GPUs with 96 GB VRAM for 31B vLLM serving) will utilize Kaggle / compatible cloud compute environments. Local machine serves as the authoring, packaging, and validation platform.

---

## 7. Licensing

This project is released under a **Custom Source-Available License**.
- Free to read, study, modify, copy, and redistribute for non-commercial purposes.
- Commercial distribution requires prior written permission from the copyright holder.
- For complete terms, see the [LICENSE](file:///e:/Projects/Impulse/LICENSE) file.
