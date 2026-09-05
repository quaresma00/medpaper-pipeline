# S07 - Artifact inventory (benchmarked) + legends written first

## Purpose
Decide exactly what the paper displays, benchmarked against what comparable papers
actually display, and write every legend before anything is drawn. Legends written
first keep panels from filling up with explanatory text later.

## Procedure
1. **Benchmark.** Retrieve comparable papers - same design, same field, the kind of
   journal you are targeting - and count what they display:
```
python tools/pubmed/client.py search --query "<design> <topic>" --retmax 100
python tools/pubmed/client.py fetch --ids <...> --with-abstract
```
   Write `project/01_protocol/artifact_benchmark.md` with headings
   `Comparable papers surveyed`, `Figure/table counts observed`, `Chosen inventory and why`.
   Record the observed range (e.g. "4-6 main figures, 2-3 main tables, n=8 papers"), and
   justify your inventory against it. Fewer, better displays beat padding.
2. **Plan.** Write `project/01_protocol/artifact_plan.json`. Every entry needs a
   `source_results` list pointing at the result JSONs it is built from - an artifact with
   no numeric source cannot be built:
```json
{
  "main_figures": [
    {"id": "Figure 1", "slug": "flow", "title": "",
     "content": "what the reader learns from it, in one sentence",
     "archetype": "flow_diagram",
     "panels": ["A", "B"], "width": "single|1.5|double",
     "script": "05_figures/code/fig1_flow.py",
     "file": "05_figures/out/Figure1.png",
     "tiff": "05_figures/out/Figure1.tiff",
     "source_results": ["03_analysis/results/dataset_summary.json"]}
  ],
  "main_tables": [
    {"id": "Table 1", "slug": "baseline", "title": "",
     "content": "", "file": "04_tables/main/Table1.xlsx", "sheet": "Table 1",
     "source_results": ["03_analysis/results/baseline.json"]}
  ],
  "supp_figures": [],
  "supp_tables": [
    {"id": "Table S1", "slug": "", "title": "", "content": "",
     "file": "04_tables/supplementary/supplementary_tables.xlsx", "sheet": "Table S1",
     "source_results": []}
  ],
  "supp_files": [{"id": "Supplementary File 1", "file": "", "what": ""}]
}
```
   Structural requirements the gate enforces: sequential numbering with no gaps; each
   main table in its own xlsx; **all supplementary tables in a single xlsx, one sheet
   each**; every figure has a `width`, a `script` and an `archetype`.
   If the reporting guideline requires a flow diagram (STROBE/CONSORT/STARD/PRISMA),
   it is Figure 1.

3. **Declare each figure's archetype.** Pick it from `reference/archetypes.toml` and read
   that entry before planning the figure - it lists the elements that chart type must have,
   and S11 checks the rendered figure for them. Choosing `km_survival` commits you to a
   number-at-risk table and censoring marks; choosing `histopathology` commits you to a
   physical scale bar. Pick the archetype that matches what the data needs, then accept its
   requirements. `other` is available but demands an `archetype_rationale`, and it turns off
   the domain checks, so prefer a real archetype.
4. **Legends.** Write `project/05_figures/legends.md`, one block per figure, each headed
   `Figure N.` / `Figure S1.` A medical figure legend is strictly an **optical navigation guide** so the reader can understand the visual elements of the chart, NOT a second Results or Methods section.
   Keep each legend strictly bounded (typically **40–80 words**, 2–3 sentences max) and enforce the **three-element visual standard**:
   - **Concise Title**: A single bold sentence summarizing what the chart displays.
   - **Panel Guides**: (A), (B)... explaining what is plotted on the axes and what the curves, bars, or markers represent.
   - **Visual & Statistical Markers**: Definition of error bars (e.g. 95% CI) and threshold markers.
      **Strict Prohibitions**:
    - **NO Results Duplication**: The legend's only role is to help the reader understand the visual chart elements. Absolutely NEVER repeat empirical outcome numbers, percentages, mean/SD, IQR, odds ratios, hazard ratios, or P-values in the legend (e.g. do NOT write "wire fracture decreased from 37.5% to 20.1% (OR=0.418, p=0.0005)"). All findings belong exclusively in Results and the chart itself.
    - **NO Methods Duplication**: NEVER describe screening steps, blinded adjudication protocols, or reliability scores in the legend. Those belong exclusively in Methods.
    - **NO Abbreviations in Legends**: Full abbreviations are placed centrally in the **Declarations and Statements** section. Do NOT duplicate an Abbreviations list inside individual figure legends.
5. **Table captions & footnotes.** Write `project/04_tables/table_captions.md`, one block per table,
   headed `Table N.` Each needs a title line plus the footnote content: units, data representation (e.g. "Data are n (%) unless stated otherwise"), the statistical tests used, and what asterisks/daggers mark.
   - **Centralized Abbreviations for Tables**: If a table contains multiple abbreviations, do NOT bloat the table footnotes by repeating an exhaustive dictionary. All abbreviations across the manuscript, figures, and tables are centralized in **Declarations and Statements** (`statements.md`). Footnotes only state: "Abbreviations are listed in the Statements section" or define at most 1–2 highly table-specific ad-hoc symbols.

## Outputs
- `01_protocol/artifact_benchmark.md`
- `01_protocol/artifact_plan.json`
- `05_figures/legends.md`
- `04_tables/table_captions.md`

## Hard rules
- Do not draw anything yet. No xlsx, no png.
- Do not plan a display item you have no result JSON for.
- **Legends must NOT report data findings**: zero percentages, zero odds ratios, zero P-values in legends.md. Pure visual guide only.
- **Abbreviations are centralized in Declarations and Statements**: do NOT clutter figure legends or table footnotes with long repetitive abbreviation lists.
- Keep legends minimal (40–80 words): readers only need to understand what is visually plotted.

## Close
```bash
uv run python tools/wf.py check
uv run python tools/wf.py advance --note "inventory: <F main / T main / F supp / T supp> vs benchmark <range>; legends written"
```
