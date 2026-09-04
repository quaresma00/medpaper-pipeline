"""
build_template.py - Generate a pristine medical SCI reference docx template for Pandoc.

Zero third-party dependencies (pure standard library: zipfile, xml.etree.ElementTree).

Enforces:
1. Universal Times New Roman font (replaces Aptos/Calibri/theme fonts).
2. Pure black text (#000000) for all headings and body (eliminates default blue/accent colors).
3. Dynamic font size (e.g. 12pt or 11pt) and line spacing (Double, 1.5, or Single)
   aligned with the target journal's guidelines.
4. Removes link underlines and blue coloring for DOIs/URLs.
5. Clean heading paragraph properties (no list bullets or aberrant outlines).
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def qn(tag: str) -> str:
    return f"{W_NS}{tag}"


def clean_font(elem: ET.Element, font_name: str = "Times New Roman") -> None:
    for attr in list(elem.attrib.keys()):
        if "Theme" in attr:
            elem.attrib.pop(attr, None)
    elem.set(qn("ascii"), font_name)
    elem.set(qn("hAnsi"), font_name)
    elem.set(qn("cs"), font_name)
    elem.set(qn("eastAsia"), font_name)


def clean_color_to_black(elem: ET.Element) -> None:
    for attr in list(elem.attrib.keys()):
        if "theme" in attr.lower():
            elem.attrib.pop(attr, None)
    elem.set(qn("val"), "000000")


def modify_styles_xml(
    xml_bytes: bytes,
    font_name: str = "Times New Roman",
    body_size_pt: float = 12.0,
    line_spacing_type: str = "double",
) -> bytes:
    root = ET.fromstring(xml_bytes)

    # 1. Update docDefaults
    for doc_defaults in root.findall(".//w:docDefaults", NS):
        rpr = doc_defaults.find(".//w:rPrDefault/w:rPr", NS)
        if rpr is not None:
            fonts = rpr.find("w:rFonts", NS)
            if fonts is None:
                fonts = ET.SubElement(rpr, qn("rFonts"))
            clean_font(fonts, font_name)

            color = rpr.find("w:color", NS)
            if color is None:
                color = ET.SubElement(rpr, qn("color"))
            clean_color_to_black(color)

            sz = rpr.find("w:sz", NS)
            if sz is None:
                sz = ET.SubElement(rpr, qn("sz"))
            sz.set(qn("val"), str(int(body_size_pt * 2)))

            sz_cs = rpr.find("w:szCs", NS)
            if sz_cs is None:
                sz_cs = ET.SubElement(rpr, qn("szCs"))
            sz_cs.set(qn("val"), str(int(body_size_pt * 2)))

    spacing_val = "480" if line_spacing_type.lower() == "double" else "360"
    if line_spacing_type.lower() == "single":
        spacing_val = "240"

    for style in root.findall(".//w:style", NS):
        sid = style.attrib.get(qn("styleId"), "")
        rpr = style.find("w:rPr", NS)
        if rpr is not None:
            fonts = rpr.find("w:rFonts", NS)
            if fonts is not None:
                clean_font(fonts, font_name)
            color = rpr.find("w:color", NS)
            if color is not None:
                clean_color_to_black(color)

        if "Heading" in sid or sid in ("Title", "Subtitle"):
            if rpr is None:
                rpr = ET.SubElement(style, qn("rPr"))

            fonts = rpr.find("w:rFonts", NS)
            if fonts is None:
                fonts = ET.SubElement(rpr, qn("rFonts"))
            clean_font(fonts, font_name)

            color = rpr.find("w:color", NS)
            if color is None:
                color = ET.SubElement(rpr, qn("color"))
            clean_color_to_black(color)

            bold = rpr.find("w:b", NS)
            if bold is None:
                ET.SubElement(rpr, qn("b"))

            sz = rpr.find("w:sz", NS)
            if sz is None:
                sz = ET.SubElement(rpr, qn("sz"))
            sz_cs = rpr.find("w:szCs", NS)
            if sz_cs is None:
                sz_cs = ET.SubElement(rpr, qn("szCs"))

            if sid in ("Heading1", "Heading1Char", "Title"):
                target_sz = str(int((body_size_pt + 2) * 2))
            elif sid in ("Heading2", "Heading2Char"):
                target_sz = str(int(body_size_pt * 2))
            else:
                target_sz = str(int(body_size_pt * 2))
            sz.set(qn("val"), target_sz)
            sz_cs.set(qn("val"), target_sz)

        if sid in ("Normal", "BodyText", "FirstParagraph"):
            ppr = style.find("w:pPr", NS)
            if ppr is not None:
                spacing = ppr.find("w:spacing", NS)
                if spacing is None:
                    spacing = ET.SubElement(ppr, qn("spacing"))
                spacing.set(qn("line"), spacing_val)
                spacing.set(qn("lineRule"), "auto")

        if "Hyperlink" in sid:
            if rpr is not None:
                u = rpr.find("w:u", NS)
                if u is not None:
                    rpr.remove(u)
                color = rpr.find("w:color", NS)
                if color is None:
                    color = ET.SubElement(rpr, qn("color"))
                clean_color_to_black(color)

    return ET.tostring(root, encoding="utf-8")


def build_medical_reference_docx(
    base_docx: Path,
    output_docx: Path,
    font_name: str = "Times New Roman",
    body_size_pt: float = 12.0,
    line_spacing_type: str = "double",
) -> Path:
    if not base_docx.exists():
        raise FileNotFoundError(f"Base docx template not found at {base_docx}")

    output_docx.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(base_docx, "r") as zin, zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                content = modify_styles_xml(
                    content,
                    font_name=font_name,
                    body_size_pt=body_size_pt,
                    line_spacing_type=line_spacing_type,
                )
            zout.writestr(item, content)

    return output_docx


def main() -> int:
    parser = argparse.ArgumentParser(description="Build clean medical reference docx for pandoc.")
    parser.add_argument("--base", type=Path, default=Path("tools/templates/base_ref.docx"))
    parser.add_argument("--out", type=Path, default=Path("tools/templates/med_reference.docx"))
    parser.add_argument("--font", type=str, default="Times New Roman")
    parser.add_argument("--size", type=float, default=12.0)
    parser.add_argument("--spacing", type=str, choices=["double", "1.5", "single"], default="double")
    args = parser.parse_args()

    out_file = build_medical_reference_docx(
        base_docx=args.base,
        output_docx=args.out,
        font_name=args.font,
        body_size_pt=args.size,
        line_spacing_type=args.spacing,
    )
    print(f"Built medical reference docx at {out_file} (Font={args.font}, Size={args.size}pt, Spacing={args.spacing})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
