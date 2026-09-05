"""Artifact-plan, table and figure structural checks."""
from __future__ import annotations

import json
import re

from .. import xlsxlite
from . import Ctx, Result, check

PLAN = "01_protocol/artifact_plan.json"
LEGENDS = "05_figures/legends.md"
CAPTIONS = "04_tables/table_captions.md"
QC = "05_figures/qc/qc_report.json"

ART_CITE_RE = re.compile(
    r"\b(?:(supplementary|supplemental|suppl\.?)\s+)?(figure|fig\.?|table)\s*(S?\d+)",
    re.I,
)
FENCE_RE = re.compile(r"```.*?```", re.S)
GROUPS = ("main_figures", "main_tables", "supp_figures", "supp_tables")


def _plan(ctx: Ctx) -> dict:
    return ctx.read_json(PLAN)


def _entries(plan: dict, groups=GROUPS) -> list[dict]:
    out = []
    for g in groups:
        for e in plan.get(g, []):
            e = dict(e)
            e["_group"] = g
            out.append(e)
    return out


def _canon(kind: str, num: str, supp: bool) -> str:
    kind = "Figure" if kind.lower().startswith("fig") else "Table"
    num = num.upper().lstrip("S")
    return f"{kind} {'S' if supp else ''}{num}"


def _plan_ids(plan: dict) -> set[str]:
    ids = set()
    for e in _entries(plan):
        supp = e["_group"].startswith("supp")
        m = re.search(r"(fig\w*|table)\s*(S?\d+)", str(e.get("id", "")), re.I)
        if m:
            ids.add(_canon(m.group(1), m.group(2), supp))
    return ids


# ---------------------------------------------------------------------------
@check("artifact_plan_sane")
def artifact_plan_sane(ctx: Ctx) -> Result:
    rel = ctx.spec.get("path", PLAN)
    if not ctx.p(rel).exists():
        return Result(False, "artifact_plan_sane", f"{rel} missing")
    try:
        plan = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "artifact_plan_sane", f"{rel} invalid JSON: {exc}")

    problems: list[str] = []
    max_fig = ctx.target("main_figures_max", 6)
    max_tab = ctx.target("main_tables_max", 5)
    if len(plan.get("main_figures", [])) > max_fig:
        problems.append(f"{len(plan['main_figures'])} main figures, cap {max_fig}")
    if len(plan.get("main_tables", [])) > max_tab:
        problems.append(f"{len(plan['main_tables'])} main tables, cap {max_tab}")
    if not plan.get("main_figures") and not plan.get("main_tables"):
        problems.append("no main display items planned")

    seen: set[str] = set()
    for e in _entries(plan):
        eid = str(e.get("id", "")).strip()
        tag = f"{e['_group']}:{eid or '<no id>'}"
        if not eid:
            problems.append(f"{e['_group']}: entry without an id")
            continue
        if eid in seen:
            problems.append(f"duplicate id {eid}")
        seen.add(eid)
        for field in ("title", "content", "source_results"):
            if not e.get(field):
                problems.append(f"{tag}: missing '{field}'")
        if not e.get("file"):
            problems.append(f"{tag}: missing 'file'")
        if e["_group"].endswith("figures"):
            if e.get("width") not in ("single", "double", "1.5"):
                problems.append(f"{tag}: width must be single | 1.5 | double")
            if not e.get("script"):
                problems.append(f"{tag}: missing 'script'")
            arch = e.get("archetype")
            if not arch:
                problems.append(f"{tag}: missing 'archetype' (see reference/archetypes.toml)")
            elif arch not in _known_archetypes():
                problems.append(f"{tag}: archetype '{arch}' is not in reference/archetypes.toml")
            elif arch == "other" and not e.get("archetype_rationale"):
                problems.append(f"{tag}: archetype 'other' requires 'archetype_rationale'")

    # supplementary tables share one workbook, distinct sheets
    supp = plan.get("supp_tables", [])
    files = {e.get("file") for e in supp if e.get("file")}
    if len(files) > 1:
        problems.append(f"supplementary tables spread over {len(files)} files; must be one workbook")
    sheets = [e.get("sheet") for e in supp]
    if len(sheets) != len(set(sheets)):
        problems.append("supplementary table sheet names are not unique")
    # main tables: one file each
    mfiles = [e.get("file") for e in plan.get("main_tables", [])]
    if len(mfiles) != len(set(mfiles)):
        problems.append("main tables must each live in their own xlsx file")

    # numbering must be 1..N with no gaps
    for group, prefix in (("main_figures", "Figure"), ("main_tables", "Table"),
                          ("supp_figures", "Figure S"), ("supp_tables", "Table S")):
        nums = []
        for e in plan.get(group, []):
            m = re.search(r"(\d+)\s*$", str(e.get("id", "")))
            if m:
                nums.append(int(m.group(1)))
        if nums and sorted(nums) != list(range(1, len(nums) + 1)):
            problems.append(f"{group}: numbering is not {prefix}1..{prefix}{len(nums)} (got {sorted(nums)})")

    if problems:
        return Result(False, "artifact_plan_sane", "; ".join(problems[:10]))
    n = len(_entries(plan))
    return Result(True, "artifact_plan_sane", f"{n} display item(s) planned, ids and files consistent")


@check("legends_cover_plan")
def legends_cover_plan(ctx: Ctx) -> Result:
    for rel in (PLAN, LEGENDS, CAPTIONS):
        if not ctx.p(rel).exists():
            return Result(False, "legends_cover_plan", f"{rel} missing")
    plan = _plan(ctx)
    problems: list[str] = []

    for rel, groups, minlen, what in (
        (LEGENDS, ("main_figures", "supp_figures"), 80, "figure legend"),
        (CAPTIONS, ("main_tables", "supp_tables"), 40, "table caption"),
    ):
        text = ctx.read(rel)
        blocks = _split_blocks(text)
        for e in _entries(plan, groups):
            eid = str(e.get("id", "")).strip()
            key = next((k for k in blocks if _same_id(k, eid)), None)
            if key is None:
                problems.append(f"{rel}: no {what} for {eid}")
            elif len(blocks[key].strip()) < minlen:
                problems.append(f"{rel}: {what} for {eid} is only {len(blocks[key].strip())} chars")
        if rel == CAPTIONS and "abbrevi" not in text.lower() and "footnote" not in text.lower():
            problems.append(f"{rel}: no footnote/abbreviation block anywhere - three-line tables need one")

    if problems:
        return Result(
            False,
            "legends_cover_plan",
            "; ".join(problems[:8]),
            ["Every planned display item needs a self-contained legend written before the figure is drawn."],
        )
    return Result(True, "legends_cover_plan", "every planned figure and table has a substantive legend")


@check("artifact_refs_consistent")
def artifact_refs_consistent(ctx: Ctx) -> Result:
    if not ctx.p(PLAN).exists():
        return Result(False, "artifact_refs_consistent", f"{PLAN} missing")
    plan = _plan(ctx)
    planned = _plan_ids(plan)
    cited: set[str] = set()
    scanned = []
    for rel in ctx.spec.get("paths", []):
        if not ctx.p(rel).exists():
            continue
        scanned.append(rel)
        text = FENCE_RE.sub(" ", ctx.read(rel))
        for supp, kind, num in ART_CITE_RE.findall(text):
            cited.add(_canon(kind, num, bool(supp) or num.upper().startswith("S")))
    if not scanned:
        return Result(False, "artifact_refs_consistent", "no manuscript files to scan")

    problems = []
    ghosts = sorted(cited - planned)
    if ghosts:
        problems.append(f"cited but not planned: {', '.join(ghosts)}")
    if ctx.spec.get("require_all_cited"):
        orphans = sorted(planned - cited)
        if orphans:
            problems.append(f"planned but never cited: {', '.join(orphans)}")
    if ctx.spec.get("require_rendered"):
        for e in _entries(plan):
            f = e.get("file")
            if f and not ctx.p(f).exists():
                problems.append(f"{e.get('id')}: {f} not rendered")
    if problems:
        return Result(
            False,
            "artifact_refs_consistent",
            "; ".join(problems[:8]),
            ["Text and artifact plan must agree exactly. Fix whichever is wrong; do not silently renumber."],
        )
    return Result(
        True,
        "artifact_refs_consistent",
        f"{len(cited)} artifact citation(s) across {len(scanned)} file(s) all match the plan",
    )


# ---------------------------------------------------------------------------
@check("tables_match_plan")
def tables_match_plan(ctx: Ctx) -> Result:
    plan = _plan(ctx)
    problems = []
    for e in _entries(plan, ("main_tables", "supp_tables")):
        f = e.get("file")
        if not f:
            continue
        p = ctx.p(f)
        if not p.exists():
            problems.append(f"{e.get('id')}: {f} not built")
            continue
        sheet = e.get("sheet")
        if sheet:
            try:
                wb = xlsxlite.Workbook(p)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{f} unreadable: {exc}")
                continue
            if wb.sheet(sheet) is None:
                problems.append(f"{f}: sheet '{sheet}' absent (has: {[s.name for s in wb.sheets]})")
    if problems:
        return Result(False, "tables_match_plan", "; ".join(problems[:8]))
    n = len(_entries(plan, ("main_tables", "supp_tables")))
    return Result(True, "tables_match_plan", f"{n} planned table(s) built at the planned locations")


@check("tables_threeline")
def tables_threeline(ctx: Ctx) -> Result:
    files = ctx.glob("04_tables/main/*.xlsx") + ctx.glob("04_tables/supplementary/*.xlsx")
    if not files:
        return Result(False, "tables_threeline", "no xlsx tables found under 04_tables/")
    problems: list[str] = []
    checked = 0
    for p in files:
        try:
            wb = xlsxlite.Workbook(p)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{p.name}: unreadable ({exc})")
            continue
        for sh in wb.sheets:
            checked += 1
            problems.extend(f"{p.name}[{sh.name}] {msg}" for msg in _audit_sheet(wb, sh))
    if problems:
        return Result(
            False,
            "tables_threeline",
            f"{len(problems)} defect(s): " + "; ".join(problems[:8]),
            [
                "Build tables with tools/tables/threeline.py, which enforces the rules automatically.",
                "Three-line = rule above header, rule below header, rule below last data row. Nothing else.",
            ],
        )
    return Result(True, "tables_threeline", f"{checked} sheet(s) conform to three-line format")


def _audit_sheet(wb: xlsxlite.Workbook, sh: xlsxlite.Sheet) -> list[str]:
    out: list[str] = []
    if sh.max_row == 0:
        return ["is empty"]

    rows = {}
    for r in range(1, sh.max_row + 1):
        cells = sh.row_cells(r)
        specs = [wb.border_of(c) for c in cells]
        rows[r] = {
            "text": " ".join(c.value or "" for c in cells).strip(),
            "top": any(s.top for s in specs),
            "bottom": any(s.bottom for s in specs),
            "vert": any(s.left or s.right for s in specs),
        }

    title = rows[1]["text"]
    if not title:
        out.append("row 1 must hold the table title")
    elif len(title) > 250:
        out.append(f"title is {len(title)} chars - too long for a table title")
    if rows[1]["top"] or rows[1]["bottom"]:
        out.append("title row must not be ruled")

    ruled = [r for r, v in rows.items() if v["top"] or v["bottom"]]
    if not ruled:
        return out + ["no horizontal rules at all - not a three-line table"]

    header = min(ruled)
    last_ruled = max(ruled)
    if not (rows[header]["top"] and rows[header]["bottom"]):
        out.append(f"header row {header} needs a rule above and below")
    if not rows[last_ruled]["bottom"]:
        out.append(f"bottom rule missing (row {last_ruled})")
    interior = [r for r in ruled if header < r < last_ruled]
    if interior:
        out.append(f"interior rule(s) at row(s) {interior} - only three rules allowed")
    if any(v["vert"] for v in rows.values()):
        out.append("vertical rules present")

    body_rows = [r for r in range(header + 1, last_ruled + 1) if rows[r]["text"]]
    if not body_rows:
        out.append("no data rows between the rules")
    footnotes = [r for r in range(last_ruled + 1, sh.max_row + 1) if rows[r]["text"]]
    if not footnotes:
        out.append("no footnote row beneath the bottom rule")
    else:
        total = sum(len(rows[r]["text"]) for r in footnotes)
        if total > 1500:
            out.append(f"footnotes are {total} chars - that is an analysis report, not a table footnote")

    for c in sh.cells:
        if c.value and len(c.value) > 300:
            out.append(f"cell {c.ref} holds {len(c.value)} chars of prose")
            break
    return out


# ---------------------------------------------------------------------------
@check("figures_match_plan")
def figures_match_plan(ctx: Ctx) -> Result:
    plan = _plan(ctx)
    problems = []
    entries = _entries(plan, ("main_figures", "supp_figures"))
    for e in entries:
        for key, what in (("file", "preview"), ("script", "plot script")):
            v = e.get(key)
            if v and not ctx.p(v).exists():
                problems.append(f"{e.get('id')}: {what} {v} missing")
        tiff = e.get("tiff")
        if tiff and not ctx.p(tiff).exists():
            problems.append(f"{e.get('id')}: print master {tiff} missing")
        elif not tiff:
            problems.append(f"{e.get('id')}: no 'tiff' print master declared")
    if problems:
        return Result(False, "figures_match_plan", "; ".join(problems[:8]))
    return Result(True, "figures_match_plan", f"{len(entries)} figure(s) rendered with print masters")


@check("figures_qc_pass")
def figures_qc_pass(ctx: Ctx) -> Result:
    if not ctx.p(QC).exists():
        return Result(
            False,
            "figures_qc_pass",
            f"{QC} missing",
            ["Run: python tools/figures/qc.py --all  (writes the QC report)"],
        )
    try:
        rep = ctx.read_json(QC)
    except json.JSONDecodeError as exc:
        return Result(False, "figures_qc_pass", f"{QC} invalid JSON: {exc}")
    figs = {str(f.get("id")): f for f in rep.get("figures", [])}
    plan = _plan(ctx)
    problems = []
    for e in _entries(plan, ("main_figures", "supp_figures")):
        eid = str(e.get("id"))
        f = figs.get(eid)
        if f is None:
            problems.append(f"{eid}: no QC entry")
            continue
        failed = [c.get("name") for c in f.get("checks", []) if (not c.get("ok")) and c.get("severity", "fail") == "fail"]
        if failed:
            problems.append(f"{eid}: failing {', '.join(failed)}")
        if not f.get("visual_reviewed"):
            problems.append(f"{eid}: never visually reviewed (deterministic QC alone is not enough)")
    if problems:
        return Result(
            False,
            "figures_qc_pass",
            "; ".join(problems[:8]),
            [
                "Fix the plotting code, re-render, re-run QC, then open the PNG and look at it.",
                "Set visual_reviewed only after the rendered PNG was actually inspected.",
            ],
        )
    return Result(True, "figures_qc_pass", f"{len(figs)} figure(s) pass QC and were visually reviewed")


@check("bundle_complete")
def bundle_complete(ctx: Ctx) -> Result:
    rel = "08_submission/bundle/manifest.json"
    if not ctx.p(rel).exists():
        return Result(False, "bundle_complete", f"{rel} missing")
    try:
        man = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "bundle_complete", f"{rel} invalid JSON: {exc}")
    items = man.get("items", [])
    problems = []
    roles = {str(i.get("role", "")).lower() for i in items}
    for need in ("title_page", "manuscript", "cover_letter", "figures", "tables", "checklist"):
        if need not in roles:
            problems.append(f"no bundle item with role '{need}'")
    listed = set()
    for i in items:
        f = i.get("file")
        if not f:
            problems.append(f"item {i.get('role')} has no file")
            continue
        listed.add(f)
        if not ctx.p(f).exists():
            problems.append(f"{f} listed but absent")
        if not i.get("required_by"):
            problems.append(f"{f}: no 'required_by' reference to the journal guideline")
    on_disk = {
        p.relative_to(ctx.project).as_posix()
        for p in (ctx.project / "08_submission/bundle").rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    stray = sorted(on_disk - listed)
    if stray:
        problems.append(f"{len(stray)} file(s) in the bundle are not in the manifest: {', '.join(stray[:5])}")
    if problems:
        return Result(False, "bundle_complete", "; ".join(problems[:8]))
    return Result(True, "bundle_complete", f"{len(items)} bundle item(s), each present and traced to a guideline rule")


# ---------------------------------------------------------------------------
def _known_archetypes() -> set[str]:
    import tomllib
    from .. import paths
    p = paths.reference_dir() / "archetypes.toml"
    if not p.exists():
        return set()
    try:
        return set(tomllib.loads(p.read_text(encoding="utf-8")).get("archetype", {}))
    except tomllib.TOMLDecodeError:
        return set()


def _split_blocks(text: str) -> dict[str, str]:
    """Split legends/captions on headings or leading bold/plain 'Figure N.' labels."""
    blocks: dict[str, str] = {}
    pattern = re.compile(
        r"^\s{0,3}(?:#{1,6}\s*)?\**\s*((?:supplementary\s+)?(?:figure|fig\.?|table)\s*S?\d+)\b[.:)]?\**",
        re.I | re.M,
    )
    marks = list(pattern.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        blocks[m.group(1)] = text[m.end():end]
    return blocks


def _same_id(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower()).replace("figure", "fig")  # noqa: E731
    return norm(a) == norm(b)
