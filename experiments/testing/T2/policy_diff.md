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
