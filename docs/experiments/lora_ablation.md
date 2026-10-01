# Stage 40 — LoRA Ablation Framework

## 1. Executive Summary & Scientific Purpose

Stage 40 establishes the controlled A/B/C/D ablation framework for the IMPULSE project.
Its primary objective is answering the foundational scientific question:

> **Does a trained LoRA adapter improve the specific target behavior it was trained to improve when all other major system dimensions are held strictly invariant?**

In accordance with Stage 37 (`OBJ-TOOL-DISCIPLINE`), the adapter is evaluated strictly on its ability to:
1. Reduce repeated failing shell and test commands.
2. Improve tool invocation correctness.
3. Choose productive subsequent actions following unexpected tool failures.

Because Stage 39 completed with zero eligible training data (`BLOCKED_BY_DATA`) and produced no adapter weights, the current execution state of Stage 40 is:
`STAGE 40 COMPLETE, ABLATION FRAMEWORK VERIFIED, EXECUTION BLOCKED BY MISSING ADAPTER`.

No adapter weights have been fabricated, no synthetic fixtures have been evaluated as real models, and no performance claims are asserted.

---

## 2. Experimental Design: The Four Conditions

The ablation protocol defines four controlled experimental conditions:

```
[Condition A] BASELINE_NO_ADAPTER (Frozen Stage 37-39 control)
       │
       ▼ (Primary Causal Delta: + LoRA Adapter ONLY)
[Condition B] L1_ADAPTER (Baseline + Verified L1 Adapter)
       │
       ├─────────────────────────────────┐
       ▼ (Secondary Delta: Prompt ONLY)  ▼ (Secondary Delta: Retrieval ONLY)
[Condition C] L1_ADAPTER_PROMPT_VARIANT [Condition D] L1_ADAPTER_RETRIEVAL_VARIANT
```

### Condition A: `BASELINE_NO_ADAPTER`
- Frozen competition baseline (`M0`).
- Base model: `gemma-4-31b-it-qat-w4a16-ct`.
- Root prompt hash: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`.
- 9 locked tool contracts.
- Retrieval `R0`, testing strategy `T0`, recovery policy `REC0`, topology `root_only`.
- LoRA adapter disabled (`adapter_enabled: false`).

### Condition B: `L1_ADAPTER` (Primary Comparison)
- Exactly identical to Condition A across all dimensions except that `adapter_enabled: true` and points to an approved, verified L1 adapter.
- **Critical Rule:** The comparison between Condition A and Condition B is the sole valid measure of whether the adapter itself causes behavioral change.

### Condition C: `L1_ADAPTER_PROMPT_VARIANT` (Secondary Ablation)
- Keeps the L1 adapter, base model, retrieval, testing, recovery, and topology identical to Condition B.
- Introduces an explicitly versioned prompt change (e.g. reinforcing tool discipline).
- Strictly gated: cannot be executed before Condition B is measured.

### Condition D: `L1_ADAPTER_RETRIEVAL_VARIANT` (Secondary Ablation)
- Keeps the L1 adapter, base model, prompt, testing, recovery, and topology identical to Condition B.
- Introduces a controlled retrieval configuration change (e.g. `R1` semantic retrieval).
- Strictly gated: cannot be executed before Condition B is measured.

---

## 3. Hard Adapter Gate

Before executing any evaluation involving an adapter (Conditions B, C, D), the framework executes the **Hard Adapter Gate** (`AdapterGateValidator`):

1. **Existence:** Adapter directory and files (`adapter_config.json`, weights `adapter_model.safetensors`, `manifest.json`) must exist.
2. **Model Match:** `base_model` must match `gemma-4-31b-it-qat-w4a16-ct`.
3. **Dataset Match:** `dataset_id` must match `L0-TOOL-DISCIPLINE-DATA-v1` (Version `1.0.0`).
4. **Objective Match:** `objective_id` must match `OBJ-TOOL-DISCIPLINE`.
5. **Run Status:** Manifest status must be `COMPLETED` (cannot be `BLOCKED_BY_DATA` or `FAILED`).
6. **Fixture Safety:** `evidence_mode` cannot be `FIXTURE`.
7. **Integrity:** Byte hash of adapter weights must match recorded SHA-256 in manifest.

If any check fails, execution fails closed with `MISSING_ADAPTER_ARTIFACT` or `INVALID_ADAPTER`.

---

## 4. Objective-Specific Metrics (OBJ-TOOL-DISCIPLINE)

The evaluation does not rely on aggregate pass rates alone. It computes targeted behavior metrics:

- `repeated_failing_command_count`: Number of invocations that repeat a command after an equivalent failure without intervening code edits or state changes.
- `repeated_command_rate`: Proportion of repeated commands relative to total tool calls.
- `tool_invocation_error_count`: Invocations returning non-zero exit codes or schema/syntax errors.
- `tool_invocation_error_rate`: Tool errors divided by total tool calls.
- `task_success_rate`: Overall benchmark tasks resolved.
- `avg_runtime_ms`, `avg_tool_calls`, `avg_turns`: Operational cost metrics.

---

## 5. Task-Paired Analysis & Collateral Regression

For Condition A vs Condition B, every task is paired 1-to-1 on identical task inputs:

### 2x2 Outcome Transition Matrix
- `A_PASS_B_PASS`: Solved in both conditions.
- `A_PASS_B_FAIL`: **Collateral regression!** Task solved without adapter fails with adapter.
- `A_FAIL_B_PASS`: **Target gain!** Task failing without adapter is solved with adapter.
- `A_FAIL_B_FAIL`: Unsolved in both conditions.

### Target-Specific Transitions
- `TARGET_FAILURE_RESOLVED`: Repeated command loop eliminated.
- `TARGET_FAILURE_REMAINS`: Repeated command loop persisted.
- `NEW_TARGET_FAILURE`: New repeated command loop introduced.

### Collateral Assessment
- If `A_PASS_B_FAIL > 0`: Classified as `COLLATERAL_REGRESSION`.
- If `A_FAIL_B_PASS > 0` and `A_PASS_B_FAIL == 0`: Classified as `TARGET_GAIN`.
- Otherwise: `UNCHANGED`.

---

## 6. Promotion Gate Boundary

An adapter candidate is eligible for promotion consideration only when:
1. Validation improvement on `OBJ-TOOL-DISCIPLINE` is empirically measured.
2. Zero collateral regressions (`A_PASS_B_FAIL == 0`).
3. Zero held-out benchmark regressions.
4. Runtime is within competition limits.

**Anti-Promotion Rule:** The ablation subsystem only outputs recommendation decisions (`PROMOTE`, `HOLD`, `REJECT`). It has zero capability or authority to automatically alter `agent.yaml` or promote candidate artifacts.

---

## 7. Current Blocker & CLI Usage

Current state:
- Trajectory dataset: empty (`TRAIN=0`, `VALIDATION=0`).
- Adapter weights: none produced.
- Execution status: `ABLATION_BLOCKED_BY_MISSING_ADAPTER`.

### CLI Commands
```bash
# Verify condition readiness and blocker status
python scripts/run_lora_ablation.py --verify

# Inspect the 4 ablation condition schemas
python scripts/run_lora_ablation.py --conditions

# Run dry-run validation of schemas, invariants, and benchmark manifests
python scripts/run_lora_ablation.py --dry-run

# Run primary A/B comparison (fails closed if no valid adapter)
python scripts/run_lora_ablation.py --compare

# Generate authoritative stage40 reports
python scripts/run_lora_ablation.py --report
```
