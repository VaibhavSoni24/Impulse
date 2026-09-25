# Local Task Runner Architecture & Execution Protocol — IMPULSE

This document records the architectural design, CLI specification, artifact format, and execution backend abstraction of the IMPULSE local task runner (`local/runner/`), established in **Stage 5** of `PLAN.md`.

---

## 1. Purpose & Scope

The local task runner provides a reproducible orchestration layer for executing IMPULSE candidates (beginning with `IMPULSE-E0`) against competition benchmark tasks.

It establishes a clean separation between:
1. **Run Specification & Input Validation:** Safe parsing of task IDs, candidate paths, and budget limits.
2. **Task Loading:** Querying and resolving tasks from the official competition manifest (`data/competition/tasks.jsonl`).
3. **Execution Backend Abstraction:** An extensible backend interface separating local host orchestration from model inference.
4. **Artifact Collection & Snapshotting:** Creating collision-resistant, self-contained run folders with machine-readable metadata.
5. **Reproducibility Guarantee:** Capturing Git commit, exact candidate snapshot, model ID, and timestamps.

---

## 2. Command-Line Interface (CLI)

The runner is invoked via the standard Python module entry point:

```bash
python -m local.runner --task <TASK_ID> [OPTIONS]
```

### CLI Arguments & Options

| Argument | Flag | Type | Default | Description |
|---|---|:---:|:---:|---|
| `--task` | `-t` | String | *Required* | Benchmark task `instance_id` (e.g. `fastapi_15661`, `rich_4070`). |
| `--candidate` | `-c` | String | `"E0"` | Candidate identifier label for run tracking. |
| `--candidate-dir` | — | Path | `agent` | Directory containing candidate configuration (`agent.yaml`, prompts). |
| `--output-dir` | `-o` | Path | `runs` | Base directory where run folders are created. |
| `--timeout` | — | Integer | `None` | Optional execution timeout in seconds. |
| `--tool-budget` | — | Integer | `None` | Optional tool-call limit. |
| `--backend` | — | String | `"unavailable"` | Execution backend (`"unavailable"`, `"local-unavailable"`, `"dry-run"`). |
| `--tasks-file` | — | Path | `data/competition/tasks.jsonl` | Path to benchmark task manifest. |
| `--list-tasks` | — | Flag | `False` | Lists all 129 available task IDs and exits. |

### Example Invocations

```bash
# List all 129 benchmark tasks
python -m local.runner --list-tasks

# Prepare a candidate run on the local host (records unavailable status)
python -m local.runner --task fastapi_15661 --candidate E0

# Run a pipeline dry run to verify orchestration without model execution
python -m local.runner --task fastapi_15661 --candidate E0 --backend dry-run
```

---

## 3. Output Run Directory Layout

Every run is assigned an isolated, timestamped, collision-resistant directory under `runs/`:

```text
runs/YYYYMMDD-HHMMSS-<candidate>-<task>/
├── run.json                  # Authoritative machine-readable execution metadata
├── task_metadata.json        # Snapshot of benchmark task problem statement & repo metadata
├── candidate_snapshot/       # Complete frozen copy of candidate agent files at execution time
│   ├── agent.yaml            # Frozen root agent config
│   └── prompts/              # Frozen prompt templates
│       └── root.md
└── logs/
    └── runner.log            # Execution log stream
```

- **Collision Resistance:** If a directory with the same timestamp and name exists, a numerical suffix (`-1`, `-2`, etc.) is appended automatically. Previous runs are never overwritten.
- **Path Confinement:** All created files and subdirectories are strictly verified to remain within `--output-dir`. Traversal attempts (`..`) are rejected with `PathSecurityError`.

---

## 4. Machine-Readable Metadata Schema (`run.json`)

The runner emits a structured `run.json` for every execution:

```json
{
  "run_id": "20260925-133045-E0-fastapi_15661",
  "candidate_id": "E0",
  "task_id": "fastapi_15661",
  "model_id": "gemma-4-31b-it-qat-w4a16-ct",
  "prompt_id": "prompts/root.md",
  "execution_backend": "local-unavailable",
  "status": "execution_unavailable_local_host",
  "termination_reason": "Local Windows host environment lacks 4x NVIDIA L4 GPUs (96 GB VRAM) and local vLLM serving stack required to run gemma-4-31b-it-qat-w4a16-ct. Execution must be dispatched to cloud GPU or Kaggle evaluation environment.",
  "start_time": "2026-09-25T13:30:45.262466+00:00",
  "end_time": "2026-09-25T13:30:45.278209+00:00",
  "elapsed_time_seconds": 0.0157,
  "timeout_seconds": null,
  "tool_calls_budget": null,
  "git_commit": "99c0da316db1df9fc5c79659e5519fbb138541eb",
  "tool_calls_count": 0,
  "turns_count": 0,
  "error_message": null,
  "patch_generated": false,
  "run_dir": "runs\\20260925-133045-E0-fastapi_15661"
}
```

---

## 5. Execution Backend Architecture

The runner decouples orchestration from model inference using the `ExecutionBackend` protocol:

```python
class ExecutionBackend(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def execute(self, spec: RunSpec, task: TaskRecord, run_dir: Path) -> ExecutionResult: ...
```

### Supported Backends in Stage 5

1. **`UnavailableLocalBackend` (Default: `"unavailable"` / `"local-unavailable"`):**
   - Active default on the current Windows host workstation.
   - Accurately reports `status: "execution_unavailable_local_host"` with termination reason detailing the missing 4× L4 GPU hardware stack.
   - **Zero Fabrication:** Never simulates fake model outputs, fake tool events, or dummy patches.
2. **`DryRunBackend` (`"dry-run"`):**
   - Plumbing verification backend for unit tests, task loading, and CI.
   - Verifies artifact creation, task resolution, and candidate snapshotting without launching LLM or container processes.

---

## 6. Local Host Environment Hardware Limitation & Execution Reality

- **Hardware Reality:**
  - The local development workstation is Windows 11 with integrated graphics and 8 GB RAM.
  - The competition model (`gemma-4-31b-it-qat-w4a16-ct`) requires a minimum of **4 × NVIDIA L4 GPUs** (96 GB total VRAM) with tensor parallelism (`tensor_parallel_size = 4`) running vLLM.
  - Full model inference and two-container SWE-bench execution (`Container A` / `Container B`) cannot run on the local host.
- **Runner Distinction:**
  - The local runner is **orchestration and metadata infrastructure**, not the full competition evaluation harness.
  - Actual end-to-end evaluation with live inference will occur in cloud/Kaggle environments equipped with the required 4× L4 GPUs.
  - The runner guarantees that candidate preparation, task metadata extraction, and artifact formats are 100% reproducible and identical across local and remote environments.
