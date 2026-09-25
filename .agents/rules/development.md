# Development Rules — IMPULSE

This document specifies the software development standards, dependency protocols, and change management procedures for **IMPULSE**.

---

## 1. Planning Discipline

Before implementing any non-trivial component, follow these strict planning principles:

1. **Consult Specifications First:** Read the relevant sections of [IMPULSE.md](file:///e:/Projects/Impulse/IMPULSE.md) and [PLAN.md](file:///e:/Projects/Impulse/PLAN.md) to understand both the architectural intent and the sequential milestone requirements.
2. **Smallest Coherent Unit:** Decompose tasks into the smallest logically complete, testable units of work.
3. **Zero Speculative Features:** Implement only what is required by the specification for the current stage. Do not add anticipatory code, unused helper methods, or speculative abstractions.
4. **Simplest Viable Design:** Prefer straightforward, explicit solutions that satisfy the requirements over complex architectural patterns.
5. **Modularity and Isolation:** Maintain clear module boundaries. Strictly isolate development and evaluation tooling (`local/`, `benchmark/`, `scripts/`) from competition-facing submission components (`agent/`).

---

## 2. Implementation Standards

- **Code Quality & Clarity:** Write readable, maintainable, and self-documenting Python code conforming to PEP 8 standards.
- **Type Annotations:** Use explicit type hints for function signatures, data structures, and configuration schemas.
- **Focused Modules:** Keep modules and functions compact and dedicated to a single responsibility.
- **Avoid Unnecessary Abstraction:** Do not construct elaborate class hierarchies or wrapper layers when simple functions or standard classes suffice.
- **DRY (Don't Repeat Yourself):** Avoid duplicated logic across the codebase while avoiding premature abstraction.
- **Config vs. Code Separation:** Keep operational parameters, model IDs, prompt templates, and timeouts externalized in configuration files rather than hard-coded in logic.
- **No Magic Constants:** Use well-named configuration settings or module-level constants with documented rationales.
- **Explicit Error Handling:**
  - Anticipate edge cases and handle exceptions explicitly.
  - Never swallow exceptions silently or use empty `except:` / `except Exception: pass` blocks without comprehensive justification.
  - Provide actionable, diagnostic context in error messages.
- **Clean Completed Code:** Remove all temporary debug print statements, scratch instrumentation, commented-out experiments, and dead code before declaring any unit complete.

---

## 3. Dependency Discipline

Dependencies add maintenance overhead, security surface, and environment fragility. Before adding any dependency:

1. **Evaluate Standard Library:** Determine whether the Python Standard Library or an already installed dependency can satisfy the requirement.
2. **Verify Compatibility:** Confirm that the package is compatible with the project environment, target Python version, and the competition harness runtime.
3. **Justify and Document:** Document the technical rationale for introducing the dependency.
4. **Update Manifests:** Add the dependency to `pyproject.toml` (and lock files if applicable) using pinned or bounded version ranges.
5. **Test in Isolation:** Verify that the dependency installs cleanly, introduces no version conflicts, and satisfies all intended tests.
6. **No Mere Convenience:** Never add third-party libraries merely to replace a few lines of straightforward code.

---

## 4. Scope and Refactoring Discipline

- **No Unrelated Refactoring:** Do not refactor adjacent code, reformat untouched files, or rename unrelated variables while working on a feature or bug fix.
- **Protect Working Code:** Do not modify established, passing code unless the modification is directly required to satisfy the assigned task.
- **Explainable Changes:** Every modified line in a commit must have a clear, justifiable relationship to the task at hand.

---

## 5. Change Management Protocol

Every implementation turn must strictly adhere to the following 13-step lifecycle:

```text
 1. Read requested stage from PLAN.md and IMPULSE.md
    ↓
 2. Inspect current repository state and existing files
    ↓
 3. Determine existing implementations and baseline points
    ↓
 4. Identify the smallest coherent implementation unit
    ↓
 5. Implement the unit with clean, typed code
    ↓
 6. Run focused tests verifying new functionality
    ↓
 7. Diagnose and resolve failures (if any)
    ↓
 8. Run relevant regression tests to prevent collateral breakages
    ↓
 9. Inspect git diff to verify precision and cleanliness
    ↓
10. Update documentation to synchronize with behavioral changes
    ↓
11. Verify no secrets, debug artifacts, or temporary files exist
    ↓
12. Commit the completed unit with a clear conventional commit message
    ↓
13. Report transparently what was implemented, tested, measured, and committed
```

- If a prompt results only in analysis and no repository changes, do not commit.
- If a work session encompasses multiple distinct units of work, make separate commits rather than one mixed commit.
- Never declare a task complete when code has only been written but not tested.

---

## 6. Non-Negotiable Requirement Rigor

- **Never Weaken Requirements:** Do not simplify specifications, relax constraints, or drop requirements because they are difficult or inconvenient.
- **Never Skip Testing:** Do not bypass test execution to save time.
- **Never Bypass Security:** Never skip secret scanning, path validation, or sandbox boundaries.
- **Never Fabricate Success:** Do not claim a component works, tests passed, or benchmarks were achieved without empirical execution data.
- **Document Necessary Pivots:** If a requirement is proven technically infeasible after investigation, report the empirical evidence and document the formal resolution before proceeding.
