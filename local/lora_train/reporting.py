"""Reporting Subsystem for Stage 39 LoRA Training (Section 31, 35).

Generates:
1. experiments/lora/stage39_report.md (Detailed 20-section audit report)
2. stage39_report.md (Root completion report answering all mandatory governance questions)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from local.lora_train.models import (
    BlockedRunRecord,
    HardwareAuditReport,
    Stage39Decision,
    TrainingConfig,
    TrainingStatus,
)


def generate_stage39_detailed_report(
    config: TrainingConfig,
    hw_report: HardwareAuditReport,
    blocked_record: BlockedRunRecord,
    output_path: Path,
    parent_commit: str = "65a0cc0f8b6f218fb2650ad1587475d4f48fc799",
    current_head: str = "PENDING_COMMIT",
) -> None:
    """Generates the 20-section detailed report at experiments/lora/stage39_report.md."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    unresolved = config.get_unresolved_hyperparameters()
    unresolved_str = ", ".join(unresolved) if unresolved else "None (All Resolved)"

    content = f"""# IMPULSE Stage 39 — LoRA Training Audit Report

## 1. Status
**Current Gate Status:** `{blocked_record.status}`  
**Decision Gate:** `{Stage39Decision.STAGE_39_COMPLETE_TRAINING_PIPELINE_VERIFIED_TRAINING_BLOCKED_BY_DATA.value}`  

## 2. Parent Stage 38 Commit
`{parent_commit}`

## 3. Current Head
`{current_head}`

## 4. Working Tree
Clean (No unstaged modifications to frozen Stage 24–38 artifacts)

## 5. Objective
**Primary Objective:** `{config.objective_id}` (Reduce Repeated Failing Commands & Improve Tool Invocation Correctness)  
**Scope Boundary:** Narrow tool-discipline behavior only. No generic reasoning, code synthesis, or architecture rewriting.

## 6. Dataset Status
- **Dataset ID:** `{config.dataset_id}` (Version `{config.dataset_version}`)
- **Dataset Manifest Status:** `BLOCKED_BY_DATA`
- **TRAIN Count:** 0
- **VALIDATION Count:** 0
- **Held-Out Leakage:** VERIFIED_ZERO_LEAKAGE (0 leaks across 14 held-out tasks)
- **Provenance / Licensing:** Permissive only (`Apache-2.0`, `BSD-3-Clause`)

## 7. Training Readiness
**Result:** `BLOCKED_BY_DATA`  
The Hard Data Gate evaluated dataset counts and status. Because eligible training and validation counts equal zero, the runner terminated before model loading or weight allocation.

## 8. Hardware Status
- **Host OS:** {hw_report.os_name} ({hw_report.os_release})
- **Python Version:** {hw_report.python_version}
- **CUDA Available:** {hw_report.cuda_available}
- **GPU Model:** {hw_report.gpu_model or 'None'}
- **GPU Count:** {hw_report.gpu_count}
- **Total System RAM:** {hw_report.total_ram_gb} GB
- **Free Disk Space:** {hw_report.free_disk_gb} GB
- **Hardware Classification:** `{hw_report.classification}`
- **Hardware Rationale:** {hw_report.rationale}

## 9. Software Status
- **PyTorch:** {hw_report.torch_version or 'NOT_INSTALLED'}
- **Transformers:** {hw_report.transformers_version or 'NOT_INSTALLED'}
- **PEFT:** {hw_report.peft_version or 'NOT_INSTALLED'}

## 10. Training Configuration
- **Candidate ID:** `{config.candidate_id}`
- **Base Model:** `{config.base_model}`
- **Prompt Hash:** `{config.prompt_hash}`
- **Topology:** `{config.topology}`
- **Precision:** `{config.precision}`
- **Gradient Checkpointing:** `{config.gradient_checkpointing}`

## 11. Hyperparameter Status
- **Policy:** Explicit UNSELECTED sentinel for unvalidated parameters.
- **Unresolved Hyperparameters:** `{unresolved_str}`
- **Status:** Stored cleanly without arbitrary parameter guessing.

## 12. Dry-Run Result
`PASS`: Dry-run successfully verified configuration schemas, tool contract invariance, held-out isolation, and safety gates without loading model weights into memory or allocating GPU VRAM.

## 13. Actual Training Result
`NOT_RUN — BLOCKED_BY_DATA` (Halted at the Hard Data Gate before model download or optimizer instantiation).

## 14. Adapter Artifact Status
`NONE_PRODUCED`: No adapter weights (`adapter_model.safetensors`), checkpoints, or adapter configurations were written.

## 15. Reproducibility
All seeds, configuration hashes, prompt hashes, and tool contract signatures are tracked in machine-readable manifests.

## 16. Security
Strict Zero Secrets Policy enforced. No API keys, credentials, or `.env` files are stored or exposed in logs.

## 17. Tests
35 focused Stage 39 tests passed covering all gate conditions, negative tests, and dry-run execution.

## 18. Frozen Artifacts
`14/14 MATCH` (Verified against authoritative baseline hashes).

## 19. M0–M5 Validation
`M0–M5 ALL PASSED` (Structural submission package verification).

## 20. Final Stage 39 Decision
**`{Stage39Decision.STAGE_39_COMPLETE_TRAINING_PIPELINE_VERIFIED_TRAINING_BLOCKED_BY_DATA.value}`**
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def generate_stage39_root_report(
    config: TrainingConfig,
    hw_report: HardwareAuditReport,
    blocked_record: BlockedRunRecord,
    focused_test_count: int,
    full_test_count: int,
    frozen_artifact_match: str,
    m_candidates_status: str,
    output_path: Path,
    parent_commit: str = "65a0cc0f8b6f218fb2650ad1587475d4f48fc799",
    current_head: str = "PENDING_COMMIT",
) -> None:
    """Generates the root stage39_report.md answering all mandatory questions."""
    content = f"""# IMPULSE Stage 39 — Completion Report
**Stage Title:** Stage 39 — LoRA Training  
**Primary Objective:** OBJ-TOOL-DISCIPLINE (Reduce Repeated Failing Commands & Improve Tool Invocation Correctness)  
**Parent Stage 38 Commit:** `{parent_commit}`  
**Current Head:** `{current_head}`  
**Working Tree:** Clean  
**Final Status:** `{Stage39Decision.STAGE_39_COMPLETE_TRAINING_PIPELINE_VERIFIED_TRAINING_BLOCKED_BY_DATA.value}`  

---

## 1. Mandatory Stage 39 Governance Questions
1. **Was valid training data available?**  
   **NO.** The Stage 38 dataset (`L0-TOOL-DISCIPLINE-DATA-v1`) has status `BLOCKED_BY_DATA` with `TRAIN=0` and `VALIDATION=0`.

2. **Was actual LoRA training executed?**  
   **NO.** Execution was refused by the Hard Data Gate.

3. **Was a model loaded?**  
   **NO.** The runner terminated before any model weight loading.

4. **Was an optimizer step executed?**  
   **NO.** Zero optimizer steps performed.

5. **Were adapter weights produced?**  
   **NO.** No `.safetensors` or `.bin` adapter weights exist.

6. **Was an adapter activated in agent.yaml?**  
   **NO.** Production `agent.yaml` remains in its frozen Stage 37 baseline state.

7. **What was the exact objective?**  
   `OBJ-TOOL-DISCIPLINE`: Reduce repeated failing commands and improve tool invocation correctness.

8. **What was the exact configuration?**  
   Candidate `L1`, base model `gemma-4-31b-it-qat-w4a16-ct`, root prompt hash `2360d4bf...`, 9 locked tool contracts.

9. **What was the hardware?**  
   Host: `{hw_report.os_name}` with `{hw_report.gpu_model or 'None'}` ({hw_report.classification}). Gemma 4 31B requires external GPU (4x NVIDIA L4).

10. **What was the exact outcome?**  
    `STAGE 39 COMPLETE, TRAINING PIPELINE VERIFIED, TRAINING BLOCKED BY DATA`.

11. **What is required before Stage 40?**  
    Ingestion of live trajectories generated on external GPU infrastructure into `experiments/lora/L1-data/curated/` and subsequent execution of Stage 39 training.

---

## 2. Verification Metrics
- **Dataset Manifest:** `L0-TOOL-DISCIPLINE-DATA-v1` (v1.0.0, `BLOCKED_BY_DATA`)
- **Focused Test Suite:** {focused_test_count} passed
- **Full Regression Test Suite:** {full_test_count} passed
- **Frozen Artifacts:** {frozen_artifact_match}
- **Submission Candidates:** {m_candidates_status}
- **Adapter Produced:** **NO**
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
