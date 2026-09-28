# Architecture Decision Record: Reviewer Specialist Agent (Stage 23)

## Status
ACCEPTED (Stage 23 Implementation)

## Context
Following Stage 21 (Scout specialist for read-only repository localization) and Stage 22 (Debugger specialist for read-only post-failure diagnosis), IMPULSE requires a mechanism to perform an independent, read-only final assessment of completed candidate patches before submission.

In prior configurations (E0 through E11, E_S1/E_S2, D1/D2, and candidate V0), the Root agent performs patch generation, verification, and final submission decisions unilaterally. While Root can run verification tests, complex repository edits often harbor subtle omissions:
- Scope creep or unintended modifications to adjacent modules.
- Accidental inclusion of temporary debug code, machine-specific paths, or secrets.
- Missing edge-case handling or weak test coverage that nominally passes but does not exercise the full requirement.
- Inconsistencies between the issue statement and the implemented patch.

Stage 23 introduces a dedicated, read-only specialist: the **Reviewer Agent**.

---

## Decision

### 1. Purpose of the Reviewer Agent
The Reviewer assesses whether a completed candidate patch satisfies the issue requirements, remains properly scoped, is supported by sound test evidence, and is safe and hygienic to ship.

The Reviewer answers:
> *"Does the completed change satisfy the issue, and does the evidence support shipping the current patch?"*

The Reviewer does **NOT**:
- Edit or create source files (`edit_file`, `write_file` are omitted).
- Submit patches (`submit_patch` is omitted).
- Execute commands or run tests (`run_command` is omitted).
- Execute rollbacks or recovery procedures.
- Act as a coder, debugger, scout, or recovery controller.
- Replace the Root agent's authority over final submission decisions.

### 2. Distinction Between Scout, Debugger, and Reviewer
| Dimension | Scout Specialist (Stage 21) | Debugger Specialist (Stage 22) | Reviewer Specialist (Stage 23) |
|---|---|---|---|
| **Primary Question** | "Where is the relevant code?" | "Why did the verification fail?" | "Does the completed change satisfy the issue and is it safe to ship?" |
| **Phase of Invocation** | Pre-edit repository reconnaissance & localization | Post-failure diagnostic reasoning | Pre-submission final patch assessment |
| **Trigger Condition** | Localization uncertainty (`SCOUT_TRIGGER`) | Difficult verification failure (`DEBUGGER_TRIGGER`) | Completed patch + verification under `REVIEWER_TRIGGER` |
| **Input Signals** | Issue statement, symbols, directory layout | Failing test output, stack trace, diff, prior hypothesis | Issue, candidate diff summary, test results, verification evidence |
| **Output Focus** | Candidate files, symbols, relationships | Causal mechanism, contradictions, next inspection targets | Status (`APPROVE`, `CHANGES_REQUESTED`, `INSUFFICIENT_EVIDENCE`), blocking/nonblocking findings, hygiene risks |

### 3. Read-Only Guarantees and Tool Subset
To structurally prevent repository mutation, workspace corruption, or unauthorized patch submissions, the Reviewer is restricted at both configuration and prompt levels:
- **Exposed Read-Only Tools (5 tools)**:
  - `read_file`: Inspect modified source files, test fixtures, configuration, and documentation.
  - `get_status`: Inspect working tree status without modification.
  - `search_similar_code`: Semantic retrieval for relevant symbols or usage patterns.
  - `get_code_neighbors`: Examine callers and callees of modified interfaces.
  - `get_code_subgraph`: Inspect interaction topologies around changed components.
- **Prohibited Tools**:
  - `edit_file`, `write_file`, and `submit_patch` are completely omitted from the Reviewer's declaration.
  - `run_command` is omitted from the sub-agent to prevent arbitrary command execution or test runner side-effects. Root runs tests and supplies structured outcomes.
- **Prompt Prohibitions**: The Reviewer prompt explicitly forbids file modification, file creation, shell operations, rollback initiation, or patch submission.

### 4. Reviewer Input Contract
The Reviewer consumes a concise, bounded input record (`ReviewerInput`), preventing context exhaustion or raw trace dumping:
- `issue`: Stated problem description or issue requirement.
- `diff_summary`: Summary or unified diff of proposed changes (bounded).
- `relevant_tests`: List of targeted tests executed to verify the change.
- `result_summary`: Summary of verification test outcomes (e.g., passed/failed count, failure messages).
- `changed_files`: Bounded list of files modified, added, or deleted.
- `verification_status`: Status of verification execution (`PASSED`, `FAILED`, `UNVERIFIED`).
- `metadata`: Optional bounded contextual facts.

### 5. Structured Output Contract (`ReviewerResult`)
The Reviewer outputs a structured assessment record:
- `status`: Categorical outcome:
  - `APPROVE`: No blocking issues identified based on supplied evidence (does NOT imply a formal correctness guarantee).
  - `CHANGES_REQUESTED`: Concrete blocking findings identified.
  - `INSUFFICIENT_EVIDENCE`: Supplied verification evidence is inadequate for a sound assessment.
- `issue_alignment`: Assessment of whether the patch satisfies requested behavior.
- `diff_scope`: Assessment of change scope, file relevance, and unexpected edits.
- `test_assessment`: Assessment of test coverage, relevancy, and passing evidence.
- `regression_risk`: Evaluation of potential adverse impacts on adjacent features.
- `security_hygiene`: Audit of accidental secrets, tokens, debug code, or generated files.
- `blocking_findings`: List of critical issues precluding submission.
- `nonblocking_findings`: List of minor concerns, cleanup notes, or recommendations.
- `missing_evidence`: Specific missing tests, logs, or verification details.
- `required_followups`: Concrete actionable items recommended for the Root agent.
- `observed_evidence`: Concrete observations directly verifiable in diffs or test logs.
- `inferred_risks`: Plausible risks or potential gaps (clearly distinguished from observations).
- `summary`: Concise synthesis (max 500 characters).

*Note: No numeric scores, 0–100 quality ratings, or arbitrary "confidence percentages" are permitted.*

### 6. Review Trigger (`REVIEWER_TRIGGER`)
The Reviewer is invoked near the end of the Root workflow when:
1. `has_candidate_diff == True` (Root has generated a non-empty patch).
2. `verification_attempted == True` (Relevant verification tests have been run).
3. `result_summary_present == True` (A concrete verification result summary exists).
4. `is_approaching_finalization == True` (Root is preparing for submission).
5. `patch_already_reviewed == False` (The Reviewer has not already reviewed this exact patch state).

Reviewer is **NOT** invoked after every tool call, before meaningful changes exist, during initial scouting, or in routine recovery loops.

### 7. Invocation Bounds and Loop Prevention
- **Episode Bound**: Maximum 1 Reviewer invocation per unchanged patch/review episode.
- **Suppression Rule**: If Reviewer returns `CHANGES_REQUESTED` or `INSUFFICIENT_EVIDENCE`, repeat calls are blocked until Root makes a material code modification or executes new tests.
- **Loop Avoidance**: Chained `Reviewer -> Reviewer -> Reviewer` loops with no intermediate state mutations are strictly prohibited by `ReviewerControllerV1`.

### 8. Security and Hygiene Checks
The Reviewer inspects patches specifically for accidental inclusion of:
- Secrets, tokens, and credentials (`ghp_*`, `AKIA*`, API keys, private keys, passwords).
- Environment configurations (`.env`, `.env.local`).
- Temporary files, debug artifacts, or log dumps.
- Machine-specific absolute paths or credentials.
- Accidental debug prints (`console.log`, `breakpoint()`, `pdb`, `print(...)` left in test harness).

Reviewer reports concrete observations based solely on supplied evidence rather than asserting universal security guarantees.

### 9. TaskState Integration
Review outcomes are recorded compactly in `TaskState`:
- `review_count`: Total review episodes executed.
- `review_status`: Latest status (`APPROVE`, `CHANGES_REQUESTED`, `INSUFFICIENT_EVIDENCE`).
- `blocking_findings`: Current blocking items.
- `nonblocking_findings`: Nonblocking items.
- `review_summary`: High-level summary of findings.
- `last_reviewed_fingerprint`: Diff fingerprint of the evaluated patch state.

---

## Controlled Experiment Design (V0 vs. V1)

Stage 23 isolates the effect of the Reviewer agent by comparing two candidates:

- **Candidate V0 (Root + Scout + Debugger)**:
  - Root agent + Scout available + Debugger available.
  - Reviewer specialist is **unavailable** (not declared in `agent.yaml`).
  - Root performs all pre-submission evaluation unilaterally.
- **Candidate V1 (Root + Scout + Debugger + Reviewer)**:
  - Root agent + Scout available + Debugger available + Reviewer available.
  - Reviewer is invoked once at the final review point under `REVIEWER_TRIGGER`.

### Controlled Invariants
- Root model: `gemma-4-31b-it-qat-w4a16-ct`.
- Scout model: `gemma-4-31b-it-qat-w4a16-ct`.
- Debugger model: `gemma-4-31b-it-qat-w4a16-ct`.
- Reviewer model: `gemma-4-31b-it-qat-w4a16-ct`.
- Generation settings: `temperature: 0.2`, `top_p: 0.95`, `max_output_tokens: 16384`, `thinking_level: high`, `thinking_budget: 4096`.
- Root tools: Exact 9 competition tools.
- Scout tools: Exact 5 read-only tools.
- Debugger tools: Exact 5 read-only tools.
- Reviewer tools: Exact 5 read-only tools.
- Skills: Exact canonical `test_strategy` and `repo_triage` skills.
- Retrieval, failure taxonomy (E9), no-progress detection (E10), and recovery subsystem (E11) remain identical.

---

## Known Limitations & Cost Trade-Offs
1. **Model Call Overhead**: Invoking the Reviewer consumes an additional model call and token budget. If a patch is already high-quality and well-tested, Reviewer adds inference latency without altering the outcome.
2. **Read-Only Scope**: The Reviewer cannot autonomously apply fixes or run missing tests; it must rely on the Root agent to act on `required_followups`.
3. **Evidence Dependency**: If Root supplies truncated diffs or omitted test outputs, Reviewer returns `INSUFFICIENT_EVIDENCE` and cannot independently verify patch behavior.

---

## Boundary with Stage 24
Stage 23 implements **only** the Reviewer agent. It does **not** implement:
- Multi-agent topologies, coordinator agents, or consensus voting (Stage 24).
- Context compaction or memory pruning (Stage 25).
- Tool-call optimization or rate limiting (Stage 26).
- Submission packaging or LoRA fine-tuning (Stage 27+).
