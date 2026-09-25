# Git Rules — IMPULSE

This document establishes the mandatory Git workflows, commit standards, branch practices, and repository hygiene requirements for **IMPULSE**.

---

## 1. Mandatory Git Discipline

Version control is an active instrument of project safety, traceability, and reproducibility. Git is mandatory for all development in IMPULSE.

### 5-Step Pre-Commit Inspection
Before creating any commit, execute this non-negotiable sequence:
1. **Inspect Diff:** Run `git diff` (and `git diff --cached`) to verify every modified and staged line. Confirm that all changes are intentional and minimal.
2. **Inspect Status:** Run `git status` to ensure untracked files, scratch files, or unwanted logs are not present or accidentally staged.
3. **Run Verification Tests:** Execute the relevant unit, integration, or packaging tests associated with the changed code. Ensure tests pass cleanly.
4. **Scan for Secrets:** Confirm no credentials, `.env` files, API tokens, or private paths exist in staged files.
5. **Stage and Commit:** Stage only the specific files relevant to the completed unit and commit with a standard message.

---

## 2. Incremental Commits vs. Monolithic Commits

- **Frequent, Coherent Commits:** Commit work incrementally as discrete, logically coherent units of functionality, testing, or documentation are completed.
- **Multiple Commits Encouraged:** When a prompt or working session encompasses several distinct accomplishments (e.g., adding a utility, writing tests for it, and then updating documentation), create separate, focused commits for each unit.
- **No Monolithic Commits:** **NEVER** defer committing until the entire project, milestone, or stage is completed to create a massive "dump" commit.
- **Atomic Commits:** Each commit should represent a self-contained state where tests pass and the repository remains in a functioning, reproducible condition.

---

## 3. Commit Message Conventions

Commit messages must follow the Conventional Commits specification. They must clearly communicate the *type* and *scope* of the change.

### Acceptable Types
- `feat:` A new agent capability, skill, tool integration, or runner feature.
- `fix:` A bug fix in agent logic, test harness, configuration, or packaging.
- `test:` Adding, refining, or fixing unit, integration, or regression tests.
- `docs:` Documentation additions, rule updates, or architecture specifications.
- `refactor:` Code refactoring that neither fixes a bug nor adds a feature.
- `chore:` Maintenance tasks, dependency updates, `.gitignore` modifications, or build tooling.

### Examples of Good Commit Messages
```text
feat: add repository triage workflow
feat: add graph retrieval policy
fix: prevent repeated test retries in failure loop
test: add failure classification coverage
docs: document submission packaging requirements
refactor: isolate patch review logic
chore: add project gitignore
```

### Prohibited Commit Messages
Never write vague, lazy, or meaningless commit messages, including:
- `update`
- `changes`
- `fix`
- `stuff`
- `work`
- `done`
- `wip`

---

## 4. History Preservation & Safety

- **No Rewriting Public History:** Never perform destructive operations on shared or published branches (e.g., `git reset --hard <upstream>`, interactive rebasing of published commits) without explicit authorization.
- **No Force Pushing:** Never force push (`git push --force` or `git push -f`) unless explicitly directed after safety verification.
- **Clean Branches:** Keep branches focused and short-lived. Delete merged feature branches when no longer required.

---

## 5. Artifact & Weight Restrictions

- **Never Commit Model Weights:** Full base model checkpoints (`gemma-4-31B...`) and large weight files (`*.bin`, `*.pt`, `*.safetensors`) must never be committed to Git.
- **Adapter Exception:** Only validated, small LoRA adapters strictly required for competition submission may be tracked under `agent/adapters/`, provided they are small, necessary, and accompanied by their `adapter_config.json`.
- **Ignore Local Caches:** Ensure `.gitignore` continuously shields the repository from Python caches, test logs, OS artifacts, and evaluation run outputs in `runs/`.
