# IMPULSE — Complete Development and Execution Plan

**Project:** IMPULSE  
**Purpose:** Build, test, optimize, package, and submit an autonomous software-engineering agent for the Google Gemma 4 Developer Agent Competition.  
**Status:** Final execution plan  
**Plan date:** 2026-09-25

> `IMPULSE.md` defines what the project is. This file defines how to create it from zero, establish a trustworthy baseline, iterate scientifically, and finish with a validated competition submission.

---

# 0. Operating Rules for the Entire Build

Before doing any implementation work, lock the following rules.

1. Do not optimize by intuition alone. Measure.
2. Do not change multiple major dimensions at once unless the experiment is explicitly designed as a combined ablation.
3. Never use a final leaderboard score as proof that a change worked for a causal reason.
4. Keep the development repository separate from the final competition archive.
5. Never store credentials in the repository or submission ZIP.
6. Never assume that a generic ADK example is valid for the competition harness.
7. Treat the downloaded competition dataset, harness README, and current rules as the immediate source of truth.
8. Keep a clean baseline that can always be restored.
9. Keep held-out tasks untouched during routine optimization.
10. Do not add LoRA until the inference-time system is already strong enough to measure.
11. Every release candidate receives a unique version identifier and reproducibility manifest.
12. Before final submission, re-check all current competition rules, schema, deadlines, model restrictions, and submission instructions.

---

# 1. Final Build Outcome

At the end, there must be two separate artifacts:

### Development system

A complete Git repository containing:

- source code;
- prompts;
- agent configuration;
- sub-agents;
- skills;
- local evaluator;
- benchmarks;
- experiments;
- diagnostics;
- packaging scripts;
- documentation;
- results.

### Competition artifact

A clean:

```text
submission.zip
```

with `agent.yaml` at its root and only the files needed by the competition to reconstruct the selected IMPULSE agent.

---

# 2. Stage 0 — Read the Current Competition Source of Truth

Do this before creating the first configuration file.

## Step 0.1 — Open the competition

Open:

`https://www.kaggle.com/competitions/gemma-4-developer-agent`

Verify that the account has joined/accepted the competition requirements where required.

The Kaggle API documentation notes that competition data access requires accepting the competition rules. citeturn995049search0

## Step 0.2 — Record current facts

Create:

```text
local/competition_facts.json
```

Record:

```text
competition slug
start date
entry deadline
team merger deadline
final submission deadline
supported model
submission format
root config filename
submission budget
available predefined tools
skill constraints
adapter format
current harness/version information
```

Do not hard-code values that are not visible in the current downloaded competition source.

## Step 0.3 — Download the competition data

After joining and authenticating:

```bash
mkdir -p data/raw
kaggle competitions download gemma-4-developer-agent -p data/raw
```

The Kaggle CLI supports competition downloads through `kaggle competitions download -c <competition>`. citeturn995049search0

Unpack into a controlled directory, preserving the original archive.

```bash
mkdir -p data/competition
unzip -q data/raw/*.zip -d data/competition
```

Do not delete the original archive.

## Step 0.4 — Inspect the dataset tree

Identify:

```text
tasks.jsonl or equivalent task manifest
repository snapshots
code graphs
embeddings
starter files
harness README
Docker files
wheelhouse/evaluation packages
sample submission files
```

Do not infer names from articles or examples if the downloaded directory uses different names.

## Step 0.5 — Read `HARNESS_README.md`

This file is mandatory reading before the first serious implementation.

Extract:

- exact submission layout;
- exact evaluator flow;
- exact local evaluation method;
- task format;
- model loading behavior;
- agent config restrictions;
- environment boundaries;
- timing rules;
- test patch behavior;
- prohibited configuration fields.

---

# 3. Stage 1 — Establish the Development Environment

## Step 1.1 — OS

Prefer Linux for the full local evaluator because Docker, CUDA, vLLM, and repository build environments are easier to reproduce there.

Windows may be used for documentation/editing, but full local evaluation should run in a Linux environment such as a Linux machine, WSL2, or a cloud/Kaggle Linux runtime where supported.

## Step 1.2 — Python

Do not guess the required Python version.

Read the current harness README and/or downloaded package metadata and create an environment using the version required by the exact harness version.

## Step 1.3 — Git

Initialize:

```bash
git init
```

Set a local identity if necessary:

```bash
git config user.name "IMPULSE Developer"
git config user.email "local@example.invalid"
```

Create the initial commit only after the project skeleton exists.

## Step 1.4 — Docker

Verify:

```bash
docker --version
docker info
```

If the competition package provides a Dockerfile for its repository sandbox, use that exact file rather than constructing a substitute before understanding it.

## Step 1.5 — GPU discovery

Check:

```bash
nvidia-smi
```

Record:

```text
GPU model
GPU count
VRAM per GPU
CUDA version
driver version
```

If no NVIDIA GPU exists locally, continue with architecture/configuration work and use Kaggle or another free environment for model execution.

Kaggle currently documents free P100 and T4×2 notebook configurations and limited free GPU availability. These are useful development resources but are not the competition's guaranteed evaluator hardware. citeturn689163search0

---

# 4. Stage 2 — Create the Project Skeleton

Create:

```text
IMPULSE/
├── IMPULSE.md
├── PLAN.md
├── README.md
├── LICENSE
├── pyproject.toml
├── agent/
├── local/
├── benchmark/
├── experiments/
├── scripts/
├── tests/
└── docs/
```

Create all empty directories required by the architecture.

Immediately commit:

```bash
git add .
git commit -m "chore: initialize IMPULSE project"
```

This commit becomes the restoration point for all early development.

---

# 5. Stage 3 — Reproduce the Competition Harness Before Building Intelligence

The goal of this stage is not to solve tasks. The goal is to prove that the machine can load the evaluator.

## Step 5.1 — Identify the exact evaluation packages

From the competition download, locate all supplied wheels/packages.

Record their exact names and versions.

Do not install an arbitrary latest version of Google ADK, vLLM, or other dependencies and assume compatibility.

## Step 5.2 — Build the host environment

Install only the packages required by the actual harness documentation and package metadata.

## Step 5.3 — Verify configuration parsing

Create the smallest possible agent configuration that uses the required model and one or two simple tools.

Run the competition or supplied validator if available.

The goal is:

```text
config loads
model identifier accepted
root agent builds
no schema errors
```

## Step 5.4 — Inspect the evaluator pipeline

Determine exactly where the following happen:

```text
agent initialization
repository snapshot initialization
sandbox start
agent invocation
patch extraction
patch application
validation/test execution
score/result recording
```

Write the observed sequence to:

```text
docs/decisions/evaluator_flow.md
```

---

# 6. Stage 4 — Build a Minimal Baseline Agent

This is the first real IMPULSE candidate: `IMPULSE-E0`.

## Step 6.1 — Root config

Create:

```text
agent/agent.yaml
```

Use the exact current Agent Config syntax accepted by the competition harness.

The root model must be:

```text
gemma-4-31b-it-qat-w4a16-ct
```

The current competition explicitly requires this model for every agent and sub-agent. citeturn538596search1

## Step 6.2 — Root prompt

Create:

```text
agent/prompts/root.md
```

Version 0 prompt requirements:

- identify the issue;
- inspect repository state;
- search before editing;
- make minimal changes;
- run a targeted test;
- iterate on failures;
- inspect final diff;
- submit only after review.

Do not add clever retrieval or multi-agent logic yet.

## Step 6.3 — Tools

Expose the minimum competition tools:

```text
run_command
read_file
edit_file
write_file
get_status
submit_patch
```

The current competition documents all six of these tools. citeturn538596search1

## Step 6.4 — Baseline behavior

Expected loop:

```text
issue
→ inspect
→ search
→ inspect candidate
→ edit
→ test
→ fix if necessary
→ inspect diff
→ submit
```

## Step 6.5 — Save baseline

Commit:

```bash
git add agent
git commit -m "feat: add IMPULSE E0 baseline agent"
```

Tag if desired:

```bash
git tag E0-baseline
```

---

# 7. Stage 5 — Build the Local Task Runner

Create:

```text
local/runner/
```

The runner must accept:

```text
task ID
candidate version
optional timeout/budget
output directory
```

It must create a unique run directory:

```text
runs/YYYYMMDD-HHMMSS-<candidate>-<task>/
```

Record:

```text
configuration
prompt version
model ID
task ID
start time
end time
tool events
stdout/stderr where available
final patch
test results
termination reason
```

---

# 8. Stage 6 — Create the First Smoke-Test Set

Do not start with the entire task universe.

Select a small diverse set containing:

- one easy localization bug;
- one multi-file task;
- one test-driven bug;
- one task with a misleading surface symptom;
- one task where graph retrieval could plausibly help later.

The task IDs must be taken from the actual competition dataset.

Create:

```text
benchmark/tasks/smoke.jsonl
```

The smoke set is only for plumbing and regression checks.

---

# 9. Stage 7 — Verify Patch Extraction

For a completed smoke task:

1. inspect workspace state;
2. create a small deliberate change;
3. call `submit_patch()`;
4. verify untracked file behavior;
5. inspect the resulting patch;
6. ensure temporary files are captured only when intended.

The current competition documentation says `submit_patch()` stages untracked-file intents and captures the diff, so accidental debug files can become part of the patch. citeturn538596search1

Create an explicit test:

```text
tests/packaging/test_patch_capture.py
```

---

# 10. Stage 8 — Baseline Evaluation

Run E0 against the smoke set.

Then run it against a development benchmark of meaningful size.

Record:

```text
pass rate
fail rate
avg tool calls
avg turns
avg time
files read
files changed
diff size
failure classes
```

Create:

```text
experiments/baseline/E0/
├── manifest.json
├── results.jsonl
└── report.md
```

Do not modify E0 after this point. Any new prompt is E1+.

---

# 11. Stage 9 — Build the Evaluation Database

Create an experiment store.

A simple SQLite database is sufficient.

Suggested tables:

```text
runs
run_events
tasks
candidates
metrics
failures
submissions
```

Minimum fields for each run:

```text
run_id
candidate_id
task_id
model_id
adapter_id
success
termination_reason
elapsed_seconds
tool_calls
turns
files_read
files_changed
diff_lines
failure_class
```

Avoid adding a sophisticated database service. SQLite is adequate.

---

# 12. Stage 10 — Prompt Engineering Loop

Create `E1` by changing only the root prompt.

## Experiment procedure

1. Freeze E0.
2. Identify a specific failure pattern from E0.
3. Add one targeted prompt change.
4. Run smoke tests.
5. Run development benchmark.
6. Compare to E0.
7. Keep the change only if it survives validation.
8. Document why.

Example target:

```text
Observed failure:
agent edited before establishing expected behavior.

Prompt change:
require an explicit evidence-backed hypothesis before non-trivial edits.
```

Do not simply make the prompt longer.

---

# 13. Stage 11 — Implement Structured Task State

Once the root agent's baseline behavior is understood, add a structured state representation.

Possible implementation:

```text
TaskState
├── summary
├── repository_facts
├── candidates
├── hypothesis
├── evidence
├── plan
├── edits
├── tests
├── failures
├── no_progress_count
└── final_review
```

The model does not need to see every internal field on every turn.

The state is primarily for maintaining continuity and preventing repeated exploration.

Run a controlled experiment:

```text
E2 = E1 + structured task state
```

---

# 14. Stage 12 — Add Semantic Retrieval

Now create the first graph-aware candidate.

Expose:

```text
search_similar_code
```

The current competition describes this tool as searching top-k graph nodes by embedding similarity. citeturn538596search1

## Retrieval policy v1

Use semantic search when:

- exact issue terms are unlikely to match implementation names;
- the repository is large;
- multiple candidate subsystems exist;
- normal text search returns weak candidates.

## Retrieval policy v1 rules

- do not call semantic search blindly on every turn;
- keep initial `k` small;
- inspect returned candidates before expanding;
- fall back to text search when semantic results are weak.

Record all retrieval calls for later analysis.

---

# 15. Stage 13 — Add Graph Neighbors

Add:

```text
get_code_neighbors
```

The current competition describes it as retrieving incoming and outgoing neighbors from the repository call/dependency graph. citeturn538596search1

## Policy

After a promising symbol is found:

```text
inspect symbol
→ get neighbors
→ select useful relations
→ inspect source
```

Do not expand every symbol automatically.

---

# 16. Stage 14 — Add Selective Subgraph Retrieval

Add:

```text
get_code_subgraph
```

The tool should be used only after selecting a small set of relevant symbols.

Experiment with:

```text
k = 2
k = 4
k = 8
```

or equivalent candidate-set sizes determined by actual tool behavior.

Measure:

```text
pass rate
context growth
tool count
runtime
```

Choose the smallest retrieval breadth that preserves or improves task-solving performance.

---

# 17. Stage 15 — Build the Hybrid Localization Policy

The retrieval controller should become:

```text
Issue
 ↓
Cheap exact search / repository reconnaissance
 ↓
If ambiguous → semantic search
 ↓
If symbol found → graph neighbors
 ↓
If multiple related symbols → subgraph
 ↓
Read exact source regions
```

The system should not call all retrieval tools automatically.

This is an information-gain strategy.

---

# 18. Stage 16 — Build the Testing Skill

Create:

```text
agent/skills/test_strategy/SKILL.md
```

The skill should encode:

1. discover test framework;
2. identify relevant test area;
3. reproduce narrowly;
4. run targeted test;
5. broaden intelligently;
6. interpret result;
7. avoid running huge suites unnecessarily.

Do not encode specific repository answers.

---

# 19. Stage 17 — Build the Repository Triage Skill

Create:

```text
agent/skills/repo_triage/SKILL.md
```

It should teach the agent how to rapidly establish:

```text
language
framework
package manager
entry points
tests
CI/build convention
repository layout
```

Measure whether a skill reduces redundant commands.

---

# 20. Stage 18 — Build Failure Classification

Implement deterministic or prompt-guided failure categories:

```text
environment
command
pre-existing failure
regression
incomplete fix
wrong hypothesis
new edge case
unknown
```

The root agent must explicitly choose a failure class whenever a meaningful test fails.

Then test whether explicit classification reduces repeated bad edits.

---

# 21. Stage 19 — Implement the No-Progress Detector

Maintain counters for patterns such as:

```text
same command repeated
same error repeated
same file repeatedly edited
same hypothesis repeated
```

When the threshold is reached, trigger a recovery instruction:

```text
STOP REPEATING.
Restate the facts.
Identify what the previous hypothesis failed to explain.
Choose a different investigation path.
```

The exact threshold should be experimentally chosen, not assumed.

---

# 22. Stage 20 — Implement Recovery Paths

At minimum:

### Recovery A — Search fallback

```text
semantic → exact search → tree inspection → graph
```

### Recovery B — Test failure

```text
classify → inspect diff → inspect stack/call path → revise hypothesis
```

### Recovery C — Bad edit

```text
inspect diff → revert/repair → rerun targeted test
```

### Recovery D — Tool failure

```text
bounded retry → alternate tool → continue or terminate
```

### Recovery E — Budget pressure

```text
stop low-value exploration → targeted validation → final review
```

---

# 23. Stage 21 — Create the Scout Agent

Only now create the first specialist.

Create:

```text
agent/sub_agents/scout.yaml
agent/prompts/scout.md
```

The Scout must be read-only.

Run two candidates:

```text
E_S1 = root + scout available
E_S2 = root + scout mandatory under selected uncertainty condition
```

The experiment must answer:

> Does Scout-generated evidence improve successful localization enough to justify its extra model calls?

If not, remove or restrict Scout invocation.

---

# 24. Stage 22 — Create the Debugger Agent

Create:

```text
agent/sub_agents/debugger.yaml
agent/prompts/debugger.md
```

Invoke it primarily after meaningful test failures.

Do not invoke it after every command.

Compare:

```text
root-only debugging
vs.
root + Debugger on difficult failures
```

---

# 25. Stage 23 — Create the Reviewer Agent

Create:

```text
agent/sub_agents/reviewer.yaml
agent/prompts/reviewer.md
```

Reviewer gets:

```text
issue
diff summary
relevant tests
result summary
```

Reviewer is not allowed to mutate the workspace in v1.

Evaluate whether its final review catches issues the root agent misses.

---

# 26. Stage 24 — Multi-Agent Topology Experiments

Run controlled comparisons.

```text
M0 root only
M1 root + Scout
M2 root + Debugger
M3 root + Reviewer
M4 root + Scout + Debugger
M5 root + Scout + Debugger + Reviewer
```

Use identical benchmark splits.

Record the delta in:

```text
pass rate
runtime
turns
tool calls
failure recovery
```

Select the smallest topology that materially improves held-out performance.

---

# 27. Stage 25 — Context Compaction

Analyze traces to identify:

- repeated file dumps;
- duplicate logs;
- repeated repository facts;
- stale hypotheses;
- verbose tool output.

Implement compact summaries where safe.

Possible techniques:

```text
file fingerprinting
changed-file tracking
last-observation summaries
test-log truncation
repository-map caching
```

Do not summarize away critical error lines or exact code fragments needed for a decision.

---

# 28. Stage 26 — Tool-Call Budgeting

For each major tool:

```text
call count distribution
success contribution
average information value
```

Identify wasteful calls.

Examples:

```text
Repeated ls of unchanged directories
Repeated reads of identical file ranges
Repeated full test runs after tiny edits
Repeated semantic search for the same query
```

Introduce bounded caching where repository state has not changed.

---

# 29. Stage 27 — Final Diff Discipline

Create a mandatory review sequence:

```bash
git status --short
git diff --stat
git diff -- <relevant files>
```

Then remove:

```text
scratch files
log files
debug prints
temporary fixtures
local configuration
machine-specific artifacts
```

Run relevant tests again after cleanup if cleanup changed any tracked file.

---

# 30. Stage 28 — Build the Local Evaluator Properly

The evaluator must execute tasks against clean copies.

For each run:

```text
clean repository snapshot
↓
load candidate
↓
run agent
↓
extract patch
↓
apply patch to fresh snapshot
↓
run verification
↓
record result
```

Do not validate the patch only in the agent's dirty workspace. A clean application test is essential because final competition scoring applies the patch to a fresh repository state. citeturn538596search1

---

# 31. Stage 29 — Create Dataset Splits

From the actual competition development data, create:

```text
DEV
VALIDATION
HELD_OUT
```

Selection must avoid obvious duplication and repository overlap where feasible.

Do not tune repeatedly on HELD_OUT.

Store split manifests with hashes so the benchmark does not silently change.

---

# 32. Stage 30 — Establish Failure Dashboard Without Building a Web App

Use simple generated reports.

For each candidate produce:

```text
summary.md
failures.jsonl
metrics.csv
```

Report:

```text
overall pass rate
pass rate by repository
pass rate by task type
failure categories
average runtime
average tool calls
```

A lightweight Python report is sufficient.

---

# 33. Stage 31 — Failure-Driven Development Loop

From this point onward, development becomes a closed loop.

```text
Run benchmark
   ↓
Collect failures
   ↓
Cluster failures
   ↓
Choose highest-value cluster
   ↓
Form one intervention
   ↓
Implement candidate
   ↓
Run smoke test
   ↓
Run validation benchmark
   ↓
Run held-out confirmation when promising
   ↓
Promote or reject
   ↓
Repeat
```

Every improvement must answer:

> Which failure mode did this change target, and did that failure mode actually decrease?

---

# 34. Stage 32 — Prompt Optimization Loop

For every prompt change:

```text
P0 baseline
P1 one change
P2 one change
...
```

Do not merge several prompt rewrites before measuring them.

Store each prompt version under:

```text
experiments/prompts/<candidate>/
```

---

# 35. Stage 33 — Retrieval Optimization Loop

Test variants such as:

```text
R0 no semantic retrieval
R1 semantic retrieval
R2 semantic + neighbors
R3 semantic + selective subgraph
R4 dynamic retrieval depth
```

Measure both quality and cost.

A retrieval method that improves easy tasks but causes the agent to drown in context on large tasks is not automatically an improvement.

---

# 36. Stage 34 — Testing Strategy Optimization Loop

Compare:

```text
T0 minimal targeted test
T1 targeted + adjacent tests
T2 targeted + subsystem + full when feasible
T3 adaptive escalation based on failure risk
```

The desired result is not "run more tests".

The desired result is:

> choose tests with maximum useful evidence at acceptable cost.

---

# 37. Stage 35 — Recovery Optimization Loop

Mine traces for repeated failure patterns.

For each pattern:

1. write the failure definition;
2. identify the earliest point where it could be detected;
3. add one recovery rule or prompt instruction;
4. rerun the same failure set;
5. confirm that the fix does not create a new loop.

---

# 38. Stage 36 — Skill Optimization Loop

Skills must be treated as code/configuration.

For every skill revision:

```text
version
scope
expected behavior
benchmark tasks
result
```

Remove instructions that duplicate the root prompt without adding useful behavior.

---

# 39. Stage 37 — Prepare for LoRA Only After the Agent Is Strong

Before training an adapter, verify that:

- baseline architecture is stable;
- benchmark is stable;
- failure taxonomy is useful;
- tool contracts are stable;
- root prompt is not changing daily;
- the training objective is specific.

If those conditions are not met, do not train LoRA yet.

---

# 40. Stage 38 — Construct LoRA Training Data

Use only legally and competition-permitted data.

Training examples should capture useful trajectories, such as:

```text
Issue
→ evidence gathering
→ correct tool usage
→ localization
→ appropriate edit
→ validation
→ recovery when needed
```

Avoid rewarding:

- unnecessary commands;
- giant code dumps;
- random edits;
- unsafe shell patterns;
- tool loops;
- test suppression.

The goal is to teach useful behavior, not transcript imitation.

---

# 41. Stage 39 — LoRA Training

Use PEFT/LoRA with the competition-supported base model.

Keep adapter configuration versioned.

Record:

```text
base model identifier
training data hash
training split
validation split
rank
alpha
dropout
learning rate
batch size
gradient accumulation
epochs/steps
sequence length
seed
software versions
adapter SHA-256
```

Exact values must be selected experimentally and according to what the available free hardware can actually run.

Do not copy hyperparameters from unrelated models without testing.

---

# 42. Stage 40 — LoRA Ablation

At minimum compare:

```text
A. Root prompt, no adapter
B. Same root prompt + adapter
C. Same adapter + changed prompt
D. Same adapter + graph/retrieval system
```

The point is to determine whether the adapter improves the specific behavior it was trained to improve.

---

# 43. Stage 41 — Multi-Adapter Experiment

The competition allows different adapters to be associated with different agents. citeturn538596search1

Only experiment with this after a single adapter produces a measurable benefit.

Possible design:

```text
root → coding/reasoning adapter
scout → localization adapter
reviewer → review adapter
```

But this is an experimental branch, not part of the mandatory architecture.

---

# 44. Stage 42 — Free Compute Strategy

Use free compute where possible.

### Kaggle notebook

Useful for:

- model serving experiments;
- GPU-dependent testing;
- final-compatible runtime experiments.

Current Kaggle documentation lists free P100 and T4×2 notebook configurations and a 12-hour notebook session limit at the time of the current docs. Availability can place users in a queue. citeturn689163search0

### Local CPU

Use for:

- prompts;
- config validation;
- packaging;
- benchmark analysis;
- experiment database;
- report generation;
- unit tests;
- ZIP validation.

### Local GPU

Use if available for faster repeated model runs.

The official checkpoint currently has a 23.3 GB model file, so hardware needs to be checked rather than guessed. citeturn606491search2

---

# 45. Stage 43 — Version Every Candidate

Candidate naming:

```text
E0  baseline
E1  prompt-v1
E2  state-v1
R1  semantic-retrieval
R2  semantic+graph
D1  debug-recovery
S1  scout
V1  reviewer
C1  context-optimized
L1  lora-v1
RC1 release-candidate
```

Do not reuse a candidate name after changing its behavior.

---

# 46. Stage 44 — Candidate Promotion Gate

Promote a candidate only if:

```text
validation improvement
AND
no unacceptable held-out regression
AND
runtime acceptable
AND
configuration valid
AND
behavior reproducible
```

Otherwise reject it and preserve the result for learning.

---

# 47. Stage 45 — Build a Regression Suite for Every Discovered Failure

Whenever a task reveals a general failure mode, add a regression case to the development suite.

Examples:

```text
semantic search misleads agent
agent edits before reading tests
agent loops on failing test
agent leaves temporary file
agent changes unrelated file
agent fails to inspect caller
agent stops after first red test
agent submits without final diff review
```

A regression case can be a full task or a smaller harness-level test.

---

# 48. Stage 46 — Stress Tests

Before finalizing, test difficult conditions:

- very large repository;
- ambiguous issue wording;
- misleading function names;
- multi-file fix;
- hidden dependency relationship;
- failing test with long logs;
- pre-existing failing test;
- required new file;
- binary or unusual file intent when present;
- repeated test failure;
- expensive full-suite tests.

The goal is to expose failure modes before final submission.

---

# 49. Stage 47 — Package Validator

Create:

```text
scripts/validate_submission.py
```

It must check:

```text
ZIP exists
agent.yaml at root
no symlinks
only permitted relative paths
no ../ traversal
all include targets exist
no undeclared adapter references
adapter files have correct names
sub-agent files resolve
skill manifests are valid
model identifier is permitted
no credentials detected
no development-only files
```

Also inspect ZIP contents programmatically.

---

# 50. Stage 48 — Deterministic Packaging

Create:

```text
scripts/package_submission.py
```

The script should:

1. start from a clean agent package directory;
2. validate it;
3. create `submission.zip` with deterministic ordering;
4. print the SHA-256 hash;
5. produce a package manifest.

The development repository and the final ZIP must never be confused.

---

# 51. Stage 49 — Final Pre-Submission Configuration Audit

Re-read the current competition page and current rules.

Check:

```text
model restriction
submission file structure
adapter format
skill rules
submission limits
team state
entry deadline
final deadline
current evaluator changes
```

Do not rely on this plan's historical date values if the organizers have changed them.

Current web-verified competition facts are documented in `IMPULSE.md`, but must be checked again at release time. citeturn538596search1

---

# 52. Stage 50 — Final Candidate Evaluation

Run the release candidate against:

```text
smoke
full development
validation
held-out
stress/regression
```

Generate:

```text
docs/release/RC-final-report.md
```

Include:

```text
candidate ID
model
adapter
prompt version
tools
skills
sub-agents
benchmark versions
pass rates
runtime
tool counts
known failures
final recommendation
```

---

# 53. Stage 51 — Freeze the Winning Candidate

After final selection:

1. create a release branch/tag;
2. freeze prompt files;
3. freeze sub-agent configs;
4. freeze skills;
5. freeze adapter files;
6. freeze model ID;
7. freeze packaging script;
8. record all hashes.

Example:

```bash
git tag -a IMPULSE-RC-FINAL -m "IMPULSE final competition candidate"
```

Do not modify the frozen candidate while simultaneously testing other branches.

---

# 54. Stage 52 — Final ZIP Build

Run:

```bash
python scripts/validate_submission.py
python scripts/package_submission.py
```

Inspect:

```bash
unzip -l submission.zip
sha256sum submission.zip
```

Confirm:

```text
agent.yaml is at archive root
```

not:

```text
submission/agent.yaml
IMPULSE/agent.yaml
agent/agent.yaml
```

unless the current competition harness explicitly says otherwise.

The current competition page explicitly requires `agent.yaml` at the root of `submission.zip`. citeturn538596search1

---

# 55. Stage 53 — Submission Dry Run

Perform a clean dry run from the ZIP itself.

Procedure:

```text
new temporary directory
↓
unzip submission.zip
↓
run current harness structural validator
↓
load root agent
↓
execute at least one smoke task
↓
verify patch extraction
```

This prevents a common failure where the development directory works but the ZIP does not.

---

# 56. Stage 54 — Submit to Kaggle

Use the competition's supported submission mechanism.

Do not invent a different upload format.

Record:

```text
submission timestamp
submission candidate ID
submission file hash
Kaggle submission identifier
status
```

If the platform UI uses upload rather than the public competition CLI for this agent format, use the UI as instructed by the current competition page.

---

# 57. Stage 55 — Post-Submission Diagnostics

When a score/result becomes available, record it separately from local results.

Do not overwrite local benchmark numbers with leaderboard numbers.

Create:

```text
experiments/submissions/<submission-id>/
├── manifest.json
├── kaggle_result.json
└── analysis.md
```

---

# 58. Stage 56 — Continue the Improvement Loop

Project A is not finished merely because a first submission exists.

The optimization loop continues:

```text
Kaggle result
↓
compare with local estimate
↓
identify mismatch/failure
↓
form one hypothesis
↓
change one component
↓
retest locally
↓
held-out confirmation
↓
new candidate
↓
package
↓
submit
```

Never change the production candidate directly without first creating a new version.

---

# 59. Stage 57 — Leaderboard Diagnosis

Treat leaderboard movement as evidence, not explanation.

If a candidate improves:

```text
Ask which local failure classes also improved.
```

If a candidate worsens:

```text
Identify whether the cause is retrieval, prompts, runtime, topology, nondeterminism, or task-distribution mismatch.
```

Do not declare a causal explanation until local traces support it.

---

# 60. Stage 58 — Nondeterminism Control

Agent behavior can vary because of model sampling and environment conditions.

For meaningful experiments:

- keep sampling parameters fixed;
- keep model version fixed;
- keep task order/split fixed;
- repeat promising candidates when feasible;
- record seeds when supported;
- compare aggregate outcomes rather than one lucky task.

A one-run improvement is not sufficient evidence when variance is high.

---

# 61. Stage 59 — Statistical Confidence Procedure

For important changes:

1. run baseline on the same task set;
2. run candidate on the same task set;
3. compare task-by-task outcomes;
4. inspect changed failures;
5. repeat on a second sample when feasible;
6. confirm on held-out tasks.

For small benchmarks, report the raw task table instead of pretending to have precise statistical certainty.

---

# 62. Stage 60 — Complexity Audit

Before final release, ask:

```text
Does each specialist earn its inference cost?
Does each skill earn its context cost?
Does each retrieval step earn its tool cost?
Does each prompt instruction correspond to a measured behavior?
Does LoRA outperform no-LoRA under controlled conditions?
```

Remove components that do not justify themselves.

---

# 63. Stage 61 — Security Audit

Search the final repository and ZIP for:

```text
API keys
passwords
private tokens
SSH keys
cloud credentials
`.env` files
machine-specific paths
```

Use secret scanners if available, but also inspect manually.

Never upload a personal Kaggle API token into `submission.zip`.

---

# 64. Stage 62 — Documentation Freeze

Update:

```text
README.md
IMPULSE.md
PLAN.md
```

`IMPULSE.md` should describe the final architecture.

`PLAN.md` should remain the historical execution plan and can be supplemented with a final completion section, but it must not silently rewrite history.

Create:

```text
docs/release/final_release_notes.md
```

---

# 65. Stage 63 — Project A Completion Gate

Project A is complete only when all of these are true:

```text
[ ] baseline exists
[ ] local runner works
[ ] local evaluator works
[ ] benchmark split is frozen
[ ] retrieval policy is tested
[ ] failure recovery is tested
[ ] specialist topology is measured
[ ] context strategy is measured
[ ] LoRA is either validated or intentionally rejected
[ ] final candidate is tagged
[ ] submission validator passes
[ ] submission ZIP dry run passes
[ ] final ZIP hash recorded
[ ] Kaggle submission recorded
[ ] final known-failure report exists
```

---

# 66. The Continuous Improvement Loop in One Diagram

```text
                 ┌─────────────────────────┐
                 │  CURRENT BEST IMPULSE   │
                 └────────────┬────────────┘
                              │
                              ▼
                       Run benchmark
                              │
                              ▼
                        Collect traces
                              │
                              ▼
                        Cluster failures
                              │
                              ▼
                   Pick highest-value issue
                              │
                              ▼
                       Form hypothesis
                              │
                              ▼
                        One intervention
                              │
                              ▼
                       Smoke test
                              │
                    ┌─────────┴─────────┐
                    │                   │
                  FAIL                PASS
                    │                   │
                    ▼                   ▼
             reject/debug        Validation benchmark
                                        │
                               ┌────────┴────────┐
                               │                 │
                             WORSE             BETTER
                               │                 │
                               ▼                 ▼
                            reject         Held-out test
                                                 │
                                         ┌───────┴───────┐
                                         │               │
                                       FAIL            PASS
                                         │               │
                                         ▼               ▼
                                      reject       New BEST
                                                         │
                                                         ▼
                                                   Package RC
                                                         │
                                                         ▼
                                                    Submit
                                                         │
                                                         ▼
                                                 New evidence
                                                         │
                                                         └──────→ repeat
```

---

# 67. Exact Experiment Order

The default order of major milestones is:

```text
E0  Minimal root agent
E1  Prompt/evidence discipline
E2  Structured task state
R1  Semantic retrieval
R2  Graph neighbors
R3  Selective subgraphs
T1  Testing strategy
F1  Failure taxonomy
F2  Recovery + no-progress
S1  Scout
D1  Debugger
V1  Reviewer
C1  Context compaction
C2  Tool-call optimization
L0  LoRA feasibility study
L1  LoRA candidate
A1  Best combined architecture
RC1 Final release candidate
```

This order minimizes confounding variables.

---

# 68. Stop Conditions for Individual Experiments

Stop an experiment early when:

- configuration fails validation;
- the candidate cannot complete a smoke task;
- an error is caused by an invalid tool contract;
- the candidate creates persistent loops;
- the candidate clearly degrades on the target failure set;
- the hardware cannot support the proposed runtime;
- a competition constraint is violated.

Do not spend GPU time on a candidate that fails basic plumbing.

---

# 69. Reproducibility Checklist for Every Candidate

Before recording a candidate result, store:

```text
candidate ID
Git commit
agent.yaml hash
prompt hashes
skill hashes
sub-agent hashes
adapter hashes
model identifier
software versions
benchmark split hash
runtime settings
sampling settings
hardware
start/end time
result summary
```

---

# 70. Final Submission Checklist

```text
COMPETITION
[ ] Joined competition
[ ] Rules accepted
[ ] Current rules re-read
[ ] Current deadline rechecked
[ ] Team status correct

MODEL
[ ] Supported Gemma 4 model only
[ ] All sub-agents use permitted base model
[ ] Adapter references resolve

PACKAGE
[ ] agent.yaml at ZIP root
[ ] include paths valid
[ ] sub-agent paths valid
[ ] skills valid
[ ] no symlinks
[ ] no path traversal
[ ] no credentials
[ ] no development artifacts

AGENT
[ ] tools work
[ ] retrieval works
[ ] tests work
[ ] recovery works
[ ] reviewer works if included
[ ] final diff is clean
[ ] submit_patch works

VALIDATION
[ ] smoke tasks pass or known behavior understood
[ ] validation benchmark completed
[ ] held-out benchmark completed
[ ] regression suite completed
[ ] final result recorded

RELEASE
[ ] ZIP hash recorded
[ ] release tag created
[ ] submission uploaded
[ ] submission identifier recorded
```

---

# 71. Project B Handoff Procedure

Once Project A is frozen:

1. copy the final candidate manifest;
2. copy benchmark and failure statistics;
3. preserve all experiment records;
4. list unexplained performance differences;
5. identify the most generalizable improvement;
6. identify which evidence can become research;
7. create a separate Project B repository or branch.

Do not modify the historical Project A records after the handoff.

The current Paper Track explicitly supports research on PEFT/RL, code comprehension, graph generation/embedding, benchmarks/resources, and graph reasoning. citeturn538596search0

---

# 72. Research Questions to Preserve for Project B

The Project A experiment log should make it possible to ask questions such as:

```text
Does graph retrieval improve localization?
When does semantic retrieval outperform lexical search?
Does explicit hypothesis tracking reduce regressions?
Does a read-only debugger reduce repeated failed edits?
Does final diff review improve patch quality?
Which failure classes dominate residual errors?
Does LoRA improve tool use, code edits, or both?
Can structured repository state reduce context/tool cost without reducing accuracy?
```

No result should be assumed in advance.

---

# 73. Current Research Facts Used in This Plan

The current official competition page states:

- the competition is about autonomous software engineering agents;
- the agent is evaluated via submitted patches and validation tests;
- the main competition currently has a 12-hour global agent budget;
- `gemma-4-31b-it-qat-w4a16-ct` is the currently supported model;
- optional LoRA adapters are supported;
- predefined shell/file/status/patch/graph retrieval tools exist;
- the submission archive must contain root-level `agent.yaml`;
- skills are sandboxed and their scripts consume the central budget. citeturn538596search1

Google's Gemma 4 documentation states that the family provides reasoning, long context, function calling, coding capabilities, and native system-prompt support; the 31B model supports a 256K context window. citeturn606491search1turn606491search4

The official Hugging Face checkpoint currently lists the QAT W4A16 model at approximately 23.3 GB and documents vLLM and Transformers usage. citeturn606491search2turn606491search5

Google ADK supports YAML Agent Configs, sub-agents, tools, and configurable workflows, but the competition applies a restricted compilation environment, so the current competition harness remains the final authority. citeturn189205search0turn538596search1

---

# 74. Final Plan Status

**PLAN.md is FINALIZED as the execution contract for Project A.**

The project starts at Stage 0 and proceeds sequentially until a release candidate exists. After the first valid submission, the same measurement-driven loop continues for subsequent candidate releases until the project is intentionally frozen and handed off to Project B.

The only values that must be re-verified immediately before final competition submission are organizer-controlled rules, deadlines, harness versions, and current evaluator details.
