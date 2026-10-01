# Stage 39 — LoRA Training Architecture and Safety Specification

## 1. Objective and Scope
Stage 39 introduces the Parameter-Efficient Fine-Tuning (PEFT / LoRA) training architecture for IMPULSE.
The adapter is dedicated strictly to:
**`OBJ-TOOL-DISCIPLINE`**: *Reduce Repeated Failing Commands & Improve Tool Invocation Correctness*.

The objective is intentionally narrow and decoupled from agent topology, root prompt engineering, test strategies, or general code synthesis. It teaches the model to:
- Inspect repository state before issuing repetitive commands.
- Avoid rerunning commands that just failed without intervening state changes or updated hypotheses.
- Formulate targeted tool calls rather than broad repository sweeps.

---

## 2. Hard Data-Availability Gate
Training is protected by a strict, non-bypassable **Data Gate**.
Before any model loading, PEFT initialization, optimizer creation, or GPU allocation, the runner verifies:
1. `dataset_id == "L0-TOOL-DISCIPLINE-DATA-v1"` and `dataset_version == "1.0.0"`.
2. `dataset_status == "DATASET_READY"`.
3. `TRAIN > 0` and `VALIDATION > 0`.
4. Zero held-out benchmark leakage across all 14 held-out tasks.
5. Zero unpermitted or unknown license sources.
6. Zero detected secrets or private tokens.
7. Fixture isolation (fixtures quarantined under `experiments/lora/L1-data/fixtures/` and barred from training).

If any check fails, training halts immediately with:
`status: BLOCKED_BY_DATA`
No weights are loaded into memory, and no adapter artifacts are generated.

---

## 3. Base Model and Invariance Constraints
The competition-supported base model is:
`gemma-4-31b-it-qat-w4a16-ct`

All other architectural dimensions remain frozen to isolate the causal impact of the adapter:
- Root prompt: `2360d4bf...`
- Tool contracts: 9 locked tool schemas
- Retrieval policy: `R0`
- Testing strategy: `T0`
- Recovery policy: `REC0`
- Topology: `root_only`

Any mutation to these frozen dimensions triggers an `InvarianceViolationError`.

---

## 4. Hyperparameter Management
Hyperparameters must be resolved through empirical experiments on target GPU infrastructure.
Mandatory parameters:
- `rank` ($r$)
- `alpha` ($\alpha$)
- `dropout`
- `learning_rate`
- `batch_size`
- `gradient_accumulation_steps`
- `epochs`
- `sequence_length`

Unselected hyperparameters are marked with the explicit sentinel `UNSELECTED`. Any execution attempt with `UNSELECTED` parameters raises `UnresolvedHyperparameterError`.

---

## 5. Hardware Requirements and Classification
Gemma 4 31B weights (~23.3 GB) require multi-GPU VRAM for LoRA fine-tuning (e.g. 4x NVIDIA L4 24GB or A100 80GB).
The local Windows host (Intel Iris Xe graphics, 0 CUDA GPUs) is classified as:
`TRAINING_HARDWARE_UNAVAILABLE`

The training runner is portable to external GPU clusters and enforces that training is executed only on verified CUDA hardware.

---

## 6. Execution Modes
1. **Deterministic Verification:**
   ```bash
   python scripts/run_lora_training.py --verify
   ```
   Evaluates all gates and reports the exact blocker reason.

2. **Dry-Run Validation:**
   ```bash
   python scripts/run_lora_training.py --dry-run
   ```
   Validates configurations, invariance, and schemas without loading model weights or allocating GPU memory.

3. **Training Invocation:**
   ```bash
   python scripts/run_lora_training.py --train [--config <path>]
   ```
   Fails closed if the data gate or hardware gate fails. Executes full SFT/PEFT loop only when all gates pass.

---

## 7. Artifact Layout and Run Manifests
For a real training run, artifacts are saved under `experiments/lora/runs/<run_id>/`:
- `manifest.json`: Complete execution metadata, hashes, seeds, and adapter SHA-256.
- `config.json`: Serialized training configuration.
- `dataset_manifest.json`: Verifiable data snapshot.
- `environment.json`: Sanitized host and package version audit (no credentials).
- `metrics.json`: Training and validation loss telemetry, steps, runtime, throughput.
- `checkpoints/`: Model adapter checkpoints.
- `report.md`: Markdown summary of the run.

If training is blocked, no fake run directory is created. Instead, a blocked feasibility record is written to `experiments/lora/blocked_run_record.json`.

---

## 8. No Automatic Promotion
**Stage 39 does NOT promote adapters to production.**
- `agent.yaml` is NOT modified.
- No release candidates are created.
- Promotion requires evaluation on the validation benchmark and zero held-out regression during Stage 40 ablation.
