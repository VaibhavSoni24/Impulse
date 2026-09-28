# Architecture Decision Record: Tool-Call Budgeting (Stage 26)

## Status
ACCEPTED (Stage 26 Implementation)

## Context
Across multi-turn autonomous software engineering tasks, agents make dozens of tool calls to explore repositories, inspect symbols, execute tests, and modify source files. Without principled measurement and caching, agents frequently perform redundant or wasteful calls:
- Repeated directory listings (`get_status`, `ls`) when the working tree has not changed;
- Redundant reads of identical file slices;
- Repeated full test suite executions when no relevant code has been modified;
- Redundant semantic code searches using identical queries under unchanged indexes.

To optimize token efficiency and execution time, PLAN.md Stage 26 establishes **Tool-Call Budgeting**.
The subsystem answers:
1. Which tools are called most often?
2. Which tools are repeatedly called on unchanged state?
3. Which calls produce materially new evidence?
4. Which calls are redundant or low-information?
5. Which calls are associated with successful task resolution?
6. Which calls are associated with recovery from failures?
7. Where can bounded caching safely eliminate redundant calls?
8. What is the measured cost/benefit of each cache or budget rule?

Crucially, **Stage 26 prioritizes measurement and safe bounded caching over aggressive dynamic enforcement**. It enforces strict non-causal labeling for success associations and deterministic, hindsight-free information-gain metrics.

---

## Decision

### 1. Tool Call Event Model
Every tool invocation is tracked deterministically as a `ToolCallEvent`:
- `run_id`, `task_id`, `turn_id`, `call_id`
- `tool_name` and `category` (`READ_OBSERVATION`, `MUTATION`, `EXECUTION`, `SUBMISSION`)
- `normalized_arguments`: Posix-normalized paths, trimmed commands preserving diagnostic flags, sorted seed lists, and sanitized credentials.
- `repository_state_id`: Bound to the authoritative Stage 25 `manifest_digest` or content fingerprint.
- `information_value`: Structured decomposition of evidence novelty.
- `waste_class`: Redundancy classification.
- `cacheable`, `cache_hit`, `cache_invalidated`

### 2. Tool Classification Boundaries
- **READ / OBSERVATION:** `read_file`, `get_status`, `search_similar_code`, `get_code_neighbors`, `get_code_subgraph`. Eligible for bounded caching under identical repository state.
- **MUTATION:** `edit_file`, `write_file`. Strictly non-cacheable; trigger targeted invalidation upon execution.
- **EXECUTION:** `run_command`. Non-cacheable by default; allows narrow deterministic test result reuse only when command, relevant source fingerprint, and environment are identical.
- **SUBMISSION:** `submit_patch`. Strictly non-cacheable.

### 3. Deterministic Information-Gain Model (Hindsight-Free)
Information value is evaluated at the exact moment of execution against prior observation history, avoiding retrospective bias:
1. **New File Content:** `read_file` returns a content digest not previously observed for that path.
2. **Changed File:** A previously observed file path presents a new content digest.
3. **New Symbol / Relation:** Graph retrieval returns symbol/relation identifiers previously unseen.
4. **New Search Result:** Semantic search returns candidate chunks previously unseen.
5. **New Test Result:** Test execution produces a different exit code, failing test set, or assertion failure.
6. **New Repository State:** `get_status` returns a changed working tree digest.
7. **New Failure Class:** Diagnostic output causes E9 failure classification to transition.
8. **Recovery-Relevant Evidence:** Call provides evidence that updates the working hypothesis or recovery action.

Classification:
- `NEW_EVIDENCE`: Entire observation is empirically novel.
- `PARTIAL_NEW_EVIDENCE`: Mixture of seen and novel evidence units.
- `NO_NEW_EVIDENCE`: 100% redundant with prior observations for that query/state.

### 4. Observational Success Association (Strictly Non-Causal)
Tool invocation frequency on successful vs unsuccessful tasks is aggregated into neutral categories:
- `ASSOCIATED_WITH_SUCCESS`
- `ASSOCIATED_WITH_FAILURE`
- `NO_RESOLUTION`
- `INSUFFICIENT_DATA`

> [!NOTE]
> Correlation is not causation. A tool may be used frequently on successful runs because difficult tasks require extensive investigation, or on failing runs because an agent struggled during recovery. The system never claims that a tool "caused" task resolution.

### 5. Waste & Redundancy Detection
- `SAFE_REDUNDANT`: Identical read or status query repeated under identical repository state with zero new evidence.
- `POSSIBLY_REDUNDANT`: Repeated command execution under unchanged state without intervening edits.
- `NECESSARY_REPEAT`: Legitimate repetition (test rerun after edit, retry after transient error, recovery verification).
- `UNKNOWN`: Default when uncertain.

### 6. Bounded Tool Cache Architecture
- **Scope:** Run-scoped in-process cache (`BoundedToolCache`).
- **Cache Key:** `tool_name | arguments_digest | repository_state_id | target_path | index_version`.
- **Targeted Invalidation:** Modifying `src/foo.py` invalidates `read_file` on `src/foo.py`, `get_status`, and affected test results. Unrelated static reads (e.g. `README.md`) remain cached.
- **Bounds:** Default capacity bound of 200 entries with deterministic Least-Recently-Used (LRU) eviction.

### 7. Stage 25 & E9/E10/E11 Integration
- Reuses Stage 25 `ChangedFileTracker`, `compute_content_sha256`, `normalize_path`, and `sanitize_text`.
- Preserves E9 failure classification, E10 no-progress detection, and E11 recovery controller semantics with zero alteration.

---

## Consequences
- Provides transparency into tool-call distributions and information yield.
- Safely eliminates redundant tool calls under unchanged state without risking stale data.
- Enforces strict scientific hygiene against causal overclaiming.
- Fully preserves frozen Stage 24 multi-agent topology packages and specialist configurations.
- Scope bounds preserved: Stage 27 (cleanup automation), Stage 28 (clean-copy evaluator), Stage 29 (dataset construction), and LoRA are strictly deferred.
