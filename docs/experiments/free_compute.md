# IMPULSE Free Compute Strategy

## 1. Overview & Purpose
The Free Compute Strategy provides a deterministic, free-first compute portability layer for IMPULSE. It enables the repository to move seamlessly between:
1. **Local Windows CPU environment** (development, testing, analysis, packaging)
2. **Kaggle free GPU notebook environments** (dual T4, single P100 sessions)
3. **External Linux GPU environments** (multi-L4, A100 training clusters)

without altering the scientific definition of any experiment.

> [!IMPORTANT]
> **Production Boundary:** The Free Compute Strategy is experimental infrastructure designed for model evaluation and training portability. It is **not** part of the mandatory production architecture (`agent.yaml`, frozen prompts, or frozen specialists).

---

## 2. Invariance & Separation Principles
A compute environment must **never** silently alter an experiment. IMPULSE strictly separates:
- **Experiment Configuration:** Model identifier, prompt hash, tool contracts, skill hashes, sampling parameters, benchmark splits, and topology.
- **Compute Environment:** Operating system, hardware classification, CUDA availability, package versions, and environment fingerprint.
- **Results & Evidence:** Traces, metrics, logs, and evidence modes (`LIVE`, `FIXTURE`, `INFRASTRUCTURE_ONLY`, `UNAVAILABLE`).

The experiment hash remains 100% stable regardless of which compute environment runs it.

---

## 3. Environment Classifications
| Environment Class | Description | Primary Role |
| :--- | :--- | :--- |
| `LOCAL_CPU` | Host development machine (Windows, Intel Iris Xe) | CPU validation, prompts, tests, packaging, analysis |
| `LOCAL_GPU` | Local workstation with dedicated NVIDIA CUDA GPU | Fast local iteration when CUDA hardware is available |
| `KAGGLE_FREE_GPU` | Free Kaggle Notebook sessions (T4x2, P100) | Free GPU-accelerated model serving and evaluation |
| `EXTERNAL_LINUX_GPU` | Dedicated cloud / cluster Linux GPU (4x L4, A100) | Multi-GPU PEFT/LoRA training for 31B model |
| `UNKNOWN` | Unrecognized or unclassified environment | Blocked from launching GPU-dependent runs |

---

## 4. Local CPU Responsibilities
The local Windows/CPU environment executes all non-model workloads without requiring 31B weights:
- Prompt engineering and template validation
- YAML/JSON agent configuration schema verification
- Experiment manifest generation
- Benchmark split analysis and leakage verification
- Failure Driven Development (FDD) clustering and taxonomy dashboards
- Dataset gate and provenance verification
- Authoritative report and markdown generation
- Unit testing and full regression test execution
- Package validation and deterministic submission ZIP generation
- SHA-256 fingerprinting and artifact verification
- LoRA training and ablation dry runs
- Compute environment discovery and auditing

---

## 5. GPU-Dependent Responsibilities
GPU environments are reserved strictly for:
- Gemma 4 31B QAT inference
- PEFT/LoRA training execution
- Single-adapter and multi-adapter inference routing
- GPU-dependent benchmark evaluation
- Runtime latency and throughput profiling

If GPU resources or required CUDA runtimes are unavailable, the system strictly returns `GPU_REQUIRED` and terminates before attempting execution. CPU approximations must **never** be substituted for real model execution.

---

## 6. Free-First Policy & Security
- **Free-First Priority:** Prioritizes local CPU and free Kaggle notebook sessions over paid infrastructure.
- **Zero Secrets:** No personal credentials, Kaggle API tokens (`kaggle.json`), cloud billing setups, or SSH private keys are ever stored, committed, or transferred.
- **Sanitization:** Environment fingerprints strip usernames, personal paths, IP addresses, and sensitive environment variables.

---

## 7. Artifact Transfer & Hash Verification
When dispatching experiments to external environments:
1. **Outbound Manifest (`ArtifactTransferManifest`):** Cryptographically signs all transferred assets (configs, prompts, benchmark splits, contracts) with SHA-256 digests. Sensitive files (`.env`, `.key`, `.log`, `.git`) are strictly excluded.
2. **Pre-Execution Check:** External bootstrap verifies that all received files exist and match their SHA-256 digests.
3. **Return Manifest (`ReturnArtifactManifest`):** Returned metrics, execution logs, and adapter artifacts are hashed into a verifiable result digest.

---

## 8. Kaggle Notebook Support
Kaggle execution scripts reside in `compute/kaggle/`:
- `README.md`: Usage guide and security rules.
- `bootstrap.sh`: Bash setup script probing `nvidia-smi` and dependencies.
- `bootstrap.py`: Python bootstrap recording environment metadata.
- `environment_check.py`: Hardware, software, and capability matrix diagnostic.
- `run_experiment.py`: Provider-neutral runner executing experiments under invariant configurations.

---

## 9. Experiment Pre-Flight
Before any GPU-dependent experiment begins, `scripts/compute_preflight.py` executes 14 checks:
1. Experiment contract existence
2. Git commit resolution
3. Clean working tree policy
4. Permitted model identifier (`gemma-4-31b-it-qat-w4a16-ct`)
5. Benchmark split integrity (smoke, dev, validation, held-out)
6. Root prompt hash resolution
7. Tool contract validation
8. Adapter availability (Hard Gate)
9. Hardware and CUDA compatibility
10. Required ML packages (`torch`, `transformers`, `peft`, `accelerate`)
11. Disk space budget with 5 GB safety margin
12. GPU availability
13. CUDA capability classification
14. Output directory safety

Outcomes: `READY`, `BLOCKED`, `INCOMPATIBLE`, `UNKNOWN`. Execution terminates immediately if `BLOCKED` or `INCOMPATIBLE`.

---

## 10. Current Local Limitations & Verification Status
- **Current Local Host:** Windows 10, 12th Gen Intel Core i5-1235U, 7.68 GB RAM, Intel Iris Xe graphics (non-CUDA).
- **Local Classification:** `NO_CUDA_GPU` (`LOCAL_CPU`).
- **External Execution Status:** `NOT_PERFORMED`. Framework portability is established and verified, while live external GPU execution remains unexecuted until required by future stages.
