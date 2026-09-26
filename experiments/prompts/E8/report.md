# Experiment Report: Candidate E8 (Repository Triage Skill V1)

**Candidate ID:** E8  
**Parent Candidate:** E7  
**Parent Git Commit:** `4ce966dab411859df341690bb13e530fad7a4def`  
**Date:** 2026-09-26  
**Status:** Validated (Structural & Skill Verification Only)

---

## 1. Executive Summary & Purpose

Candidate E8 implements **Stage 17 of PLAN.md**, establishing the **Systematic Repository Triage Skill**:
$$\text{E8} = \text{E7} + \text{Systematic Repository Triage Skill}$$

### Why Stage 17 Exists
Autonomous agents solving SWE-bench tasks frequently waste tool calls and context during early turns conducting unstructured, blind exploration—guessing frameworks, running arbitrary directory searches, and repeatedly re-reading configuration manifests.

Candidate E7 gave the agent a systematic testing skill (`test_strategy`) and hybrid localization controller. Candidate E8 front-loads repository discovery by introducing `repo_triage`, teaching the agent to systematically identify language, framework, build manager, entry points, layout, test topology, and CI conventions early, recording verified facts into structured task state.

---

## 2. E7 $\to$ E8 Architecture Delta

1. **Tool Parity Preserved**:
   - Zero competition tools added or removed. All 9 tools declared in E7 are strictly preserved: `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`.
2. **Model & Generation Parameters**:
   - Model remains `gemma-4-31b-it-qat-w4a16-ct`.
   - Temperature (`0.2`), `top_p` (`0.95`), `max_output_tokens` (`16384`), and thinking config (`level: high`, `budget: 4096`, `include_thoughts: true`) are unchanged.
3. **Skill Artifacts Added**:
   - Canonical repository location: `agent/skills/repo_triage/SKILL.md`.
   - Candidate submission layout: `experiments/candidates/E8/skills/repo_triage/SKILL.md`.
   - Both skills declared in `experiments/candidates/E8/agent.yaml`:
     ```yaml
     skills:
       - skills/test_strategy
       - skills/repo_triage
     ```
4. **Prompt Delta**:
   - Root prompt (`experiments/candidates/E8/prompts/root.md`) updated to reference the `repo_triage` skill under Operational Workflow and in Step 2 (`Inspect Repository State`), while preserving E7's testing and localization guidance.

---

## 3. Skill Content Structure & Generic Design

The `repo_triage` skill guides the agent across 7 core reconnaissance dimensions:
1. **Language & Polyglot Boundaries**: Identify primary and secondary languages from root manifests and file extensions.
2. **Framework & Ecosystem**: Determine application framework from dependency manifests and entry-point imports.
3. **Package & Build Manager**: Identify packaging tools and local execution wrappers (e.g., `make`, `tox`, `poetry`, `npm`).
4. **Entry Points**: Locate executable scripts, console scripts, and main modules.
5. **Test Topology**: Establish test directories, runner configurations, and naming conventions.
6. **CI & Build Conventions**: Extract canonical build and test commands from workflow definitions.
7. **Repository Layout**: Construct a concise structural mapping of source, test, and documentation paths.

### Anti-Hardcoding Invariant
The skill contains **zero repository-specific or task-specific answers** for FastAPI, Requests, Rich, HTTPX, or SWE-bench tasks. It teaches general discovery principles applicable across languages and ecosystems.

---

## 4. Relationship to `test_strategy`

- **`repo_triage`** establishes the global repository map early (Step 2).
- **`test_strategy`** guides narrow reproduction, targeted verification, and result interpretation later (Step 7).
- Neither skill duplicates the other's detailed lifecycle.

---

## 5. Experimental Hypothesis & Future Metrics

### Hypothesis
> A generic repository triage skill that front-loads high-value repository reconnaissance will reduce redundant exploratory commands and shorten the path from task start to useful source/test locations without reducing localization quality.

### Proposed Future Measurements (For Live Inference)
- `triage_command_count`: Number of tool calls spent in initial reconnaissance.
- `redundant_exploration_command_count`: Repeated directory or manifest searches.
- `time_to_first_relevant_source_seconds`: Wall-clock latency to first relevant source file.
- `patch_resolution_rate`: Fraction of benchmark tasks resolved.

---

## 6. Verification & Hashes

### 6.1. Submission Validator Result
```
=== Validating Submission Directory: experiments\candidates\E8 ===
Total Files Inspected: 4
Total YAML Files:      1
Total Unpacked Size:   22,611 bytes (0.02 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 6.2. SHA-256 Hashes
- **E8 `agent.yaml`**: `c7c7f49faae94b904357583b2fc0e46ce9be0999688641f5d18e8a1e0e905f15`
- **E8 `root.md`**: `d607c494fc32f3132df3301bccc693adf8ba4074bdbc190860b1df65b6f78220`
- **Canonical `repo_triage/SKILL.md`**: `ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce`
- **Canonical `test_strategy/SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148` (Invariant)
- **Parent E7 `root.md`**: `d1195b317a475a2411b99b49d701d16e71bedd9b3c6c035d800970e15914950d`

---

## 7. Anti-Fabrication Disclosures

In strict compliance with `AGENTS.md`:
1. **No Live Gemma Inference**: Candidate E8 has not been executed against live Gemma 4 inference on this workstation.
2. **No Official Benchmark Execution**: Benchmark evaluation has not been executed for E8.
3. **No Pass Rate Claim**: `pass_rate: null`, `triage_command_count: null`.
4. **No Performance Claims**: No assertion is made that repository triage reduces commands or improves task pass rates until empirical evaluations on official competition platforms demonstrate it.
5. **No Stage 18+ Features**: Failure classification, no-progress detection, recovery paths, and sub-agents are strictly excluded.
