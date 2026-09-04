# S08 - Methods

## Purpose
Write the Methods section. One file, this stage only.

## Inputs
- `01_protocol/protocol_final.md` and `01_protocol/protocol_diff.md`
- `02_data/codebook.md`, `02_data/provenance.md`
- `03_analysis/method_scan.md` (for the methods you cite)
- `03_analysis/results/*.json` (for every number)

## Procedure
1. Re-read the protocol. The Methods describes what was actually done, in the order the
   reporting guideline expects. Follow the guideline's item list; if the guideline wants a
   subsection you have nothing for, that is a finding, not something to gloss over.
2. Write `project/07_manuscript/methods.md`. Typical subsections:
   study design and setting; data source and period; participants and eligibility;
   exposure/predictor definition; outcome definition and ascertainment; covariates;
   statistical analysis; sensitivity analyses; software and versions; ethics.
3. Cite methodological choices with pandoc markers `[@key]` - the cutoff you adopted, the
   scoring system, the model, the guideline itself. Keys must come from records already
   retrieved this session.
4. Numbers: study period, follow-up, n screened/excluded/analysed, software versions -
   all must already exist in `03_analysis/results/*.json`. If a number you need is not
   there, go back and dump it from code rather than typing it.
5. Do not describe an analysis you did not run, and do not omit one you did.

## Outputs
- `07_manuscript/methods.md`

## Hard rules
- ONE section file this stage. Do not also write Results.
- Every number traceable to results JSON (gate: `numbers_have_provenance`).
- No placeholders. `TODO`, `TBD`, `xx.x` and friends fail the gate.
- Past tense, declarative. No "we aimed to comprehensively investigate".

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "methods drafted; guideline items covered: <...>; citations used: <n>"
```
