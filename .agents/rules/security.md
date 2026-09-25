# Security Rules — IMPULSE

This document establishes the mandatory security rules, credential handling protocols, and operational safety standards for **IMPULSE**.

---

## 1. Zero Secrets Policy

Under no circumstances may sensitive secrets or credentials be committed to the repository, embedded in agent prompts, packaged into skill directories, or included in `submission.zip`.

### Prohibited Secret Types
Never hard-code, commit, or log:
- API keys (Google AI, Kaggle, Hugging Face, OpenAI, Anthropic, etc.)
- Personal Access Tokens (PATs)
- Passwords and passphrases
- Private keys (`*.pem`, `*.key`, `*.p12`, `id_rsa`)
- Cloud platform credentials (GCP service account JSON, AWS credentials, Azure tokens)
- Session cookies and authentication headers
- Kaggle credential files (`kaggle.json`)

### Safe Placeholders
When creating configuration examples, templates, or documentation, always use unmistakable placeholder syntax:
```text
YOUR_API_KEY_HERE
YOUR_KAGGLE_USERNAME_HERE
YOUR_HF_TOKEN_HERE
```
Never use realistic, hash-like dummy strings that could trigger security scanner alerts or be mistaken for actual credentials.

---

## 2. Environment Variables & `.env` Protocol

- **Local Development Only:** `.env` files are strictly for local developer machine configuration.
- **Never Commit `.env`:** Ensure `.env` and all `.env.*` variants remain untracked.
- **`.env.example` Requirement:** When environment variables are introduced, provide a checked-in `.env.example` containing descriptive variable names and benign placeholders only.
- **Verify Gitignore:** Always verify that `.gitignore` actively ignores `.env` and credential files before committing changes.

---

## 3. Sensitive Data Protection

- **No Personal Identifiers:** Do not embed personal email addresses, private file paths (e.g., local home directories containing usernames), or private machine metadata in source code, documentation, or commit messages.
- **Sanitize Experiment Logs:** Ensure that evaluation traces, test outputs, and diagnostic logs generated in `runs/` or `experiments/` do not capture host credentials, authorization tokens, or sensitive environment dumps.
- **Dataset Privacy:** Never commit proprietary, non-public, or raw competition datasets to the Git repository.

---

## 4. Shell Command Safety & Destructive Operations

Autonomous agents and developers must exercise extreme caution when running shell commands via terminal tools:

### High-Risk Operations
Before executing any of the following, inspect and verify the exact target path and scope:
- Directory removal (`rm -rf`, `Remove-Item -Recurse -Force`)
- Git state manipulation (`git reset --hard`, `git clean -fd`, `git checkout -- .`)
- History rewrites and force pushes (`git push --force`)
- Overwriting existing files (`write_file` or redirection `>`)
- Destructive migration or cleanup scripts

### Safety Rules
1. **Never "Clean Up" Blindly:** Do not execute recursive removal commands to "tidy up" without first listing the exact files targeted.
2. **Explicit Paths:** Always specify exact, fully-qualified or unambiguous relative paths rather than wildcards (`*`) in destructive commands.
3. **Workspace Isolation:** All repository modification commands must be confined within the designated project root or sandbox `/workspace`.

---

## 5. Network & Sandbox Isolation

- **No Unauthorized Network Calls:** Competition code must operate entirely self-contained. Do not write code that assumes runtime internet access, dynamic downloads of models, or external API calls during evaluation.
- **Respect Sandbox Boundaries:** Adhere strictly to the sandbox boundaries enforced by Docker and the competition harness. Never attempt directory traversal outside `/workspace` or bypass sandbox security controls.

---

## 6. Supply Chain Integrity

- **Verified Sources Only:** Install dependencies exclusively from trusted indices (PyPI, official wheels provided in the competition package).
- **No Untrusted Scripts:** Never execute remote scripts (`curl ... | sh` or `Invoke-WebRequest ... | iex`) or run unvetted third-party binaries.
- **Pin Dependencies:** Maintain explicit, pinned dependencies in configuration manifests to ensure deterministic, reproducible builds and avoid supply chain drift.
