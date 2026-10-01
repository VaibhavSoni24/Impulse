# Stage 41 — Multi-Adapter Experimentation Framework

## 1. Executive Purpose & Governance Status

Stage 41 defines the experimental multi-adapter orchestration architecture for IMPULSE.

> **CRITICAL ARCHITECTURAL BOUNDARY:**  
> Multi-adapter routing is an **exploratory experimental branch**, **not** part of the mandatory production architecture. The competition-ready submission architecture remains the frozen baseline (`M0`) unless a candidate adapter demonstrably satisfies the project's promotion gate.

### The Scientific Precondition Rule
In accordance with `PLAN.md` Stage 41:
> *"Only experiment with multiple adapters after a single adapter produces a measurable benefit."*

Because Stage 39/40 completed with zero training data (`BLOCKED_BY_DATA`) and no adapter was trained or validated, the single-adapter prerequisite is currently **NOT SATISFIED**.

Therefore, the current Stage 41 status is:
**`STAGE 41 COMPLETE, MULTI-ADAPTER FRAMEWORK VERIFIED, BLOCKED BY SINGLE-ADAPTER PREREQUISITE`**

No multi-adapter training occurred, no adapter weights were produced, and zero performance claims are asserted.

---

## 2. Role-to-Adapter Mapping Architecture

The multi-adapter subsystem allows binding specialized adapters to distinct agent roles while strictly preventing cross-role weight leakage:

```
[IMPULSE Multi-Agent Mesh]
       │
       ├── ROOT Agent     ──► [Root Adapter: Coding / Reasoning / Tool Discipline]
       ├── SCOUT Agent    ──► [Scout Adapter: Symbol Localization / Retrieval]
       └── REVIEWER Agent ──► [Reviewer Adapter: Patch Critique / Defect Catching]
```

### Role Isolation Invariant
- **Role Binding:** An adapter declared for `root` cannot be bound to `scout` or `reviewer`.
- **Base Model Invariance:** All adapters in any multi-adapter candidate must use the uniform competition model (`gemma-4-31b-it-qat-w4a16-ct`).
- **Status Gate:** An adapter may only be activated in a candidate when its lifecycle status is `VALIDATED`.

---

## 3. The 8-Member Experiment Matrix (MA0 - MA7)

The framework defines an 8-member factorial matrix to systematically isolate the marginal value of specialization:

| Candidate | Description | Root Adapter | Scout Adapter | Reviewer Adapter | Topology |
|---|---|---|---|---|---|
| **MA0** | Frozen Baseline Control | None | None | None | `root_only` |
| **MA1** | Single Root Adapter Control | Yes | None | None | `root_only` |
| **MA2** | Scout Adapter Only | None | Yes | None | `specialist_mesh` |
| **MA3** | Reviewer Adapter Only | None | None | Yes | `specialist_mesh` |
| **MA4** | Root + Scout Adapters | Yes | Yes | None | `specialist_mesh` |
| **MA5** | Root + Reviewer Adapters | Yes | None | Yes | `specialist_mesh` |
| **MA6** | Scout + Reviewer Specialists | None | Yes | Yes | `specialist_mesh` |
| **MA7** | Full Specialization | Yes | Yes | Yes | `specialist_mesh` |

---

## 4. Evaluation Metrics & Cost Accounting

Evaluating multi-adapter systems requires assessing both role-specific behavior and system-level overhead:

### Role-Specific Behaviors
- **Root:** Task completion, tool-discipline adherence, syntax validity, patch generation.
- **Scout:** Localization precision, irrelevant symbol filtering, downstream task success.
- **Reviewer:** Defect detection recall, false-positive critique rate.

### Specialization Costs
Multi-adapter routing carries non-trivial costs that must be empirically justified:
- Total adapter artifact storage (MB/GB).
- Model switching and VRAM initialization latency.
- Composite inference latency across multiple agents.
- Context window token consumption.

---

## 5. Promotion Gate & Production Safety

- **Held-Out Protection:** The frozen `held_out` split (`held_out.lock`) must never be used to tune adapter assignments or select role mappings.
- **Anti-Promotion Constraint:** The multi-adapter runner is purely experimental. It possesses zero capability to modify production `agent.yaml`, update frozen skills, or promote unvalidated candidates.

---

## 6. CLI Usage

```bash
# Verify single-adapter prerequisite eligibility
python scripts/run_multi_adapter.py --verify

# Inspect available adapter inventory
python scripts/run_multi_adapter.py --inventory

# Inspect the 8-member experiment matrix
python scripts/run_multi_adapter.py --matrix

# Run dry-run validation of schemas, matrix, and isolation
python scripts/run_multi_adapter.py --dry-run

# Generate authoritative stage41 reports
python scripts/run_multi_adapter.py --report
```
