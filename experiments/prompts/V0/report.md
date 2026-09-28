# Candidate Report: V0 (Stage 23)

## 1. Candidate Overview
- **Candidate ID**: `V0`
- **Stage**: Stage 23 (Create the Reviewer Agent — Baseline Control Candidate)
- **Parent Candidate**: `D2`
- **Parent Git Commit**: `be36a504ef741466de6b9aa7bd6df171326da6f2`
- **Model**: `gemma-4-31b-it-qat-w4a16-ct`
- **Base Architecture**: Root Agent + Scout Specialist + Debugger Specialist
- **Reviewer Policy**: `UNAVAILABLE` (Root performs final pre-submission inspection and patch submission directly)

---

## 2. Experimental Role
Candidate `V0` serves as the negative control candidate for the Stage 23 experiment. In `V0`, the Reviewer specialist is not declared or available. The Root agent retains access to the read-only Scout (for pre-edit localization) and read-only Debugger (for post-failure diagnosis), but carries out all final pre-submission checks and submission decisions unilaterally.

Candidate `V0` tests whether the agent system operates effectively without an independent final-review stage.

---

## 3. Configuration & Integrity
- **Root Agent Config**: `experiments/candidates/V0/agent.yaml` (`dbc19fe450687636bb2da1adfa65975b928a25f9345f3ebcf562292465673e36`)
- **Root Prompt**: `experiments/candidates/V0/prompts/root.md` (`3aeecc3db73e07e699a76059dd847bca6fcf5d90145368b3fb9bf4a79fc2baca`)
- **Scout Sub-Agent Config**: `experiments/candidates/V0/sub_agents/scout.yaml` (`335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877`)
- **Scout Prompt**: `experiments/candidates/V0/prompts/scout.md` (`d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805`)
- **Debugger Sub-Agent Config**: `experiments/candidates/V0/sub_agents/debugger.yaml` (`07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199`)
- **Debugger Prompt**: `experiments/candidates/V0/prompts/debugger.md` (`a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f`)
- **Reviewer Sub-Agent**: Not configured / unavailable.
- **Skills**:
  - `skills/test_strategy` (`3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`)
  - `skills/repo_triage` (`ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce`)
- **Tools**: Exactly 9 root tools; exactly 5 Scout read-only tools; exactly 5 Debugger read-only tools; 0 Reviewer tools.

---

## 4. Controlled Comparison
The experiment strictly isolates the availability and intervention of the Reviewer specialist:
- `V0`: Reviewer unavailable; Root directly decides when to submit patch.
- `V1`: Reviewer available; Root invokes Reviewer once at final review point under `REVIEWER_TRIGGER`.

All other dimensions are held constant:
- Model (`gemma-4-31b-it-qat-w4a16-ct`) across root and sub-agents.
- Generation settings (`temp=0.2`, `top_p=0.95`, `max_tokens=16384`, `thinking=high/4096`).
- Root 9 competition tools.
- Scout 5 read-only tools and canonical prompt.
- Debugger 5 read-only tools and canonical prompt.
- Canonical skills (`test_strategy`, `repo_triage`).
- Downstream E9 failure taxonomy, E10 no-progress detector, and E11 recovery subsystem.

---

## 5. Empirical Claims & Validation Status
- **Submission Validator**: PASSED (`scripts/validate_submission.py`)
- **Live Inference**: `UNEXECUTED` (Gemma 4 31B inference not hosted in local development environment)
- **Pass Rate**: `null` (Strict Zero-Fabrication policy in compliance with AGENTS.md §2.5)
