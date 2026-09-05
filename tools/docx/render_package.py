"""
render_package.py - Assemble and render publication-grade Word documents for the submission bundle.

Handles:
1. Dynamically parsing target journal guidelines (font size, line spacing) from guidelines_extract.md.
2. Generating a matched medical reference docx (Times New Roman, pure black, no link underlines).
3. Counting actual unique citations referenced in the text and auto-calibrating Title Page reference count.
4. Assembling the complete manuscript:
   - title_page.md (calibrated reference count, clean metadata)
   - abstract.md (with cleaned Keywords appended at end)
   - introduction.md, methods.md, results.md, discussion.md, statements.md (with centralized Abbreviations)
   - # References heading
   - # Figure Legends (stripped of Abbreviations, stripped of Results/Methods duplication, pure visual guide)
5. Compiling manuscript.docx with pandoc citeproc against refs.bib and journal CSL.
6. Compiling cover_letter.docx and supplementary_materials.docx.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def extract_guideline_formatting(guidelines_path: Path) -> tuple[float, str]:
    """Parse guidelines_extract.md for font size and line spacing preferences."""
    body_size = 12.0
    line_spacing = "double"

    if not guidelines_path.exists():
        return body_size, line_spacing

    text = guidelines_path.read_text(encoding="utf-8", errors="ignore").lower()

    if "11 pt" in text or "11-point" in text or "11pt" in text:
        body_size = 11.0
    elif "12 pt" in text or "12-point" in text or "12pt" in text:
        body_size = 12.0

    if "1.5 line" in text or "1.5-spaced" in text or "one and a half" in text:
        line_spacing = "1.5"
    elif "double" in text or "2.0 line" in text:
        line_spacing = "double"
    elif "single" in text:
        line_spacing = "single"

    return body_size, line_spacing


def count_actual_citations(project_dir: Path) -> int:
    """Extract all unique citation keys actually referenced in manuscript prose."""
    manuscript_dir = project_dir / "07_manuscript"
    keys: set[str] = set()
    for name in ("introduction.md", "methods.md", "results.md", "discussion.md", "statements.md"):
        p = manuscript_dir / name
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            # Pandoc citations: [@smith2020; @johnson2021] or @doe2022
            for grp in re.findall(r"\[([^\]]*@[^\]]*)\]", text):
                keys.update(re.findall(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)", grp))
            for single in re.findall(r"(?<!\w)@([A-Za-z][\w:.#$%&+?<>~/-]*)", text):
                keys.add(single)
    return len(keys)


def calibrate_title_page_refcount(title_page_text: str, actual_ref_count: int) -> str:
    """Ensure Title Page states the real number of cited references, not the whole library size."""
    if not title_page_text:
        return title_page_text

    # Match patterns like "Number of references: 50" or "References: 50"
    pattern = r"(?i)(\b(?:number\s+of\s+references|references?)\s*:\s*)\d+"
    if re.search(pattern, title_page_text):
        return re.sub(pattern, rf"\g<1>{actual_ref_count}", title_page_text)
    return title_page_text


def clean_keywords(text: str) -> str:
    """Clean MeSH / code qualifiers from keywords and ensure canonical placement at Abstract end."""
    kw_pattern = r'(?is)(?:#+\s*)?(?:Keywords?|Key\s*words?)(?:\s*\([^)]*\))?:?\s*(.+?)(?=\n\s*#|\Z)'
    m = re.search(kw_pattern, text)
    if not m:
        return text
    raw_kws = m.group(1).strip()

    parts = re.split(r'[;,\n]', raw_kws)
    cleaned = []
    for p in parts:
        p = p.strip().rstrip('.')
        if not p:
            continue
        if '/' in p:
            p = ' '.join([sp.strip() for sp in p.split('/') if sp.strip()])
        p = p.replace('&', 'and')
        words = p.split()
        if words:
            p = words[0].capitalize() + (' ' + ' '.join(words[1:]) if len(words) > 1 else '')
        if p and p not in cleaned:
            cleaned.append(p)

    final_kws = ', '.join(cleaned[:5])
    kw_line = f"**Keywords:** {final_kws}."

    text_without_kw = re.sub(kw_pattern, '', text).strip()
    return text_without_kw + '\n\n' + kw_line


def clean_legend_block(legend_text: str) -> str:
    """Clean figure legends: strip duplicate Abbreviations, strip Methods/Results bloat, ensure clean visual guide."""
    if not legend_text.strip():
        return ""

    blocks = re.split(r"(?m)(?=^(?:#+\s*)?Figure\s+[S\d]+)", legend_text)
    cleaned_blocks = []

    for block in blocks:
        b = block.strip()
        if not b:
            continue

        # Strip out Abbreviations block from individual legend (as it is in Declarations/Statements)
        b = re.sub(r"(?is)\bAbbreviations?:?\s*.*$", "", b).strip()

        # Format title e.g. "Figure 1. Flow diagram..." -> "**Figure 1.** Flow diagram..."
        m = re.match(r"^(?:#+\s*)?(Figure\s+[S\d]+[\.\:]?)\s*(.*)", b, re.IGNORECASE | re.DOTALL)
        if m:
            prefix = m.group(1).rstrip(":").rstrip(".")
            body = m.group(2).strip()
            # Clean header Markdown symbols
            b = f"**{prefix}.** {body}"

        cleaned_blocks.append(b)

    return "\n\n".join(cleaned_blocks)


def assemble_manuscript_md(project_dir: Path) -> Path:
    """Combine sections into a unified markdown file ready for pandoc."""
    manuscript_dir = project_dir / "07_manuscript"
    figures_dir = project_dir / "05_figures"

    def read_part(name: str) -> str:
        p = manuscript_dir / name
        return p.read_text(encoding="utf-8", errors="ignore").strip() if p.exists() else ""

    # Count real citations
    real_refs = count_actual_citations(project_dir)

    title_page = calibrate_title_page_refcount(read_part("title_page.md"), real_refs)
    abstract = clean_keywords(read_part("abstract.md"))
    intro = read_part("introduction.md")
    methods = read_part("methods.md")
    results = read_part("results.md")
    discussion = read_part("discussion.md")
    statements = read_part("statements.md")

    # Figure legends at the end of manuscript
    legends_file = figures_dir / "legends.md"
    legends = ""
    if legends_file.exists():
        raw_legends = legends_file.read_text(encoding="utf-8", errors="ignore").strip()
        cleaned_legends = clean_legend_block(raw_legends)
        if cleaned_legends:
            legends = "# Figure Legends\n\n" + cleaned_legends

    # Combine with clear boundaries
    parts = [
        title_page,
        abstract,
        intro,
        methods,
        results,
        discussion,
        statements,
        "# References",  # Explicit References header for Pandoc citeproc
    ]

    combined = "\n\n".join([p for p in parts if p])

    if legends:
        # Pandoc citeproc places the bibliography before or at the end;
        # We append Figure Legends as the final section
        combined += "\n\n" + legends + "\n"

    out_path = project_dir / "07_manuscript" / "manuscript_assembled.md"
    out_path.write_text(combined, encoding="utf-8")
    return out_path


def render_all(project_dir: Path, csl_path: Path | None = None) -> int:
    guidelines_path = project_dir / "08_submission" / "guidelines_extract.md"
    body_size, line_spacing = extract_guideline_formatting(guidelines_path)

    # 1. Build matched reference docx
    ref_builder = ROOT / "tools" / "docx" / "build_template.py"
    base_docx = ROOT / "tools" / "templates" / "base_ref.docx"
    cache_dir = project_dir / "08_submission" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    med_ref_docx = cache_dir / "med_reference.docx"

    cmd_template = [
        sys.executable, str(ref_builder),
        "--base", str(base_docx),
        "--out", str(med_ref_docx),
        "--font", "Times New Roman",
        "--size", str(body_size),
        "--spacing", line_spacing,
    ]
    subprocess.run(cmd_template, check=True)

    # 2. Assemble manuscript markdown
    assembled_md = assemble_manuscript_md(project_dir)

    # 3. Render manuscript.docx
    bundle_dir = project_dir / "08_submission" / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    manuscript_docx = bundle_dir / "manuscript.docx"
    bib_file = project_dir / "06_refs" / "refs.bib"

    pandoc_cmd = [
        "pandoc",
        str(assembled_md),
        f"--reference-doc={med_ref_docx}",
        "-o", str(manuscript_docx),
    ]
    if bib_file.exists():
        pandoc_cmd.extend(["--citeproc", f"--bibliography={bib_file}"])
    if csl_path and csl_path.exists():
        pandoc_cmd.append(f"--csl={csl_path}")

    print(f"Rendering manuscript.docx via Pandoc (Font=Times New Roman, Size={body_size}pt, Spacing={line_spacing})...")
    subprocess.run(pandoc_cmd, check=True)
    print(f"Rendered: {manuscript_docx}")

    # 4. Render cover_letter.docx
    cover_letter_md = bundle_dir / "cover_letter.md"
    if not cover_letter_md.exists():
        cover_letter_md = project_dir / "08_submission" / "cover_letter.md"
    if cover_letter_md.exists():
        cover_letter_docx = bundle_dir / "cover_letter.docx"
        cmd_cl = [
            "pandoc", str(cover_letter_md),
            f"--reference-doc={med_ref_docx}",
            "-o", str(cover_letter_docx),
        ]
        subprocess.run(cmd_cl, check=True)
        print(f"Rendered: {cover_letter_docx}")

    # 5. Render supplementary_materials.docx
    supp_methods_md = project_dir / "07_manuscript" / "supplementary_methods.md"
    if supp_methods_md.exists():
        supp_docx = bundle_dir / "supplementary_materials.docx"
        cmd_supp = [
            "pandoc", str(supp_methods_md),
            f"--reference-doc={med_ref_docx}",
            "-o", str(supp_docx),
        ]
        subprocess.run(cmd_supp, check=True)
        print(f"Rendered: {supp_docx}")

    print("\nAll submission bundle Word documents rendered successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render publication-grade Word submission bundle.")
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--csl", type=Path, default=None)
    args = parser.parse_args()

    return render_all(args.project, args.csl)


if __name__ == "__main__":
    sys.exit(main())
