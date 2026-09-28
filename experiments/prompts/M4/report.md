# Candidate Report: M4 (Stage 24)

## 1. Candidate Overview
- **Candidate ID**: M4
- **Topology Name**: root_plus_scout_debugger
- **Stage**: Stage 24 (Multi-Agent Topology Experiments)
- **Parent Git Commit**: d8f8522f8a64b9bb4c93b314ed29563ca43a508d
- **Model**: gemma-4-31b-it-qat-w4a16-ct
- **Specialists Declared**: scout, debugger

---

## 2. Experimental Role
Candidate M4 evaluates topology root_plus_scout_debugger (Root agent with Scout and Debugger specialists.) within the Stage 24 multi-agent topology experiment matrix.

All six candidates (M0–M5) share:
- The exact same root prompt (prompts/root.md).
- The exact same 9 competition tools.
- The exact same generation configuration (	emp=0.2, 	op_p=0.95, max_tokens=16384, 	hinking=high/4096).
- Canonical skills (skills/test_strategy, skills/repo_triage).
- Canonical read-only specialist definitions where declared.

---

## 3. Configuration & Integrity
- **Root Agent Config**: experiments/candidates/M4/agent.yaml (63e37a622f8ee84476dcd279571bc6e512efdf50e5b0e7afe2df522bc6812e94)
- **Root Prompt**: experiments/candidates/M4/prompts/root.md (2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e)
- **Skills**:
  - skills/test_strategy (3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148)
  - skills/repo_triage (ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce)
- **Submission Validator**: PASSED (scripts/validate_submission.py)

---

## 4. Empirical Claims & Validation Status
- **Submission Validator**: PASSED
- **Live Inference**: UNEXECUTED (Full Gemma 4 31B local inference not hosted on development workstation)
- **Pass Rate**: 
ull (Strict Zero-Fabrication policy in compliance with AGENTS.md §2.5)
- **Selection Status**: UNRESOLVED
