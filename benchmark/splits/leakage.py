"""Cross-split leakage validation and verification subsystem (Stage 29 Phase 14).

Verifies:
1. Task IDs are unique within each split.
2. No task ID appears in multiple splits.
3. No duplicate task problem statement or fingerprint crosses splits.
4. Repository identities do not cross splits when policy requires repository isolation.
5. Source snapshot (base_commit) overlap never crosses splits.
6. Exact accounting completeness: DEV + VALIDATION + HELD_OUT + EXCLUSIONS == SOURCE.
7. Every split task exists in source and has not been silently altered.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from benchmark.splits.hashing import compute_task_fingerprint
from benchmark.splits.models import ExclusionRecord, LeakageAuditReport, SplitPolicyType


class LeakageValidationError(Exception):
    """Raised when critical benchmark leakage or integrity violation is detected."""


def validate_split_leakage(
    splits: dict[str, list[dict[str, Any]]],
    source_records: list[dict[str, Any]],
    policy_name: str,
    exclusions: list[ExclusionRecord] | None = None,
) -> LeakageAuditReport:
    """Performs rigorous leakage audit across all benchmark splits."""
    exclusions = exclusions or []
    excluded_ids = {e.instance_id for e in exclusions}

    checks: dict[str, bool] = {}
    split_names = list(splits.keys())

    # Map task_id -> set of split names
    task_split_map: dict[str, set[str]] = defaultdict(set)
    # Map repo -> set of split names
    repo_split_map: dict[str, set[str]] = defaultdict(set)
    # Map commit -> set of split names
    commit_split_map: dict[str, set[str]] = defaultdict(set)
    # Map text fingerprint -> set of split names
    text_fingerprint_map: dict[str, set[str]] = defaultdict(set)

    # 1. Internal uniqueness within each split
    internal_unique = True
    for s_name, tasks in splits.items():
        seen_in_split = set()
        for t in tasks:
            tid = str(t.get("instance_id", "")).strip()
            if tid in seen_in_split:
                internal_unique = False
            seen_in_split.add(tid)
            task_split_map[tid].add(s_name)

            repo = str(t.get("repo", "")).strip()
            if repo:
                repo_split_map[repo].add(s_name)

            commit = str(t.get("base_commit", "")).strip()
            if commit:
                commit_split_map[commit].add(s_name)

            problem = str(t.get("problem_statement", "")).replace("\r\n", "\n").strip()
            if problem:
                text_fingerprint_map[problem].add(s_name)

    checks["internal_uniqueness"] = internal_unique

    # 2. Cross-split task ID overlap
    cross_split_tasks = [tid for tid, s_names in task_split_map.items() if len(s_names) > 1]
    checks["cross_split_task_disjointness"] = len(cross_split_tasks) == 0

    # 3. Cross-split duplicate problem statements
    cross_split_duplicate_text = [
        prob[:80] for prob, s_names in text_fingerprint_map.items() if len(s_names) > 1
    ]
    checks["no_cross_split_duplicate_text"] = len(cross_split_duplicate_text) == 0

    # 4. Cross-split repository overlap
    cross_split_repos = {
        repo: sorted(list(s_names))
        for repo, s_names in repo_split_map.items()
        if len(s_names) > 1
    }
    if policy_name == SplitPolicyType.REPO_DISJOINT.value:
        checks["repository_isolation"] = len(cross_split_repos) == 0
    else:
        # Non-disjoint repo policy allows repos across splits
        checks["repository_isolation"] = True

    # 5. Cross-split commit overlap (Mandatory across ALL policies: tasks sharing base_commit must stay in same split)
    cross_split_commits = {
        commit: sorted(list(s_names))
        for commit, s_names in commit_split_map.items()
        if len(s_names) > 1
    }
    checks["commit_snapshot_isolation"] = len(cross_split_commits) == 0

    # 6. Source fidelity: All tasks in splits exist in source with matching fingerprint
    source_map = {str(r.get("instance_id", "")).strip(): r for r in source_records}
    source_fidelity = True
    for s_name, tasks in splits.items():
        for t in tasks:
            tid = str(t.get("instance_id", "")).strip()
            if tid not in source_map:
                source_fidelity = False
                break
            src_fp = compute_task_fingerprint(source_map[tid])
            split_fp = compute_task_fingerprint(t)
            if src_fp != split_fp:
                source_fidelity = False
                break
    checks["source_fidelity"] = source_fidelity

    # 7. Accounting completeness
    total_in_splits = sum(len(tasks) for tasks in splits.values())
    total_accounted = total_in_splits + len(exclusions)
    unaccounted_ids = []
    source_ids = set(source_map.keys())
    split_and_excl_ids = set(task_split_map.keys()) | excluded_ids
    for sid in source_ids:
        if sid not in split_and_excl_ids:
            unaccounted_ids.append(sid)

    checks["accounting_completeness"] = (total_accounted == len(source_records)) and len(unaccounted_ids) == 0

    # Determine overall status
    mandatory_checks = [
        checks["internal_uniqueness"],
        checks["cross_split_task_disjointness"],
        checks["no_cross_split_duplicate_text"],
        checks["commit_snapshot_isolation"],
        checks["source_fidelity"],
        checks["accounting_completeness"],
    ]
    if policy_name == SplitPolicyType.REPO_DISJOINT.value:
        mandatory_checks.append(checks["repository_isolation"])

    if all(mandatory_checks):
        overall_status = "PASS"
    elif not checks["commit_snapshot_isolation"] or not checks["cross_split_task_disjointness"]:
        overall_status = "FAIL"
    else:
        overall_status = "FAIL"

    return LeakageAuditReport(
        status=overall_status,
        cross_split_task_overlap=cross_split_tasks,
        cross_split_repo_overlap=cross_split_repos,
        cross_split_commit_overlap=cross_split_commits,
        duplicate_problem_statements=cross_split_duplicate_text,
        unaccounted_source_records=unaccounted_ids,
        checks=checks,
    )
