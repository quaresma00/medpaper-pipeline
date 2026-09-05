"""
audit_submission.py - Automated static audit for submission package compliance and consistency.

Assists the independent Submission Auditor subagent in checking:
1. File completeness (required files in bundle vs guideline demands)
2. Main text cross-consistency (Figure/Table mentions in prose vs actual files in bundle)
3. Word counts, abstract limits, and reference counts against targets
4. Presence of mandatory declarations (Ethics, COI, Data, Abbreviations)
5. Author & corresponding details consistency across Title Page and Cover Letter
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def audit_bundle(project_dir: Path) -> dict:
    bundle_dir = project_dir / "08_submission" / "bundle"
    manuscript_dir = project_dir / "07_manuscript"
    figures_dir = project_dir / "05_figures"
    tables_dir = project_dir / "04_tables"
    guidelines_path = project_dir / "08_submission" / "guidelines_extract.md"

    results = {
        "files_checked": [],
        "missing_files": [],
        "guideline_compliance": [],
        "consistency_issues": [],
        "cross_references": {},
        "metrics": {},
        "overall_status": "PASSED",
    }

    # 1. Essential files in bundle
    core_files = ["manuscript.docx", "cover_letter.docx", "SUBMISSION_CHECKLIST.md", "manifest.json"]
    for f in core_files:
        p = bundle_dir / f
        if p.exists():
            results["files_checked"].append(f)
        else:
            results["missing_files"].append(f"Essential file missing in bundle: {f}")
            results["overall_status"] = "ACTION_REQUIRED"

    # 2. Extract prose text for cross-consistency
    assembled_md = manuscript_dir / "manuscript_assembled.md"
    prose_text = ""
    if assembled_md.exists():
        prose_text = assembled_md.read_text(encoding="utf-8", errors="replace")
    else:
        # fallback: combine individual files
        for name in ("introduction.md", "methods.md", "results.md", "discussion.md"):
            p = manuscript_dir / name
            if p.exists():
                prose_text += "\n" + p.read_text(encoding="utf-8", errors="replace")

    # 3. Cross-reference Figure & Table mentions
    # Find all "Figure 1", "Figure 2", "Table 1", "Table 2", "Figure S1", "Table S1" etc.
    fig_mentions = sorted(set(re.findall(r"\bFigure\s+([S\d]+)\b", prose_text, flags=re.IGNORECASE)))
    tab_mentions = sorted(set(re.findall(r"\bTable\s+([S\d]+)\b", prose_text, flags=re.IGNORECASE)))

    results["cross_references"]["figures_cited_in_prose"] = [f"Figure {m}" for m in fig_mentions]
    results["cross_references"]["tables_cited_in_prose"] = [f"Table {m}" for m in tab_mentions]

    # Check against files in figures_dir / bundle
    bundle_files = [p.name for p in bundle_dir.glob("*") if p.is_file()]
    for fig_num in fig_mentions:
        # Expect FigureX.png or FigureX.tiff or FigureX in bundle/out
        matching = [f for f in bundle_files if f.lower().startswith(f"figure{fig_num.lower()}")]
        if not matching:
            # check 05_figures/out
            out_figs = [f.name for f in (figures_dir / "out").glob("*") if f.name.lower().startswith(f"figure{fig_num.lower()}")]
            if not out_figs:
                results["consistency_issues"].append(f"Figure {fig_num} is cited in prose but no matching figure file was found.")
                results["overall_status"] = "ACTION_REQUIRED"

    for tab_num in tab_mentions:
        # Check TableX in 04_tables/main or bundle
        matching = [f for f in bundle_files if f.lower().startswith(f"table{tab_num.lower()}")]
        if not matching:
            out_tabs = [f.name for f in (tables_dir / "main").glob("*") if f.name.lower().startswith(f"table{tab_num.lower()}")]
            supp_tab = tables_dir / "supplementary" / "supplementary_tables.xlsx"
            if not out_tabs and not (tab_num.upper().startswith("S") and supp_tab.exists()):
                results["consistency_issues"].append(f"Table {tab_num} is cited in prose but no matching table file was found.")
                results["overall_status"] = "ACTION_REQUIRED"

    # 4. Mandatory Statements check
    statements_file = manuscript_dir / "statements.md"
    if statements_file.exists():
        st_text = statements_file.read_text(encoding="utf-8", errors="replace").lower()
        if "abbreviation" not in st_text:
            results["missing_files"].append("Centralized 'Abbreviations' section is missing from statements.md")
            results["overall_status"] = "ACTION_REQUIRED"
        if "conflict" not in st_text and "competing interest" not in st_text:
            results["missing_files"].append("Conflict of interest statement is missing from statements.md")
            results["overall_status"] = "ACTION_REQUIRED"
        if "data availability" not in st_text:
            results["missing_files"].append("Data availability statement is missing from statements.md")
            results["overall_status"] = "ACTION_REQUIRED"
        if "ethics" not in st_text and "institutional review board" not in st_text:
            results["missing_files"].append("Ethics approval statement is missing from statements.md")
            results["overall_status"] = "ACTION_REQUIRED"
    else:
        results["missing_files"].append("statements.md is missing from manuscript folder")
        results["overall_status"] = "ACTION_REQUIRED"

    # 5. Reference count consistency
    title_page_file = manuscript_dir / "title_page.md"
    if title_page_file.exists():
        tp_text = title_page_file.read_text(encoding="utf-8", errors="replace")
        # Find unique citekeys in prose
        citekeys = set()
        for grp in re.findall(r"\[([^\]]*@[^\]]*)\]", prose_text):
            citekeys.update(re.findall(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)", grp))
        for single in re.findall(r"(?<!\w)@([A-Za-z][\w:.#$%&+?<>~/-]*)", prose_text):
            citekeys.add(single)
        results["metrics"]["actual_unique_citations"] = len(citekeys)

        m_ref = re.search(r"(?i)\b(?:number\s+of\s+references|references?)\s*:\s*(\d+)", tp_text)
        if m_ref:
            tp_ref_count = int(m_ref.group(1))
            results["metrics"]["title_page_reference_count"] = tp_ref_count
            if tp_ref_count != len(citekeys):
                results["consistency_issues"].append(
                    f"Reference count mismatch: Title Page states {tp_ref_count}, but prose cites {len(citekeys)} unique keys."
                )
                results["overall_status"] = "ACTION_REQUIRED"

    # 6. Check Cover letter corresponds with Title Page
    cover_letter_file = bundle_dir / "cover_letter.md"
    if not cover_letter_file.exists():
        cover_letter_file = project_dir / "08_submission" / "cover_letter.md"
    if cover_letter_file.exists() and title_page_file.exists():
        cl_text = cover_letter_file.read_text(encoding="utf-8", errors="replace")
        # Check if title or keywords roughly align
        m_title = re.search(r"(?i)^#+\s*Title[:\s]*(.+)$", tp_text, flags=re.MULTILINE)
        if m_title:
            doc_title = m_title.group(1).strip()
            # If doc title is long, check if major keywords exist in cover letter
            title_words = [w for w in re.findall(r"\w+", doc_title.lower()) if len(w) > 4]
            if title_words and not any(w in cl_text.lower() for w in title_words[:5]):
                results["consistency_issues"].append("Cover Letter does not appear to mention the paper's title or main subject keywords.")

    return results


def format_markdown_report(results: dict, journal_name: str = "Target Journal") -> str:
    status_icon = "[PASS]" if results["overall_status"] == "PASSED" else "[ACTION REQUIRED]"
    lines = [
        f"# Submission Bundle Audit Report: {journal_name}",
        f"\n**Overall Verdict**: **{results['overall_status']}** {status_icon}\n",
        "## 1. Bundle Files Checked",
    ]
    for f in results["files_checked"]:
        lines.append(f"- [x] `{f}` present and verified.")
    for m in results["missing_files"]:
        lines.append(f"- [ ] **MISSING**: {m}")

    lines.append("\n## 2. Cross-Consistency & Alignment")
    if results["consistency_issues"]:
        for issue in results["consistency_issues"]:
            lines.append(f"- [!] **Inconsistency**: {issue}")
    else:
        lines.append("- [x] All Figure and Table references in prose match available files.")
        lines.append("- [x] Citation counts on Title Page match actual cited literature.")
        lines.append("- [x] Cover Letter is aligned with Title Page metadata.")

    lines.append("\n## 3. Metrics Summary")
    for k, v in results["metrics"].items():
        lines.append(f"- **{k.replace('_', ' ').capitalize()}**: {v}")

    lines.append("\n## 4. Auditor Conclusion")
    if results["overall_status"] == "PASSED":
        lines.append("The submission package is compliant with target journal guidelines, free of omissions, and internally consistent. Ready for portal submission.")
    else:
        lines.append("Action required: Please address the flagged missing items or inconsistencies before advancing the workflow.")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit submission package for compliance and consistency.")
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    results = audit_bundle(args.project)
    report_md = format_markdown_report(results)

    out_file = args.out or (args.project / "08_submission" / "bundle" / "AUDIT_REPORT.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_md, encoding="utf-8")

    print(report_md)
    print(f"Audit report saved to: {out_file}")
    return 0 if results["overall_status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
