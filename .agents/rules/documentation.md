# Documentation Rules — IMPULSE

This document specifies the documentation standards, empirical reporting requirements, and synchronization policies for **IMPULSE**.

---

## 1. Reality-Grounded Documentation

Documentation must accurately reflect the *current, implemented state* of the repository. It is a historical and operational record, not an aspirational marketing brochure.

- **Current State Only:** Never describe planned, proposed, or speculative features as existing or functional. If a component is in progress, explicitly label it `[In Development]` or `[Planned]`.
- **Zero Fabrication of Benchmarks:** Never invent benchmark results, pass rates, execution times, or accuracy metrics to make the system appear more capable.
- **Explicit Untested Disclaimers:** If a capability, module, or configuration has not been empirically tested, explicitly state that it is untested.
- **Document Missing Dependencies:** If an external tool, runtime, or GPU environment is unavailable locally, document that limitation candidly rather than fabricating successful execution output.

---

## 2. Empirical Measurement Reporting Standards

Whenever performance numbers, latencies, or benchmark scores are cited:
1. **Measured Values Only:** Use values obtained directly from verified execution runs.
2. **Environment Recording:** Accompany every measurement with:
   - Hardware specifications (CPU, GPU model, VRAM).
   - Software versions (Python version, CUDA driver, framework releases).
   - Date, timestamp, and git commit hash of the candidate evaluated.
   - Specific benchmark task split and parameters used.
3. **Executable Commands:** Every command listed in documentation (setup steps, test invocations, runner commands) must be executed and confirmed working before publication.

---

## 3. Synchronization with Architecture & Plan

- **Synchronized Truth:** Technical documentation, docstrings, and README files must remain strictly synchronized with [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) and [PLAN.md](file:///e:/Projects/Impulse/PLAN.md).
- **Update with Code:** When code, configuration schemas, or CLI arguments change, update the corresponding documentation within the same development unit.
- **Traceable External Claims:** Every competition-specific claim (deadlines, rules, quotas, supported models, harness behavior) must be directly traceable to official competition documentation or empirical harness inspection.

---

## 4. Progressive README Architecture

As the repository evolves, the root `README.md` will be constructed incrementally to eventually include:
1. **Overview:** Project purpose, problem definition, and competition context.
2. **Architecture:** Summary of the shallow hierarchical multi-agent design, tool suite, and retrieval strategy.
3. **Setup & Prerequisites:** Step-by-step reproducible environment installation (OS, Python, Docker, GPU prerequisites).
4. **Development Workflow:** Instructions for running local tests, formatting code, and managing changes.
5. **Testing & Validation:** Commands for executing unit, integration, and packaging test suites.
6. **Local Evaluation:** Instructions for running benchmark splits and collecting traces.
7. **Experiments & Ablations:** Historical progression of candidates (E0 through RC1) and ablation findings.
8. **Submission Packaging:** Instructions for creating and validating `submission.zip`.
9. **Measured Benchmarks:** Empirical pass rates and timing tables from actual recorded runs.
10. **Reproducibility & Manifests:** Checksums, configuration hashes, and environment reproducibility guides.
11. **Security & Sandbox Isolation:** Security guarantees and safe execution policies.
12. **Limitations & Known Issues:** Transparent disclosure of current failure modes and edge-case limitations.

*Note: Do not populate sections with placeholder benchmarks or speculative claims. Add sections only when backed by working code and verified data.*

---

## 5. Formatting & Markdown Guidelines

- **Clickable File Links:** Link to workspace files using relative markdown paths or `file:///` URLs (e.g., `[IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md)`).
- **Valid Code Blocks:** All code examples must specify the syntax language (`python`, `bash`, `yaml`, `json`, `markdown`) and contain valid, syntactically correct code.
- **Concise & Direct:** Write in active voice, using concise, unambiguous technical language.
