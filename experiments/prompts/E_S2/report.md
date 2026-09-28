# Candidate E_S2 Experiment Report: Scout Specialist (Mandatory under Uncertainty)

**Candidate ID:** E_S2  
**Parent Candidate:** E11  
**Parent Git Commit:** `70679eb7680be0867e5edf8c18a8f89cb0ea583d`  
**Date:** 2026-09-28  
**Status:** Validated (Structural validation only; execution unasserted)

---

## 1. Motivation and Purpose (Stage 21)

Stage 21 introduces the first specialist agent in the IMPULSE architecture: the **Scout Agent**.
The objective of Scout is to perform read-only codebase exploration, trace symbols and relationships, and gather structured localization evidence for the root agent.

In Candidate **E_S2**, Scout is configured under the **Mandatory under Uncertainty** invocation policy:
- When the deterministic localization-uncertainty condition fires (`SCOUT_TRIGGER == True`), invocation of Scout is mandatory once.
- The root agent incorporates Scout's structured localization evidence into task state and proceeds with normal evidence-driven verification and repair.
- Loop prevention limits Scout to at most 1 invocation per unchanged uncertainty episode.

---

## 2. Architecture Delta (E11 → E_S2)

```text
Candidate E11 (Stage 20):
  Model: gemma-4-31b-it-qat-w4a16-ct
  Sub-agents: None
  Tools: 9 competition tools
  Skills: [skills/test_strategy, skills/repo_triage]
  Policy: Triage + hybrid localization + testing strategy + failure taxonomy + no-progress detection + recovery paths

Candidate E_S2 (Stage 21):
  Model: gemma-4-31b-it-qat-w4a16-ct (Preserved identical)
  Sub-agents: [scout] (Read-only specialist using gemma-4-31b-it-qat-w4a16-ct)
  Scout Tools: [read_file, get_status, search_similar_code, get_code_neighbors, get_code_subgraph]
  Root Tools: 9 competition tools (Preserved identical)
  Skills: [skills/test_strategy, skills/repo_triage] (Preserved identical)
  Delta: Added Scout sub-agent declaration, Scout prompt/config, Scout data models (ScoutResult),
         and mandatory Scout invocation under explicit localization uncertainty.
```

---

## 3. Structural Validation Results

### 3.1. Submission Validator Output
```text
=== Validating Submission Directory: experiments\candidates\E_S2 ===
Total Files Inspected: 6
Total YAML Files:      2
Total Unpacked Size:   29,874 bytes (0.03 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 3.2. SHA-256 Hashes
- **Root `agent.yaml`**: `d91eab2b640108945ff3c1eb3de6ecbc41522f566159a0a9405a88bd04d03876`
- **Root `root.md`**: `e0cc66e573c3e961630fc11add52f53370cfee67d3319196b21a21ddcb4e21cd`
- **Scout `scout.yaml`**: `335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877`
- **Scout `scout.md`**: `d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805`
- **Canonical `test_strategy/SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148` (Invariant)
- **Canonical `repo_triage/SKILL.md`**: `ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce` (Invariant)

---

## 4. Controlled Difference: E_S1 vs. E_S2

The experimental setup isolates invocation policy:
- **E_S1**: Scout available; root agent decides whether information gain justifies the call.
- **E_S2**: Scout mandatory once when localization uncertainty is detected.
- All other parameters (Scout prompt, Scout config, tools, models, skills, generation parameters) are held constant.

---

## 5. Anti-Fabrication Disclosures

In strict adherence to `AGENTS.md`:
1. **No Live Gemma Inference**: Candidate E_S2 has not been executed against live Gemma 4 inference on this workstation.
2. **No Official Benchmark Execution**: Benchmark evaluation has not been executed for E_S2.
3. **No Pass Rate Claim**: `pass_rate: null`, `localization_accuracy: null`.
4. **No Performance Claims**: No claim is asserted that mandatory Scout invocation improves pass rates until empirical measurements on official competition platforms demonstrate it.
5. **No Stage 22+ Features**: Debugger, Reviewer, multi-agent topology orchestration, and LoRA adapters are strictly excluded.
