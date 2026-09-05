#!/usr/bin/env python3
"""Freeze or verify the submission package approved for independent review."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wfcore.packagefreeze import FREEZE_REL, verify_freeze, write_freeze  # noqa: E402


def get_review_prompt(project_dir: Path) -> str:
    """Generate prompt instructions for the Triple-Perspective Submission Reviewer subagent."""
    return f"""# Triple-Perspective Final Reviewer Subagent Prompt

You are the authoritative Independent Reviewer for a medical SCI submission package.
Your mission is to perform a comprehensive, single-pass **Triple-Perspective Final Review**:
1. **Independent Academic Reader**: Check readability, clarity, self-explanatory figures, and identify any incomprehensible or disjointed prose.
2. **Journal Editor & Reviewer**: Zero tolerance for low-level defects (cross-check numbers between Abstract, Results, and Tables/Figures; verify Figure/Table citation order; evaluate scientific innovation and Cover Letter persuasion).
3. **Submission Compliance Auditor**: Execute mechanical validation (`tools/audit/audit_submission.py`) to verify physical DOCX integrity, soft line breaks (zero down-arrows ↓), outline levels (zero outlineLvl), TIFF resolutions, and target journal guidelines.

## Execution Steps:
1. Verify package freeze:
   `uv run python tools/package_review.py verify --project {project_dir}`
2. Run compliance audit:
   `uv run python tools/audit/audit_submission.py --project {project_dir}`
3. Read the manuscript files, figures, tables, and cover letter in `{project_dir}/08_submission/bundle/` and `{project_dir}/07_manuscript/`.
4. Perform the 3-perspective review:
   - **Perspective A (Reader)**: Can an intelligent reader outside the immediate subfield understand the narrative? Are figure panels self-explanatory? Are all abbreviations explained centrally? Are there conceptual leaps?
   - **Perspective B (Editor)**: Are there low-level errors? Do numbers in Abstract match Results and Tables? Are Figure/Table numbers correctly referenced without mislabeling? Is the Cover Letter compelling?
   - **Perspective C (Compliance)**: Did physical docx audit pass? Are guidelines respected?
5. Write the final structured report to:
   `{project_dir}/08_submission/bundle/AUDIT_REPORT.md`
6. Verify package freeze again to prove read-only compliance:
   `uv run python tools/package_review.py verify --project {project_dir}`
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="freeze, verify, or generate prompt for final submission review")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "verify", "prompt"):
        command = sub.add_parser(name)
        command.add_argument("--project", type=Path, default=Path("project"))
        command.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    freeze = args.freeze.resolve() if args.freeze else project / Path(FREEZE_REL)
    try:
        if args.command == "prompt":
            print(get_review_prompt(project))
            return 0
        if args.command == "freeze":
            output = write_freeze(project, freeze)
            ok, problems, count = verify_freeze(project, output)
            if not ok:
                raise ValueError("; ".join(problems))
            print(f"froze {count} final-review file(s) -> {output}")
            return 0
        ok, problems, count = verify_freeze(project, freeze)
        if not ok:
            print("submission package changed after user confirmation:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 2
        print(f"verified {count} frozen final-review file(s); no changes detected")
        return 0
    except (OSError, ValueError) as exc:
        print(f"package review error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
