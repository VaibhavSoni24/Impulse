# Recovery Optimization Experiment Report: Candidate `REC3`

## Candidate Metadata
- **Candidate ID:** `REC3`
- **Parent Candidate:** `REC0`
- **Policy Hash:** `ca867587fd8a916fbeb92e1a2b0c27c5a38f36ef55ada8167cc351b42eade030`
- **Evidence Mode:** `UNAVAILABLE`
- **Benchmark Split:** `dev`
- **Promotion Decision:** `NO_ACTIONABLE_DATA`
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
- **Target Failure:** `RECOVERY_LOOP / RECOVERY_THRASHING`
- **Observation:** Alternating recovery actions can oscillate without progress.
- **Hypothesis:** Explicit state-fingerprint checking and oscillation suppression will terminate loops cleanly.
- **Recovery Change:** Enable loop guard signature checks; add oscillation stop condition.
- **Expected Signal:** recovery_loop_count reaches 0; runtime decreases.
- **Rejection Condition:** Collateral regressions or premature termination of solvable tasks.

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

## Policy Differences vs. Parent
# Recovery Policy Diff: REC0 vs. REC3

- **Baseline Variant:** `REC0` (hash: `ee77ab01ea32`)
- **Candidate Variant:** `REC3` (hash: `ca867587fd8a`)
- **Identical:** `NO`

## Changed Settings

### Feature Flags & Thresholds
| Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `alternate_path_routing_enabled` | `False` | `True` |
| `early_detection_enabled` | `False` | `True` |
| `loop_guard_enabled` | `False` | `True` |
| `no_progress_threshold_turns` | `3` | `1` |

### Retry Budget Bounds
| Bound Parameter | Baseline | Candidate |
| :--- | :--- | :--- |
| `max_alternate_paths` | `1` | `2` |
| `max_recovery_runtime_seconds` | `120.0` | `100.0` |
| `max_recovery_tool_calls` | `8` | `6` |
| `max_same_action_retries` | `2` | `1` |
| `max_total_recovery_attempts` | `4` | `3` |

### Trigger Thresholds
| Trigger Key | Baseline | Candidate |
| :--- | :--- | :--- |
| `bad_edit_max_attempts` | `2` | `1` |
| `budget_pressure_remaining_seconds` | `300.0` | `250.0` |
| `budget_pressure_remaining_tools` | `10` | `8` |
| `loop_guard_signature_check` | `None` | `True` |
| `search_fallback_max_attempts` | `5` | `2` |
| `test_failure_escalate_attempts` | `2` | `1` |

### Action Configurations
| Action Setting | Baseline | Candidate |
| :--- | :--- | :--- |
| `state_fingerprint_guard` | `None` | `True` |
| `suppress_oscillation` | `None` | `True` |

### Fallback Rules
| Condition | Baseline Rule | Candidate Rule |
| :--- | :--- | :--- |
| `on_bad_edit` | `REPAIR_OR_REVERT` | `SAFE_REVERT_GUARD` |
| `on_search_exhaustion` | `EXACT_THEN_TREE_THEN_GRAPH` | `BOUNDED_TREE_THEN_STOP` |
| `on_test_failure` | `CLASSIFY_THEN_INSPECT` | `SAFE_REVISE_OR_TERMINATE` |
| `on_tool_failure` | `RETRY_THEN_ALTERNATE` | `ALTERNATE_TOOL_WITH_LOOP_GUARD` |

### Stop Conditions
- **Added Conditions:** `oscillation_detected`, `state_unchanged_after_recovery`

## Unchanged Settings
Total unchanged configuration parameters: **7**

