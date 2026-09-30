# Testing Strategy Experiment: T2 (T2)

## Candidate Metadata
- **Candidate ID:** `T2`
- **Testing Variant:** `T2`
- **Policy Hash:** `cada62c1b0291ee4db996080671bf80b0249a21f810171fd17c21a91cd739d25`
- **Evidence Mode:** `UNAVAILABLE`
- **Prompt ID:** `P0` (SHA-256: `2360d4bf64dd91cb905d1890b903cac26bed792787a79664db42c76cb252527e`)
- **Retrieval Policy Hash:** `3e1b234a2ac756a8d83395f37f3ddf0043758f5da731c097b412d333a8459cf7`
- **Test Skill Hash:** `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148`
- **Topology:** `root_only`
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct`
- **Created At:** `2026-09-30T17:23:58.293378+00:00`

## Lineage
- **Parent Candidate:** `T1`
- **Creation Commit:** `HEAD`
- **Experiment ID:** `exp-testing-t2`

## Target Failure & Hypothesis
- **Target Failure Mode:** `REGRESSION`
- **Source Cluster ID:** `N/A`
- **Observation:** Targeted and adjacent tests miss cross-component interactions that only subsystem or full suite validation detects.
> **Hypothesis:** Targeted + subsystem + full suite (when feasible) prevents subsystem-level regressions.
- **Testing Change:** `Enable subsystem test level and conditional full-suite validation governed by explicit feasibility evaluation.`
- **Expected Metric Signal:** Detection of cross-module subsystem regressions prior to submission.
- **Rejection Condition:** Full suite repeatedly times out or causes excessive cost without finding new regressions.

## Testing Policy Diff
### Testing Policy Diff: `T1` (T1) -> `T2` (T2)

- **Parent Policy Hash:** `418d055b9cdcdc02923afeee8b8aa57d715c89d45283dfcd8b094fdcaa9dbff1`
- **Candidate Policy Hash:** `cada62c1b0291ee4db996080671bf80b0249a21f810171fd17c21a91cd739d25`
- **Identical:** `NO`

#### Enabled Strategy Levels
- `subsystem_enabled`: `False` -> `True`
- `full_suite_enabled`: `False` -> `True`

#### Budgets & Execution Limits
- `max_test_commands`: `4` -> `6`
- `max_test_cases`: `40` -> `80`
- `runtime_budget_seconds`: `180.0` -> `300.0`

#### Escalation Rules
- `escalate_on_adjacent_regression`: `False` -> `True`
- `escalate_on_high_risk`: `False` -> `True`

#### Stopping Rules
- `stop_on_adjacent_pass_if_no_regressions`: `True` -> `False`


## Evidence & Quality Metrics
- **Pass Rate:** 0.00%
- **Failure Rate:** 0.00%
- **Target Failure Mode:** `REGRESSION`
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
- `metrics.json`: `cb5a05865802e35a4c54e00f0b9c8204b3b3127bed6540ca65b8ca5ba4438e97`
- `policy.json`: `4d70b26be03e8feb8d5b4ca81d12096d0a3a7bca535fa112768a7843e17787d9`
- `policy_diff.json`: `9f375fa0de9097523f36de7f0bb3254f5e8287dba6f4bdce3af2abc11dd8b889`
- `policy_diff.md`: `9796062fa414f5e391e659e369c01218b3a6844d7a713d12ddd7744fe164e40c`
- `test_trace.jsonl`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`