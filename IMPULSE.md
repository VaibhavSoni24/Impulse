# IMPULSE — Autonomous Software Engineering Agent

**Project name:** IMPULSE  
**Project type:** Autonomous software-engineering agent for repository-level issue resolution  
**Primary target:** Google — The Gemma 4 Developer Agent Competition  
**Status:** Final architecture specification  
**Specification date:** 2026-09-25  
**Primary model:** `gemma-4-31b-it-qat-w4a16-ct`  
**License of primary model:** Apache 2.0  
**Development-cost objective:** $0 in paid APIs/services  

> This document is the frozen definition of what IMPULSE is, what it must contain, how it must behave, what is deliberately excluded, and what constitutes a releasable version. It is a project specification, not a development diary.

---

## 0. Document Control and Authority

### 0.1 Purpose

`IMPULSE.md` is the single source of truth for the intended architecture and behavior of Project A. `PLAN.md` is the single source of truth for the sequence used to construct, validate, improve, and release the implementation.

If implementation details conflict with this specification, the implementation is considered wrong until one of these documents is deliberately revised.

### 0.2 Information hierarchy

When deciding whether a design detail is permitted, use the following order:

1. Current official competition page, rules, starter files, harness README, and supplied evaluator code.
2. Official Google Gemma and Google ADK documentation.
3. Source code of the exact competition harness/runtime version actually downloaded for development.
4. Reproducible local experiments.
5. Secondary articles or community discussions, used only as supporting evidence.

A community example must never override the current competition harness.

### 0.3 Mutable facts

Competition deadlines, quotas, compute availability, accepted submission schema, supported harness versions, and other organizer-controlled details can change. IMPULSE therefore treats these as **release-time facts** that must be re-read before packaging the final competition submission.

The architecture itself is not dependent on the calendar deadline.

---

# 1. Executive Overview

IMPULSE is an autonomous coding agent whose purpose is to transform a software issue into a verified repository patch.

The complete lifecycle is:

```text
Issue
  ↓
Understand
  ↓
Reconnaissance
  ↓
Locate relevant code
  ↓
Build evidence-backed hypothesis
  ↓
Plan minimal change
  ↓
Edit repository
  ↓
Run targeted tests
  ↓
Inspect failures
  ↓
Revise hypothesis / edit again
  ↓
Broaden verification
  ↓
Review final diff
  ↓
Submit patch
```

The competition evaluates the resulting patch, not a conversational answer. For each issue, the submitted patch is applied to the target repository and validation tests are run. IMPULSE's score is the percentage of issues whose patched repository passes validation. The competition currently imposes a 12-hour aggregate time limit for the agent to submit patches for all tasks, inclusive of sandbox setup and excluding patch-validation time. citeturn538596search1

IMPULSE is therefore optimized around one objective:

> **Produce the smallest justified patch that makes the target behavior correct while preserving existing behavior and terminating reliably.**

---

# 2. Problem Definition

## 2.1 Input

An IMPULSE task contains, directly or indirectly through the competition harness:

- a repository snapshot;
- an issue or task description;
- an initial repository state;
- a sandbox in which repository commands can execute;
- tools for reading/writing/editing files;
- code-graph and semantic-retrieval tools derived from the repository;
- a mechanism for extracting the final patch.

The exact task schema is determined by the current competition dataset and harness and must be inspected during bootstrap.

## 2.2 Output

IMPULSE must produce a repository patch. The patch is the actual product of one task execution.

The final patch must be:

- relevant to the issue;
- internally coherent;
- free from accidental debugging artifacts;
- as small as reasonably possible;
- compatible with repository conventions;
- validated by appropriate tests when feasible;
- extractable by the competition harness through `submit_patch()`.

## 2.3 Success condition

There are two different definitions of success.

**Engineering success:** the agent produces a technically correct patch according to local verification.

**Competition success:** the competition's evaluator applies the produced patch to a fresh repository and its validation tests pass.

Competition success is the final authority for leaderboard scoring. citeturn538596search1

---

# 3. Design Goals

IMPULSE must optimize the following properties in this order:

### 3.1 Correctness

The agent must solve the actual issue rather than produce a plausible-looking edit.

### 3.2 Reliability

The agent must recover from wrong hypotheses, failed tests, tool errors, and incomplete first attempts.

### 3.3 Repository understanding

The agent must be able to work in unfamiliar repositories instead of relying on memorized project-specific patterns.

### 3.4 Efficient investigation

The agent must prefer evidence-rich, targeted inspection over indiscriminate repository dumping.

### 3.5 Test-driven verification

The agent must use tests and runtime observations as evidence and must not regard its own reasoning as proof of correctness.

### 3.6 Controlled autonomy

IMPULSE must be free to investigate and modify the repository while being constrained by deterministic sandbox boundaries and explicit resource budgets.

### 3.7 Generality

The architecture must support repositories written in different languages and frameworks without hard-coding the solution to one ecosystem.

### 3.8 Reproducibility

Every experimental version must have a unique configuration, recorded prompts, model identifier, tool set, retrieval policy, and evaluation result.

---

# 4. Explicit Non-Goals

IMPULSE is **not** intended to be:

- a general-purpose chat assistant;
- a web application;
- a mobile application;
- a replacement for an IDE;
- a SaaS coding product;
- a general-purpose autonomous internet agent;
- a multi-model orchestration platform;
- a distributed inference framework;
- a custom LLM training stack from scratch;
- a dashboard-first project;
- an autonomous agent swarm containing many redundant agents.

Any feature that does not measurably improve repository-level issue resolution is secondary and should not be allowed to increase core complexity without evidence.

---

# 5. Competition Grounding

The current competition requires an `submission.zip` whose root contains `agent.yaml`. The archive can contain prompts, configuration includes, sub-agent configurations, skills, and optional PEFT LoRA adapters. The competition compiler converts the submission configuration into an ADK-based agent. citeturn538596search1

The currently documented model is:

```text
gemma-4-31b-it-qat-w4a16-ct
```

Every agent and sub-agent must use that supported base model. Optional LoRA adapters may be supplied, including different adapters for different agents, but IMPULSE does not require a LoRA adapter for its baseline. citeturn538596search1

The documented predefined tools are:

```text
run_command(command: str) -> str
submit_patch() -> str
get_status() -> str
read_file(filepath, start_line=None, end_line=None) -> str
edit_file(filepath, old_string, new_string, allow_multiple=False) -> str
write_file(filepath, content) -> str
get_code_neighbors(node, edge_type=None, max_neighbors=50) -> str
search_similar_code(query, k=10) -> str
get_code_subgraph(nodes) -> str
```

Their current documented semantics are summarized below. citeturn538596search1turn606491search0

| Tool | IMPULSE purpose |
|---|---|
| `run_command` | Execute repository commands inside `/workspace`; primary mechanism for discovery, builds, tests, version control, and runtime reproduction. |
| `read_file` | Read exact file regions with line slicing. |
| `edit_file` | Perform a surgical replacement in an existing non-empty file. |
| `write_file` | Create or overwrite a file. |
| `get_status` | Inspect live budget and patch status. |
| `submit_patch` | Materialize untracked file intents and capture the final repository diff. |
| `search_similar_code` | Retrieve semantically related code-graph nodes from precomputed embeddings. |
| `get_code_neighbors` | Inspect incoming/outgoing dependency or call relationships around a symbol. |
| `get_code_subgraph` | Extract an induced subgraph for selected symbols. |

The exact tool contract used in production is whatever the current harness actually exposes. During implementation, every contract will be checked against the downloaded competition package.

---

# 6. Core Design Philosophy

IMPULSE follows six operating principles.

### Principle 1 — Evidence before modification

The agent should know why it is changing a file before it changes it.

### Principle 2 — Minimal change

The agent should prefer the smallest change that explains and fixes the observed problem.

### Principle 3 — Retrieval before context saturation

The agent should retrieve relevant code rather than flooding the model with unrelated repository contents.

### Principle 4 — Tests are evidence

A passing targeted test increases confidence; it does not automatically prove all behavior is correct.

### Principle 5 — One owner of the workspace

The root engineer owns repository modifications. Read-only specialists provide evidence but do not independently mutate the workspace unless a future experiment demonstrates that this is beneficial and safe.

### Principle 6 — Every optimization must be measured

No prompt, tool-policy, retrieval strategy, agent, skill, or LoRA change is considered an improvement without a controlled comparison.

---

# 7. High-Level Architecture

IMPULSE is intentionally hierarchical and shallow.

```text
                              ┌─────────────────────┐
                              │     IMPULSE ROOT    │
                              │  Autonomous Engineer │
                              └──────────┬──────────┘
                                         │
                       ┌─────────────────┼─────────────────┐
                       │                 │                 │
                       ▼                 ▼                 ▼
                 Scout Agent       Debugger Agent    Reviewer Agent
                  read-only          read-only         read-only
                       │                 │                 │
                       └─────────────────┼─────────────────┘
                                         │
                                         ▼
                               Competition Tool Layer
                                         │
        ┌─────────────┬─────────────┬────┴─────┬─────────────┐
        ▼             ▼             ▼          ▼             ▼
   Filesystem      Shell        Code Graph  Semantic      Status/Patch
                                           Retrieval       Capture
                                         │
                                         ▼
                                   Repository State
```

The specialist agents are advisory. The root agent remains the decision-maker and workspace owner.

---

# 8. Why the Architecture Is Not a Large Agent Swarm

Using the same model repeatedly does not automatically create intelligence. Each additional agent introduces more context, tool calls, coordination, failure surfaces, and opportunities for inconsistent decisions.

IMPULSE therefore starts with a single root agent. Scout, Debugger, and Reviewer are added only after the single-agent baseline is operational and measurable.

The architecture is deliberately compatible with the simplicity of contemporary SWE-agent designs, where a compact iterative control loop can be highly effective, while still exploiting the competition's repository graph and semantic retrieval primitives. A notable example is mini-SWE-agent, which emphasizes a very small agent loop and direct environment interaction. This is an external engineering reference, not a competition requirement. citeturn997755search0

---

# 9. Root Agent — IMPULSE Engineer

## 9.1 Responsibility

The root agent owns the complete task lifecycle:

1. understand the issue;
2. establish repository facts;
3. localize relevant code;
4. form a hypothesis;
5. plan the smallest justified change;
6. modify files;
7. run tests or reproduction commands;
8. diagnose failures;
9. iterate;
10. review the final diff;
11. submit the patch.

## 9.2 Required behavior

The root agent must:

- prefer inspection over guessing;
- prefer targeted commands over enormous command output;
- preserve useful observations in structured task state;
- avoid rereading unchanged content unnecessarily;
- distinguish evidence from assumptions;
- explicitly revise its hypothesis after contradictory evidence;
- stop when the patch is sufficiently validated;
- avoid leaving temporary artifacts in the repository.

## 9.3 Root state

The root agent must conceptually maintain:

```text
Task summary
Repository facts
Current hypothesis
Evidence supporting hypothesis
Relevant files
Relevant symbols
Relevant tests
Plan
Actions already taken
Edits already made
Last test results
Failure classification
Next intended action
No-progress counters
Budget state
Final-review state
```

The exact serialization mechanism is an implementation choice, but the information itself is mandatory.

---

# 10. Scout Agent

## 10.1 Purpose

The Scout is a read-only repository-localization specialist.

Its task is to answer:

> Where is the smallest useful part of this repository that can explain the reported issue?

## 10.2 Inputs

- issue description;
- current repository state;
- optionally an initial candidate symbol/file from the root agent.

## 10.3 Outputs

The Scout should return concise evidence:

```text
Candidate files
Candidate symbols
Relevant tests
Relevant callers/callees
Potential related implementation
Confidence and rationale
Recommended next inspection
```

## 10.4 Scout restrictions

The Scout should not modify source files in the default architecture.

---

# 11. Debugger Agent

## 11.1 Purpose

The Debugger explains failing validation or runtime behavior.

## 11.2 Inputs

- current issue summary;
- current hypothesis;
- current diff summary;
- failing command;
- relevant failure output.

## 11.3 Output

The Debugger should classify the failure and suggest the next evidence-gathering action.

```text
Failure class
Observed evidence
Likely causal chain
Whether current patch is implicated
Alternative hypotheses
Recommended next action
```

It should not replace the root agent as final decision-maker.

---

# 12. Reviewer Agent

## 12.1 Purpose

The Reviewer evaluates whether the final repository state is ready for patch extraction.

## 12.2 Inputs

- issue description;
- final diff;
- test commands and results;
- known constraints.

## 12.3 Review checklist

The Reviewer checks:

- relevance;
- correctness evidence;
- accidental file changes;
- debug artifacts;
- temporary files;
- API compatibility;
- obvious regressions;
- test coverage;
- unnecessary complexity;
- formatting or repository convention violations.

## 12.4 Reviewer output

A structured response:

```text
READY / NOT_READY
Critical problems
Non-critical concerns
Required action, if any
```

The Reviewer does not receive authority to submit the final patch by default.

---

# 13. Tool Architecture

## 13.1 Shell tool: `run_command`

This is the primary general-purpose interaction mechanism.

IMPULSE uses it for:

- directory inspection;
- repository status;
- project metadata discovery;
- text search;
- build commands;
- test commands;
- version inspection;
- runtime reproductions;
- git diff inspection;
- small deterministic scripts;
- repository-specific tooling.

### Shell policy

The root prompt must require:

- commands to be purposeful;
- output to be bounded whenever practical;
- expensive commands to be justified;
- package installation to be avoided unless the environment explicitly requires it and the competition harness permits it;
- external-network assumptions to be avoided.

## 13.2 File tools

`read_file`, `edit_file`, and `write_file` are used when structured file-level operations are more reliable than shell redirection.

### Edit preference

`edit_file` is preferred for small existing-code modifications.

`write_file` is appropriate for:

- new files;
- complete replacement when strongly justified;
- generated minimal artifacts.

Large blind rewrites are discouraged.

## 13.3 Status tool

`get_status()` is consulted when:

- starting a long stage;
- deciding whether to run an expensive command;
- diagnosing why an execution stopped;
- determining whether the patch is ready for submission.

## 13.4 Patch tool

`submit_patch()` is used only after final review.

Because patch extraction includes untracked file intents, temporary reproduction scripts or debugging files left in the repository can unintentionally become part of the patch. The implementation must therefore include explicit workspace cleanup and final-diff review. The current competition documentation states that `submit_patch()` stages untracked file intents and captures the diff. citeturn538596search1

---

# 14. Repository Retrieval Architecture

IMPULSE uses a hybrid retrieval strategy.

```text
Issue semantics
      ↓
Semantic code search
      ↓
Candidate symbols/files
      ↓
Exact file inspection
      ↓
Code neighbors
      ↓
Small subgraph
      ↓
Targeted filesystem search
      ↓
Reasoned localization
```

No single retrieval mechanism is assumed to solve every issue.

---

# 15. Semantic Code Search

The competition exposes `search_similar_code()` over precomputed embeddings.

IMPULSE should use semantic search when issue wording and implementation vocabulary may differ.

Example:

```text
Issue: cache returns stale result after invalidation

Semantic query:
"cache invalidation, result lifetime, eviction, stale lookup"
```

The result list is evidence, not truth. Every candidate must be inspected in repository context.

Default starting values are the tool's documented defaults unless controlled experiments show that different retrieval breadth is superior.

---

# 16. Code-Graph Retrieval

The competition exposes:

- `get_code_neighbors()`;
- `get_code_subgraph()`.

The graph should be treated as a map, not as a replacement for source reading.

## 16.1 Neighbor strategy

When a promising symbol is identified, inspect:

- direct callers;
- direct callees;
- relevant dependency edges;
- nearby tests where present.

## 16.2 Subgraph strategy

Use `get_code_subgraph()` only after candidate nodes have been selected.

Avoid uncontrolled graph expansion.

The goal is:

```text
small relevant graph
```

not:

```text
largest possible graph
```

The competition explicitly provides these graph and embedding tools and encourages research using code graphs and embeddings. citeturn538596search1turn538596search0

---

# 17. Repository Reconnaissance

The agent begins by determining the repository's development conventions.

It should selectively inspect files such as:

```text
README*
pyproject.toml
package.json
pnpm-lock.yaml
package-lock.json
yarn.lock
Cargo.toml
go.mod
pom.xml
build.gradle
settings.gradle
Makefile
justfile
CONTRIBUTING*
CI configuration
existing test directories
```

This is an adaptive checklist, not a mandatory sequence. The agent should stop investigating infrastructure once it has enough information to execute the relevant workflow.

---

# 18. Task Understanding

Before making changes, IMPULSE should internally answer:

```text
What is wrong?
What behavior is expected?
What behavior is observed or implied?
Under what conditions does the issue occur?
What is the likely subsystem?
What evidence would falsify the current hypothesis?
What would constitute a successful fix?
```

The output is a compact task model.

---

# 19. Hypothesis-Driven Debugging

Every substantive code edit should be tied to a hypothesis.

Example:

```text
Hypothesis:
The invalidation operation clears the primary cache index but leaves a secondary lookup structure populated.

Evidence:
- invalidation mutates structure A;
- reads use structure B;
- A and B share the same logical cache key.

Falsifier:
A targeted regression test demonstrating B is updated through the same path.
```

This prevents the agent from entering an edit-test-random-edit cycle.

---

# 20. Code Modification Policy

IMPULSE follows a minimal-patch doctrine.

### 20.1 Preferred

- change the smallest relevant function;
- preserve public interfaces;
- preserve style;
- reuse existing abstractions;
- avoid unrelated cleanup;
- add the smallest necessary test or fixture only when appropriate.

### 20.2 Discouraged

- broad refactors during bug fixing;
- mass formatting changes;
- unnecessary dependency changes;
- speculative optimizations;
- unrelated renaming;
- deleting existing tests merely because they fail;
- weakening assertions to force a green suite.

---

# 21. Testing Architecture

IMPULSE uses progressive validation.

```text
1. Reproduce or target the issue
        ↓
2. Run the narrowest useful test
        ↓
3. Run directly related tests
        ↓
4. Run the broader relevant subsystem suite
        ↓
5. Run full-suite verification when justified
```

The agent should infer testing conventions from repository metadata and existing automation.

Examples include `pytest`, `npm test`, `cargo test`, `go test`, Maven, Gradle, or repository-specific commands. The architecture is language-agnostic.

---

# 22. Test Selection Policy

The agent should prefer tests with high information value.

The selection should answer one or more of:

- Does the reported bug reproduce?
- Does the proposed fix remove the failure?
- Does nearby existing behavior remain correct?
- Did the change introduce a regression?

A full test suite is not automatically required after every change.

---

# 23. Failure Taxonomy

Every significant failure should be classified.

```text
F1  Environment/setup failure
F2  Dependency/tooling failure
F3  Invalid test invocation
F4  Pre-existing unrelated test failure
F5  Patch-induced regression
F6  Incomplete fix
F7  Wrong hypothesis
F8  Newly discovered edge case
F9  Tool execution failure
F10 No-progress loop
F11 Budget exhaustion risk
F12 Unknown / insufficient evidence
```

The classification determines the next action.

---

# 24. Recovery Architecture

## 24.1 Wrong hypothesis

```text
Contradictory evidence
→ invalidate current hypothesis
→ restate observed facts
→ identify new candidate subsystem
→ retrieve new evidence
```

## 24.2 Patch-induced regression

```text
Regression
→ inspect diff
→ identify changed path
→ revert or repair
→ rerun targeted test
```

## 24.3 Repeated failure

If the same failure persists after multiple materially similar attempts, IMPULSE must change investigation strategy rather than repeating the same edit.

## 24.4 Tool failure

Use a bounded retry, then use an alternative mechanism where possible.

Example:

```text
semantic search unavailable
→ exact text search
→ repository tree inspection
→ graph retrieval if candidate symbol exists
```

## 24.5 No-progress detector

A task enters no-progress state when, for example:

- the same test failure repeats without new evidence;
- the same file is modified repeatedly with no improvement;
- the same command is issued repeatedly for no informational gain;
- the hypothesis remains unchanged despite contradictory evidence.

When triggered, the agent must re-localize or reframe the problem.

---

# 25. Context and Memory Architecture

The long context capability of Gemma 4 is useful, but IMPULSE must not interpret a 256K context window as permission to send entire repositories into every model call. Google documents up to 256K context for the 31B and other medium Gemma 4 models, alongside built-in reasoning, function calling, and coding capabilities. citeturn606491search1turn606491search4

IMPULSE maintains a compact working state containing:

```text
Task summary
Repository facts
Candidate locations
Evidence
Current hypothesis
Current plan
Attempt history
Test history
Known failures
Current diff summary
Next action
```

Raw logs should be retained only when necessary and should not automatically be recopied into every subsequent turn.

---

# 26. Task Memory Boundary

Task-specific memory is isolated per issue.

IMPULSE must not allow repository-specific discoveries from one task to become untrusted facts in another task.

Cross-task reusable knowledge is limited to:

- generic testing patterns;
- tool usage rules;
- repository-agnostic troubleshooting procedures;
- stable skill documentation.

---

# 27. Specialist Invocation Policy

Specialists are tools for reducing uncertainty, not mandatory stages.

### Scout is useful when:

- issue localization is ambiguous;
- multiple subsystems appear plausible;
- the root agent needs dependency evidence.

### Debugger is useful when:

- a test fails unexpectedly;
- runtime behavior contradicts the hypothesis;
- the failure log is large or ambiguous.

### Reviewer is useful when:

- a candidate patch exists;
- tests are sufficiently complete;
- the root agent is considering `submit_patch()`.

The root agent should not invoke a specialist when it can resolve the question cheaply and reliably itself.

---

# 28. Skills Architecture

The competition allows ADK Skill directories containing a `SKILL.md` manifest, optional scripts, and optional resources. Skill scripts execute in the competition sandbox and share the repository environment; their execution counts against the central execution budget. citeturn538596search1

IMPULSE will use skills for procedural knowledge, not for hidden intelligence.

Proposed skill set:

```text
repo_triage/
repository_search/
test_strategy/
failure_analysis/
recovery/
patch_review/
```

Additional ecosystem-specific skills may be introduced only when experiments show they improve generalization.

---

# 29. Skill: Repository Triage

Purpose:

- identify project type;
- identify major source/test directories;
- identify build/test tooling;
- establish repository state;
- produce a short repository map.

It should stop early once enough evidence has been gathered.

---

# 30. Skill: Repository Search

Purpose:

- formulate targeted text searches;
- combine exact and semantic searches;
- avoid broad recursive output when a narrower query exists;
- inspect candidate definitions and call sites.

The skill should teach a strategy, not encode a fixed list of filenames.

---

# 31. Skill: Test Strategy

Purpose:

- discover test framework;
- find likely regression test;
- choose the narrowest useful test first;
- escalate test breadth based on evidence;
- interpret exit codes and common failure structures.

---

# 32. Skill: Failure Analysis

Purpose:

- classify test/runtime failures;
- distinguish infrastructure from code failures;
- extract the highest-value evidence from long logs;
- recommend the next investigation step.

---

# 33. Skill: Recovery

Purpose:

- break repeated-failure loops;
- reframe hypotheses;
- fall back from unavailable retrieval mechanisms;
- clean temporary artifacts;
- establish a final recoverable state before submission.

---

# 34. Skill: Patch Review

Purpose:

- inspect final diff;
- identify accidental changes;
- check debugging artifacts;
- verify issue relevance;
- ensure a patch can be cleanly extracted.

---

# 35. Prompt Architecture

Prompts are configuration, not random text.

The root system instruction must define:

1. role;
2. objective;
3. operating rules;
4. repository interaction policy;
5. evidence requirements;
6. editing discipline;
7. testing policy;
8. recovery behavior;
9. budget awareness;
10. final-review requirements;
11. submission behavior.

Prompts must avoid unnecessarily rigid procedural scripts that prevent adaptive reasoning.

---

# 36. Prompt Hierarchy

IMPULSE has three conceptual prompt levels.

### Root system prompt

Defines the autonomous engineer role and non-negotiable policies.

### Specialist prompts

Define each specialist's narrow responsibility and output contract.

### Skill instructions

Provide procedural guidance when the root or specialist explicitly uses the relevant skill.

Prompt content must not conflict with actual tool availability.

---

# 37. Deterministic Guardrails

Gemma decides what to investigate and what edits to attempt, but the surrounding system must enforce deterministic constraints.

Guardrails include:

- sandbox root boundaries;
- path validation;
- tool schemas;
- execution timeouts;
- task-level budgets;
- final diff inspection;
- explicit submission stage;
- no hidden external dependency.

The current competition explicitly disallows path traversal outside the submission root and restricts agents to supported tools or custom subagents defined through the allowed configuration mechanisms. citeturn538596search1

---

# 38. Budget Management

There are several distinct resources:

```text
Model inference time
Agent turns
Tool calls
Shell execution time
Skill execution time
Repository/test runtime
Context capacity
GPU memory during local development
Disk during data/model preparation
```

IMPULSE must maintain a budget-aware strategy.

The competition's documented global execution allowance is 12 hours for submission of all task patches, including sandbox setup and excluding patch validation. The implementation must therefore avoid wasting the budget on repeated repository scans or unbounded tests. citeturn538596search1

---

# 39. Time Allocation Policy

The exact runtime distribution is task-dependent. IMPULSE must not assume every issue deserves the same amount of investigation.

A sensible conceptual allocation is:

```text
Early task:
fast reconnaissance + localization

Middle task:
deep evidence + modification

Late task:
validation + cleanup + review
```

If a task is already well localized, more time should be allocated to validation.

If localization is uncertain, premature coding is prohibited by the preferred strategy.

---

# 40. No-Progress and Termination Policy

IMPULSE must terminate cleanly in one of these states:

```text
SOLVED_AND_REVIEWED
SOLVED_WITH_LIMITED_VALIDATION
UNRESOLVED_BEST_EFFORT
BUDGET_EXHAUSTION
FATAL_TOOL_ENVIRONMENT_FAILURE
```

A task should never remain in an endless self-repair loop.

When the agent cannot establish further evidence cheaply, it must make its best justified patch or stop with the current state according to the evaluator's required behavior.

---

# 41. Model Specification

IMPULSE's competition candidate uses:

```text
gemma-4-31b-it-qat-w4a16-ct
```

Google documents Gemma 4 as having reasoning capability, long context, function calling, coding capability, and native system-prompt support. The 31B variant supports a 256K context window. citeturn606491search1turn606491search4

The Hugging Face checkpoint currently lists a 23.3 GB model file for the QAT W4A16 checkpoint and provides documented Transformers, vLLM, and Docker Model Runner usage. citeturn606491search2turn606491search5

IMPULSE does not depend on the model being served by a specific local runtime during final competition evaluation; the competition harness supplies the runtime. Local inference must match the competition model identity and tool behavior as closely as practical.

---

# 42. Inference Runtime Policy

## 42.1 Competition runtime

The competition harness is the source of truth.

## 42.2 Local development runtime

Supported development options include current-compatible Google/Gemma tooling and open-source runtimes such as Transformers or vLLM. The exact runtime version must be pinned after checking the downloaded competition wheelhouse/harness rather than guessed from generic documentation. The official model page currently documents vLLM serving for the checkpoint. citeturn606491search5

## 42.3 Hardware

The checkpoint itself is approximately 23.3 GB, so a single 16 GB GPU must not be assumed sufficient. Actual memory requirements also depend on runtime, CUDA libraries, KV cache, context length, and parallelism. Hardware fit must be empirically verified.

Kaggle currently documents free notebook environments including a single P100 and T4×2 configurations, with limited availability and 12-hour notebook sessions at the time of the current documentation. These are development resources, not a guarantee that a specific competition evaluator uses the same hardware. citeturn689163search0

---

# 43. Development-Cost Policy

IMPULSE is designed to be developable without paid services.

Core planned software components are open-source or freely accessible:

```text
Python
Git
Docker
Google ADK / competition-provided config/runtime components
Gemma open weights
Transformers
vLLM
pytest and repository-native testing tools
Kaggle free notebook resources where available
```

The plan assumes zero paid API calls.

Internet access, package availability, and free GPU availability can change. No component is considered mandatory merely because it is free today; the project must remain runnable on the actual environment available.

---

# 44. Development Repository Structure

The complete development repository is broader than the competition ZIP.

```text
IMPULSE/
├── README.md
├── IMPULSE.md
├── PLAN.md
├── LICENSE
├── pyproject.toml
├── uv.lock                         # only if the chosen package manager generates it
│
├── agent/
│   ├── agent.yaml
│   ├── prompts/
│   │   ├── root.md
│   │   ├── scout.md
│   │   ├── debugger.md
│   │   └── reviewer.md
│   ├── sub_agents/
│   │   ├── scout.yaml
│   │   ├── debugger.yaml
│   │   └── reviewer.yaml
│   ├── skills/
│   │   ├── repo_triage/
│   │   ├── repository_search/
│   │   ├── test_strategy/
│   │   ├── failure_analysis/
│   │   ├── recovery/
│   │   └── patch_review/
│   └── adapters/
│       └── <validated adapters only>
│
├── local/
│   ├── runner/
│   ├── sandbox/
│   ├── evaluator/
│   ├── dataset_tools/
│   └── diagnostics/
│
├── benchmark/
│   ├── tasks/
│   ├── manifests/
│   ├── splits/
│   └── results/
│
├── experiments/
│   ├── baseline/
│   ├── retrieval/
│   ├── debugging/
│   ├── specialists/
│   ├── context/
│   ├── prompts/
│   └── lora/
│
├── scripts/
│   ├── bootstrap.py
│   ├── inspect_competition.py
│   ├── run_task.py
│   ├── evaluate.py
│   ├── compare_runs.py
│   ├── package_submission.py
│   └── validate_submission.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── packaging/
│
└── docs/
    ├── decisions/
    ├── experiments/
    ├── traces/
    └── release/
```

The exact implementation may merge files, but conceptual responsibilities must remain identifiable.

---

# 45. Local Evaluation Harness

The local evaluator is not the competition itself. Its purpose is to answer whether a candidate version improved under controlled conditions.

It must:

1. identify a task;
2. prepare a clean repository snapshot;
3. run the candidate agent;
4. capture tool trajectory;
5. capture final patch;
6. apply the patch to a fresh copy;
7. run the designated verification tests available in the local development data;
8. record pass/fail and diagnostics;
9. store the exact candidate configuration.

The competition's own validation remains authoritative for final scoring.

---

# 46. Local Benchmark Strategy

IMPULSE needs a held-out evaluation set.

It must be partitioned conceptually as:

```text
DEV
  used for prompt/tool/retrieval iteration

VALIDATION
  used for candidate selection

HELD-OUT
  used only for final confirmation
```

No candidate should be selected solely because it performs better on the same tasks repeatedly used during design.

Where the competition dataset permits it, repository-level and task-level leakage must be avoided.

---

# 47. Evaluation Metrics

The primary metric is issue pass rate.

Secondary engineering metrics:

```text
Issue pass rate
Patch success rate
Targeted-test pass rate
Regression rate
Tool calls / task
Model turns / task
Elapsed agent time
Commands / task
Files read / task
Files changed / task
Diff size
Specialist invocations
No-progress events
Termination reason
```

Efficiency metrics are diagnostics. A faster agent is not automatically better if its pass rate decreases.

---

# 48. Experimental Methodology

Every experiment must change one major factor or one tightly coupled factor group.

Example sequence:

```text
E0 Baseline
E1 Prompt revision
E2 Retrieval policy
E3 Graph augmentation
E4 Debugger specialist
E5 Reviewer specialist
E6 Context compaction
E7 Skill improvements
E8 Combined candidate
E9 LoRA
```

A candidate is promoted only when:

- its pass rate improves on validation;
- it does not introduce unacceptable regressions on a held-out slice;
- runtime remains within practical limits;
- behavior remains reproducible.

---

# 49. Baseline Definition

The first baseline is intentionally simple.

```text
One root agent
Basic repository tools
No specialists
No LoRA
Minimal system prompt
Basic testing loop
Final diff review by root agent
```

The baseline is not expected to be excellent. It is required because every later result needs a reference point.

---

# 50. Retrieval Optimization Program

Retrieval experiments will evaluate:

1. filesystem/text search only;
2. semantic search augmentation;
3. semantic search + graph neighbors;
4. semantic search + selective graph subgraphs;
5. dynamic retrieval depth;
6. retrieval driven by issue subtype.

The winning policy must balance localization quality and context/tool cost.

---

# 51. Multi-Agent Optimization Program

Specialist variants must be evaluated against the same tasks and budget.

Candidate structures include:

```text
A. Root only
B. Root + Scout
C. Root + Debugger
D. Root + Reviewer
E. Root + Scout + Debugger
F. Root + Scout + Debugger + Reviewer
```

The full architecture is not accepted merely because it feels more sophisticated.

---

# 52. Context Optimization Program

IMPULSE will experiment with:

- compact task state;
- repeated-content suppression;
- file-window targeting;
- test-log summarization;
- repository map persistence;
- evidence ranking;
- adaptive context expansion.

Success requires equal or better task-solving performance with lower unnecessary context/tool cost.

---

# 53. LoRA / Post-Training Program

LoRA is optional and is a later optimization layer.

The order is:

```text
Strong inference-time baseline
↓
Failure analysis
↓
Trajectory collection
↓
Training-data construction
↓
LoRA candidate
↓
Controlled validation
↓
Ablation
↓
Promote only if beneficial
```

Training targets may include:

- tool selection;
- repository localization;
- test selection;
- code-editing behavior;
- failure recovery;
- patch-review behavior.

The base model remains the competition-supported Gemma 4 model. The current rules permit one or more `.safetensors` LoRA adapters, including different adapters for different agents. citeturn538596search1

---

# 54. Why LoRA Is Not Part of v1

Without a strong baseline, LoRA makes causal diagnosis harder.

A poor agent can have a well-trained adapter and still fail because:

- it retrieves the wrong file;
- it does not run the right test;
- it destroys the diff;
- it loops on failures;
- the prompt/tool contract is wrong.

IMPULSE therefore treats LoRA as an optimization, not as the foundation.

---

# 55. Prompt and Tool Contract Integrity

The prompt must never tell the model to call a tool that is not actually exposed.

This matters especially with evolving ADK SkillToolset behavior. Recent ADK issue reports have documented cases where skill tool instructions could advertise tools that were filtered out, leading to unexpected tool-call failures. This is an upstream implementation detail, not a reason to avoid skills, but it reinforces the IMPULSE requirement to validate the exact runtime and tool declarations before every release. citeturn189205search2turn189205search4

IMPULSE release checks therefore include:

```text
Prompt tool names == exposed tools
Skill tool names == available skill tools
Sub-agent names == loaded sub-agents
Declared model == permitted model
Referenced files exist
No unsupported configuration keys
```

---

# 56. Security and Sandbox Model

IMPULSE assumes the repository is untrusted program input.

The system must therefore:

- respect sandbox boundaries;
- avoid assuming arbitrary commands are harmless;
- avoid writing outside `/workspace` during competition execution;
- treat repository scripts as potentially arbitrary code;
- avoid network-dependent operation unless the official harness explicitly permits it;
- keep secrets outside the agent package;
- never place private credentials in prompts, skills, or adapters.

The competition itself explicitly restricts path traversal outside the submission root and executes skill scripts inside the persistent sandbox. citeturn538596search1

---

# 57. External Dependency Policy

Final competition IMPULSE must not depend on:

- OpenAI APIs;
- Anthropic APIs;
- Gemini APIs outside the competition harness;
- proprietary coding-agent APIs;
- paid vector databases;
- paid observability services;
- online package downloads at task runtime;
- external LLMs.

The competition must be able to reconstruct the agent from the submission archive and its own environment.

Local development may use additional software for diagnostics, but no candidate can be considered competition-ready unless its final archive stands alone under the competition's supported execution model.

---

# 58. Submission Archive Definition

The final competition artifact is:

```text
submission.zip
```

Current competition documentation specifies a root `agent.yaml` and gives the following supported conceptual structure: citeturn538596search1

```text
submission.zip
├── agent.yaml                         REQUIRED
├── configs/                           OPTIONAL
│   └── sampling.yaml
├── prompts/                           OPTIONAL
│   ├── system.md
│   └── ...
├── sub_agents/                        OPTIONAL
│   └── *.yaml
├── adapters/                          OPTIONAL
│   └── <adapter_name>/
│       ├── adapter_config.json
│       └── adapter_model.safetensors
└── skills/                            OPTIONAL
    └── <skill_name>/
        ├── SKILL.md
        ├── scripts/
        └── resources/
```

Only files actually supported by the current competition harness will be included.

No development data, local benchmark results, model cache, `.git/` directory, credentials, or temporary artifacts belong in the competition ZIP.

---

# 59. `agent.yaml` Requirements

The final `agent.yaml` must:

- be located at the archive root;
- use the competition-supported Agent Config syntax;
- reference the supported Gemma 4 model;
- reference only available tools/sub-agents/skills;
- use valid relative include paths;
- avoid path traversal;
- remain within all current competition restrictions.

The general Google ADK Agent Config system supports YAML-defined agents, tools, and sub-agents. The competition uses a restricted compiler, so generic ADK examples must not be copied blindly. citeturn189205search0turn538596search1

---

# 60. Competition Tool Set

The final baseline should expose only the tools that are demonstrably needed.

Minimum expected root set:

```text
run_command
read_file
edit_file
write_file
get_status
submit_patch
```

Graph/retrieval tools are added in the graph-aware candidate.

Specialist agents are added only in candidates that pass controlled evaluation.

---

# 61. Final Review Checklist

Before `submit_patch()`:

```text
[ ] Issue understood
[ ] Root cause supported by evidence
[ ] Relevant files identified
[ ] Patch is minimal
[ ] No unrelated changes
[ ] Temporary files removed
[ ] Targeted test passed or best available evidence recorded
[ ] Related tests considered
[ ] Regression risk considered
[ ] Final diff inspected
[ ] No debug prints / logs left behind
[ ] No credentials / secrets
[ ] Workspace is in expected state
[ ] Budget permits final submission
```

---

# 62. Release Candidate Requirements

A candidate may be called `RC` only when:

1. it loads under the exact competition-supported configuration parser;
2. the root model identifier is correct;
3. all referenced files exist;
4. all tools are supported;
5. at least one end-to-end task completes from repository initialization through patch extraction;
6. local evaluation artifacts can be reproduced;
7. packaging is deterministic;
8. no unsupported external dependency is required;
9. held-out validation is acceptable relative to the previous candidate;
10. the final ZIP passes structural checks.

---

# 63. Best-Version Selection Policy

The best IMPULSE version is not necessarily the version with the largest number of features.

Selection hierarchy:

1. higher held-out issue pass rate;
2. no unacceptable regression on development tasks;
3. lower or equal unnecessary tool/runtime cost;
4. more stable termination;
5. simpler implementation when performance is otherwise equivalent.

Complexity is justified by measured benefit.

---

# 64. Competition Submission Process

The final process is:

```text
Freeze candidate
  ↓
Run packaging validator
  ↓
Build submission.zip
  ↓
Inspect archive contents
  ↓
Hash archive
  ↓
Run final local smoke test
  ↓
Verify current Kaggle rules and deadlines
  ↓
Join/accept competition requirements as needed
  ↓
Submit current candidate
  ↓
Record submission identifier/status
  ↓
Do not silently modify the submitted candidate
```

Kaggle's public API supports competition downloads after accepting competition rules, using commands such as `kaggle competitions download -c <competition>`. citeturn995049search0

---

# 65. Final Competition Facts as Currently Documented

As of this specification date:

- Competition start: 2026-09-23.
- Main competition final submission deadline: 2026-12-02 at 11:59 PM UTC unless organizers revise the schedule.
- Entry deadline: 2026-11-25.
- Team merger deadline: 2026-11-25.
- Optional Paper Track deadline: 2026-11-12 at 11:59 PM UTC.
- Main competition prize pool: $65,000.
- Optional Paper Track prize pool: $35,000.
- Main competition total prize pool across both tracks: $100,000.
- Current supported model: `gemma-4-31b-it-qat-w4a16-ct`.
- Agent evaluation: patch-based PASS/FAIL validation.
- Global agent submission budget: 12 hours, inclusive of sandbox setup and excluding patch-validation time.

These facts are current web-verified facts, not timeless project requirements. Re-check them immediately before the actual final submission. citeturn538596search1turn538596search0

---

# 66. Project Deliverables

The completed Project A must produce the following.

## 66.1 Specification deliverables

```text
IMPULSE.md
PLAN.md
README.md
```

## 66.2 Agent deliverables

```text
agent/agent.yaml
agent/prompts/*
agent/sub_agents/*
agent/skills/*
agent/adapters/*    only if an adapter is selected
```

## 66.3 Development tooling

```text
local runner
local evaluator
benchmark utilities
experiment recorder
submission packager
submission validator
```

## 66.4 Quality artifacts

```text
baseline results
experiment manifests
comparison reports
held-out validation results
final release report
```

## 66.5 Competition deliverable

```text
submission.zip
```

---

# 67. Deliverables for the Competition ZIP

The minimum final archive is the smallest valid package containing the selected IMPULSE configuration.

A mature candidate may contain:

```text
submission.zip
├── agent.yaml
├── configs/
├── prompts/
├── sub_agents/
├── adapters/
└── skills/
```

Optional directories are omitted when unused.

The ZIP must not contain:

```text
.git/
__pycache__/
.venv/
local benchmark data
raw competition dataset
credentials
API keys
model cache
training checkpoints unrelated to the selected adapter
private logs
OS-specific junk files
```

---

# 68. Reproducibility Deliverables

For every release candidate, preserve outside the competition ZIP:

```text
release_manifest.json
agent_config snapshot
prompt versions
model identifier
adapter hash, if any
software versions
experiment ID
benchmark split
result table
submission.zip SHA-256
submission timestamp
```

---

# 69. Project B Handoff Contract

Project A ends when the competition-ready IMPULSE agent is frozen.

Project B may use the evidence generated by Project A, but must not retroactively rewrite Project A's historical experiment results.

Useful handoff artifacts:

```text
final IMPULSE configuration
best/worst task traces
failure taxonomy statistics
retrieval ablations
specialist ablations
prompt ablations
LoRA results
performance by task/repository type
known failure clusters
```

The likely research direction is to convert one or more of these measured findings into a general method, dataset, tool, or empirical study appropriate for the separate Paper Track. The Paper Track currently accepts original unpublished research and has a 3,000-word maximum. citeturn538596search0

---

# 70. Final Acceptance Criteria

Project A is considered complete only when every statement below is true.

### Functional

- IMPULSE can receive a real repository issue.
- IMPULSE can explore the repository.
- IMPULSE can use semantic/graph retrieval in graph-aware versions.
- IMPULSE can modify code.
- IMPULSE can execute tests.
- IMPULSE can diagnose failures.
- IMPULSE can iterate.
- IMPULSE can review its diff.
- IMPULSE can extract a patch.

### Reliability

- repeated failures do not create infinite loops;
- tool errors are recoverable where possible;
- unrelated failures are distinguished from patch failures;
- temporary artifacts are cleaned;
- the final diff is explicitly inspected.

### Reproducibility

- every candidate has a recorded configuration;
- experiments can be rerun;
- package contents are deterministic;
- final submission hash is recorded.

### Competition compatibility

- `agent.yaml` is at the ZIP root;
- only supported model(s) are declared;
- all tools are permitted;
- referenced files resolve;
- sandbox constraints are respected;
- no external paid service is necessary;
- the package passes the current competition harness's structural validation.

### Performance

- the final candidate beats or matches the baseline on held-out validation;
- each major architectural addition has evidence of benefit or has been removed;
- the final candidate is not maintained merely because it is more sophisticated.

---

# 71. Final System Definition

The frozen conceptual definition of IMPULSE is:

```text
IMPULSE
│
├── Model
│   └── Gemma 4 31B QAT W4A16
│
├── Root Engineer
│   ├── understand issue
│   ├── inspect repository
│   ├── localize code
│   ├── form hypothesis
│   ├── edit
│   ├── test
│   ├── debug
│   ├── iterate
│   ├── review
│   └── submit
│
├── Optional Specialists
│   ├── Scout
│   ├── Debugger
│   └── Reviewer
│
├── Repository Intelligence
│   ├── filesystem/shell
│   ├── semantic code search
│   ├── dependency/call graph
│   └── induced subgraph retrieval
│
├── Reliability
│   ├── hypothesis tracking
│   ├── progressive testing
│   ├── failure taxonomy
│   ├── no-progress detection
│   ├── recovery
│   └── final diff review
│
├── Optimization
│   ├── prompts
│   ├── retrieval policy
│   ├── skill procedures
│   ├── specialist topology
│   ├── context policy
│   └── optional LoRA
│
└── Final Artifact
    └── submission.zip
```

This is the architectural contract for Project A.

---

# 72. Research Basis and Primary Sources

1. Kaggle — Google: The Gemma 4 Developer Agent Competition  
   https://www.kaggle.com/competitions/gemma-4-developer-agent

2. Kaggle — Google: The Gemma 4 Developer Agent Paper Track  
   https://www.kaggle.com/competitions/gemma-4-developer-agent-paper

3. Google AI for Developers — Gemma 4 model card  
   https://ai.google.dev/gemma/docs/core/model_card_4

4. Google AI for Developers — Gemma 4 overview  
   https://ai.google.dev/gemma/docs/core

5. Hugging Face — `google/gemma-4-31B-it-qat-w4a16-ct`  
   https://huggingface.co/google/gemma-4-31B-it-qat-w4a16-ct

6. Google ADK documentation — Agent Config  
   https://github.com/google/adk-docs/blob/main/docs/agents/config.md

7. Kaggle — Getting Started / Notebooks  
   https://www.kaggle.com/docs/notebooks

8. Kaggle — Public API guidance  
   https://www.kaggle.com/getting-started/524433

9. SWE-agent / mini-SWE-agent reference implementation  
   https://github.com/SWE-agent/mini-swe-agent

10. Google ADK SkillToolset source  
    https://github.com/google/adk-python/blob/main/src/google/adk/tools/skill_toolset.py

---

# 73. Specification Status

**IMPULSE architecture: FINALIZED.**

The calendar deadline is not an architectural constraint.  
The competition harness and rules are release-time constraints.  
The implementation plan in `PLAN.md` is the authoritative construction sequence.

Any future change to the system must be recorded as an explicit architecture revision rather than being silently introduced.
