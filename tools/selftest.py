#!/usr/bin/env python3
"""End-to-end self test. Builds a throwaway project, exercises the toolchain against the
real gate checks, then deletes everything it made.

    .venv/Scripts/python tools/selftest.py
    .venv/Scripts/python tools/selftest.py --keep     # leave the temp project for inspection
    .venv/Scripts/python tools/selftest.py --online   # also hit PubMed, Crossref

Run this after changing the style module, the table writer, the QC script or any check.
It is the regression test for the parts of the pipeline that code can verify.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, PASS if ok else FAIL, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


# ---------------------------------------------------------------------------
def build_fixture(proj: Path) -> None:
    """A minimal but structurally complete project: results JSON, tables, a figure,
    an artifact plan, legends, captions and a Results section that cites them."""
    import numpy as np
    from figures.style import PALETTE, apply_style, figure, save, significance
    from tables.threeline import ci, fmt, p_value, write_table, write_workbook

    for sub in ("03_analysis/results", "04_tables/main", "04_tables/supplementary",
                "05_figures/out", "05_figures/qc", "01_protocol", "07_manuscript", "temp"):
        (proj / sub).mkdir(parents=True, exist_ok=True)

    res = {
        "analysis": "primary_model", "script": "03_analysis/code/03_primary.py",
        "n_eligible": 1380, "n_analysed": 1284, "n_excluded": 96,
        "groups": {"a": {"n": 642, "age_mean": 62.14, "age_sd": 11.42},
                   "b": {"n": 642, "age_mean": 61.73, "age_sd": 12.05}},
        "estimates": [{"term": "exposure", "estimate": 1.87, "ci_low": 1.34,
                       "ci_high": 2.61, "p": 0.00021, "scale": "HR"}],
        "age_p": 0.62,
        "roc": {"auc": 0.781, "auc_low": 0.742, "auc_high": 0.820},
    }
    (proj / "03_analysis/results/primary.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")

    g = res["groups"]
    write_table(
        path=proj / "04_tables/main/Table1.xlsx", sheet="Table 1",
        title="Table 1. Baseline characteristics of the study population.",
        header=["Characteristic", f"Group A (n={g['a']['n']})",
                f"Group B (n={g['b']['n']})", "P value"],
        rows=[["Age, years, mean (SD)",
               f"{fmt(g['a']['age_mean'])} ({fmt(g['a']['age_sd'])})",
               f"{fmt(g['b']['age_mean'])} ({fmt(g['b']['age_sd'])})",
               p_value(res["age_p"])],
              ["Exposure, HR (95% CI)", ci(1.87, 1.34, 2.61), "reference",
               p_value(0.00021)]],
        footnotes=["Data are mean (SD) unless stated otherwise.",
                   "Abbreviations: SD, standard deviation; HR, hazard ratio; "
                   "CI, confidence interval.",
                   "P values from the two-sided t test."],
    )
    write_workbook(
        path=proj / "04_tables/supplementary/supplementary_tables.xlsx",
        tables=[{"sheet": "Table S1", "title": "Table S1. Sensitivity analyses.",
                 "header": ["Model", "HR (95% CI)", "P value"],
                 "rows": [["Complete case", ci(1.87, 1.34, 2.61), p_value(0.00021)]],
                 "footnotes": ["Abbreviations: HR, hazard ratio; CI, confidence interval."]},
                {"sheet": "Table S2", "title": "Table S2. Discrimination.",
                 "header": ["Model", "AUC (95% CI)"],
                 "rows": [["Primary", ci(0.781, 0.742, 0.820, 3)]],
                 "footnotes": ["Abbreviations: AUC, area under the curve."]}],
    )

    apply_style()
    fig, panels = figure(width="double", height_mm=75, panels=(1, 2))
    (sfA, axA), (sfB, axB) = panels
    rng = np.random.default_rng(7)
    fpr = np.linspace(0, 1, 200)
    axA.plot(fpr, fpr ** 0.42, color=PALETTE[0], label=f"Primary (AUC {res['roc']['auc']:.3f})")
    axA.plot([0, 1], [0, 1], ls="--", lw=0.6, color="#4D4D4D")
    axA.set_xlabel("1 - specificity"); axA.set_ylabel("Sensitivity")
    axA.set_xlim(0, 1); axA.set_ylim(0, 1); axA.legend(loc="lower right")
    sfA.suptitle("Discrimination")

    vals = [rng.normal(m, 1.0, 60) for m in (3.1, 4.4)]
    bp = axB.boxplot(vals, widths=0.5, patch_artist=True, showfliers=False)
    for patch, col in zip(bp["boxes"], PALETTE):
        patch.set_facecolor(col); patch.set_alpha(0.35); patch.set_edgecolor("black")
    for key in ("medians", "whiskers", "caps"):
        for art in bp[key]:
            art.set_color("black"); art.set_linewidth(0.6)
    axB.set_xticks([1, 2]); axB.set_xticklabels(["Group A", "Group B"])
    axB.set_ylabel("Grip strength (kg)")
    significance(axB, 1, 2, max(v.max() for v in vals) + 0.3, "***")
    sfB.suptitle("Grip strength by group")
    save(fig, proj / "05_figures/out/Figure1", width="double")

    plan = {
        "main_figures": [{"id": "Figure 1", "slug": "primary",
                          "title": "Discrimination and grip strength",
                          "content": "ROC curve and grip strength by group",
                          "archetype": "other",
                          "archetype_rationale": "composite plate: panel A is a ROC curve, "
                                                 "panel B a box plot; no single archetype fits",
                          "panels": ["A", "B"], "width": "double",
                          "script": "05_figures/code/fig1_primary.py",
                          "file": "05_figures/out/Figure1.png",
                          "tiff": "05_figures/out/Figure1.tiff",
                          "source_results": ["03_analysis/results/primary.json"]}],
        "main_tables": [{"id": "Table 1", "slug": "baseline",
                         "title": "Baseline characteristics", "content": "cohort by group",
                         "file": "04_tables/main/Table1.xlsx", "sheet": "Table 1",
                         "source_results": ["03_analysis/results/primary.json"]}],
        "supp_figures": [],
        "supp_tables": [
            {"id": "Table S1", "slug": "sens", "title": "Sensitivity analyses",
             "content": "robustness",
             "file": "04_tables/supplementary/supplementary_tables.xlsx",
             "sheet": "Table S1", "source_results": ["03_analysis/results/primary.json"]},
            {"id": "Table S2", "slug": "disc", "title": "Discrimination", "content": "AUC",
             "file": "04_tables/supplementary/supplementary_tables.xlsx",
             "sheet": "Table S2", "source_results": ["03_analysis/results/primary.json"]}],
        "supp_files": [],
    }
    (proj / "01_protocol/artifact_plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8")
    (proj / "05_figures/code").mkdir(parents=True, exist_ok=True)
    (proj / "05_figures/code/fig1_primary.py").write_text("# fixture\n", encoding="utf-8")

    (proj / "05_figures/legends.md").write_text(
        "# Figure legends\n\n## Figure 1.\nDiscrimination and grip strength. (A) Receiver "
        "operating characteristic curve for the primary model; the dashed line marks chance "
        "performance. (B) Grip strength by group as box plots (median, interquartile range, "
        "whiskers to 1.5x IQR, outliers omitted). n=1284. ***P<0.001, two-sided Wilcoxon "
        "rank-sum test. Abbreviations: AUC, area under the curve; IQR, interquartile range.\n",
        encoding="utf-8")
    (proj / "04_tables/table_captions.md").write_text(
        "# Table captions\n\n## Table 1.\nBaseline characteristics of the study population. "
        "Data are mean (SD) unless stated otherwise. Abbreviations: SD, standard deviation.\n\n"
        "## Table S1.\nSensitivity analyses. Abbreviations: HR, hazard ratio.\n\n"
        "## Table S2.\nDiscrimination. Abbreviations: AUC, area under the curve.\n",
        encoding="utf-8")
    (proj / "07_manuscript/results.md").write_text(
        "# Results\n\nOf 1380 eligible participants, 96 were excluded and 1284 were "
        "analysed. Mean age was 62.14 (SD 11.42) years in group A and 61.73 (SD 12.05) "
        "years in group B (P=0.62) (Table 1).\n\nExposure was associated with the outcome "
        "(HR 1.87, 95% CI 1.34 to 2.61; P<0.001). The primary model discriminated moderately "
        "(AUC 0.781, 95% CI 0.742 to 0.820) (Figure 1A). Grip strength differed between "
        "groups (Figure 1B). Results were unchanged in the complete-case analysis "
        "(Table S1), and discrimination was similar (Table S2).\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
def run_checks(proj: Path) -> None:
    from wfcore import gates, registry
    from wfcore.checks import Ctx, Result, get, load_all
    from wfcore.state import State

    load_all()
    pipe = registry.load()
    st = State(proj, ".wf")
    st.create(pipe.meta["name"], pipe.meta["version"], pipe.first().id)

    def run(check_name: str, stage_id: str, **spec) -> Result:
        fn = get(check_name)
        ctx = Ctx(pipeline=pipe, state=st, project=proj,
                  stage=pipe.stage(stage_id), spec={"check": check_name, **spec})
        return fn(ctx)

    section("structural checks (expected to pass)")
    for name, stage, spec in [
        ("tables_threeline", "S10_tables", {}),
        ("tables_match_plan", "S10_tables", {}),
        ("artifact_plan_sane", "S07_artifacts", {"path": "01_protocol/artifact_plan.json"}),
        ("legends_cover_plan", "S07_artifacts", {}),
        ("figures_match_plan", "S11_figures", {}),
        ("numbers_have_provenance", "S10_tables", {"source": "tables"}),
        ("numbers_have_provenance", "S09_results", {"path": "07_manuscript/results.md"}),
        ("artifact_refs_consistent", "S09_results",
         {"paths": ["07_manuscript/results.md"], "require_all_cited": True}),
        ("no_ai_boilerplate", "S09_results", {"path": "07_manuscript/results.md"}),
        ("temp_clean", "S10_tables", {}),
    ]:
        r = run(name, stage, **spec)
        record(f"{name}({spec.get('source') or spec.get('path') or 'plan'})", r.ok, r.detail)

    section("negative controls (checks must catch injected faults)")

    bad = proj / "07_manuscript/bad.md"
    bad.write_text("# Results\n\nThe hazard ratio was 4.44 (95% CI 2.01 to 9.87).\n",
                   encoding="utf-8")
    r = run("numbers_have_provenance", "S09_results", path="07_manuscript/bad.md")
    record("invented statistic is rejected", not r.ok, r.detail[:110])

    bad.write_text("# Results\n\nSee Figure 9 and Table 7 for details.\n", encoding="utf-8")
    r = run("artifact_refs_consistent", "S09_results", paths=["07_manuscript/bad.md"])
    record("citation to an unplanned artifact is rejected", not r.ok, r.detail[:110])

    bad.write_text("# Results\n\nThe adjusted estimate was TODO and warrants attention.\n",
                   encoding="utf-8")
    r = run("no_ai_boilerplate", "S09_results", path="07_manuscript/bad.md")
    record("placeholder text is rejected", not r.ok, r.detail[:110])

    bad.write_text("# Results\n\nWe cite [@fabricated2021smith] here.\n", encoding="utf-8")
    r = run("citekeys_resolve", "S08_methods", paths=["07_manuscript/bad.md"])
    record("citekey with no bib entry is rejected", not r.ok, r.detail[:110])
    bad.unlink()

    (proj / "03_analysis/code").mkdir(parents=True, exist_ok=True)
    plot = proj / "03_analysis/code/oops.py"
    plot.write_text("import matplotlib.pyplot as plt\nplt.plot([1,2])\n", encoding="utf-8")
    r = run("no_plot_calls", "S05_analysis", glob="03_analysis/code/*.*")
    record("plotting during exploratory analysis is rejected", not r.ok, r.detail[:110])
    plot.unlink()

    scratch = proj / "temp/scratch.csv"
    scratch.write_text("a,b\n1,2\n", encoding="utf-8")
    r = run("temp_clean", "S10_tables")
    record("leftover scratch file is rejected", not r.ok, r.detail[:110])
    scratch.unlink()

    r = run("decision_recorded", "S11_figures",
            name="figures_visually_confirmed", allowed=["YES"])
    record("unrecorded decision is rejected", not r.ok, r.detail[:110])

    st.record_decision("figures_visually_confirmed", "YES", "too short")
    r = run("decision_recorded", "S11_figures",
            name="figures_visually_confirmed", allowed=["YES"])
    record("decision with a thin rationale is rejected", not r.ok, r.detail[:110])

    section("three-line writer rejects malformed input")
    from tables.threeline import write_table
    for label, kwargs in [
        ("missing footnotes", dict(footnotes=[])),
        ("title without a Table N prefix", dict(title="Baseline characteristics")),
        ("prose dumped into a cell", dict(rows=[["x", "y" * 400, "z", "w"]])),
    ]:
        base = dict(path=proj / "temp/bad.xlsx", sheet="Table 9",
                    title="Table 9. Fixture.", header=["a", "b", "c", "d"],
                    rows=[["1", "2", "3", "4"]], footnotes=["Abbreviations: none."])
        base.update(kwargs)
        try:
            write_table(**base)
            record(label, False, "writer accepted it")
        except ValueError as exc:
            record(label, True, str(exc)[:90])
    (proj / "temp/bad.xlsx").unlink(missing_ok=True)

    section("gate runner over every stage (must not raise)")
    raised = []
    for stage in pipe.stages:
        for r in gates.run_stage(pipe, st, proj, stage):
            if "check raised" in r.detail:
                raised.append(f"{stage.id}/{r.check}: {r.detail}")
    record("no check raised an exception", not raised, "; ".join(raised[:3]))


def run_qc(proj: Path) -> None:
    section("figure QC (subprocess, as the agent runs it)")
    env = {**os.environ, "MEDPAPER_PROJECT": str(proj), "MEDPAPER_ROOT": str(ROOT),
           "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, str(ROOT / "tools/figures/qc.py"), "--all"],
                       capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        if line.strip().startswith("[") or "pass deterministic" in line:
            print("  " + line.strip())
    record("all deterministic figure QC checks pass", "1/1 figure(s) pass" in out,
           "" if "1/1 figure(s) pass" in out else "see output above")
    rep = proj / "05_figures/qc/qc_report.json"
    record("qc_report.json written", rep.exists())
    if rep.exists():
        data = json.loads(rep.read_text(encoding="utf-8"))
        fig = data["figures"][0]
        record("visual_reviewed defaults to false", fig.get("visual_reviewed") is False,
               "QC alone must never satisfy the visual-verification gate")


SLOP = """# Discussion

In today's rapidly evolving landscape of modern clinical care, sarcopenia plays a crucial
role in patient outcomes. It is worth noting that we utilized a robust and comprehensive
approach to delve into this multifaceted problem, and our cutting-edge analysis paves the
way for a comprehensive understanding of the intricate interplay involved.

Our primary finding was an association between exposure and the outcome (HR 1.87, 95% CI
1.34 to 2.61; P<0.001), which aligns with previous work [@smith2020cohort]. Furthermore,
the effect was seamlessly consistent across strata. Moreover, discrimination was moderate
(AUC 0.781) (Figure 1A). Additionally, results held in sensitivity analyses (Table S1).

The data was analyzed in 3 centers, and 10-20 participants per site were characterised
using a 5mg dose. P-value thresholds were applied and P = 0.000 was observed in one
subgroup. This finding may potentially suggest that the exposure could possibly cause the
outcome, and underscores the importance of further work. Further studies are warranted.
"""

CLEAN = """# Discussion

Sarcopenia was associated with mortality in this cohort. We analysed a single prospective
cohort with prespecified exposure and outcome definitions.

The primary finding was an association between exposure and the outcome (HR 1.87, 95% CI
1.34 to 2.61; P<0.001), consistent with the earlier cohort of Smith and colleagues
[@smith2020cohort]. The effect was stable across strata, discrimination was moderate
(AUC 0.781) (Figure 1A), and the estimate was unchanged in sensitivity analyses (Table S1).

Data were collected at 3 centres, with 10\u201320 participants per site characterised after a
5 mg dose. One subgroup reached P < 0.001. Because the design is observational, these data
support an association rather than a causal effect; the direction of residual confounding
cannot be established from these data.
"""


def run_archetypes(proj: Path) -> None:
    """The archetype gate must detect mandatory elements, not take the plan's word for it."""
    import tomllib

    import matplotlib.pyplot as plt
    import numpy as np
    from figures import elements as el
    from figures.style import apply_style, figure, save
    from wfcore import registry
    from wfcore.checks import Ctx, get, load_all
    from wfcore.state import State

    section("archetypes: registry")
    reg = tomllib.loads((ROOT / "reference/archetypes.toml").read_text(encoding="utf-8"))
    arches = reg.get("archetype", {})
    record("registry parses", bool(arches), f"{len(arches)} archetype(s)")
    unknown = sorted({k for a in arches.values()
                      for k in list(a.get("requires", [])) + list(a.get("forbids", []))}
                     - set(el.DETECTORS))
    record("every requires/forbids element has a detector", not unknown,
           f"undetectable: {unknown}" if unknown else
           f"{len(el.DETECTORS)} detectors cover all mandatory elements")
    universal = reg.get("meta", {}).get("universal_requires", [])
    record("universal requires are detectable",
           all(u in el.DETECTORS for u in universal), f"{universal}")

    section("archetypes: element detection on constructed figures")
    apply_style()
    rng = np.random.default_rng(3)

    # a compliant bar_dot: points, error bars, baseline at zero
    fig, panels = figure(width="single", height_mm=60, panels=(1, 1), letters=False)
    _, ax = panels[0]
    ax.bar([1, 2], [3.0, 4.2], yerr=[0.4, 0.5], capsize=2.5, color=["C0", "C1"], alpha=0.35,
           edgecolor="black", linewidth=0.6)
    for i, m in ((1, 3.0), (2, 4.2)):
        ax.scatter(np.full(5, i) + rng.normal(0, 0.05, 5), rng.normal(m, 0.3, 5),
                   s=6, color="black", zorder=3)
    ax.set_ylim(0, 5.5)
    ax.set_xticks([1, 2]); ax.set_xticklabels(["Control", "Treated"])
    ax.set_xlabel("Group"); ax.set_ylabel("Relative expression")
    found = el.detect_all(fig)
    for key in reg["archetype"]["bar_dot"]["requires"]:
        record(f"bar_dot detects {key}", found[key]["found"], found[key]["evidence"][:70])
    plt.close(fig)

    # the same figure with a truncated baseline must fail
    fig, panels = figure(width="single", height_mm=60, panels=(1, 1), letters=False)
    _, ax = panels[0]
    ax.bar([1, 2], [3.0, 4.2], color="C0")
    ax.set_ylim(2.5, 4.5)
    ax.set_xlabel("Group"); ax.set_ylabel("Relative expression")
    found = el.detect_all(fig)
    record("truncated bar baseline is detected", not found["baseline_zero"]["found"],
           found["baseline_zero"]["evidence"][:70])
    record("missing individual points are detected", not found["individual_points"]["found"])
    plt.close(fig)

    # missing axis labels
    fig, panels = figure(width="single", height_mm=50, panels=(1, 1), letters=False)
    _, ax = panels[0]
    ax.plot([0, 1], [0, 1])
    found = el.detect_all(fig)
    record("missing axis labels are detected", not found["axis_labels"]["found"],
           found["axis_labels"]["evidence"][:70])
    plt.close(fig)

    # a missing glyph must be caught during rasterization
    fig, panels = figure(width="single", height_mm=40, panels=(1, 1), letters=False)
    _, ax = panels[0]
    ax.plot([0, 1], [0, 1]); ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.text(0.4, 0.5, "\u2f00\u2f01\u4e2d\u6587")     # glyphs absent from the Latin stack
    warns = el.glyph_warnings(fig)
    record("missing font glyphs are caught", bool(warns),
           (warns[0][:70] if warns else "no warning raised - font may cover these glyphs"))
    plt.close(fig)

    # tick labels forced to collide
    fig, panels = figure(width="single", height_mm=40, panels=(1, 1), letters=False)
    _, ax = panels[0]
    ax.plot(range(40), range(40))
    ax.set_xticks(range(40))
    ax.set_xticklabels([f"label{i}" for i in range(40)])
    ax.set_xlabel("x"); ax.set_ylabel("y")
    fig.canvas.draw()
    coll = el.tick_label_collisions(fig, fig.canvas.get_renderer())
    record("tick-label collisions are caught", bool(coll),
           f"{len(coll)} collision(s)" if coll else "none detected")
    plt.close(fig)

    # a deliberate dead band between panels
    fig, panels = figure(width="single", height_mm=90, panels=(1, 1), letters=False)
    sf, ph = panels[0]
    ph.remove()
    a1, a2 = sf.subplots(2, 1, gridspec_kw={"hspace": 1.4})
    for a in (a1, a2):
        a.plot([0, 1], [0, 1]); a.set_xlabel("x"); a.set_ylabel("y")
    fig.canvas.draw()
    voids = el.interior_voids(fig, fig.canvas.get_renderer())
    record("interior dead band is caught", bool(voids),
           f"{voids[0]['gap_pct']}% gap" if voids else "none detected")
    plt.close(fig)

    section("archetypes: gate rejects a plan without an archetype")
    load_all()
    pipe = registry.load()
    st = State(proj, ".wf").load()
    plan_path = proj / "01_protocol/artifact_plan.json"
    original = plan_path.read_text(encoding="utf-8")
    plan = json.loads(original)

    def plan_check():
        fn = get("artifact_plan_sane")
        return fn(Ctx(pipeline=pipe, state=st, project=proj, stage=pipe.stage("S07_artifacts"),
                      spec={"check": "artifact_plan_sane", "path": "01_protocol/artifact_plan.json"}))

    plan["main_figures"][0].pop("archetype", None)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    r = plan_check()
    record("figure without an archetype is rejected", not r.ok, r.detail[:90])

    plan["main_figures"][0]["archetype"] = "not_a_real_archetype"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    r = plan_check()
    record("unknown archetype is rejected", not r.ok, r.detail[:90])

    plan["main_figures"][0]["archetype"] = "other"
    plan["main_figures"][0].pop("archetype_rationale", None)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    r = plan_check()
    record("archetype 'other' without a rationale is rejected", not r.ok, r.detail[:90])

    plan["main_figures"][0]["archetype"] = "roc_curve"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    r = plan_check()
    record("valid archetype is accepted", r.ok, r.detail[:90])
    plan_path.write_text(original, encoding="utf-8")

    section("archetypes: journal palettes")
    for name in ("okabe_ito", "nejm", "lancet", "jama", "jco", "nature"):
        colors = apply_style(palette=name)
        ok = isinstance(colors, list) and len(colors) >= 5 and all(
            c.startswith("#") and len(c) == 7 for c in colors)
        record(f"palette {name}", ok, f"{len(colors)} colours")
    try:
        apply_style(palette="nope")
        record("unknown palette is rejected", False, "accepted silently")
    except ValueError as exc:
        record("unknown palette is rejected", True, str(exc)[:60])
    apply_style()
    import matplotlib
    record("axes.unicode_minus disabled", matplotlib.rcParams["axes.unicode_minus"] is False,
           "a negative sign cannot render as a missing-glyph box")


def run_skill_guard(proj: Path) -> None:
    """The guard is what makes skill arbitration enforced rather than advisory."""
    import tomllib
    guard = ROOT / "tools/hooks/skill_guard.py"
    policy = ROOT / "reference/skill_policy.toml"

    section("skill guard: policy")
    record("policy file exists", policy.exists())
    if not policy.exists():
        return
    entries = {s["name"]: s for s in
               tomllib.loads(policy.read_text(encoding="utf-8")).get("skill", [])}
    record("policy parses", bool(entries), f"{len(entries)} skill(s) classified")
    bad_verdict = [n for n, s in entries.items()
                   if s.get("verdict") not in ("blocked", "gated", "allow")]
    record("every verdict is valid", not bad_verdict, f"invalid: {bad_verdict}")
    no_reason = [n for n, s in entries.items() if len((s.get("reason") or "").strip()) < 30]
    record("every entry carries a reason", not no_reason, f"thin: {no_reason[:5]}")
    blocked_no_route = [n for n, s in entries.items()
                       if s["verdict"] == "blocked" and not s.get("replaced_by")]
    record("every blocked skill names its replacement", not blocked_no_route,
           f"missing replaced_by: {blocked_no_route[:5]}")
    gated_no_where = [n for n, s in entries.items()
                      if s["verdict"] == "gated" and not s.get("use_at")]
    record("every gated skill says where it may be used", not gated_no_where,
           f"missing use_at: {gated_no_where[:5]}")
    for must in ("write-paper", "orchestrate", "make-figures", "search-lit",
                 "polish-language", "manage-refs", "analyze-stats", "find-journal"):
        record(f"{must} is blocked", entries.get(must, {}).get("verdict") == "blocked",
               entries.get(must, {}).get("replaced_by", "ABSENT FROM POLICY"))
    for must in ("check-reporting", "peer-review", "revise"):
        v = entries.get(must, {}).get("verdict")
        record(f"{must} is not blocked", v in ("gated", "allow"), f"verdict={v}")

    section("skill guard: enforcement")
    cases = [
        ({"tool_name": "disclose_context", "tool_input": {"name": "write-paper"}}, 2,
         "blocked, documented payload shape"),
        ({"toolInput": {"name": "orchestrate"}}, 2, "blocked, camelCase payload"),
        ({"session": {"x": [{"skill": "make-figures"}]}}, 2, "blocked, name nested elsewhere"),
        ({"name": "search-lit"}, 2, "blocked, flat payload"),
        ({"tool_input": {"name": "check-reporting"}}, 0, "gated returns exit 0"),
        ({"tool_input": {"name": "peer-review"}}, 0, "allow is silent"),
        ({"tool_input": {"name": "radiomics-ml"}}, 0, "imaging domain allowed"),
        ({"tool_input": {"name": "an-unseen-skill"}}, 0, "unknown falls through to default"),
        ({}, 0, "empty payload does not block"),
    ]
    for payload, want, label in cases:
        p = subprocess.run([sys.executable, str(guard)], input=json.dumps(payload),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        detail = ((p.stderr or "").strip().splitlines() or [""])[0][:70] if p.returncode == 2 else ""
        record(label, p.returncode == want, detail or f"exit={p.returncode}")

    p = subprocess.run([sys.executable, str(guard)],
                       input=json.dumps({"tool_input": {"name": "check-reporting"}}),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        d = json.loads(p.stdout)["hookSpecificOutput"]
        ok = d["permissionDecision"] == "ask" and len(d["permissionDecisionReason"]) > 40
        detail = d["permissionDecisionReason"][:60]
    except Exception:  # noqa: BLE001
        ok, detail = False, (p.stdout or "")[:60]
    record("gated emits a usable ask decision", ok, detail)

    p = subprocess.run([sys.executable, str(guard), "--explain", "write-paper"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    record("--explain reports the verdict and route",
           "blocked" in (p.stdout or "") and "S08" in (p.stdout or ""),
           (p.stdout or "").strip().splitlines()[1][:60] if p.stdout else "")

    p = subprocess.run([sys.executable, str(guard), "--audit"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    record("--audit lists installed skills by verdict",
           "BLOCKED" in (p.stdout or "") and "installed skills found" in (p.stdout or ""))


def run_polish(proj: Path) -> None:
    from wfcore import registry
    from wfcore.checks import Ctx, get, load_all
    from wfcore.state import State

    load_all()
    pipe = registry.load()
    st = State(proj, ".wf").load()
    tool = ROOT / "tools/text/polish.py"
    env = {**os.environ, "MEDPAPER_PROJECT": str(proj), "MEDPAPER_ROOT": str(ROOT),
           "PYTHONIOENCODING": "utf-8"}

    def polish(*argv):
        return subprocess.run([sys.executable, str(tool), *argv], capture_output=True,
                              text=True, env=env, encoding="utf-8", errors="replace")

    def gate(name: str, stage: str = "S19_polish", **spec):
        fn = get(name)
        return fn(Ctx(pipeline=pipe, state=st, project=proj,
                      stage=pipe.stage(stage), spec={"check": name, **spec}))

    disc = proj / "07_manuscript/discussion.md"
    abstract = proj / "07_manuscript/abstract.md"

    section("polish: linting AI slop")
    disc.write_text(SLOP, encoding="utf-8")
    abstract.write_text("# Abstract\n\nExposure was associated with the outcome "
                        "(HR 1.87, 95% CI 1.34 to 2.61).\n", encoding="utf-8")
    p = polish("snapshot")
    record("snapshot taken", p.returncode == 0 and (proj / "07_manuscript/prepolish/facts.json").exists())
    record("snapshot refuses to overwrite silently", polish("snapshot").returncode == 1)

    p = polish("lint")
    out = p.stdout or ""
    counts = json.loads((proj / "07_manuscript/polish_report.json").read_text(encoding="utf-8"))["counts"]
    record("tier-A AI phrases detected", counts["ai_tier_a"] >= 10, f"{counts['ai_tier_a']} found")
    record("structural tells detected", counts["structure_blocking"] >= 1,
           f"{counts['structure_blocking']} blocking")
    record("house-style defects detected", counts["style_blocking"] >= 4,
           f"{counts['style_blocking']} blocking")
    for want, label in [("utilize", "inflated verb"), ("range_dash", "hyphen numeric range"),
                        ("unit_spacing", "value glued to unit"), ("data_agreement", "'data was'"),
                        ("p_zero", "P = 0.000"), ("causal_overclaim", "causal overclaim"),
                        ("hedge_stacking", "stacked hedges")]:
        record(f"caught: {label}", want in out, "" if want in out else f"{want!r} absent from report")

    r = gate("ai_tells_clean")
    record("ai_tells_clean rejects the slop", not r.ok, r.detail[:100])
    r = gate("style_consistent")
    record("style_consistent rejects the slop", not r.ok, r.detail[:100])

    section("polish: fact preservation")
    disc.write_text(CLEAN, encoding="utf-8")
    p = polish("diff")
    record("polished text preserves every fact", p.returncode == 0,
           (p.stdout or "").strip().splitlines()[-1][:90])
    polish("lint")
    r = gate("ai_tells_clean")
    record("ai_tells_clean accepts the polished text", r.ok, r.detail[:100])
    r = gate("style_consistent")
    record("style_consistent accepts the polished text", r.ok, r.detail[:100])

    disc.write_text(CLEAN.replace("HR 1.87, 95% CI\n1.34 to 2.61", "HR 1.90, 95% CI\n1.40 to 2.60"),
                    encoding="utf-8")
    p = polish("diff")
    record("altered statistic is caught by diff", p.returncode == 2,
           next((ln.strip() for ln in (p.stdout or "").splitlines() if "LOST" in ln), "")[:90])
    r = gate("polish_preserves_facts")
    record("polish_preserves_facts gate rejects it", not r.ok, r.detail[:100])

    disc.write_text(CLEAN.replace("[@smith2020cohort]", ""), encoding="utf-8")
    record("dropped citation is caught by diff", polish("diff").returncode == 2)

    disc.write_text(CLEAN.replace("(Figure 1A)", ""), encoding="utf-8")
    record("dropped figure reference is caught by diff", polish("diff").returncode == 2)

    disc.write_text(CLEAN, encoding="utf-8")
    record("restoring the text clears diff", polish("diff").returncode == 0)

    section("polish: journal limits")
    (proj / "08_submission").mkdir(parents=True, exist_ok=True)
    gx = proj / "08_submission/guidelines_extract.md"
    gx.write_text("# Guidelines\n\n## Word limits\nAbstract: 250 words. Main text: 3500 words "
                  "excluding references. References: maximum 50.\n", encoding="utf-8")
    polish("lint")
    r = gate("journal_limits_met")
    record("journal_limits_met parses the quoted caps and passes", r.ok, r.detail[:110])
    gx.write_text("# Guidelines\n\n## Word limits\nAbstract: 250 words. Main text: 100 words "
                  "excluding references. References: maximum 50.\n", encoding="utf-8")
    r = gate("journal_limits_met")
    record("journal_limits_met rejects an over-limit manuscript", not r.ok, r.detail[:110])
    gx.write_text("# Guidelines\n\n## Word limits\nSee the website.\n", encoding="utf-8")
    r = gate("journal_limits_met")
    record("journal_limits_met rejects unquoted limits", not r.ok, r.detail[:110])

    section("polish: allowlist escape hatch")
    disc.write_text(CLEAN + "\nThe guideline states that screening plays a crucial role.\n",
                    encoding="utf-8")
    polish("lint")
    record("allowlist absent -> phrase blocks", not gate("ai_tells_clean").ok)
    (proj / "07_manuscript/polish_allowlist.tsv").write_text(
        "plays a crucial role\tquoted verbatim from the 2023 guideline\n", encoding="utf-8")
    polish("lint")
    record("allowlisted phrase stops blocking", gate("ai_tells_clean").ok)

    for f in (disc, abstract, gx, proj / "07_manuscript/polish_allowlist.tsv"):
        f.unlink(missing_ok=True)
    shutil.rmtree(proj / "07_manuscript/prepolish", ignore_errors=True)
    (proj / "07_manuscript/polish_report.json").unlink(missing_ok=True)


def run_online(proj: Path) -> None:
    section("live API (network)")
    env = {**os.environ, "MEDPAPER_PROJECT": str(proj), "MEDPAPER_ROOT": str(ROOT),
           "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, str(ROOT / "tools/pubmed/client.py"),
                        "fetch", "--ids", "32150289", "--with-abstract"],
                       capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    record("PubMed efetch returns a real record",
           "Sarcopenia Definition" in (p.stdout or ""), (p.stderr or "")[:100])
    p = subprocess.run([sys.executable, str(ROOT / "tools/pubmed/build_library.py"),
                        "--add-ids", "32150289,34315158", "--export"],
                       capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    record("library builds and exports", (proj / "06_refs/refs.bib").exists(),
           (p.stderr or "")[:100])
    p = subprocess.run([sys.executable, str(ROOT / "tools/pubmed/verify.py")],
                       capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    record("verification confirms every entry against the source",
           "verified 2/2" in (p.stdout or ""), (p.stdout or "").strip()[-90:])


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="self test for the medpaper toolchain")
    ap.add_argument("--keep", action="store_true", help="do not delete the temp project")
    ap.add_argument("--online", action="store_true", help="also exercise the live APIs")
    args = ap.parse_args()

    for mod, why in (("matplotlib", "figures"), ("numpy", "QC"), ("openpyxl", "tables")):
        try:
            __import__(mod)
        except ImportError:
            print(f"cannot run: {mod} is required for {why}.\n"
                  f"  uv pip install --python .venv/Scripts/python.exe {mod}")
            return 1

    tmp = Path(tempfile.mkdtemp(prefix="medpaper_selftest_"))
    proj = tmp / "project"
    os.environ["MEDPAPER_PROJECT"] = str(proj)
    os.environ["MEDPAPER_ROOT"] = str(ROOT)
    print(f"temp project: {proj}\n")

    try:
        section("building fixture")
        build_fixture(proj)
        record("fixture built", True)
        run_checks(proj)
        run_qc(proj)
        run_archetypes(proj)
        run_skill_guard(proj)
        run_polish(proj)
        if args.online:
            run_online(proj)
    finally:
        if args.keep:
            print(f"\nkept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    failed = [r for r in results if r[1] == FAIL]
    print("\n" + "=" * 70)
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        for name, _, detail in failed:
            print(f"  FAIL  {name}  {detail}")
        return 2
    print("selftest: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
