# Architecture Decision Record: Multi-Agent Topology Experiments (Stage 24)

## Status
ACCEPTED (Stage 24 Implementation)

## Context
Following the construction of the three read-only specialist sub-agents:
- **Scout** (Stage 21: pre-edit repository reconnaissance and localization)
- **Debugger** (Stage 22: post-failure causal diagnostic reasoning)
- **Reviewer** (Stage 23: pre-submission patch scope and hygiene assessment)

IMPULSE must determine the optimal multi-agent topology. In complex autonomous software engineering systems, multi-agent delegation introduces substantial tradeoffs: while specialists can provide structured focus, each sub-agent invocation consumes additional model inference calls, increases wall-clock latency, and expands token budgets.

Rather than assuming that a maximal topology (all specialists enabled) is inherently superior, PLAN.md Stage 24 establishes a rigorous, controlled experiment comparing six candidate topologies (M0 through M5) to select the smallest topology that materially improves held-out performance.

---

## Decision

### 1. The Six Topology Definitions

The topology experiment strictly compares six discrete configurations:

| Topology | ID | Specialists | Architectural Role |
|---|---|---|---|
| **M0** | `root_only` | *(none)* | Baseline control: Root agent operates unilaterally using all 9 tools, skills, and E9–E11 recovery. |
| **M1** | `root_plus_scout` | `scout` | Isolates the contribution of pre-edit localization assistance. |
| **M2** | `root_plus_debugger` | `debugger` | Isolates the contribution of post-failure causal diagnostics. |
| **M3** | `root_plus_reviewer` | `reviewer` | Isolates the contribution of pre-submission patch assessment. |
| **M4** | `root_plus_scout_debugger` | `scout`, `debugger` | Evaluates combined reconnaissance and diagnosis without final review. |
| **M5** | `root_full_specialists` | `scout`, `debugger`, `reviewer` | Evaluates the full three-specialist delegation architecture. |

*Boundary Enforcement: No additional or hybrid variants (e.g. Scout + Reviewer, 4-agent ensembles, dynamic coordinator agents) are introduced in Stage 24.*

### 2. Controlled-Variable Methodology
To ensure that benchmark variance is causally attributable solely to specialist availability, all other dimensions are held strictly constant across M0 through M5:
- **Base Model:** Exact model `gemma-4-31b-it-qat-w4a16-ct` declared for Root and all specialists.
- **Root Generation Configuration:** `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096`.
- **Root Tools:** Exact 9 competition tools across all candidates.
- **Specialist Tools:** Exact 5 read-only tools across all declared specialists.
- **Specialist Invariance:** Canonical byte-for-byte YAML configs and prompts for Scout, Debugger, and Reviewer.
- **Canonical Skills:** Identical `test_strategy` and `repo_triage` skill packages.
- **Unified Root Prompt:** Identical byte-for-byte prompt across all candidates (`prompts/root.md`), using topology-neutral availability guidance.
- **Subsystems:** E9 failure classification, E10 no-progress detection, and E11 recovery paths are shared without topology-specific alterations.

### 3. Fairness and Evaluation Protocol
1. **Repository Isolation:** Each task execution must begin from a clean repository snapshot. State or file artifacts from one run are never inherited by subsequent runs.
2. **Benchmark Splits:**
   - **DEV Split:** Initial smoke testing and baseline metric collection.
   - **VALIDATION Split:** Controlled head-to-head comparison to evaluate pass rates and operational stability.
   - **HELD_OUT Split:** Final confirmation of the chosen configuration. The held-out split is never used for iterative tuning.
3. **Execution Limits:** Identical task timeout ceilings (900 seconds) and turn limits (50 turns) apply uniformly across all topologies.

### 4. Metrics & Cost Accounting
Evaluation explicitly measures the performance-to-cost tradeoff across topologies:
- **Pass Rate:** Fraction of benchmark tasks resolved.
- **Runtime:** Wall-clock seconds per task.
- **Turns & Tool Calls:** Total agent turns and tool invocations.
- **Specialist Overhead:** Total specialist invocations and average specialist calls per task.
- **Failure Recovery Rate:** Success rate when executing recovery paths following test failures.

### 5. Selection Rule: Smallest Sufficient Topology
In accordance with PLAN.md Stage 24:
> *"Select the smallest topology that materially improves held-out performance."*

The decision rule enforces:
1. **Evidence Requirement:** A topology can only be promoted when empirical validation and held-out evidence exist.
2. **Parsimony / Cost-Awareness:** If two topologies achieve statistically comparable pass rates (within a defined tolerance, e.g. 5%), the topology with fewer specialists is selected to minimize latency and token expenditure.
3. **Anti-Complexity Bias:** Candidate `M5` is not chosen simply for possessing all specialists.
4. **No-Evidence Handling:** In the absence of live benchmark inference on the local workstation, `selection_status` remains strictly **`UNRESOLVED`**. No numbers or superiority claims are fabricated.

---

## Known Limitations & Trade-Offs
1. **Model Call Inflation:** Topologies with more specialists (M4, M5) incur higher inference call counts and token usage. If localization or repair is trivial, specialist calls add latency without improving task success.
2. **Read-Only Scope:** All specialists are strictly read-only; the Root agent remains the sole author of code modifications and patch submissions.
3. **Local Benchmark Unavailability:** Official competition-scale inference (Gemma 4 31B QAT) is not hosted on local workstations, requiring selection to remain unresolved until execution on competition evaluation infrastructure.

---

## Boundary with Stage 25
Stage 24 implements **only** multi-agent topology experimentation. It does **not** implement:
- Context compaction, file fingerprint caching, or log truncation (Stage 25).
- Tool-call budgeting or rate limiting (Stage 26).
- Fine-tuning or LoRA adapter integration (Stage 27+).
