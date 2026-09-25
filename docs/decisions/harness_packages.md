# Harness Packages & Wheelhouse Inventory — IMPULSE

This document records the exact package inventory, wheel metadata, platform compatibility, and installation characteristics discovered from the Google / Kaggle competition source of truth and dataset manifests.

---

## 1. Core Host Evaluation Libraries

These three cooperating libraries form the proprietary host evaluation and submission compilation stack defined in `HARNESS_README.md`:

| Package | Exact File / Ref | Version | Purpose | Source / Runtime | Platform Target |
|---|---|---|---|---|---|
| **`swegemma`** | `swegemma-0.2.7-py3-none-any.whl` | `0.2.7` | SWE-bench benchmark harness, two-container lifecycle (`Container A` / `Container B`), tool binding (`SwegemmaContext`), patch extraction, and `pytest` scoring. | Competition Host Environment (`HARNESS_README.md`) | Linux (Host controller) / Pure Python |
| **`adk-submission`** | `adk-submission-0.2.11-py3-none-any.whl` | `0.2.11` | Sandboxed declarative YAML agent compiler (`compile_submission`), schema validation, `!include` resolver, and inference server manager (`VllmServer`). | Competition Host Environment (`HARNESS_README.md`) | Linux (Host controller) / Pure Python |
| **`adk-eval-core`** | `adk-eval-core-0.1.0-py3-none-any.whl` | `0.1.0` | Core benchmark task/result data models (`BenchmarkTask`, `EvaluationResult`), 3-tier resilient string replacement (`apply_replacement`), token budgets, and ATIF v1.7 tracing. | Competition Host Environment (`HARNESS_README.md`) | Linux (Host controller) / Pure Python |
| **`google-adk`** | Upstream ADK wheel | `~0.1.x` | Base agent framework (`BaseAgent`, `LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`, `App`). | Host evaluation runtime | Pure Python (`py3-none-any`) |
| **`vllm`** | `vllm-0.19.1+...whl` | `0.19.1` | Local inference engine serving `gemma-4-31b-it-qat-w4a16-ct` on 4x NVIDIA L4 GPUs (`tensor_parallel_size=4`). | Dedicated 4x L4 host environment | Linux x86_64 (`manylinux`) + CUDA 12 |

> [!NOTE]
> `swegemma`, `adk-submission`, and `adk-eval-core` are proprietary competition evaluation libraries pre-installed in the Kaggle scoring image. They are not published on the public PyPI index.

---

## 2. Sandbox Wheelhouse Inventory (`/wheels/`)

The competition dataset contains exactly **124 offline wheels** across **41 unique distributions** in `/wheels/` (cataloged in `data/competition/wheels_manifest.json`). These wheels are mounted read-only into `/wheels` in the `swebench-sandbox:latest` container and resolved offline by `/sandbox/setup.py`:

### 2.1. Build Backends & Packaging

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`setuptools`** | `setuptools-83.0.0-py3-none-any.whl` | `83.0.0` | `py3-none-any` | Yes | Standard build backend & editable installer |
| **`setuptools`** | `setuptools-82.0.1-py3-none-any.whl` | `82.0.1` | `py3-none-any` | Yes | Legacy build backend for older snapshots |
| **`wheel`** | `wheel-0.47.0-py3-none-any.whl` | `0.47.0` | `py3-none-any` | Yes | Wheel packaging utility |
| **`hatchling`** | `hatchling-1.30.1-py3-none-any.whl` | `1.30.1` | `py3-none-any` | Yes | PEP 517 build backend for modern repos |
| **`flit_core`** | `flit_core-3.12.0-py3-none-any.whl` | `3.12.0` | `py3-none-any` | Yes | PEP 517 build backend |
| **`poetry_core`** | `poetry_core-2.4.1-py3-none-any.whl` | `2.4.1` | `py3-none-any` | Yes | Poetry PEP 517 build backend |
| **`pdm_backend`** | `pdm_backend-2.4.9-py3-none-any.whl` | `2.4.9` | `py3-none-any` | Yes | PDM PEP 517 build backend |
| **`editables`** | `editables-0.6-py3-none-any.whl` | `0.6` | `py3-none-any` | Yes | Editable install path redirection |
| **`packaging`** | `packaging-26.3-py3-none-any.whl` | `26.3` | `py3-none-any` | Yes | Core version and specifier parsing |
| **`packaging`** | `packaging-26.2-py3-none-any.whl` | `26.2` | `py3-none-any` | Yes | Version compatibility fallback |

### 2.2. Testing Infrastructure

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`pytest`** | `pytest-9.1.1-py3-none-any.whl` | `9.1.1` | `py3-none-any` | Yes | Primary regression test harness |
| **`pytest`** | `pytest-8.3.4-py3-none-any.whl` | `8.3.4` | `py3-none-any` | Yes | Compatibility test harness |
| **`pytest`** | `pytest-6.2.5-py3-none-any.whl` | `6.2.5` | `py3-none-any` | Yes | Legacy test harness for older snapshots |
| **`pluggy`** | `pluggy-1.6.0-py3-none-any.whl` | `1.6.0` | `py3-none-any` | Yes | Plugin management for pytest |
| **`iniconfig`** | `iniconfig-2.3.0-py3-none-any.whl` | `2.3.0` | `py3-none-any` | Yes | `pytest.ini` configuration parser |

### 2.3. Web Frameworks & Runtimes

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`fastapi`** | `fastapi-0.141.1-py3-none-any.whl` | `0.141.1` | `py3-none-any` | Yes | Target repository dependency |
| **`starlette`** | 56 distinct wheel versions (`0.19.0` $\to$ `1.6.0`) | `0.19.0`–`1.6.0` | `py3-none-any` | Yes | Target repository dependency across task commits |
| **`flask`** | `flask-3.1.3-py3-none-any.whl` | `3.1.3` | `py3-none-any` | Yes | Target repository dependency |
| **`flask`** | `flask-2.3.3-py3-none-any.whl` | `2.3.3` | `py3-none-any` | Yes | Target repository dependency |
| **`flask`** | `Flask-2.2.5-py3-none-any.whl` | `2.2.5` | `py3-none-any` | Yes | Target repository dependency |
| **`werkzeug`** | `werkzeug-3.1.8-py3-none-any.whl` | `3.1.8` | `py3-none-any` | Yes | WSGI utility library |
| **`werkzeug`** | `werkzeug-2.3.8-py3-none-any.whl` | `2.3.8` | `py3-none-any` | Yes | WSGI utility library |
| **`jinja2`** | `jinja2-3.1.6-py3-none-any.whl` | `3.1.6` | `py3-none-any` | Yes | Template engine for web frameworks |
| **`itsdangerous`** | `itsdangerous-2.2.0-py3-none-any.whl` | `2.2.0` | `py3-none-any` | Yes | Cryptographic signing for session tokens |
| **`markupsafe`** | `markupsafe-3.0.3-cp313-cp313-manylinux...whl` | `3.0.3` | `cp313-cp313-manylinux` | **No** (Linux only) | String escape utilities (compiled C extension) |
| **`markupsafe`** | `markupsafe-3.0.3-cp312-cp312-manylinux...whl` | `3.0.3` | `cp312-cp312-manylinux` | **No** (Linux only) | C extension for Python 3.12 |

### 2.4. ORM & Data Validation

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`pydantic`** | `pydantic-2.13.4-py3-none-any.whl` | `2.13.4` | `py3-none-any` | Yes | Schema validation library (v2) |
| **`pydantic`** | `pydantic-1.10.15-py3-none-any.whl` | `1.10.15` | `py3-none-any` | Yes | Schema validation library (v1 fallback) |
| **`pydantic_core`**| `pydantic_core-2.46.4-cp313-cp313-manylinux...whl` | `2.46.4` | `cp313-cp313-manylinux` | **No** (Linux only) | Compiled Rust core for Pydantic v2 (Python 3.13) |
| **`pydantic_core`**| `pydantic_core-2.46.4-cp312-cp312-manylinux...whl` | `2.46.4` | `cp312-cp312-manylinux` | **No** (Linux only) | Compiled Rust core for Python 3.12 |
| **`annotated_types`**| `annotated_types-0.8.0-py3-none-any.whl` | `0.8.0` | `py3-none-any` | Yes | Metadata typing for Pydantic |
| **`annotated_types`**| `annotated_types-0.7.0-py3-none-any.whl` | `0.7.0` | `py3-none-any` | Yes | Metadata typing |
| **`sqlalchemy`** | `sqlalchemy-2.0.51-py3-none-any.whl` | `2.0.51` | `py3-none-any` | Yes | Pure Python SQL toolkit & ORM |
| **`sqlalchemy`** | `sqlalchemy-2.0.51-cp313-cp313-manylinux...whl` | `2.0.51` | `cp313-cp313-manylinux` | **No** (Linux only) | C extensions for SQLAlchemy 2.0 (Python 3.13) |
| **`sqlalchemy`** | `sqlalchemy-2.0.52-cp312-cp312-manylinux...whl` | `2.0.52` | `cp312-cp312-manylinux` | **No** (Linux only) | C extensions for Python 3.12 |
| **`sqlmodel`** | 5 distinct versions (`0.0.24`, `0.0.25`, `0.0.27`, `0.0.31`, `0.0.39`) | `0.0.24`–`0.0.39` | `py3-none-any` | Yes | SQLModel ORM for FastAPI |

### 2.5. Networking & HTTP Clients

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`requests`** | `requests-2.34.2-py3-none-any.whl` | `2.34.2` | `py3-none-any` | Yes | HTTP library |
| **`requests`** | `requests-2.33.0-py3-none-any.whl` | `2.33.0` | `py3-none-any` | Yes | HTTP library fallback |
| **`httpx`** | `httpx-0.28.1-py3-none-any.whl` | `0.28.1` | `py3-none-any` | Yes | Async HTTP client |
| **`httpcore`** | `httpcore-1.0.9-py3-none-any.whl` | `1.0.9` | `py3-none-any` | Yes | Core HTTP transport |
| **`urllib3`** | `urllib3-2.7.0-py3-none-any.whl` | `2.7.0` | `py3-none-any` | Yes | HTTP client library |
| **`certifi`** | `certifi-2026.7.22-py3-none-any.whl` | `2026.7.22` | `py3-none-any` | Yes | CA bundle |
| **`idna`** | `idna-3.19-py3-none-any.whl` | `3.19` | `py3-none-any` | Yes | Internationalized Domain Names |
| **`charset_normalizer`** | `charset_normalizer-3.4.7-py3-none-any.whl` | `3.4.7` | `py3-none-any` | Yes | Pure Python charset detector |
| **`charset_normalizer`** | `charset_normalizer-3.4.9-cp313-cp313-manylinux...whl` | `3.4.9` | `cp313-cp313-manylinux` | **No** (Linux only) | C-accelerated charset detector (Python 3.13) |
| **`charset_normalizer`** | `charset_normalizer-3.5.1-cp312-cp312-manylinux...whl` | `3.5.1` | `cp312-cp312-manylinux` | **No** (Linux only) | C-accelerated charset detector (Python 3.12) |
| **`anyio`** | `anyio-4.14.2-py3-none-any.whl` | `4.14.2` | `py3-none-any` | Yes | Async compatibility layer |
| **`sniffio`** | `sniffio-1.3.1-py3-none-any.whl` | `1.3.1` | `py3-none-any` | Yes | Async library sniffer |

### 2.6. CLI & Formatting Tools

| Package | Exact File | Version | ABI / Platform Tag | Windows Compatible? | Role in Sandbox |
|---|---|---|---|:---:|---|
| **`typer`** | `typer-0.26.7-py3-none-any.whl` | `0.26.7` | `py3-none-any` | Yes | CLI builder |
| **`click`** | `click-8.4.2-py3-none-any.whl` | `8.4.2` | `py3-none-any` | Yes | CLI framework |
| **`rich`** | `rich-15.0.0-py3-none-any.whl` | `15.0.0` | `py3-none-any` | Yes | Rich text and terminal formatting |
| **`colorama`** | `colorama-0.4.6-py2.py3-none-any.whl` | `0.4.6` | `py2.py3-none-any` | Yes | Terminal color support |
| **`pygments`** | `pygments-2.21.0-py3-none-any.whl` | `2.21.0` | `py3-none-any` | Yes | Syntax highlighting |
| **`markdown_it_py`**| `markdown_it_py-4.2.0-py3-none-any.whl` | `4.2.0` | `py3-none-any` | Yes | Markdown parser |
| **`mdurl`** | `mdurl-0.1.2-py3-none-any.whl` | `0.1.2` | `py3-none-any` | Yes | URL utilities for markdown-it |
| **`tqdm`** | `tqdm-4.70.0-py3-none-any.whl` | `4.70.0` | `py3-none-any` | Yes | Terminal progress bars |
| **`typing_extensions`**| `typing_extensions-4.16.0-py3-none-any.whl` | `4.16.0` | `py3-none-any` | Yes | Backported typing features |

---

## 3. Platform Compatibility Summary

- **Total Wheels in Manifest:** 124
- **Pure Python (`py3-none-any` / `py2.py3-none-any`):** **116 wheels (93.5%)** — cross-platform, installable directly on Windows and Linux.
- **Platform-Specific (`manylinux_x86_64`):** **8 wheels (6.5%)** — strictly Linux x86_64 only:
  - 4 wheels compiled for Python 3.13 ABI (`cp313`): `charset_normalizer-3.4.9`, `markupsafe-3.0.3`, `pydantic_core-2.46.4`, `sqlalchemy-2.0.51`.
  - 4 wheels compiled for Python 3.12 ABI (`cp312`): `charset_normalizer-3.5.1`, `markupsafe-3.0.3`, `pydantic_core-2.46.4`, `sqlalchemy-2.0.52`.
- **Windows Local Workstation Implication:**
  The 8 platform-specific Linux C-extensions cannot be installed on native Windows, but they are repository execution dependencies intended strictly for the `/workspace` container sandbox, not for the host agent authoring environment.
