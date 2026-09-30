# Recovery Optimization Experiment Report: Candidate `REC0`

## Candidate Metadata
- **Candidate ID:** `REC0`
- **Parent Candidate:** `REC0`
- **Policy Hash:** `ee77ab01ea322ad61276eeb627de6eab64f5b732adc868110e8e6f4fdd713f7f`
- **Evidence Mode:** `UNAVAILABLE`
- **Benchmark Split:** `dev`
- **Promotion Decision:** `BASELINE`
- **Decision Rationale:** Candidate initialized in UNAVAILABLE evidence mode (local hardware limitation).

## Invariance Verification
- **Root Prompt Hash:** `2360d4bf64dd...` (Invariant)
- **Retrieval Policy Hash:** `3e1b234a2ac7...` (Invariant R0)
- **Testing Policy Hash:** `76820d5c5e2a...` (Invariant T0)
- **Topology:** `root_only` (Invariant)
- **Model ID:** `gemma-4-31b-it-qat-w4a16-ct` (Invariant)
- **Test Strategy Skill:** `3d027b0f9a7f...` (Frozen)
- **Repo Triage Skill:** `ac7a967136bb...` (Frozen)

## Causal Recovery Hypothesis
- **Target Failure:** `Baseline Canonical Recovery Paths`
- **Observation:** Stage 20 baseline recovery paths reacting after failure recurrence.
- **Hypothesis:** Baseline configuration for bounded recovery across 5 families.
- **Recovery Change:** None (Baseline)
- **Expected Signal:** Baseline metrics established.
- **Rejection Condition:** Baseline is immutable.

## Recovery Quality & Effectiveness
| Metric | Value |
| :--- | :--- |
| Targeted Recovery Success Rate | 0.0% |
| Targeted Failure Reduction | 0 tasks |
| Recovery Loop Count | 0 |
| Detection Latency (Events) | 0.0 |
| Detection Latency (Turns) | 0.0 |
| Average Recovery Attempts | 0.00 |
| Tasks Recovered After Failure | 0 |
| Tasks Abandoned After Failure | 0 |
| Alternate Path Success Rate | 0.0% |
| First-Attempt Success Rate | 0.0% |

## Resource & Recovery Cost Metrics
| Metric | Value |
| :--- | :--- |
| Total Recovery Tool Calls | 0 |
| Recovery Turns Used | 0 |
| Total Retries Executed | 0 |
| Total Recovery Runtime | 0.0 ms |
| Additional Tests Caused | 0 |
| Additional Retrievals Caused | 0 |
| Additional Context Growth | 0 bytes |
| Repeated Failed Interventions | 0 |

## Deterministic Diagnostics
- **Late Recovery:** `NO`
- **Repeated Identical Recovery:** `NO`
- **Recovery Oscillation:** `NO`
- **Retry Waste:** `NO`
- **Recovery Without State Change:** `NO`
- **Missed Recovery Opportunity:** `NO`
- **Failed Recovery:** `NO`
- **Unrelated Regression Caused:** `NO`
- **Excessive Testing:** `NO`
- **Excessive Retrieval:** `NO`
- **Budget Exhaustion:** `NO`
- **Success After Unnecessary Repetitions:** `NO`
