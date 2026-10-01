# LoRA Training Data Curation Architecture & Policy (Stage 38)

## 1. Primary Objective: `OBJ-TOOL-DISCIPLINE`

In Stage 37, multi-dimensional feasibility analysis selected **`OBJ-TOOL-DISCIPLINE`** (*Reduce Repeated Failing Commands & Improve Tool Invocation Correctness*) as the sole viable candidate objective for LoRA fine-tuning in IMPULSE.

### Why OBJ-TOOL-DISCIPLINE?
1. **Narrow & Mechanistic:** LoRA fine-tuning on a 31B parameter model (`gemma-4-31b-it-qat-w4a16-ct`) is prone to catastrophic forgetting or prompt instruction dilution when trained on broad objectives (e.g. general coding, test generation, or root prompt obedience).
2. **High ROI:** Empirical failure audits across Stages 30–35 revealed that repeated command failures without intermediate state inspection or evidence updates accounted for significant wasted agent turns.
3. **Decoupled from Agent Topology:** Tool-discipline behavior can be learned purely at the action-decision boundary without altering agent prompt contracts, retrieval mechanisms, or sub-agent topology.

---

## 2. Training Example Criteria

An example qualifies for inclusion in the training dataset **only** if its learning signal directly reinforces tool-use discipline:
- **Pattern A (Path Correction):** When a command or tool fails due to an invalid path or missing target, the agent inspects the repository state or uses discovery commands instead of repeating the identical failing command.
- **Pattern B (Dependency & Environment Grounding):** When a test or script reports an uninstalled package or missing virtual environment binary, the agent queries the environment instead of blindly rerunning the command.
- **Pattern C (Hypothesis Falsification):** When a tool output disproves the current debugging hypothesis, the agent updates its hypothesis and switches to a relevant file or tool rather than perseverating on the falsified path.
- **Pattern D (State Idempotency):** The agent refrains from re-invoking tools that return static repository state (e.g. `get_status`) unless a state-altering command has been executed.

---

## 3. Exclusion Categories & Quality Filters

Candidate examples are rejected deterministically under the following failure taxonomy:
1. `REJECT_LEAKAGE`: Any example containing task IDs, problem statements, repository/base-commit pairs, or patch fingerprints matching the 14 immutable held-out benchmark tasks in `benchmark/splits/v1/held_out.lock`.
2. `REJECT_SECRET`: Any example containing private cryptographic keys, API tokens (OpenAI, Google, GitHub, etc.), or embedded URL credentials.
3. `REJECT_FIXTURE_ISOLATION`: Fixture records are strictly quarantined under `experiments/lora/L1-data/fixtures/` and prohibited from entering `curated/train.jsonl` or `curated/validation.jsonl`.
4. `REJECT_INFRASTRUCTURE_ONLY`: Trajectories reflecting local environment unavailability (such as missing CUDA hardware) are excluded.
5. `REJECT_NO_DECISION_SIGNAL`: Examples lacking clear preferred actions or grounded evidence rationales.
6. `REJECT_DUPLICATE`: Examples with identical hashes or identical normalized tool invocation chains.
7. `REJECT_UNSAFE`: Examples recommending destructive shell patterns (`rm -rf /`, `chmod 777`, fork bombs).
8. `REJECT_NOT_PERMITTED`: Data from sources lacking explicit permissive licenses (`Apache-2.0`, `BSD-3-Clause`, etc.) or lacking training permission.

---

## 4. Provenance and Licensing Policy

All training examples must have a fully resolved `ProvenanceRecord` detailing:
- `source_name`, `source_location`, and `source_type`.
- Exact license name (e.g. `Apache-2.0`, `MIT`, `BSD-3-Clause`).
- Verification that training use and redistribution are legally permitted.
Only sources with status `PERMITTED` or `PERMITTED_WITH_ATTRIBUTION` may enter the dataset. Sources with `UNKNOWN` or `NOT_PERMITTED` status are rejected.

---

## 5. Held-Out Benchmark & Cross-Split Protection

1. **Held-Out Benchmark Immutability:**
   The held-out evaluation benchmark defined in `benchmark/splits/v1/held_out.jsonl` (locked by `held_out.lock`) is cryptographically sealed. Leakage checks are run before ingestion.
2. **Train / Validation Disjoint Partitioning:**
   The training and validation sets are split deterministically (seed = 42) along task boundaries (`task_id`). No task ID or near-identical trajectory may appear in both `TRAIN` and `VALIDATION`.

---

## 6. Zero Fabrication & Fixture Isolation

Under the IMPULSE Constitution (AGENTS.md):
- Fixtures used to validate pipeline mechanics must have `evidence_mode = FIXTURE` and remain in `experiments/lora/L1-data/fixtures/`.
- If zero eligible live trajectories exist (e.g. due to lack of local NVIDIA L4 GPUs), the curated training dataset remains count 0, and dataset status is recorded as `BLOCKED_BY_DATA`.
- Synthetic data is **never** presented as empirical live evaluation evidence.

---

## 7. How Stage 39 Consumes This Dataset

Stage 39 will ingest this dataset via `experiments/lora/L1-data/training_contract.json`:
1. **Fixed Dimensions:**
   - Base model: `gemma-4-31b-it-qat-w4a16-ct`
   - Prompt hash: `2360d4bf...` (unchanged)
   - Tool contracts: 9 locked tool schemas
   - Primary metric: `command_redundancy_count`
2. **Stage 39 Optimization Variables:**
   - LoRA rank ($r$), alpha ($\alpha$), dropout, learning rate, batch size, gradient accumulation, and training epochs are selected during Stage 39 experiments on target GPU infrastructure.
