# Candidate E11 Experiment Report: Recovery Paths V1

**Candidate ID:** E11  
**Parent Candidate:** E10  
**Parent Git Commit:** `7e2fd4aa707c62b6ba03d0adcf27b1212d05bb84`  
**Date:** 2026-09-26  
**Status:** Validated (Structural validation only; execution unasserted)

---

## 1. Motivation and Purpose (Stage 20)

Autonomous software engineering agents operating across complex repositories face predictable failure modes: test failures, regressions, ambiguous localization, tool execution errors, and impending budget limits. While Stage 18 provided diagnostic classification (*What kind of failure just occurred?*) and Stage 19 provided temporal progress monitoring (*Has the agent ceased making meaningful progress?*), agents previously lacked a systematic, bounded controller to navigate out of dead-ends.

Stage 20 implements **Recovery Paths V1** to answer:
$$\text{"What bounded change of investigation or repair should the agent make after a recognized failure or no-progress condition?"}$$

---

## 2. E10 → E11 Architecture Delta

```text
Candidate E10 (Stage 19):
  Model: gemma-4-31b-it-qat-w4a16-ct
  Tools: 9 competition tools
  Skills: [skills/test_strategy, skills/repo_triage]
  Policy: Repository triage + hybrid localization + testing strategy + 8-class failure taxonomy + no-progress detection

Candidate E11 (Stage 20):
  Model: gemma-4-31b-it-qat-w4a16-ct (Preserved identical)
  Tools: 9 competition tools (Preserved identical; zero tools added or removed)
  Skills: [skills/test_strategy, skills/repo_triage] (Preserved identical)
  Delta: Added Recovery Paths V1 (RecoveryControllerV1, policy rules for 5 canonical recovery families,
         safe-change ownership checks, bounded retry/action limits),
         prompt instruction establishing bounded recovery behavior,
         and structured recording into TaskState evidence.
```

---

## 3. The Five Canonical Recovery Families

1. **Search Fallback**: Laddering `semantic -> exact search -> tree inspection -> graph`. Halts exploratory queries once direct source evidence explains the defect; obeys existing E6 retrieval limits.
2. **Test-Failure Recovery**: Laddering `classify -> inspect diff -> inspect stack/call path -> revise hypothesis`. Guided by E9 failure taxonomy; prioritizes minimal targeted verification before broadening.
3. **Bad-Edit Recovery**: Laddering `inspect diff -> repair/revert -> rerun targeted test`. Strictly adheres to Safe Change Ownership (never reverts pre-existing user files or performs repository-wide resets).
4. **Tool-Failure Recovery**: Laddering `bounded retry -> alternate tool -> continue or terminate`. Enforces a single retry bound for transient tool failures; never retries deterministic syntax errors; routes to compatible alternate tools.
5. **Budget-Pressure Recovery**: Laddering `stop low-value exploration -> targeted validation -> final review`. Triggered under remaining tool call ($\le 10$) or time ($\le 300\text{s}$) thresholds.

---

## 4. Safe Change Ownership & Invariant Safeguards

- **Strict File-Level Isolation**: Files are reverted or repaired only if they belong exclusively to `agent_owned_files` and NOT `unrelated_modified_files`.
- **Pre-Existing Changes Protected**: Any modified file originating prior to the agent session cannot be touched. Ambiguous ownership causes recovery to fall back to hypothesis revision (`REVISE_HYPOTHESIS`).
- **No Blanket Rollback**: Destructive repository-wide resets (`git reset --hard`, `git checkout .`, `git clean -fdx`) are strictly prohibited.
- **Bounded Attempts**: Each recovery path allows at most 2 attempts (`MAX_PATH_ATTEMPTS = 2`) before path exhaustion, preventing infinite recovery loops.

---

## 5. Structural Validation Results

### 5.1. Submission Validator Output
```text
=== Validating Submission Directory: experiments\candidates\E11 ===
Total Files Inspected: 4
Total YAML Files:      1
Total Unpacked Size:   26,432 bytes (0.03 MB)
Discovered Models:     ['gemma-4-31b-it-qat-w4a16-ct']

RESULT: PASSED (Schema, single-model rule, and limits verified)
```

### 5.2. SHA-256 Hashes
- **E11 `agent.yaml`**: `688e0269c966db0f7dd367735190dbd3fa193a69c73dc7b3d48eff63237da01a`
- **E11 `root.md`**: `42a895fe99b5c537c348e92f02d7c906185b32afb450f393cf0e8255bd407356`
- **Canonical `test_strategy/SKILL.md`**: `3d027b0f9a7f830bfc68452cc98d962bb702ab16963a62574fcd4e85e31b7148` (Invariant)
- **Canonical `repo_triage/SKILL.md`**: `ac7a967136bba6ebd085511595ecbbcd7b3c258927518bfede77cc82a9bb10ce` (Invariant)
- **Parent E10 `root.md`**: `4766117f671fd7fb4e4e8ade8afe46d7c9412fbe7255ee2a29f9b38ebc25b73f`
- **Parent E10 `agent.yaml`**: `779f70c0feeb9f89b577a62c73361afc3aae7823d86a05e23b6fc246b66babf7`

---

## 6. Anti-Fabrication Disclosures

In strict adherence to `AGENTS.md`:
1. **No Live Gemma Inference**: Candidate E11 has not been executed against live Gemma 4 inference on this workstation.
2. **No Official Benchmark Execution**: Benchmark evaluation has not been executed for E11.
3. **No Pass Rate Claim**: `pass_rate: null`, `recovery_success_rate: null`.
4. **No Performance Claims**: No claim is asserted that recovery paths improve pass rates until empirical measurements on official competition platforms demonstrate it.
5. **No Stage 21+ Features**: Scout, Debugger, Reviewer, multi-agent orchestration, context compaction, and LoRA adapters are strictly excluded.
