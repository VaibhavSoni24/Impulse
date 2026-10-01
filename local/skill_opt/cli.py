"""Command-Line Interface for Skill Optimization Loop (Stage 36 Section 40).

Provides commands:
- `--inventory`: inspect repository skill inventory and frozen status
- `--skill test_strategy/repo_triage`: select skill ID
- `--candidate S0/S1`: candidate ID
- `--parent S0`: parent candidate ID (default: S0)
- `--analyze`: inspect skill content, root duplication, and diagnostics
- `--diff`: display skill diff against parent
- `--report`: display candidate report.md
- `--matrix`: display top-level comparative matrix
- `--verify`: verify candidate artifacts, frozen baselines, and invariance
- `--json`: machine-readable JSON output
- `--dry-run`: read-only execution without baseline mutation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from local.skill_opt.analyzer import analyze_skill_content
from local.skill_opt.diff import diff_skills, render_skill_diff_md
from local.skill_opt.experiment import SkillExperimentManager
from local.skill_opt.inventory import SkillInventory
from local.skill_opt.models import SkillCandidateManifest, SkillScopeType
from local.skill_opt.validator import validate_skill_candidate_invariance


def run_skill_cli(argv: Optional[List[str]] = None) -> int:
    """CLI driver for the Skill Optimization Loop."""
    parser = argparse.ArgumentParser(
        description="IMPULSE Stage 36: Skill Optimization Loop CLI"
    )
    parser.add_argument("--inventory", action="store_true", help="Display repository skill inventory")
    parser.add_argument("--skill", type=str, default="test_strategy", help="Skill ID (e.g. test_strategy, repo_triage)")
    parser.add_argument("--candidate", type=str, default=None, help="Candidate ID (e.g. S0, S1)")
    parser.add_argument("--parent", type=str, default="S0", help="Parent candidate ID (default: S0)")
    parser.add_argument("--analyze", action="store_true", help="Inspect skill duplication and diagnostics")
    parser.add_argument("--diff", action="store_true", help="Display diff against parent")
    parser.add_argument("--report", action="store_true", help="Display candidate report.md")
    parser.add_argument("--matrix", action="store_true", help="Display top-level comparative matrix")
    parser.add_argument("--verify", type=str, nargs="?", const="DEFAULT", default=None, help="Verify candidate directory integrity")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--dry-run", action="store_true", help="Read-only execution without baseline mutation")

    args = parser.parse_args(argv)
    manager = SkillExperimentManager(repo_root=Path.cwd())
    inventory = SkillInventory(repo_root=Path.cwd())

    # 1. Inventory
    if args.inventory:
        skills = inventory.discover_skills()
        if args.json:
            print(json.dumps([s.to_dict() for s in skills], indent=2))
        else:
            print(inventory.render_inventory_md())
        return 0

    # 2. Matrix
    if args.matrix:
        matrix_path = manager.exp_root / "stage36_report.md"
        if not matrix_path.exists():
            manager.setup_canonical_candidates()
        content = matrix_path.read_text(encoding="utf-8")
        if args.json:
            print(json.dumps({"path": str(matrix_path), "content": content}, indent=2))
        else:
            print(content)
        return 0

    # 3. Verification
    if args.verify is not None:
        cand_id = args.candidate or "S0"
        skill_id = args.skill or "test_strategy"
        if args.verify != "DEFAULT":
            vpath = Path(args.verify)
            if vpath.is_dir():
                cand_id = vpath.name
                skill_id = vpath.parent.name
        cand_dir = manager.get_candidate_dir(skill_id, cand_id)
        if not cand_dir.exists():
            print(f"[FAIL] Candidate directory '{cand_dir}' does not exist.", file=sys.stderr)
            return 1

        required_files = [
            "SKILL.md", "manifest.json", "skill_diff.json", "skill_diff.md",
            "paired_results.jsonl", "paired_results.csv", "metrics.json", "report.md"
        ]
        missing = [f for f in required_files if not (cand_dir / f).exists()]
        if missing:
            print(f"[FAIL] Candidate '{skill_id}/{cand_id}' missing artifacts: {missing}", file=sys.stderr)
            return 1

        manifest_data = json.loads((cand_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest = SkillCandidateManifest.from_dict(manifest_data)
        ok, errs = validate_skill_candidate_invariance(manifest, repo_root=Path.cwd(), verify_frozen=True)
        if not ok:
            print(f"[FAIL] Candidate '{skill_id}/{cand_id}' validation failed:", file=sys.stderr)
            for e in errs:
                print(f"  - {e}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps({"status": "PASS", "candidate": f"{skill_id}/{cand_id}"}, indent=2))
        else:
            print(f"[PASS] Candidate '{skill_id}/{cand_id}' artifacts and frozen baselines verified.")
        return 0

    # 4. Analyze
    if args.analyze:
        cand_id = args.candidate or args.parent or "S0"
        skill_id = args.skill or "test_strategy"
        cand_dir = manager.get_candidate_dir(skill_id, cand_id)
        if not cand_dir.exists():
            manager.setup_canonical_candidates()
        skill_path = cand_dir / "SKILL.md"
        if not skill_path.exists():
            print(f"[FAIL] Skill file not found: {skill_path}", file=sys.stderr)
            return 1
        skill_text = skill_path.read_text(encoding="utf-8")

        root_prompt_path = manager.repo_root / "experiments" / "candidates" / "M0" / "prompts" / "root.md"
        root_prompt = root_prompt_path.read_text(encoding="utf-8") if root_prompt_path.exists() else ""
        scope = SkillScopeType.TESTING.value if "test" in skill_id else SkillScopeType.REPOSITORY_TRIAGE.value
        dup_report, diagnostics = analyze_skill_content(skill_text, root_prompt, scope)

        out = {
            "skill_id": skill_id,
            "candidate_id": cand_id,
            "duplication_report": dup_report.to_dict(),
            "diagnostics": diagnostics.to_dict(),
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"# Skill Content Analysis: {skill_id}/{cand_id}")
            print(f"- Total Lines: {dup_report.total_skill_lines}")
            print(f"- Exact Root Duplicates: {dup_report.exact_duplicate_lines}")
            print(f"- Near Duplicates: {dup_report.near_duplicate_lines}")
            print(f"- Unique Lines: {dup_report.unique_lines}")
            print(f"- Duplication Ratio: {dup_report.duplication_ratio:.2%}")
            print(f"- Scope Leakage: {'YES' if diagnostics.has_scope_leakage else 'NO'}")
            print(f"- Contradictions: {'YES' if diagnostics.has_contradictions else 'NO'}")
            print(f"- Bloat Detected: {'YES' if diagnostics.has_bloat else 'NO'}")
        return 0

    # 5. Diff
    if args.diff:
        skill_id = args.skill or "test_strategy"
        parent_id = args.parent or "S0"
        cand_id = args.candidate or "S1"
        p_dir = manager.get_candidate_dir(skill_id, parent_id)
        c_dir = manager.get_candidate_dir(skill_id, cand_id)
        if not p_dir.exists() or not c_dir.exists():
            manager.setup_canonical_candidates()
        p_text = (p_dir / "SKILL.md").read_text(encoding="utf-8")
        c_text = (c_dir / "SKILL.md").read_text(encoding="utf-8")
        diff_data = diff_skills(p_text, c_text, parent_id, cand_id)
        if args.json:
            print(json.dumps(diff_data, indent=2))
        else:
            print(render_skill_diff_md(diff_data))
        return 0

    # 6. Report
    if args.report:
        skill_id = args.skill or "test_strategy"
        cand_id = args.candidate or "S1"
        cand_dir = manager.get_candidate_dir(skill_id, cand_id)
        if not cand_dir.exists():
            manager.setup_canonical_candidates()
        report_file = cand_dir / "report.md"
        if not report_file.exists():
            print(f"[FAIL] Report file not found: {report_file}", file=sys.stderr)
            return 1
        content = report_file.read_text(encoding="utf-8")
        if args.json:
            print(json.dumps({"path": str(report_file), "content": content}, indent=2))
        else:
            print(content)
        return 0

    parser.print_help()
    return 0


def main() -> int:
    return run_skill_cli()
