# Machine Environment Specification — IMPULSE

This document records the verified hardware architecture, operating system, and virtualization capabilities of the local development workstation.

---

## 1. Workstation Hardware Profile

| Attribute | Verified Value | Source / Method |
|---|---|---|
| **System Model** | Laptop (x86_64) | WMI `Win32_ComputerSystem` |
| **CPU** | 12th Gen Intel(R) Core(TM) i5-1235U | WMI `Win32_Processor` |
| **Physical Cores / Threads** | 10 Cores (2 P-Cores, 8 E-Cores) / 12 Logical Processors | WMI `Win32_Processor` |
| **Physical RAM** | 7.68 GB (~8 GB usable) | WMI `Win32_ComputerSystem.TotalPhysicalMemory` |
| **Primary Storage Volumes** | `C:` (OS), `D:` (101 GB free), `E:` (Workspace: 40.85 GB free) | PowerShell `Get-PSDrive FileSystem` |
| **Graphics Adapter** | Intel(R) Iris(R) Xe Graphics Family (Driver `32.0.101.5542`) | WMI `Win32_VideoController` |
| **NVIDIA GPU** | **None** (`nvidia-smi` not found) | Hardware probe |

---

## 2. Operating System & Subsystem Profile

| Attribute | Verified Value | Details |
|---|---|---|
| **Operating System** | Microsoft Windows 11 Home Single Language | Version `10.0.26200`, Build `26200` |
| **Architecture** | 64-bit (`x86_64`) | `[System.Environment]::Is64BitOperatingSystem` |
| **WSL2 Subsystem** | Installed binary (`C:\WINDOWS\system32\wsl.exe`) | Active Linux distributions: **None** (`HKCU:\...\Lxss` is empty; `LxssManager` not running) |
| **Hypervisor / Virtual Machine Platform** | Present at OS level | Not currently provisioned with active WSL2 Linux distros |
| **Docker Engine** | **Not Installed** | No `docker` command in PATH; no Docker Desktop directory in `Program Files` |

---

## 3. Local Development Mode Analysis

The competition harness evaluation stack (`swegemma`, `adk-submission`, `adk-eval-core`) requires a Linux-compatible container sandbox (`swebench-sandbox:latest` running Python 3.13) and 4x NVIDIA L4 GPUs for vLLM inference.

Evaluating the four potential development modes:

- **Mode A (Native Windows + Docker Desktop / WSL2):**
  - Requires installing Docker Desktop or WSL2 on Windows.
  - Good for local syntax verification, compiling declarative agent YAMLs (`adk-submission`), and running subprocess sandboxes.
- **Mode B (WSL2 Linux + Docker):**
  - Requires installing Ubuntu on WSL2 and Docker inside WSL2.
- **Mode C (Native Linux):**
  - Not available on this physical workstation.
- **Mode D (Current Workstation State — No usable Docker/Linux environment yet):**
  - Active state on this machine.

### Recommended Dual-Tier Development Strategy

1. **Tier 1 — Local Development Workstation (Native Windows):**
   - Authoring agent architectures (`agent.yaml`, sub-agents, prompt templates, tools, skills).
   - Validating declarative schemas using `adk-submission` schema validation without running heavy containers.
   - Performing unit tests, linting, packaging `submission.zip`, and Git workflow management.
   - Using `swegemma eval --sandbox subprocess` for lightweight unit and tool tests if needed.
2. **Tier 2 — Execution & Evaluation Environment (Kaggle Cloud Compute):**
   - The competition model (`gemma-4-31b-it-qat-w4a16-ct`) requires a minimum of 4x NVIDIA L4 GPUs (96 GB VRAM) running vLLM, which exceeds local laptop memory (8 GB RAM, integrated graphics).
   - Full evaluation runs, benchmark scoring across all 129 tasks, and end-to-end sandbox verification will run in Kaggle's dedicated cloud runtime (or equivalent GPU cloud instance).

---

## 4. Minimum Steps to Enable Local Docker / WSL2 (If Desired)

If local container testing is desired in future stages:

1. **Enable WSL2 and Install Ubuntu:**
   ```powershell
   # Run in an elevated Administrator PowerShell prompt:
   wsl --install -d Ubuntu
   ```
2. **Install Docker Desktop for Windows:**
   - Download the installer from [docker.com](https://www.docker.com/products/docker-desktop) or run:
     ```powershell
     winget install Docker.DockerDesktop
     ```
   - Ensure the "Use the WSL 2 based engine" checkbox is selected during installation.
