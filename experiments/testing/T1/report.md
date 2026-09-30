# Testing Strategy Experiment: T1 (T1)

## Candidate Metadata
- **Candidate ID:** `T1`
- **Testing Variant:** `T1`
- **Policy Hash:** `418d055b9cdcdc02923afeee8b8aa57d715c89d45283dfcd8b094fdcaa9dbff1`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Retrieval Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Test Skill Hash:** `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T17:23:58.253853+00:00`

## Lineage
- **Parent Candidate:** `T0`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-testing-t1`

## Target Failure & Hypothesis
- **Target Failure Mode:** `INCOMPLETE_FIX`
- **Source Cluster ID:** `N/A`
- **Observation:** Targeted tests pass but closely related neighboring tests catch regressions in same module/class.
> **Hypothesis:** Targeted + adjacent test selection detects regressions introduced by incomplete fixes with modest additional execution cost.
- **Testing Change:** `Enable adjacent test level (same module/class/neighboring tests).`
- **Expected Metric Signal:** Detection of hidden regressions and reduction in incomplete fix failures.
- **Rejection Condition:** Zero new failures detected or adjacent test execution time exceeds acceptable budget.

## Testing Policy Diff
### Testing Policy Diff: `T0` (T0) -> `T1` (T1)

- **Parent Policy Hash:** `76820d5c5e2a983e4d013180d80dda7601b7cba14ad6bebeb56a93e42e730c36`
- **Candidate Policy Hash:** `418d055b9cdcdc02923afeee8b8aa57d715c89d45283dfcd8b094fdcaa9dbff1`
- **Identical:** `NO`

#### Enabled Strategy Levels
- `adjacent_enabled`: `False` -> `True`

#### Budgets & Execution Limits
- `max_test_commands`: `2` -> `4`
- `max_test_cases`: `20` -> `40`
- `runtime_budget_seconds`: `120.0` -> `180.0`

#### Escalation Rules
- `escalate_on_targeted_failure`: `False` -> `True`

#### Stopping Rules
- `stop_on_targeted_pass_if_low_risk`: `True` -> `False`


## Evidence & Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `INCOMPLETE_FIX`
- **Target Failure Count:** 0
- **Target Failure Rate:** 0.00%
- **Regressions Caught:** 0
- **Incomplete Fixes Caught:** 0
- **Targeted Behavior Confirmed:** 0
- **Adjacent Failures Discovered:** 0
- **Subsystem Failures Discovered:** 0
- **Full Suite Failures Discovered:** 0
- **False-Confidence Cases Avoided:** 0
- **Earliest Detection Level:** `NONE`
- **Clean-Copy Verification:** PASSED

## Cost Metrics
- **Total Test Commands:** 0
  - Targeted Commands: 0
  - Adjacent Commands: 0
  - Subsystem Commands: 0
  - Full Suite Commands: 0
- **Total Test Cases Executed:** 0
- **Total Test Runtime:** 0.0 ms
- **Mean Test Duration:** N/A
- **Median Test Duration:** N/A
- **p95 Test Duration:** N/A
- **Total Output Volume:** 0 bytes
- **Repeated Commands:** 0
- **Duplicate Test Cases:** 0
- **Testing Tool-Call Share:** N/A

## Testing Diagnostics
- **Duplicate Commands:** 0
- **Duplicate Test Cases:** 0
- **Reruns Without Edit:** 0
- **Unnecessary Full Suites:** 0
- **Zero-New-Evidence Adjacent Runs:** 0
- **Zero-New-Evidence Subsystem Runs:** 0
- **Repeated Identical Failures:** 0

## Paired Task Comparison
- No paired baseline comparison executed.

## Evaluation Gates
- **Smoke Gate:** SKIPPED
- **Validation Gate:** UNEXECUTED
- **Held-Out Gate:** UNEXECUTED (held-out protected)
- **Authoritative Decision:** `INCONCLUSIVE`
- **Decision Rationale:** Live inference unavailable locally on Windows host.

## Artifact Hashes
- `metrics.json`: `3d602c3e326b2fb9cb3a1a4be7b1cea5b772b1a02bfed49de38e1fb2932bd8f1`
- `policy.json`: `9f5a9cb6f3973679f811ac375bf11216f7000ed94f7df25b84c63c666e86ddc9`
- `policy_diff.json`: `104fd4f29a9b7bceb8be8100baad7478405ce0b6c0d7b695652ea117cd794378`
- `policy_diff.md`: `9e6546b7b4be14250ee8aa5e67237e45410c0e9f6eb816b28330e1716b219cea`
- `test_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`