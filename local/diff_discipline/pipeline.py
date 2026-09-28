"""Master Git review and repository hygiene pipeline for Stage 27.

Implements the deterministic 10-step final diff review sequence:
1. git status --short
2. git diff --stat
3. git diff --name-status
4. inspect tracked changed files
5. inspect untracked files
6. inspect suspicious ignored files
7. run artifact hygiene checks
8. run security / secret checks
9. evaluate test rerun necessity
10. produce comprehensive HygieneReport
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

from local.context_compaction.fingerprints import normalize_path
from local.diff_discipline.classifier import ArtifactClassifier
from local.diff_discipline.cleaner import SafeCleaner
from local.diff_discipline.detectors import (
    scan_content_for_debug_markers,
    scan_content_for_machine_paths,
    scan_content_for_secrets,
)
from local.diff_discipline.frozen_verifier import verify_frozen_artifacts
from local.diff_discipline.git_inspector import GitInspector
from local.diff_discipline.models import (
    ArtifactClass,
    ArtifactFinding,
    GitReviewSnapshot,
    HygieneAction,
    HygieneReport,
)
from local.diff_discipline.reference_checker import ReferenceChecker


class FinalDiffReviewPipeline:
    """Executes deterministic repository review and hygiene auditing."""

    def __init__(self, repo_root: Optional[str | Path] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.git_inspector = GitInspector(self.repo_root)
        self.ref_checker = ReferenceChecker(self.repo_root)
        self.classifier = ArtifactClassifier(self.repo_root)
        self.cleaner = SafeCleaner(self.repo_root)

    def run_review(
        self,
        auto_clean: bool = False,
        scan_all_tracked: bool = False,
    ) -> HygieneReport:
        """Runs the complete review sequence and produces a HygieneReport."""
        # 1-3. Git status and diff snapshot
        snapshot = self.git_inspector.inspect_snapshot()

        # Build reference cache
        self.ref_checker.build_cache()

        findings: list[ArtifactFinding] = []
        security_violations: list[str] = []

        # 4. Check modified tracked files
        for mod_path in snapshot.modified_files:
            is_ref = self.ref_checker.is_referenced(mod_path)
            f = self.classifier.classify_file(
                mod_path, is_tracked=True, is_referenced=is_ref
            )
            findings.append(f)

            # Deep inspect changed file content
            full_p = self.repo_root / mod_path
            if full_p.exists() and full_p.is_file():
                try:
                    content = full_p.read_text(encoding="utf-8", errors="ignore")
                    debug_findings = scan_content_for_debug_markers(
                        mod_path, content, is_tracked=True
                    )
                    findings.extend(debug_findings)

                    path_findings = scan_content_for_machine_paths(
                        mod_path, content, is_tracked=True
                    )
                    findings.extend(path_findings)

                    secret_findings = scan_content_for_secrets(
                        mod_path, content, is_tracked=True
                    )
                    findings.extend(secret_findings)
                    for sf in secret_findings:
                        security_violations.append(
                            f"Potential secret detected in {mod_path} (Line {sf.details.get('line_number')})"
                        )
                except OSError:
                    pass

        # 5. Untracked file audit (Phase 11)
        for untracked_path in snapshot.untracked_files:
            is_ref = self.ref_checker.is_referenced(untracked_path)
            f = self.classifier.classify_file(
                untracked_path, is_tracked=False, is_referenced=is_ref
            )
            findings.append(f)

            # Scan untracked file content if text
            full_p = self.repo_root / untracked_path
            if full_p.exists() and full_p.is_file():
                try:
                    content = full_p.read_text(encoding="utf-8", errors="ignore")
                    debug_findings = scan_content_for_debug_markers(
                        untracked_path, content, is_tracked=False
                    )
                    findings.extend(debug_findings)

                    sec_findings = scan_content_for_secrets(
                        untracked_path, content, is_tracked=False
                    )
                    findings.extend(sec_findings)
                    for sf in sec_findings:
                        security_violations.append(
                            f"Potential secret in untracked file: {untracked_path}"
                        )
                except OSError:
                    pass

        # Optional full-repo scan of all tracked files
        if scan_all_tracked:
            tracked = self.git_inspector.get_tracked_files()
            for t_path in tracked:
                if t_path in snapshot.modified_files:
                    continue  # already checked
                is_ref = self.ref_checker.is_referenced(t_path)
                f = self.classifier.classify_file(
                    t_path, is_tracked=True, is_referenced=is_ref
                )
                findings.append(f)

        # Conservative cleanup if requested
        if auto_clean:
            removable = [f for f in findings if f.recommended_action == HygieneAction.REMOVE]
            if removable:
                self.cleaner.execute_cleanup(removable, dry_run=False)
                # Re-snapshot after cleanup
                snapshot = self.git_inspector.inspect_snapshot()

        # 7-8. Verify frozen artifacts
        frozen_passed, frozen_details = verify_frozen_artifacts(self.repo_root)
        if not frozen_passed:
            for path, det in frozen_details.items():
                if det["status"] != "MATCH":
                    findings.append(
                        ArtifactFinding(
                            path=path,
                            artifact_class=ArtifactClass.REQUIRED_EXPERIMENT_ARTIFACT,
                            recommended_action=HygieneAction.REVIEW,
                            reason=f"Frozen artifact integrity violation: {det['status']} (expected {det['expected'][:8]}, got {det['actual'][:8]})",
                            confidence=1.0,
                            is_tracked=True,
                            is_referenced=True,
                            details=det,
                        )
                    )

        # 9. Test rerun evaluation
        # If any tracked python files in agent/, local/, or tests/ are modified, tests must rerun
        requires_rerun = any(
            (p.startswith("agent/") or p.startswith("local/") or p.startswith("tests/"))
            and p.endswith(".py")
            for p in snapshot.modified_files
        )

        # Summaries
        class_counts = Counter(f.artifact_class.value for f in findings)
        action_counts = Counter(f.recommended_action.value for f in findings)

        # Cleanliness condition:
        # A repository is clean if:
        # - zero security violations
        # - zero blocking findings (e.g. no REMOVE findings remain, no unverified frozen mismatches)
        has_removals = any(f.recommended_action == HygieneAction.REMOVE for f in findings)
        has_secrets = len(security_violations) > 0
        is_clean = not has_removals and not has_secrets and frozen_passed

        return HygieneReport(
            findings=findings,
            summary_by_class=dict(class_counts),
            summary_by_action=dict(action_counts),
            security_violations=security_violations,
            git_snapshot=snapshot,
            is_clean=is_clean,
            requires_test_rerun=requires_rerun,
        )

    def format_report(self, report: HygieneReport) -> str:
        """Formats the HygieneReport as human-readable markdown text."""
        lines: list[str] = []
        lines.append("# Final Diff Discipline & Repository Hygiene Report")
        lines.append("")
        lines.append(f"- **Timestamp:** {report.timestamp}")
        lines.append(f"- **Cleanliness Status:** {'CLEAN' if report.is_clean else 'ACTION REQUIRED'}")
        lines.append(f"- **Requires Test Rerun:** {'YES' if report.requires_test_rerun else 'NO'}")
        lines.append(f"- **Head Commit:** {report.git_snapshot.head_commit or 'N/A'}")
        lines.append(f"- **Branch:** {report.git_snapshot.branch}")
        lines.append("")

        lines.append("## Git Working Tree Snapshot")
        if report.git_snapshot.status_short:
            lines.append("```")
            lines.extend(report.git_snapshot.status_short[:20])
            if len(report.git_snapshot.status_short) > 20:
                lines.append(f"... ({len(report.git_snapshot.status_short) - 20} more lines)")
            lines.append("```")
        else:
            lines.append("Working tree clean (no modified or untracked files).")
        lines.append("")

        if report.git_snapshot.diff_stat:
            lines.append("### Diff Statistics")
            lines.append("```")
            lines.append(report.git_snapshot.diff_stat)
            lines.append("```")
            lines.append("")

        lines.append("## Summary by Action")
        for action in [HygieneAction.KEEP.value, HygieneAction.REVIEW.value, HygieneAction.REMOVE.value]:
            count = report.summary_by_action.get(action, 0)
            lines.append(f"- **{action}:** {count}")
        lines.append("")

        lines.append("## Summary by Artifact Category")
        for cls_name, count in sorted(report.summary_by_class.items()):
            lines.append(f"- `{cls_name}`: {count}")
        lines.append("")

        if report.security_violations:
            lines.append("## Security Findings")
            for sec in report.security_violations:
                lines.append(f"- [WARNING] {sec}")
            lines.append("")
        else:
            lines.append("## Security Findings")
            lines.append("Zero security or credential violations detected.")
            lines.append("")

        # Detail findings requiring review or removal
        actionable = [
            f for f in report.findings if f.recommended_action in (HygieneAction.REVIEW, HygieneAction.REMOVE)
        ]
        if actionable:
            lines.append("## Actionable Findings")
            for f in actionable[:25]:
                lines.append(f"- `[{f.recommended_action.value}]` **{f.path}** ({f.artifact_class.value}): {f.reason}")
            if len(actionable) > 25:
                lines.append(f"- ... and {len(actionable) - 25} more actionable items.")
            lines.append("")

        return "\n".join(lines)
