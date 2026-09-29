# IMPULSE Prompt Optimization Loop (Stage 32)

## 1. Purpose and Philosophy

The **Prompt Optimization Loop** establishes a disciplined, evidence-based experimental methodology for refining IMPULSE agent prompts. Rather than engaging in speculative prompt rewrites, subjective evaluation, or prompt bloat, every prompt modification must answer:

> *"Does this specific prompt change reduce a specific observed failure mode without causing unacceptable regression?"*

Stage 32 provides the formal control loop, candidate isolation, deterministic diff engine, and paired task analysis infrastructure required to conduct rigorous prompt experiments.

---

## 2. Fundamental Experiment Rule: One Change Per Candidate

Stage 32 strictly enforces single-dimension, single-change discipline:

```text
P0 (Frozen baseline prompt)
 ↓
P1 = P0 + exactly ONE causal prompt intervention
 ↓
P2 = P1 + exactly ONE causal prompt intervention
...
```

Never bundle multiple conceptual changes (e.g. changing retrieval instructions + rewording recovery + modifying test strategy) into a single candidate. Every candidate must represent an experimentally separable delta.

### Non-Prompt Dimensions Remain Invariant
All of the following must remain fixed during a prompt experiment:
- Model identifier (`gemma-4-31b-it-qat-w4a16-ct`)
- Multi-agent topology (`root_only` / `M0`)
- Tool definitions and contracts
- Python codebase and execution logic
- Retrieval heuristics and implementations
- Recovery logic and skill files
- Benchmark version, split manifests, and task ordering
- Clean-copy evaluation machinery

---

## 3. P0 Frozen Baseline and P(n) Candidate Versioning

### P0 Frozen Baseline
- **Path:** `experiments/prompts/P0/root.md`
- **Source:** Exact byte-identical replica of `experiments/candidates/M0/prompts/root.md`
- **SHA-256 Digest:** `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`
- **Policy:** Strictly immutable. P0 is never modified in place.

### P(n) Candidate Directory Structure
Every prompt version is preserved in an isolated directory under `experiments/prompts/<candidate>/`:
```text
experiments/prompts/P0/
    root.md                  # Immutable baseline prompt
    manifest.json            # Baseline manifest and SHA-256 hashes
    report.md                # Quantitative baseline summary

experiments/prompts/P1/
    root.md                  # P1 prompt with exactly one intervention
    manifest.json            # Reproducibility manifest
    prompt_diff.json         # Machine-readable diff
    prompt_diff.md           # Human-readable diff
    paired_results.jsonl     # Task-level paired outcome table
    paired_results.csv       # Standard CSV paired outcomes
    report.md                # Full experimental audit report
```

---

## 4. Structured Prompt Hypothesis

Every prompt candidate requires a typed, verifiable `PromptHypothesis`:
- **TARGET FAILURE:** Exact failure class (e.g., `WRONG_HYPOTHESIS`, `INCOMPLETE_FIX`, `COMMAND`).
- **OBSERVATION:** Concrete empirical observation from baseline runs.
- **HYPOTHESIS:** Technical explanation for why this wording/instruction change will reduce the targeted failure.
- **INTERVENTION:** Precise instruction or wording being added, removed, or modified.
- **EXPECTED BEHAVIOR:** Observable behavioral shift in agent reasoning or tool interaction.
- **EXPECTED METRIC SIGNAL:** Targeted reduction in the chosen failure mode.
- **REJECTION CONDITION:** Measurable outcome dictating candidate rejection (e.g., zero reduction in target failure, or collateral regressions).

### Controlled Vocabulary for Change Types (`PromptChangeType`)
- `ADD_INSTRUCTION`: Adding a new operational constraint or heuristic.
- `REMOVE_INSTRUCTION`: Removing an instruction (ablation or bloat removal).
- `REWORD_INSTRUCTION`: Clarifying phrasing while preserving intent.
- `REORDER_INSTRUCTION`: Modifying instruction priority or sequence.
- `TIGHTEN_CONSTRAINT`: Making a requirement stricter or mandatory.
- `RELAX_CONSTRAINT`: Loosening an overly restrictive instruction.
- `FORMAT_CHANGE`: Modifying output formatting guidance.
- `PRIORITY_CHANGE`: Changing relative guidance weighting.

---

## 5. Deterministic Prompt Diffing & Cost Metrics

The prompt diff engine (`local/prompt_opt/diff.py`) provides:
- Unified line diffs (`difflib`)
- Added, removed, and modified line counts
- Character count delta
- Estimated token delta (~4 characters per token heuristic without external dependencies)
- Affected markdown sections

### Bloat Diagnostics
Detects repetitive or non-operational prompt text:
- Duplicate non-trivial lines
- Generic motivational filler (e.g. *"do your best"*, *"you are a genius"*)
- Contradictory instructions across sections

---

## 6. Task-Level Paired Comparison

Beyond aggregate pass rates, Stage 32 evaluates task-by-task transitions on identical tasks (`local/prompt_opt/paired.py`):
- `FAIL → PASS`: Direct fix attributed to intervention.
- `PASS → FAIL`: Direct collateral regression.
- `FAIL_A → FAIL_B`: Failure mode shift.
- `FAIL → FAIL`: Unresolved failure.
- `PASS → PASS`: Retained capability.

---

## 7. Integration with Stage 31 FDD Loop

Prompt experiments execute through the Stage 31 FDD state machine:
1. Select active failure cluster.
2. Formalize structured prompt hypothesis.
3. Generate candidate P(n) from parent P(n-1).
4. Validate single-component prompt integrity (`validate_prompt_candidate_integrity`).
5. Execute smoke evaluation (immediate rejection if smoke fails).
6. Execute validation benchmark on `validation` split.
7. Compute targeted failure delta and collateral shifts.
8. If promising, execute held-out confirmation with `held_out.lock` verification.
9. Apply Stage 31 promotion gate.
10. Persist complete reproducibility artifacts.

---

## 8. Evidence Modes & Local Host Behavior

- **`LIVE`**: Competition Gemma 4 31B model inference evaluated against clean repository copies.
- **`FIXTURE`**: Synthetic agent responses used to verify pipeline mechanics locally. Strictly segregated from live production metrics.
- **`UNAVAILABLE` / `INFRASTRUCTURE_ONLY`**: Local host lacking required GPU resources (4x NVIDIA L4).

### Real Local Data Status
Running analysis on candidate `E0` against the `dev` split correctly reports `NO_ACTIONABLE_LIVE_FAILURES`. Stage 32 preserves strict evidence: zero synthetic live improvements are fabricated.

---

## 9. Command-Line Interface

```bash
# Analyze P0 baseline prompt and bloat diagnostics
python scripts/run_prompt_experiment.py --parent P0 --analyze

# Verify cryptographic integrity of a prompt candidate
python scripts/run_prompt_experiment.py --verify experiments/prompts/P0

# Inspect prompt diff for a candidate
python scripts/run_prompt_experiment.py --candidate P1 --diff

# Display human-readable audit report
python scripts/run_prompt_experiment.py --candidate P1 --report
```

---

## 10. Scope and Non-Goals
- **No Retrieval Optimization:** Stage 33 will address semantic retrieval.
- **No Testing Optimization:** Stage 34 will optimize test selection.
- **No Recovery Optimization:** Stage 35 will address error recovery heuristics.
- **No LoRA Training:** Stage 37+ will handle adapter training.
- **No Leaderboard Gaming:** Optimization is guided strictly by empirical failure reduction.
