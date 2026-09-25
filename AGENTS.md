# IMPULSE — Project Constitution

This document establishes the binding governance and operating principles for all AI agents and engineers working in the **IMPULSE** repository.

---

## 1. Project Authority and Specifications

- **Project Name:** IMPULSE (Autonomous software-engineering agent for repository-level issue resolution).
- **Authoritative Specifications:**
  - [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md): The frozen, complete architectural and system specification (Single Source of Truth for architecture and system behavior).
  - [PLAN.md](file:///e:/Projects/Impulse/PLAN.md): The complete implementation and execution plan (Single Source of Truth for construction sequence, validation stages, and release gates).
- **Mandatory Alignment:** Implementation must strictly adhere to the finalized architecture and plan. No agent may silently alter the system architecture, component topology, tool boundaries, or operational models.
- **Controlled Revisions:** Architectural changes require explicit evidence, deliberate justification, and formal documentation before code modification.

---

## 2. Core Governance Principles

1. **Evidence-Based Decisions:** Verify uncertain facts instead of guessing. Base every hypothesis, code modification, and recovery action on concrete observations and verifiable data.
2. **Authoritative Verification:** Current competition rules, deadlines, quotas, harness APIs, and platform requirements must be verified against current official documentation and harness sources before taking dependent actions. Never rely on external assumptions or outdated examples.
3. **Strict Reproducibility:** Every candidate release must record exact prompt versions, configuration hashes, tool definitions, model identifiers, software versions, and benchmark splits.
4. **Mandatory Testing:** Tests are an integral part of implementation, not an afterthought. Every non-trivial change requires targeted verification and regression evaluation.
5. **Zero Fabrication:**
   - Benchmark scores, latency measurements, and pass rates must **never** be fabricated or assumed.
   - Final documentation and `README.md` must only assert numbers and capabilities that were empirically measured and reproducible locally or on official platforms.
   - Never write "tested", "verified", "100% reliable", or similar claims without concrete proof.
6. **Clean Repository Hygiene:**
   - Temporary test scripts, debug outputs, scratch files, and intermediate logs must be purged from the repository.
   - The repository must remain reproducible, minimalist, and cleanly structured at all times.
7. **Strict Security:**
   - **Zero Secrets Policy:** Never hard-code or commit credentials, API keys, access tokens, private keys, or session tokens.
   - Obey sandbox isolation and never use destructive commands without verified targets.
8. **Disciplined Incremental Git Workflow:**
   - Work must proceed in small, coherent units.
   - Complete units must be verified, tested, inspected via `git diff`, and committed with concise, conventional commit messages.
   - Never wait until the end of a project or major stage to create a single monolithic commit.

---

## 3. Modular Governance Rules

All development within IMPULSE is governed by the detailed modular rules located in `.agents/rules/`:

- [Development Rules](file:///e:/Projects/Impulse/.agents/rules/development.md): Planning discipline, implementation hygiene, dependency policies, and change management protocol.
- [Architecture Rules](file:///e:/Projects/Impulse/.agents/rules/architecture.md): Architectural authority, separation of development tooling vs. submission artifacts, and non-negotiable architectural boundaries.
- [Security Rules](file:///e:/Projects/Impulse/.agents/rules/security.md): Secret protection, `.env` handling, sensitive data isolation, command execution safety, and supply chain integrity.
- [Git Rules](file:///e:/Projects/Impulse/.agents/rules/git.md): Commit standards, inspection routines, `.gitignore` discipline, and branch management.
- [Testing Rules](file:///e:/Projects/Impulse/.agents/rules/testing.md): Progressive validation, test-first discipline, failure taxonomy, and zero-fabrication standards.
- [Documentation Rules](file:///e:/Projects/Impulse/.agents/rules/documentation.md): Grounded documentation, empirical measurement requirements, synchronized architecture tracking, and README standards.

Every engineer and autonomous agent must consult and uphold these rules across all turns.
