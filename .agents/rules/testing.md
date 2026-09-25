# Testing Rules — IMPULSE

This document specifies the testing standards, validation protocols, and empirical verification requirements for **IMPULSE**.

---

## 1. Testing as an Inherent Part of Implementation

Testing is not an optional post-implementation step; it is an inseparable component of development. No unit of code, configuration, prompt, or tool integration is complete until it has been verified by concrete tests.

### Test-Driven Development Flow
For every meaningful change:
1. **Identify the Test Scope:** Determine the smallest test case capable of validating the target behavior.
2. **Implement:** Write or modify the target code or configuration.
3. **Execute Focused Test:** Run the narrowest relevant test immediately.
4. **Investigate Failures:** If the test fails, diagnose the failure using empirical logs—never guess or modify assertions to force a pass.
5. **Expand Test Coverage:** Verify integration with adjacent modules and run regression suites before declaring the unit complete.

---

## 2. Comprehensive Test Coverage Domains

Testing across the IMPULSE repository must rigorously cover:
- **Unit Behavior:** Individual functions, parsing utilities, metric calculations, and formatting routines.
- **Integration Behavior:** Interactions between runner modules, sandbox controllers, and patch generators.
- **Configuration Loading:** Verification that YAML configurations (including `agent.yaml` and sub-agent configs) load cleanly without schema violations.
- **Agent Config Validity:** Strict conformance to competition ADK compiler constraints (valid model identifiers, existing tools, valid sub-agent references).
- **Prompt & Resource Loading:** Verification that referenced markdown prompt files and skill manifests resolve cleanly from relative paths.
- **Error Handling & Recovery:** Ensuring that tool timeouts, malformed outputs, and syntax errors are trapped and classified appropriately rather than crashing the runner.
- **Filesystem & Diff Hygiene:** Confirming that patch extraction captures only intentional changes and ignores untracked debug artifacts.
- **Security-Sensitive Behavior:** Verifying path traversal protections (rejection of `../`), secret scrubbing, and command validation.
- **Packaging & Submission Structure:** Deterministic creation and validation of `submission.zip` matching competition rules.

---

## 3. Strict Evidence & Zero Fabrication Standards

- **Empirical Execution Mandatory:** **NEVER** claim a test passed unless it was genuinely executed and its exit code/output was verified.
- **Zero Fabrication:** Never invent, extrapolate, or guess benchmark values, latency numbers, token counts, or pass rates.
- **No Unsubstantiated Claims:** Never write "verified", "tested", "100% reliable", "production-ready", or "bug-free" without providing reproducible test logs or measurement data.
- **Record Actual Metrics:** All recorded performance figures must be accompanied by the exact command executed, timestamp, environment details, and raw output log references.

---

## 4. Progressive Validation Architecture

In alignment with [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md), validation must proceed progressively to conserve budget and maintain information-rich feedback:

```text
1. Reproduce / Target the specific issue with the narrowest possible test
   ↓
2. Verify surgical fix on the targeted test
   ↓
3. Execute directly related unit tests in the same module
   ↓
4. Run broader subsystem test suites
   ↓
5. Run clean-snapshot regression verification before submission
```

---

## 5. Clean Repository Evaluation

- **Fresh Snapshot Requirement:** When evaluating agent-generated patches in local benchmarks, never validate solely inside the agent's dirty working directory.
- **Fresh Copy Verification:** Always extract the generated patch and apply it to a completely clean repository snapshot to verify that:
  - The patch applies cleanly (`git apply --check`).
  - No hidden dependencies on untracked temporary files or environment variables exist.
  - The patch alone resolves the target issue while passing existing repository regression suites.
