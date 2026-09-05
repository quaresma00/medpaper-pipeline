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
   - # References heading with ::: {#refs} ::: anchor so Pandoc citeproc places bibliography BEFORE Figure Legends
   - # Figure Legends (stripped of Abbreviations, visual guide only, strictly at manuscript end)
5. Compiling manuscript.docx with pandoc citeproc against refs.bib and journal CSL.
6. Post-processing docx:
   - Flattening all hyperlinks to plain text runs (eliminates blue color, underlines, and reveals hidden breaks)
   - Converting all manual line breaks (<w:br/> without page/column type) to genuine hard paragraphs (<w:p>)
   - Removing all outlineLvl and numPr attributes to eliminate black folding boxes
7. Compiling cover_letter.docx and supplementary_materials.docx with identical typography and cleaning.
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W_NS, "rel": REL_NS}


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
            for grp in re.findall(r"\[([^\]]*@[^\]]*)\]", text):
                keys.update(re.findall(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)", grp))
            for single in re.findall(r"(?<!\w)@([A-Za-z][\w:.#$%&+?<>~/-]*)", text):
                keys.add(single)
    return len(keys)


def calibrate_title_page_refcount(title_page_text: str, actual_ref_count: int) -> str:
    """Ensure Title Page states the real number of cited references, not the whole library size."""
    if not title_page_text:
        return title_page_text

    pattern = r"(?i)(\b(?:number\s+of\s+references|references?)\s*:\s*)\d+"
    if re.search(pattern, title_page_text):
        return re.sub(pattern, rf"\g<1>{actual_ref_count}", title_page_text)
    return title_page_text


def clean_markdown_soft_breaks(text: str) -> str:
    """Strip manual line break triggers (trailing backslashes, trailing whitespace, HTML br) from markdown prose."""
    if not text:
        return text
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'\\+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    return text


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
    """Clean figure legends: strip duplicate Abbreviations, format headings cleanly."""
    if not legend_text.strip():
        return ""

    blocks = re.split(r"(?m)(?=^(?:#+\s*)?Figure\s+[S\d]+)", legend_text)
    cleaned_blocks = []

    for block in blocks:
        b = block.strip()
        if not b:
            continue

        # Strip out Abbreviations block from individual legend (centralized in Declarations/Statements)
        b = re.sub(r"(?is)\bAbbreviations?:?\s*.*$", "", b).strip()

        # Format title e.g. "Figure 1. Flow diagram..." -> "**Figure 1.** Flow diagram..."
        m = re.match(r"^(?:#+\s*)?(Figure\s+[S\d]+[\.\:]?)\s*(.*)", b, re.IGNORECASE | re.DOTALL)
        if m:
            prefix = m.group(1).rstrip(":").rstrip(".")
            body = m.group(2).strip()
            b = f"**{prefix}.** {body}"

        cleaned_blocks.append(b)

    return "\n\n".join(cleaned_blocks)


def purify_docx_xml(root: ET.Element) -> bool:
    """Deeply purify docx OpenXML:

    1. Flatten all hyperlinks to plain text runs (eliminates blue color, underlines, and un-nests breaks)
    2. Split soft line breaks into hard paragraphs
    3. Remove outlineLvl and numPr from paragraphs
    """
    ET.register_namespace('w', W_NS)
    modified = False

    # 1. Flatten hyperlinks in all paragraphs
    for p in root.findall(f".//{{{W_NS}}}p"):
        hyperlinks = [c for c in list(p) if c.tag == f"{{{W_NS}}}hyperlink"]
        if hyperlinks:
            modified = True
            for hl in hyperlinks:
                idx = list(p).index(hl)
                p.remove(hl)
                for child in list(hl):
                    # Ensure child runs do not carry hyperlink color or underline
                    rPr = child.find(f"{{{W_NS}}}rPr")
                    if rPr is not None:
                        u = rPr.find(f"{{{W_NS}}}u")
                        if u is not None:
                            rPr.remove(u)
                        color = rPr.find(f"{{{W_NS}}}color")
                        if color is not None:
                            color.set(f"{{{W_NS}}}val", "000000")
                    p.insert(idx, child)
                    idx += 1

    # 2. Remove outlineLvl and numPr from paragraph properties
    for ppr in root.findall(f".//{{{W_NS}}}pPr"):
        for tag in ("outlineLvl", "numPr"):
            for node in ppr.findall(f"{{{W_NS}}}{tag}"):
                ppr.remove(node)
                modified = True

    # 3. Split manual line breaks (<w:br/> not page/column) into genuine hard paragraphs (<w:p>)
    for parent in root.iter():
        p_list = [c for c in list(parent) if c.tag == f"{{{W_NS}}}p"]
        if not p_list:
            continue

        for p in p_list:
            soft_brs = [
                br for br in p.findall(f".//{{{W_NS}}}br")
                if br.attrib.get(f"{{{W_NS}}}type") not in ("page", "column")
            ]
            if not soft_brs:
                continue

            pPr = p.find(f"{{{W_NS}}}pPr")
            pPr_copy = ET.fromstring(ET.tostring(pPr)) if pPr is not None else None

            new_paragraphs = []
            current_p = ET.Element(f"{{{W_NS}}}p")
            if pPr_copy is not None:
                current_p.append(ET.fromstring(ET.tostring(pPr_copy)))

            for child in list(p):
                if child == pPr:
                    continue
                if child.tag == f"{{{W_NS}}}r":
                    rPr = child.find(f"{{{W_NS}}}rPr")
                    current_r = ET.Element(f"{{{W_NS}}}r")
                    if rPr is not None:
                        current_r.append(ET.fromstring(ET.tostring(rPr)))

                    for r_elem in list(child):
                        if r_elem == rPr:
                            continue
                        if r_elem.tag == f"{{{W_NS}}}br" and r_elem.attrib.get(f"{{{W_NS}}}type") not in ("page", "column"):
                            # Close current run & paragraph
                            if len(current_r) > (1 if rPr is not None else 0):
                                current_p.append(current_r)
                            if len(current_p) > (1 if pPr_copy is not None else 0):
                                new_paragraphs.append(current_p)

                            # Start fresh hard paragraph
                            current_p = ET.Element(f"{{{W_NS}}}p")
                            if pPr_copy is not None:
                                current_p.append(ET.fromstring(ET.tostring(pPr_copy)))
                            current_r = ET.Element(f"{{{W_NS}}}r")
                            if rPr is not None:
                                current_r.append(ET.fromstring(ET.tostring(rPr)))
                        else:
                            current_r.append(r_elem)

                    if len(current_r) > (1 if rPr is not None else 0):
                        current_p.append(current_r)
                else:
                    current_p.append(child)

            if len(current_p) > (1 if pPr_copy is not None else 0):
                new_paragraphs.append(current_p)

            if new_paragraphs:
                idx = list(parent).index(p)
                parent.remove(p)
                for offset, np in enumerate(new_paragraphs):
                    parent.insert(idx + offset, np)
                modified = True

    return modified


def post_process_docx(docx_path: Path) -> None:
    """Purify generated docx file in-place: flatten hyperlinks, eliminate soft breaks, remove outlines."""
    if not docx_path.exists():
        return

    temp_buffer = io.BytesIO()

    with zipfile.ZipFile(docx_path, 'r') as zin:
        with zipfile.ZipFile(temp_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                content = zin.read(item.filename)
                if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                    try:
                        root = ET.fromstring(content)
                        if purify_docx_xml(root):
                            content = ET.tostring(root, encoding="utf-8")
                    except Exception:
                        content = re.sub(rb'<w:br(?:\s*/>|\s+w:type="textWrapping"\s*/>)', b'', content)

                zout.writestr(item, content)

    docx_path.write_bytes(temp_buffer.getvalue())


def assemble_manuscript_md(project_dir: Path) -> Path:
    """Combine sections into a unified markdown file ready for pandoc."""
    manuscript_dir = project_dir / "07_manuscript"
    figures_dir = project_dir / "05_figures"

    def read_part(name: str) -> str:
        p = manuscript_dir / name
        if not p.exists():
            return ""
        txt = p.read_text(encoding="utf-8", errors="ignore").strip()
        return clean_markdown_soft_breaks(txt)

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
        cleaned_legends = clean_legend_block(clean_markdown_soft_breaks(raw_legends))
        if cleaned_legends:
            legends = "# Figure Legends\n\n" + cleaned_legends

    # Combine with Pandoc ::: {#refs} anchor
    # This guarantees that Pandoc citeproc places the bibliography inside # References,
    # and keeps # Figure Legends strictly as the final section at the very end!
    parts = [
        title_page,
        abstract,
        intro,
        methods,
        results,
        discussion,
        statements,
        "# References\n\n::: {#refs}\n:::",
    ]

    combined = "\n\n".join([p for p in parts if p])

    if legends:
        combined += "\n\n" + legends + "\n"

    # Final pass of soft-break cleaning
    combined = clean_markdown_soft_breaks(combined)

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

    # Post-process docx
    post_process_docx(manuscript_docx)
    print(f"Rendered & purified (no soft arrows, no outlines, plain hyperlinks): {manuscript_docx}")

    # 4. Render cover_letter.docx
    cover_letter_md = bundle_dir / "cover_letter.md"
    if not cover_letter_md.exists():
        cover_letter_md = project_dir / "08_submission" / "cover_letter.md"
    if cover_letter_md.exists():
        cl_text = clean_markdown_soft_breaks(cover_letter_md.read_text(encoding="utf-8", errors="ignore"))
        temp_cl_md = cache_dir / "clean_cover_letter.md"
        temp_cl_md.write_text(cl_text, encoding="utf-8")

        cover_letter_docx = bundle_dir / "cover_letter.docx"
        cmd_cl = [
            "pandoc", str(temp_cl_md),
            f"--reference-doc={med_ref_docx}",
            "-o", str(cover_letter_docx),
        ]
        subprocess.run(cmd_cl, check=True)
        post_process_docx(cover_letter_docx)
        print(f"Rendered & purified: {cover_letter_docx}")

    # 5. Render supplementary_materials.docx
    supp_methods_md = project_dir / "07_manuscript" / "supplementary_methods.md"
    if supp_methods_md.exists():
        supp_text = clean_markdown_soft_breaks(supp_methods_md.read_text(encoding="utf-8", errors="ignore"))
        temp_supp_md = cache_dir / "clean_supp.md"
        temp_supp_md.write_text(supp_text, encoding="utf-8")

        supp_docx = bundle_dir / "supplementary_materials.docx"
        cmd_supp = [
            "pandoc", str(temp_supp_md),
            f"--reference-doc={med_ref_docx}",
            "-o", str(supp_docx),
        ]
        subprocess.run(cmd_supp, check=True)
        post_process_docx(supp_docx)
        print(f"Rendered & purified: {supp_docx}")

    print("\nAll submission bundle Word documents rendered and purified successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render publication-grade Word submission bundle.")
    parser.add_argument("--project", type=Path, default=Path("project"))
    parser.add_argument("--csl", type=Path, default=None)
    args = parser.parse_args()

    return render_all(args.project, args.csl)


if __name__ == "__main__":
    sys.exit(main())
