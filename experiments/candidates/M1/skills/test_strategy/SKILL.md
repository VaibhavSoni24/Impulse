---
name: test_strategy
description: Generic testing strategy for repository-level software defect reproduction, targeted verification, intelligent broadening, and test-result interpretation.
---

# Systematic Testing Strategy Skill

## Purpose
This skill establishes a disciplined, evidence-based methodology for verifying software fixes across diverse repositories. It guides agents to discover test tooling from repository evidence, isolate narrow reproductions, execute focused verification, broaden test coverage progressively, and interpret test outcomes accurately while minimizing unnecessary tool and execution budget usage.

---

## 1. Discover the Test Framework

Never assume a particular programming language, test runner, or project structure. Always inspect repository configuration files to determine how tests are structured and executed:

1. **Inspect Root Configuration Files**:
   - Python: Look for `pyproject.toml`, `setup.cfg`, `tox.ini`, `pytest.ini`, `Makefile`. Check test runner configurations (e.g., `pytest`, `unittest`, `nox`).
   - JavaScript/TypeScript: Look for `package.json` (`scripts.test`), `jest.config.js`, `vitest.config.ts`, `tsconfig.json`.
   - Rust: Look for `Cargo.toml`.
   - Go: Look for `go.mod`, `Makefile`.
   - Other languages: Check build automation and CI configs (`.github/workflows`, `.gitlab-ci.yml`, `Makefile`, `taskfile.yml`).
2. **Inspect Environment & Invocation Patterns**:
   - Check if tests must be invoked via a virtual environment runner, package manager, or build tool (e.g., `pytest`, `python -m unittest`, `cargo test`, `go test`, `npm test`).
   - Check if specific environment variables or test flags are configured in CI scripts or repository documentation.
3. **Locate Test Directories**:
   - Common patterns: `tests/`, `test/`, `spec/`, `src/**/__tests__/`, or colocated test files (`*_test.py`, `test_*.py`, `*.spec.ts`, `*_test.go`).
   - Confirm directory existence before attempting to run test commands.

---

## 2. Identify the Relevant Test Area

Connect the reported issue and modified source components to their corresponding test files:

1. **Mirroring Structure**: Most repositories mirror source hierarchy in their test directories (e.g., source file `src/pkg/client.py` often maps to `tests/test_client.py` or `tests/pkg/test_client.py`).
2. **Existing Test Search**:
   - Search for references to the suspect class, method, or error message in test files using search tools (`read_file` or exact pattern matching).
   - Locate existing regression tests or related test classes that exercise the affected code path.
3. **Inspect Fixtures and Dependencies**:
   - Check for local fixtures, helper modules, or mock setups (e.g., `conftest.py`, `fixtures/`, `helpers/`) to understand setup requirements before invoking tests.
4. **Identify Integration Boundaries**:
   - Note whether the affected component is a self-contained unit or part of a multi-module pipeline, determining what level of testing is appropriate.

---

## 3. Reproduce Narrowly Before Modifying Code

Before altering source files, verify the failure mode using the smallest possible reproduction:

1. **Formulate Minimal Reproduction**:
   - If an existing test case directly matches the issue, run that specific single test.
   - If no existing test covers the failure, identify the nearest existing test case or formulate a minimal invocation to observe the failing behavior.
2. **Run Only the Isolated Target**:
   - Avoid executing broad suites during reproduction. Target exactly one test function, method, or test file.
3. **Capture and Analyze the Baseline Output**:
   - Record the exact error message, assertion failure, or exception traceback.
   - Confirm that the observed failure matches the problem statement and is not an unrelated environment or setup failure.
4. **When Direct Reproduction Is Infeasible**:
   - If environment or test harness constraints prevent direct reproduction, document the exact reason based on observed evidence and rely on careful source analysis and targeted verification rather than inventing test results.

---

## 4. Run Targeted Verification After Editing

Once a minimal code modification is applied, execute targeted verification:

1. **Target the Smallest Relevant Unit**:
   - Run a single test function or method first.
   - If passing, run the containing test class or test file.
2. **Use Precise Filtering**:
   - Utilize framework-specific selection flags to isolate the test (e.g., filtering by test name or specific file path rather than running an entire directory).
3. **Verify the Specific Fix**:
   - Confirm that the specific error observed during reproduction is eliminated.
   - Ensure the modified code path behaves as expected without side effects on nearby unit tests in the same test module.

---

## 5. Broaden Coverage Intelligently

Do not jump immediately from a single test to a full-repository test sweep. Escalate test scope gradually and only when justified:

1. **Progressive Broadening Ladder**:
   $$\text{Targeted Single Test} \longrightarrow \text{Containing Test File} \longrightarrow \text{Related Subsystem Suite} \longrightarrow \text{Broader Suite (Only if Justified)}$$
2. **When Broadening Is Justified**:
   - **Cross-Component Changes**: The edit modified a shared utility, public interface, or widely imported data structure.
   - **Multi-Module Interactions**: The defect involved interactions across multiple modules or layers.
   - **Regression Risk**: Nearby functions in the same module share state or logic that might be affected.
3. **When Broadening Is Unjustified**:
   - The fix was isolated to an internal private helper or localized edge-case check with no external callers.
   - The broader suite includes slow end-to-end tests, network mocks, or performance benchmarks unrelated to the change.

---

## 6. Interpret Test Results Soundly

Evaluate command outcomes critically:

1. **Distinguish Exit Codes**:
   - A zero exit status indicates tests passed; non-zero indicates test failure, syntax error, or harness error.
   - A command error (e.g., missing package, command not found, syntax error) is NOT a valid test failure—it is an environment or command issue.
2. **Examine Failure Traces**:
   - Differentiate between:
     - **Regression in Modified Code**: The traceback originates directly from lines modified by the patch.
     - **Pre-Existing Failures**: Tests that were already broken in the repository baseline (check whether the test is related to the issue).
     - **Flaky or Environment Failures**: Timeout, port conflict, or network errors unrelated to code changes.
3. **Verify Meaningful Assertion Coverage**:
   - Do not mistake a test passing due to skipped execution (`SKIP`, `@skip`) as successful verification.
   - Ensure that the assertions executed actually exercise the modified conditional branch or logic path.

---

## 7. Avoid Unnecessary Full-Suite Execution

Preserve tool calls, session execution limits, and context space by avoiding wasteful testing patterns:

1. **No Blind Full-Suite Sweeps**:
   - Never run unconstrained full repository test commands without specifying target paths or filters, unless explicitly required and verified safe.
   - Full sweeps often encounter timeouts, slow integration tests, or irrelevant environment failures.
2. **No Redundant Invocations**:
   - Do not repeat identical test commands without making code modifications or changing configuration.
   - Check structured task state to recall prior test outcomes.
3. **Stop When Evidence Is Sufficient**:
   - Once the targeted test and its immediate containing module pass cleanly and provide clear evidence of resolution, conclude verification and proceed to final diff review.
