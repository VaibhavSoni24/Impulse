# Docker Environment Specification — IMPULSE

This document records the container runtime status, Linux-container capabilities, and virtualization configuration for the local development workstation.

---

## 1. Verified Container Runtime Status

| Check | Result | Command / Observation |
|---|---|---|
| **Docker CLI** | **Not Installed** | `docker : The term 'docker' is not recognized` |
| **Docker Daemon** | **Not Running** | No Docker service found in Windows Service Manager |
| **Docker Desktop** | **Not Installed** | No installation directory in `C:\Program Files\Docker` |
| **WSL2 Linux Distros** | **None Installed** | `wsl.exe` exists as Windows system utility, but no active Linux distributions registered |
| **Linux Container Capability** | **Unavailable Locally** | Cannot run Linux containers without Docker Desktop or WSL2 |

---

## 2. Container Diagnostic Test Results

- **Command Attempted:** `docker run --rm python:3.13-slim python --version`
- **Result:** **Not Executed** — Docker binary is not installed on the system.
- **Root Cause:** Neither Docker Desktop nor an alternative container runtime (such as Podman or WSL2 Docker daemon) is currently installed on this Windows workstation.

---

## 3. Relationship to Competition Evaluation Architecture

The competition harness requires container isolation:
1. **Container A (Agent Execution):** Mounts repository snapshot at `/workspace`, mounts `/wheels` read-only, runs in an air-gapped network (`network_mode="none"`), with 4 GiB RAM and 2 vCPUs.
2. **Container B (Verification):** Fresh container running `pytest` on the patched repository with anti-tampering test resets.

### Dual-Tier Execution Strategy

- **Local Host:**
  - `adk-submission` compiles and validates the declarative YAML submission structure (`agent.yaml`, sub-agents, prompts) without requiring a Docker daemon.
  - `swegemma eval` supports `--sandbox subprocess` for local lightweight process-isolated runs when a Docker daemon is absent.
- **Kaggle Cloud Environment:**
  - Kaggle's native competition runner operates the full 2-container Docker architecture (`swebench-sandbox:latest`) on 4x NVIDIA L4 GPUs.
  - Full end-to-end evaluation sweeps across all 129 development tasks will be staged and executed in the Kaggle environment.

---

## 4. Minimum Manual Steps to Install Docker Locally (If Desired)

If full local container simulation matching `Dockerfile.sandbox` is desired:

1. **Step 1: Install WSL2 and Ubuntu Distribution:**
   Open an Administrator PowerShell prompt and run:
   ```powershell
   wsl --install -d Ubuntu
   ```
   Reboot the computer if prompted by Windows.

2. **Step 2: Install Docker Desktop for Windows:**
   - Download the installer from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) or execute:
     ```powershell
     winget install Docker.DockerDesktop
     ```
   - Ensure "Use WSL 2 instead of Hyper-V" is enabled during installation.

3. **Step 3: Verify Linux Container Execution:**
   After launching Docker Desktop:
   ```powershell
   docker run --rm python:3.13-slim python --version
   ```
   Expected output: `Python 3.13.x`.
