---
name: repo_triage
description: Systematic repository triage skill for rapid, evidence-driven identification of language, framework, build manager, entry points, layout, and conventions.
---

# Systematic Repository Triage Skill

## Purpose
This skill establishes a rapid, evidence-driven reconnaissance protocol to map an unfamiliar software repository. Before attempting issue localization or code modification, the agent builds a compact structural map answering: **"What is this repository, how is it organized, and how do developers build, run, and test it?"**

Repository triage front-loads high-value discoveries into structured task state, preventing repeated blind exploration across turns.

---

## 1. Bounded Reconnaissance Protocol

Execute reconnaissance in strict priority order to maximize information gain while conserving tool calls and context:

1. **Root Directory Listing**: List repository root entries to discover primary directories and configuration manifests.
2. **Root Configuration & Manifests**: Inspect primary project manifests for language, build, and dependency declarations.
3. **Package & Build Tooling**: Determine package managers, virtual environment requirements, and build commands.
4. **Test Topology**: Locate test suites, runner configurations, and naming conventions.
5. **CI / Build Conventions**: Check CI workflows and Makefiles for canonical development commands.
6. **Source Layout & Entry Points**: Identify implementation packages, public interfaces, and application entry points.
7. **Deeper Inspection Only on Ambiguity**: Avoid examining secondary directories or deep trees unless root evidence is inconclusive.

> [!IMPORTANT]
> **Anti-Dumping Rule**: Never recursively dump entire directory trees or large generated directories (e.g., `node_modules/`, `vendor/`, `target/`, `dist/`, `.git/`, virtual environments).

---

## 2. Seven Triage Dimensions

### A. Identify Language & Polyglot Boundaries
- **Examine Evidence**: Check file extensions, root manifests, and compiler/interpreter configurations.
- **Polyglot Repositories**: Note secondary languages (e.g., C extensions in Python packages, TypeScript wrappers around Rust/Wasm cores, frontend assets in backend web applications).
- **Rule**: Never assume a language based on one file. State only languages corroborated by build manifests or core source directories.

### B. Identify the Framework & Ecosystem
- **Examine Evidence**:
  - Declared dependencies in package manifests (e.g., framework packages).
  - Framework-specific configuration files or convention directories.
  - Core import patterns across entry-point modules.
- **Rule**: Do not hard-code or guess framework names. If no framework is present (e.g., standalone CLI, pure utility library, low-level protocol implementation), explicitly record `"None / Standalone Library"`.

### C. Identify the Package & Build Manager
- **Examine Evidence**:
  - Python: `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`, `Pipfile`, `poetry.lock`, `uv.lock`.
  - JavaScript/TypeScript: `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`.
  - Rust: `Cargo.toml`, `Cargo.lock`.
  - Go: `go.mod`, `go.sum`.
  - Java/Kotlin: `pom.xml`, `build.gradle`, `build.gradle.kts`.
  - C/C++: `CMakeLists.txt`, `Makefile`, `meson.build`.
- **Invocation Conventions**: Prefer repository-local wrappers or documented commands (e.g., `make test`, `tox`, local virtualenv runners) over arbitrary global commands.

### D. Identify Entry Points
- Locate application or package entry points through evidence:
  - Console script declarations (`[project.scripts]`, `console_scripts` in `setup.cfg` or `package.json`).
  - Executable modules (`__main__.py`, `main.go`, `src/main.rs`, `index.js`, `cli.py`).
  - Application factory functions (e.g., `create_app()`, `get_application()`).
  - Documented CLI or service execution commands.
- Record candidate entry points with supporting file paths.

### E. Identify the Test Topology
- Establish repository test organization:
  - Test directories: `tests/`, `test/`, `spec/`, or colocated test files.
  - Test runner configurations: `pytest.ini`, `setup.cfg`, `tox.ini`, `jest.config.js`.
  - Test naming conventions: `test_*.py`, `*_test.py`, `*.spec.ts`.
  - Shared fixtures and mock helpers: `conftest.py`, `fixtures/`, `helpers/`.
- *Note*: Detailed execution, reproduction, and result interpretation are delegated to the `test_strategy` skill. Repository triage only maps the test layout.

### F. Identify CI & Build Conventions
- Check development workflows for canonical build and test commands:
  - `.github/workflows/*.yml`
  - `.gitlab-ci.yml`
  - `Makefile`, `Taskfile.yml`
  - Pre-commit configurations (`.pre-commit-config.yaml`)
- Extract key verification and build commands. Do not copy entire workflow YAML files into context.

### G. Map the Repository Layout
- Construct a compact structural summary:
  - `Root Manifests`: Configuration, dependency, and packaging files.
  - `Source Directories`: Core implementation packages (e.g., `src/<pkg>/` or `<pkg>/`).
  - `Test Directories`: Unit, integration, and functional test locations.
  - `Tooling & Scripts`: Utility scripts, build helpers, and maintenance tools.
  - `Documentation`: User guides, API references, architecture notes.

---

## 3. Compact Triage Summary Format

Summarize reconnaissance findings into a structured report and record key facts into `TaskState.repository_facts`:

```text
=== Repository Triage Summary ===
Language(s):          <primary language> (secondary: <if polyglot>)
Framework:            <framework name or "None / Library">
Package Manager:      <detected package/build tool>
Entry Point(s):       <key executable modules, CLI commands, or factory functions>
Source Layout:        <main source directory structure, e.g., src/pkg_name/ or pkg_name/>
Test Layout:          <test directory, runner, and naming conventions>
CI / Build Command:   <canonical test/build command from CI or Makefile>
Key Configurations:   <primary manifest files, e.g., pyproject.toml, Makefile>
Unknowns / Ambiguity: <explicit list of unresolved questions or "None">
=================================
```

---

## 4. Evidence & Anti-Fabrication Rules

1. **Verify Before Asserting**:
   - Every entry in the triage summary must be backed by a concrete file or command observation.
   - If evidence is ambiguous, record `"Unknown"` or `"Unverified"` rather than guessing.
2. **Zero Hard-Coded Benchmark Knowledge**:
   - Do NOT assume or encode paths, tools, or answers for specific benchmark repositories.
   - Never reference benchmark task IDs or competition dataset instance identifiers.
   - Discover all conventions dynamically from the repository.
3. **Strict Secrets Exclusion**:
   - Never copy API keys, access tokens, private keys, database passwords, or secret environment variables into task state or triage notes.
   - If a `.env` or configuration file contains credentials, summarize only the key names (e.g., `"Configures DB_HOST and AUTH_TOKEN"`) and exclude the secret values.
4. **Avoid Redundant Re-Triage**:
   - Store established repository facts in `TaskState.repository_facts`.
   - Before running exploration commands in subsequent turns, consult existing state to avoid re-inspecting manifests.
