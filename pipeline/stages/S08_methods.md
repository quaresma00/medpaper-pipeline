# S08 - Methods

## Purpose
Write the Methods section. One file for the main text, optionally a second file for
supplementary methods if technical detail would bloat the main text.

## Inputs
- `01_protocol/protocol_final.md` and `01_protocol/protocol_diff.md`
- `02_data/codebook.md`, `02_data/provenance.md`
- `03_analysis/method_scan.md` (for the methods you cite)
- `03_analysis/results/*.json` (for every number)

## Reference skeleton for the main-text Methods

The exact subsection headings depend on the study type and the target journal's reporting
guideline. Do not force a fixed template. However, across all major medical journals
(NEJM, Lancet, JAMA, BMJ, Nature Medicine, Gut, etc.) and all study types (RCT, cohort,
database mining, bioinformatics, wet-lab, diagnostic, meta-analysis), the main-text
Methods consistently follows a four-step causal chain:

1. **Study design, data source, and ethics** — what kind of study, where the data or
   samples came from, IRB/ethics approval, trial registration.
2. **Participants / samples and selection criteria** — who or what was included and
   excluded, the screening-to-enrollment flow.
3. **Exposures, interventions, variables, or key assays** — what was measured or done,
   how the core variables were defined and ascertained. For wet-lab work: animal models,
   cell lines, key reagents and techniques. For bioinformatics: sequencing platform,
   annotation pipeline, feature processing.
4. **Statistical analysis** — primary model, effect size and confidence intervals,
   multiple-testing correction, sample-size justification, software and versions.

**Statistical Analysis is the last substantive section of the main-text Methods.**
Some journals require a brief format-specific closing statement after it (e.g. Lancet:
"Role of the funding source"; BMJ: "Patient and public involvement"). Those are one or
two sentences, not method content — include them if the target journal requires, but do
not add further analytical method subsections after Statistical Analysis.

Within Statistical Analysis, sensitivity and subgroup analyses should be **mentioned**
(what was tested and the rationale), but keep it to 1–3 sentences in the main text.
The full specification — alternative models, changed thresholds, E-values, different
imputation schemes, subgroup interaction tests — belongs in `supplementary_methods.md`.

## What goes into supplementary_methods.md

If any of the following would take more than a short paragraph in the main text, move
the detail to `project/07_manuscript/supplementary_methods.md` and reference it from
the main text (e.g. "details are provided in Supplementary Methods"):

- Exhaustive sensitivity and robustness analysis specifications
- Full database query strings, ICD/CPT/ATC code lists, variable mapping dictionaries
- Detailed experimental SOPs (primer sequences, antibody catalog numbers, reaction
  conditions, cycling parameters)
- Algorithm hyperparameter grids, loss function derivations, network architecture tables
- Extended bioinformatics pipeline parameters and QC thresholds
- Complete search strategies for systematic reviews (per-database Boolean expressions)

The supplementary file is optional. If the study is straightforward and the main text
is not bloated, there is no need to create one.

## Procedure
1. Re-read the protocol. The Methods describes what was actually done, in the order the
   reporting guideline expects. Follow the guideline's item list; if the guideline wants a
   subsection you have nothing for, that is a finding, not something to gloss over.
2. Write `project/07_manuscript/methods.md` following the four-step skeleton above.
   Adapt the subsection headings to the study type and target journal — the skeleton is
   a reference, not a rigid template.
3. If technical detail is extensive, write `project/07_manuscript/supplementary_methods.md`
   and cross-reference it from the main text.
4. Cite methodological choices with pandoc markers `[@key]` — the cutoff you adopted, the
   scoring system, the model, the guideline itself. Keys must come from records already
   retrieved this session.
5. Numbers: study period, follow-up, n screened/excluded/analysed, software versions —
   all must already exist in `03_analysis/results/*.json`. If a number you need is not
   there, go back and dump it from code rather than typing it.
6. Do not describe an analysis you did not run, and do not omit one you did.

## Outputs
- `07_manuscript/methods.md`
- `07_manuscript/supplementary_methods.md` (optional, only if needed)

## Hard rules
- ONE main-text section file this stage. Do not also write Results.
- Statistical Analysis is the last substantive method section in the main text.
  Do not add further analytical subsections (e.g. "Sensitivity Analysis",
  "Subgroup Analysis", "Machine Learning Pipeline") as separate main-text headings
  after it. Mention them briefly within Statistical Analysis; elaborate in the
  supplementary file.
- Every number traceable to results JSON (gate: `numbers_have_provenance`).
- No placeholders. `TODO`, `TBD`, `xx.x` and friends fail the gate.
- Past tense, declarative. No "we aimed to comprehensively investigate".

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "methods drafted; guideline items covered: <...>; citations used: <n>; supplementary methods: yes/no"
```

