# Architectural Decision Record: Testing Strategy Skill — IMPULSE

**Status:** Accepted  
**Date:** 2026-09-26  
**Decision Makers:** IMPULSE Architecture Team  
**Consulted Documents:**
- [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) (Section 18, Stage 16)
- [HARNESS_README.md](file:///e:/Projects/Impulse/data/competition/HARNESS_README.md) (Sections 2.2, 2.3, 2.4)
- [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) (Sections 34, 58)
- [hybrid_localization.md](file:///e:/Projects/Impulse/docs/decisions/hybrid_localization.md)
- [tool_contracts.md](file:///e:/Projects/Impulse/docs/decisions/tool_contracts.md)

---

## 1. Context & Problem Statement

Prior candidate **E6** established a bounded, evidence-driven hybrid localization controller (`HybridLocalizationPolicy V1`) across exact, semantic, neighbor, and subgraph retrieval tools. However, once candidate source code is located and modified, the agent faces the **verification phase**.

Without systematic testing guidance, agents in SWE benchmarks exhibit several failure modes:
1. **Blind Full-Suite Sweeps**: Running unconstrained test commands (e.g., bare `pytest` or `cargo test` across an entire repository), causing session timeouts, resource exhaustion, or failure on unrelated pre-existing broken tests.
2. **Framework Assumption**: Hard-coding assumptions that all Python repositories use `pytest` or all JavaScript projects use `npm test`, failing when repositories use `unittest`, `tox`, `nox`, `jest`, or custom test harnesses.
3. **Premature Modification without Reproduction**: Modifying code before establishing a minimal reproducible failure command, making it impossible to verify whether the fix resolved the underlying issue.
4. **Superficial Result Interpretation**: Equating a command exit status of 0 with complete validation (ignoring skipped tests or suppressed exceptions) or misidentifying environment errors as test regressions.

Candidate E7 addresses this by introducing the **Systematic Testing Strategy Skill**:
$$\text{E7} = \text{E6} + \text{Systematic Testing Strategy Skill}$$

---

## 2. Seven-Step Testing Strategy

The skill (`agent/skills/test_strategy/SKILL.md`) codifies a 7-step lifecycle:

```
┌────────────────────────────────────────┐
│  1. Discover Test Framework & Tools    │  Inspect pyproject.toml, pytest.ini, Makefile, CI
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  2. Identify Relevant Test Area        │  Mirror source path, locate existing regressions
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  3. Reproduce Narrowly                 │  Run minimal single test before modifying code
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  4. Run Targeted Test After Edits      │  Target smallest direct unit / filtered test
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  5. Broaden Coverage Intelligently     │  Escalate to module/subsystem only when justified
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  6. Interpret Results Soundly          │  Inspect exit codes, traces, pre-existing vs new
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│  7. Avoid Unnecessary Full Suites      │  Preserve execution budget; stop when confident
└────────────────────────────────────────┘
```

1. **Discover Test Framework**: Determine language, runner, and conventions from repository evidence (e.g., configuration files, directory trees, CI scripts). Never assume a framework blindly.
2. **Identify Relevant Test Area**: Map suspect implementation files to their corresponding test modules using structural mirroring and symbol search.
3. **Reproduce Narrowly**: Establish the failure mode with the smallest possible command before altering source code.
4. **Run Targeted Verification**: Execute the smallest unit of testing that directly exercises the modified logic.
5. **Broaden Intelligently**: Progressively escalate test scope ($\text{single test} \to \text{test file} \to \text{subsystem}$) only when the modification crosses component boundaries or alters shared abstractions.
6. **Interpret Results Soundly**: Distinguish between test failures, command/environment errors, skipped tests, and pre-existing repository defects.
7. **Avoid Huge Suites Unnecessarily**: Block unconstrained full-repository sweeps and redundant identical commands to preserve session execution limits and tool call budget.

---

## 3. Generic-Content Boundary (Anti-Hardcoding Rule)

The testing skill is strictly **repository-agnostic and task-agnostic**:
- It contains **zero** hard-coded knowledge of specific benchmark repositories (e.g., FastAPI, Requests, Rich, HTTPX).
- It provides no task-specific command shortcuts (e.g., "for task fastapi_14786 run...").
- It teaches the agent **how to discover** repository conventions dynamically via inspection tools (`read_file`, `run_command`).

---

## 4. Skill Loading & Submission Architecture

Per `HARNESS_README.md` Section 2.2 and Section 2.3:
- The canonical skill manifest resides at:
  `agent/skills/test_strategy/SKILL.md`
- For Candidate E7, the skill is packaged within the submission directory layout:
  `experiments/candidates/E7/skills/test_strategy/SKILL.md`
- Referenced in `experiments/candidates/E7/agent.yaml`:
  ```yaml
  skills:
    - skills/test_strategy
  ```
- Referenced in the root prompt (`experiments/candidates/E7/prompts/root.md`) under Operational Workflow and Step 7.
- Complies strictly with the submission validator (`scripts/validate_submission.py`), passing schema checks and unpacked size ceilings.

---

## 5. Experimental Hypothesis & Future Metrics

### 5.1. Formal Hypothesis
> **Hypothesis (Stage 16):** An agent equipped with a generic, evidence-driven testing strategy skill will reduce redundant and unconstrained test commands while maintaining or improving targeted verification precision compared to an agent relying on unstructured verification instructions.

### 5.2. Proposed Empirical Metrics (For Future Live Evaluation)
- `redundant_test_command_count`: Number of repeated identical test commands without intermediate code modifications.
- `full_suite_invocations`: Count of unconstrained full-repository test executions.
- `targeted_test_invocations`: Count of single-function or single-file test runs.
- `verification_time_seconds`: Total wall-clock time spent in test execution per task.
- `patch_resolution_rate`: Fraction of benchmark tasks resolved by verified patches.

### 5.3. Anti-Fabrication Notice
In accordance with `AGENTS.md`:
- Candidate E7 has **not** been executed against live Gemma 4 inference on this workstation.
- All benchmark metrics remain `null` (`pass_rate: null`, `redundant_test_command_count: null`).
- No causal performance improvement is asserted without empirical live evaluation.

---

## 6. Hard Stage 17 Boundary

Candidate E7 implements **Stage 16 only**. It does **NOT** implement:
- Stage 17 Repository Triage Skill (`repo_triage/SKILL.md`);
- Stage 18 Failure Classification;
- Stage 19 No-Progress Detector;
- Stage 20 Recovery Paths;
- Sub-agents (Scout, Debugger, Reviewer) or LoRA adapters.
