# Stage 26: Tool-Call Budgeting Master Report

## 1. Executive Summary
Stage 26 implements deterministic Tool-Call Budgeting for IMPULSE as defined in PLAN.md Stage 26. The subsystem instruments tool invocation events, aggregates call-count distributions, defines a hindsight-free information-gain model, identifies wasteful calls under unchanged repository state, and provides a bounded cache with targeted invalidation.

In strict adherence to **AGENTS.md §2.5 (Zero Fabrication Policy)**:
- No competition benchmark reduction percentages or solve rate gains are fabricated.
- Live competition-scale Gemma 4 31B trace execution is explicitly recorded as **`UNAVAILABLE`** on the local development workstation.
- All empirical claims in this report are categorized explicitly into **OBSERVED**, **MEASURED**, **INFERRED**, and **UNAVAILABLE**.

---

## 2. Evidence Classification & Data Sources Analyzed

| Category | Data Source | Classification | Content Inspected / Status |
|---|---|---|---|
| **A. Real Local Traces** | `experiments/baseline/E0/results.jsonl` | `INFRASTRUCTURE_ONLY` | 5 benchmark tasks recorded on local host; all resulted in `execution_unavailable_local_host` due to local absence of 4x L4 GPUs. 0 tool calls executed. |
| **B. Synthetic / Fixture Data** | `tests/fixtures/budget_fixtures.py` & `compaction_fixtures.py` | `MEASURED` (Deterministic Fixtures) | 18 synthetic scenarios modeling repeated `read_file`, repeated `get_status`, repeated semantic queries, graph lookups, pytest/unittest runs, file mutations, and recovery reruns. |
| **C. Competition-Scale Traces** | Official Gemma 4 31B Harness Traces | `UNAVAILABLE` | Live competition inference traces have not been run locally. No competition benchmark tool-call distribution is claimed. |

---

## 3. Tool-Call Metrics Implemented

### Tool Call Event Architecture (`local/budgeting/`)
1. **Event Model (`models.py` & `normalization.py`):**
   - Canonical `ToolCallEvent` schema tracking run, task, turn, tool name, category, normalized arguments, repository state ID, information value, and waste classification.
   - Posix-normalized paths, trimmed commands with preserved diagnostic flags, sorted seed lists, and sanitized secret credentials.

2. **Call Count Distributions (`analyzer.py`):**
   - Aggregates total calls, calls per task, calls per tool, call share percentage, distinct vs repeated calls, and cache hits/misses.

3. **Deterministic Information-Gain Model (`novelty.py`):**
   - Evaluates empirical novelty at the moment of tool execution across 8 distinct evidence dimensions:
     - New file content
     - Changed file content
     - New symbols/relations
     - New search candidate items
     - New test outcomes / error signatures
     - New repository status digest
     - New failure class transitions
     - Recovery-relevant evidence
   - Computes explicit `novelty_ratio` and classifies into `NEW_EVIDENCE`, `PARTIAL_NEW_EVIDENCE`, or `NO_NEW_EVIDENCE`.

4. **Observational Success Associations (`analyzer.py`):**
   - Correlates tool usage frequency on successful vs unsuccessful tasks using strictly non-causal labels:
     - `ASSOCIATED_WITH_SUCCESS`
     - `ASSOCIATED_WITH_FAILURE`
     - `NO_RESOLUTION`
     - `INSUFFICIENT_DATA`

5. **Waste Detection (`waste_detector.py`):**
   - Identifies `SAFE_REDUNDANT` calls (identical read/status under unchanged state with zero new evidence).
   - Identifies `POSSIBLY_REDUNDANT` calls (repeated test commands without intervening edits).
   - Identifies `NECESSARY_REPEAT` calls (reruns after file modification, transient retries, recovery verification).

6. **Bounded Tool Cache (`cache.py`):**
   - Run-scoped cache permitting read/observation tools (`read_file`, `get_status`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`).
   - Mutations (`edit_file`, `write_file`) and submissions (`submit_patch`) are strictly non-cacheable.
   - Cache keys bind to `tool_name`, `arguments_digest`, and `repository_state_id`.
   - Targeted invalidation: editing `src/parser.py` invalidates reads of `src/parser.py`, `get_status`, and affected test results, while preserving unrelated static reads (`README.md`).
   - Capacity bound (default 200) with deterministic LRU eviction.

---

## 4. Measured Verification Results

The following metrics were directly measured during automated test execution on deterministic test fixtures:

| Metric | Measured Value | Classification |
|---|---|---|
| **Synthetic Fixture Scenarios Tested** | 18 | `MEASURED` |
| **Tools Evaluated Across Categories** | 9 canonical tools (Read, Mutation, Execution, Submission) | `MEASURED` |
| **Cache Hit / Miss Accuracy** | 100% (Hits on unchanged state, misses on state shift) | `MEASURED` |
| **Targeted Invalidation Precision** | 100% (Affected file invalidated; unrelated file preserved) | `MEASURED` |
| **LRU Eviction Verified** | 100% (Least recently accessed evicted upon capacity) | `MEASURED` |
| **Non-Causal Disclaimer Verified** | Present in all generated reports | `MEASURED` |
| **Secret Redaction Verified** | 100% (Tokens scrubbed to `[REDACTED_SECRET]`) | `MEASURED` |
| **Stage 26 Focused Tests Passed** | 22 / 22 (100%) | `MEASURED` |
| **Full Regression Suite Tests Passed** | 575 / 575 (100%) | `MEASURED` |
| **Submission Validator on Candidates M0–M5** | 6 / 6 valid (100%) | `MEASURED` |
| **Competition Benchmark Tool Savings** | `null` (Unexecuted) | `UNAVAILABLE` |
| **Competition Benchmark Solve Rate Impact** | `null` (Unexecuted) | `UNAVAILABLE` |

---

## 5. Frozen Invariance Verification

All prior frozen artifacts remain verified and invariant:
- **Scout Specialist YAML:** `335c1a32d7001271f8b9417e2981e2d3214c55713be99b3da1a6e0634d705877`
- **Scout Specialist Prompt:** `d57f433cf7459f258c8bc5011f82b5887aea2d07e1ef674c5b95cc8cbe007805`
- **Debugger Specialist YAML:** `07b936c8abf06d8710138e2ba94611c57e48cd476c0fb945f7c187abd25d9199`
- **Debugger Specialist Prompt:** `a743a30bcc297fcc1335b34ef5851533ca751a4699e6b0d6aede76510f57082f`
- **Reviewer Specialist YAML:** `facfcbb4fbc8d42a82f32a6979bf8b090de5857ba92b4641e4a45617b340200c`
- **Reviewer Specialist Prompt:** `d2432da56d07170989edbd83add7fe51323df1db6dd458b80f0d893cdb9264c6`
- **Shared Topology Root Prompt:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e` across M0 through M5.
- **Canonical Skills:** `skills/test_strategy` (`3d027b0f...`) and `skills/repo_triage` (`ac7a9671...`).
- **Stage 25 Context Compaction:** Fully operational and passing all 23 focused tests.
- **E9, E10, E11 Semantics:** Fully preserved and operational.

---

## 6. Known Limitations
- Exact tool-call reductions on competition benchmarks remain to be empirically quantified once competition infrastructure (4x L4 GPUs) is available.
- Tool-call budgeting in Stage 26 is observational and cached; it does not prematurely terminate tasks based on arbitrary call quotas.

---

## 7. Confirmation of Scope Bounds
- Stage 27 (Final Diff Discipline and Cleanup Automation) was **NOT** implemented.
- Stage 28 (Clean-Copy Evaluator) was **NOT** implemented.
- Stage 29 (Dataset Split Construction) was **NOT** implemented.
- Dynamic autonomous quota enforcement and LoRA fine-tuning were **NOT** implemented.
