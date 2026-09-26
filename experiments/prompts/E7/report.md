# Experiment Report: Candidate E7 (Testing Strategy Skill V1)

**Candidate ID:** E7  
**Parent Candidate:** E6  
**Parent Git Commit:** `36be03bdfc98937c3eb727ceb22a264c03935c87`  
**Date:** 2026-09-26  
**Status:** Validated (Structural & Skill Verification Only)

---

## 1. Executive Summary & Purpose

Candidate E7 implements **Stage 16 of PLAN.md**, establishing the **Systematic Testing Strategy Skill**:
$$\text{E7} = \text{E6} + \text{Systematic Testing Strategy Skill}$$

### Why Stage 16 Exists
In autonomous software engineering, defect verification is as critical as localization. An agent that generates a correct patch but cannot verify it—or one that runs unconstrained full-repository test suites causing timeouts—will fail to converge on reliable solutions.

Candidate E6 gave the agent an evidence-driven hybrid localization controller across exact, semantic, neighbor, and subgraph search tools. Candidate E7 complements this by providing an evidence-driven testing skill (`test_strategy`) to guide the agent through framework discovery, narrow reproduction, targeted verification, intelligent broadening, and test-result interpretation.

---

## 2. E6 $\to$ E7 Architecture Delta

1. **Tool Parity Preserved**:
   - Zero competition tools added or removed. All 9 tools declared in E6 are strictly preserved: `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`.
2. **Model & Generation Parameters**:
   - Model remains `gemma-4-31b-it-qat-w4a16-ct`.
   - Temperature (`0.2`), `top_p` (`0.95`), `max_output_tokens` (`16384`), and thinking config (`level: high`, `budget: 4096`, `include_thoughts: true`) are unchanged.
3. **Skill Artifact Added**:
   - Canonical repository location: `agent/skills/test_strategy/SKILL.md`.
   - Candidate submission layout: `experiments/candidates/E7/skills/test_strategy/SKILL.md`.
   - Declared in `experiments/candidates/E7/agent.yaml` under `skills: [skills/test_strategy]`.
4. **Prompt Delta**:
   - Root prompt (`experiments/candidates/E7/prompts/root.md`) minimally updated to reference the `test_strategy` skill under Operational Workflow and in Step 7 (Targeted Verification).

---

## 3. Skill Content Structure & Generic Design

The skill encodes a 7-step testing methodology:
1. **Discover Test Framework**: Read repository configuration files (`pyproject.toml`, `setup.cfg`, `package.json`, `Cargo.toml`, `go.mod`, `Makefile`) to identify runners and invocation conventions.
2. **Identify Relevant Test Area**: Map affected source modules to test directories using structural mirroring and symbol search.
3. **Reproduce Narrowly**: Run the smallest possible test or command to reproduce the reported failure before making code edits.
4. **Run Targeted Verification**: Execute the smallest relevant test unit exercising the modified behavior after applying edits.
5. **Broaden Intelligently**: Progressively escalate from single tests to file suites and subsystem suites only when justified by cross-component changes.
6. **Interpret Results Soundly**: Distinguish exit codes, test assertions, environment errors, and pre-existing failures from regressions.
7. **Avoid Unnecessary Full Suites**: Strictly discourage unconstrained repository test sweeps and redundant identical invocations to conserve tool calls and execution budget.

### Anti-Hardcoding Invariant
The skill contains **no repository-specific answers** or task-specific shortcuts for FastAPI, Requests, Rich, or any benchmark tasks. It teaches general discovery principles applicable across languages and frameworks.

---

## 4. Experimental Hypothesis & Evaluation Plan

### Hypothesis
> A generic testing skill that teaches framework discovery, narrow reproduction, targeted verification, intelligent broadening, and result interpretation will reduce redundant or unnecessarily broad test commands while preserving correct verification behavior.

### Proposed Future Measurements (For Live Inference)
- `redundant_test_command_count`: Repeated identical test executions without source modifications.
- `full_suite_invocations`: Unconstrained test executions across the full repository.
- `targeted_test_invocations`: Focused single-test or single-file test runs.
- `time_spent_in_verification`: Cumulative seconds spent executing test commands.
- `patch_resolution_rate`: Fraction of benchmark issues successfully resolved.

---

## 5. Verification & Hashes

### 5.1. Submission Validator Result
```
=== Validating Submission Directory: experiments\candidates\E7 ===
Total Files Inspected: 3
Total YAML Files:      1
Total Unpacked Size:   14,726 bytes (0.01 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 5.2. SHA-256 Hashes
- **E7 `agent.yaml`**: `92021a5379f36c7eeacca0962f666494efe028c973148f8e0f412812479692a0`
- **E7 `root.md`**: `d1195b317a475a2411b99b49d701d16e71bedd9b3c6c035d800970e15914950d`
- **Canonical `SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`
- **Parent E6 `root.md`**: `fe9805fc39ef2e4861aa4ea9b0956985080012acef70397b3f485f083733278e`

---

## 6. Anti-Fabrication Disclosures

In strict compliance with the IMPULSE Constitution (`AGENTS.md`):
1. **No Live Gemma Inference**: Candidate E7 has not been run against live Gemma 4 model inference on this workstation.
2. **No Competition Benchmark Execution**: Benchmark runs on official platforms have not been performed for E7.
3. **No Pass Rate Claim**: `pass_rate: null`, `redundant_test_command_count: null`.
4. **No Unmeasured Claims**: No claim is made that the skill reduces tool commands or improves task pass rates until empirical evaluations on official competition infrastructure demonstrate it.
5. **No Stage 17+ Features**: Repository triage, failure classification, no-progress detection, recovery loops, and sub-agents are strictly excluded.
