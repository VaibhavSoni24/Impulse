# Python Environment Specification — IMPULSE

This document records the installed Python interpreters on the host workstation, the target Python version for IMPULSE, and the environment isolation strategy.

---

## 1. Verified Python Installations on Host

| Executable Path | Version | Managed By | Active Default? |
|---|---|---|:---:|
| `D:\Softwares\Python\python.exe` | **Python 3.10.11** | Custom installation | Yes (Default in system PATH) |
| `C:\Users\shubh\AppData\Local\Programs\Python\Python311\python.exe` | **Python 3.11.9** | User installation | No (Accessible via `py -3.11`) |

### Exact Command Outputs

- **`python --version`**:
  ```text
  Python 3.10.11
  ```
- **`py -0p` (Python Launcher Registry)**:
  ```text
   -V:3.11 *        C:\Users\shubh\AppData\Local\Programs\Python\Python311\python.exe
   -V:3.10          D:\Softwares\Python\python.exe
  ```
- **`py --version`**:
  ```text
  Python 3.11.9
  ```
- **`pip --version`**:
  ```text
  pip 26.1.2 from D:\Softwares\Python\lib\site-packages\pip (python 3.10)
  ```
- **`uv --version`**:
  ```text
  Not installed on PATH
  ```

---

## 2. Selected Target Python Version for IMPULSE

- **Target Version:** **Python 3.13** (specifically matching `python:3.13-slim`).
- **Rationale:**
  1. **Strict Sandbox Alignment:** The competition harness sandbox (`Dockerfile.sandbox`, `Dockerfile.public`) is explicitly built on **Python 3.13-slim**.
  2. **Standard Library Compatibility:** Python 3.13 removes several legacy modules (`imp`, `telnetlib`), which the competition sandbox restores via explicit shims (`imp.py`, `telnetlib.py`). Developing against Python 3.13 ensures that local code, imports, and AST tools do not depend on removed standard library features.
  3. **Wheelhouse Pre-compilation:** The 124 pre-compiled offline wheels in `/wheels/` include packages compiled for Python 3.13 CPython ABI (`cp313-cp313-manylinux...`).

---

## 3. Host Python Management & Isolation Strategy

To avoid disrupting existing system workflows:

1. **Zero System Disruption:**
   - Existing Python 3.10 and 3.11 installations will **not** be modified, replaced, or uninstalled.
   - The system default Python in PATH remains unchanged.
2. **Side-by-Side Python 3.13 Provisioning:**
   - Python 3.13 can be installed side-by-side using the official Windows installer via `winget`:
     ```powershell
     winget install Python.Python.3.13
     ```
   - Alternatively, `uv` (`astral-sh.uv`) can be installed to download and manage hermetic Python 3.13 toolchains without modifying system settings:
     ```powershell
     winget install astral-sh.uv
     uv venv .venv --python 3.13
     ```
3. **Dedicated Virtual Environment:**
   - All IMPULSE development, linting, packaging, and testing will run strictly inside an isolated virtual environment (`.venv`) targeting Python 3.13.
   - The virtual environment directory `.venv/` is excluded from Git via `.gitignore`.
