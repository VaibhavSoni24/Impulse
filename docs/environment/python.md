# Python Environment Specification — IMPULSE

This document records the installed Python interpreters on the host workstation, the target Python version for IMPULSE, and the environment isolation strategy.

---

## 1. Verified Python Installations on Host

| Executable Path | Version | Managed By | Active Default? |
|---|---|---|:---:|
| `D:\Softwares\Python\python.exe` | **Python 3.10.11** | Custom installation | **Yes** (System default in PATH via `python`) |
| `C:\Users\shubh\AppData\Local\Programs\Python\Python311\python.exe` | **Python 3.11.9** | User installation | No (Accessible via `py -3.11`) |
| `C:\Users\shubh\AppData\Local\Programs\Python\Python313\python.exe` | **Python 3.13.15** | User installation | No (Accessible via `py -3.13`; default target in `py`) |

### Exact Command Outputs

- **`python --version` (System Default in PATH)**:
  ```text
  Python 3.10.11
  ```
- **`py -0p` (Python Launcher Registry)**:
  ```text
   -V:3.13 *        C:\Users\shubh\AppData\Local\Programs\Python\Python313\python.exe
   -V:3.11          C:\Users\shubh\AppData\Local\Programs\Python\Python311\python.exe
   -V:3.10          D:\Softwares\Python\python.exe
  ```
- **`py -3.13 --version`**:
  ```text
  Python 3.13.15
  ```
- **`py --version`**:
  ```text
  Python 3.11.9
  ```
- **`pip --version` (System Default Python 3.10)**:
  ```text
  pip 26.1.2 from D:\Softwares\Python\lib\site-packages\pip (python 3.10)
  ```

---

## 2. Dedicated IMPULSE Virtual Environment (`.venv`)

The project uses an isolated virtual environment built strictly with Python 3.13:

- **Virtual Environment Location:** `E:\Projects\Impulse\.venv`
- **Interpreter Path:** `E:\Projects\Impulse\.venv\Scripts\python.exe`
- **Interpreter Version:**
  ```text
  Python 3.13.15
  ```
- **Virtual Environment Pip Version:**
  ```text
  pip 26.2.1 from E:\Projects\Impulse\.venv\Lib\site-packages\pip (python 3.13)
  ```
- **Git Protection:** `.venv/` is explicitly excluded from version control via `.gitignore` (`.gitignore:20:.venv/`).

---

## 3. Four-Tier Python Environment Separation

To guarantee complete reproducibility and eliminate system-wide contamination, the development environment enforces four clearly distinguished tiers:

1. **System Default Python (`Python 3.10.11`):**
   - Executable: `D:\Softwares\Python\python.exe`
   - Role: Preserves existing system and workstation toolchain defaults. Untouched by IMPULSE.
2. **Registered Legacy Python (`Python 3.11.9`):**
   - Executable: `C:\Users\shubh\AppData\Local\Programs\Python\Python311\python.exe`
   - Role: Retained for secondary compatibility and user tools. Untouched by IMPULSE.
3. **Host Target Python (`Python 3.13.15`):**
   - Executable: `C:\Users\shubh\AppData\Local\Programs\Python\Python313\python.exe`
   - Role: Side-by-side host installation matching the competition container base (`python:3.13-slim`).
4. **IMPULSE Active Environment (`.venv` — `Python 3.13.15`):**
   - Executable: `E:\Projects\Impulse\.venv\Scripts\python.exe`
   - Role: Dedicated hermetic runtime for all IMPULSE code, package compilation, testing, and linting.

