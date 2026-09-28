# Stage 24: Multi-Agent Topology Experiments Master Report

## 1. Executive Summary
Stage 24 conducts controlled experimentation across the six-topology matrix defined in PLAN.md:
- **`M0`**: Root only
- **`M1`**: Root + Scout
- **`M2`**: Root + Debugger
- **`M3`**: Root + Reviewer
- **`M4`**: Root + Scout + Debugger
- **`M5`**: Root + Scout + Debugger + Reviewer

All six candidate packages have been compiled, verified with `scripts/validate_submission.py`, and confirmed to adhere strictly to the single-base-model constraint (`gemma-4-31b-it-qat-w4a16-ct`), the 9-tool root contract, and invariant canonical sub-agent configurations.

In strict compliance with **AGENTS.md §2.5 (Zero Fabrication Policy)**, no benchmark numbers, pass rates, or runtimes are fabricated. Because live Gemma 4 31B inference is unexecuted on the local development workstation, all performance metrics remain `null`, and the selection status is explicitly designated as **`UNRESOLVED`**.

---

## 2. Topology Comparison Table

| Topology | Name | Specialists | Pass Rate | Runtime | Turns | Tool Calls | Failure Recovery | Evidence Status |
|---|---|---|---|---|---|---|---|---|
| `M0` | `root_only` | *(none)* | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |
| `M1` | `root_plus_scout` | `scout` | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |
| `M2` | `root_plus_debugger` | `debugger` | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |
| `M3` | `root_plus_reviewer` | `reviewer` | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |
| `M4` | `root_plus_scout_debugger` | `scout`, `debugger` | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |
| `M5` | `root_full_specialists` | `scout`, `debugger`, `reviewer` | `null` | `null` | `null` | `null` | `null` | `UNEXECUTED` |

---

## 3. Experimental Controls Held Constant

Every candidate topology (M0 through M5) enforces absolute equality on all dimensions outside specialist availability:

| Control Dimension | Specification | Verification |
|---|---|---|
| **Base Model** | `gemma-4-31b-it-qat-w4a16-ct` across root and all specialists | Verified across all YAML declarations |
| **Root Generation Config** | `temp=0.2, top_p=0.95, max_tokens=16384, thinking=high/4096` | Verified identical |
| **Root Tools** | Exact 9 competition tools | Verified identical |
| **Specialist Tools** | Exact 5 read-only tools (`read_file`, `get_status`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`) | Verified identical |
| **Root Prompt** | Single shared topology-neutral prompt (`2360d4bf...`) | Verified byte-identical across M0–M5 |
| **Skills** | Canonical `test_strategy` (`3d027b0f...`) and `repo_triage` (`ac7a9671...`) | Verified byte-identical |
| **Subsystems** | E9 failure classification, E10 no-progress detection, E11 recovery paths | Shared local library |

---

## 4. Selection Status & Decision Protocol

- **Current Status:** `UNRESOLVED`
- **Promotion Rule:** The smallest topology that materially improves held-out performance will be selected once empirical evaluation is conducted on official competition platforms.
- **Cost Trade-Off Policy:** Specialist overhead (inference calls, token budgets, latency) must be justified by demonstrable pass rate improvement. Larger topologies will not be promoted if smaller topologies achieve statistically equivalent resolution rates.
