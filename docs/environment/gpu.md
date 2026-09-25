# GPU & Hardware Accelerator Specification — IMPULSE

This document records the hardware graphics and accelerator capabilities of the local development workstation, and the compute allocation plan for model inference.

---

## 1. Local Hardware Probe Results

| Dimension | Probe Result | Method / Tool |
|---|---|---|
| **NVIDIA GPU Present?** | **No** | `nvidia-smi` command not recognized |
| **Installed Video Controller** | `Intel(R) Iris(R) Xe Graphics` | WMI `Win32_VideoController` |
| **GPU Architecture** | Integrated Graphics (Intel Iris Xe Graphics Family) | Hardware probe |
| **VRAM / Shared Memory** | 4,122,667,008 bytes (~3.84 GB shared memory) | WMI `Win32_VideoController.AdapterRAM` |
| **Driver Version** | `32.0.101.5542` | WMI `Win32_VideoController.DriverVersion` |
| **CUDA Support** | **None** (Intel GPU does not support NVIDIA CUDA) | Architectural constraint |

### Probe Command Output

```powershell
PS E:\Projects\Impulse> nvidia-smi
nvidia-smi : The term 'nvidia-smi' is not recognized as the name of a cmdlet, function, script file, or operable program.
```

```powershell
PS E:\Projects\Impulse> Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor

Name                         AdapterRAM DriverVersion VideoProcessor
----                         ---------- ------------- --------------
Intel(R) Iris(R) Xe Graphics 4122667008 32.0.101.5542 Intel(R) Iris(R) Xe Graphics Family
```

---

## 2. Local GPU Usability for IMPULSE

- **Verdict:** The local integrated Intel GPU is **not usable** for running Gemma 4 31B inference, vLLM tensor parallel serving, or PEFT/LoRA fine-tuning.
- **Hardware Disparity:**
  - The competition serving environment runs on **4 × NVIDIA L4 GPUs with 96 GB total VRAM** (sharding `gemma-4-31b-it-qat-w4a16-ct` with `tensor_parallel_size = 4` and reserving ~68 GB for 32k context KV caches and LoRA buffers).
  - The local workstation has 8 GB total system RAM and integrated graphics, making local 31B parameter LLM inference impossible.

---

## 3. Compute Allocation Strategy

> **GPU-dependent execution will use Kaggle/free compatible compute when required.**

1. **Local Workstation Scope:**
   - Architecture definition, declarative YAML configuration, prompt engineering, sub-agent schemas, tool interfaces, mock testing, and submission packaging.
   - Zero GPU requirements for these activities.
2. **Cloud / Kaggle Compute Scope:**
   - Model serving (`VllmServer`), benchmark evaluation runs against `tasks.jsonl`, resolution scoring, and LoRA training (if pursued) will be executed on Kaggle notebooks / GPUs or dedicated cloud instances.
3. **Model Weight & Serving Policy:**
   - **No Gemma 4 model weights have been downloaded locally.**
   - **No vLLM server has been initialized locally.**
   - Local disk space (40.85 GB free on `E:`) is reserved for repository source code, development tools, and task metadata.
