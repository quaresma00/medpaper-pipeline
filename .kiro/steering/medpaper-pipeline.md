---
inclusion: always
---

# medpaper pipeline

This workspace is driven by a gated pipeline, not by prompt instructions.

**Before doing anything in this repo, run `python tools/wf.py status`.** It returns the
current stage, the invariants, the gate state, the last handoff and the full stage card.
Do not infer the stage from the conversation or from which files exist.

Loop: `wf status` -> do the work -> `wf check` -> `wf advance --note "..."`.

Hard rules, several mechanically enforced by the gates:

- Literature only via `tools/pubmed/`; a reference not in `project/06_refs/verified.json`
  with `verified: true` does not exist. Never recall a PMID, DOI, title, journal or year.
- Every manuscript number must already exist in `project/03_analysis/results/*.json`,
  written by executed code.
- One manuscript section per stage.
- Only create the outputs the stage declares; scratch lives in `project/temp/`.
- Figures: `python tools/figures/qc.py --all`, then load the PNG and look at it. Reading
  the plotting code is not verification.
- No explanatory prose inside figure panels.
- Language polishing changes wording only, never a number, a citation or a figure/table
  reference. Snapshot before the pass: `python tools/text/polish.py snapshot`.

## Skill arbitration in this workspace

A general medical-research skill suite may also be installed at the user level. Several of
its skills do the same job as a pipeline stage, but write their outputs elsewhere and carry
no gate, so using one instead of the stage leaves the gate red with no way to satisfy it.

**Never use these in place of a stage. In this workspace the pipeline wins:**

| Skill | Superseded by | Why |
|---|---|---|
| `write-paper` | S08, S09, S14, S16 | A competing 8-phase manuscript workflow with no gates |
| `orchestrate` | `wf status` | Routes the task away from the pipeline; the stage card is the router |
| `manage-project`, `intake-project` | `wf init`, `wf status`, S01 | Competing project scaffold and state |
| `search-lit`, `medsci-lit-api` | `tools/pubmed/client.py` | Payload never reaches `06_refs/cache/scan_manifest.json`, so `pubmed_cache_fresh` cannot pass |
| `make-figures` | S11 + `tools/figures/` | No `qc_report.json`, no archetype element checks, wrong output paths |
| `manage-refs`, `verify-refs` | S13 + `tools/pubmed/verify.py` | Does not write `06_refs/verified.json`, so every citekey reads as unverified |
| `polish-language`, `humanize` | S19 + `tools/text/polish.py` | No pre-polish snapshot, so fact preservation cannot be proven |
| `find-journal`, `sync-submission` | S18, S20 | Bypasses the fetched-and-snapshotted guideline requirement |
| `write-protocol` | S03, S06 | Competing protocol format; the gate checks specific headings |
| `analyze-stats` | S05 | No results-JSON provenance contract, so downstream numbers fail their gate |

**These are complementary. Use them inside the relevant stage:**

- `check-reporting` - run it at S12 or S19 against the declared reporting guideline. The
  pipeline records which guideline applies but does not check it item by item; this closes
  that gap.
- `self-review`, `peer-review`, `revise` - post-submission work, which the pipeline does not
  cover at all.
- `deidentify`, `generate-codebook`, `clean-data`, `version-dataset` - useful at S04, as long
  as the codebook and `dataset_summary.json` still land where S04 declares.
- `calc-sample-size`, `design-study`, `define-variables` - useful at S03, feeding into
  `protocol_v1.md`.
- Imaging and ML skills (`model-scaffold`, `radiomics-ml`, `explainability`,
  `preprocess-imaging`, `model-validation`, and similar) - a different domain, no conflict.

Rule of thumb: a skill that produces an **artifact a stage declares** must not be used unless
its output lands at the declared path and satisfies that stage's gate. A skill that produces
**analysis or a review** is fine anywhere.

The full classification is data, not prose: `reference/skill_policy.toml`. A `PreToolUse`
hook (`.kiro/hooks/medpaper-skill-guard.json`) enforces it, so this is not merely advice -
a blocked skill cannot be activated. Inspect or change it with:

```
python tools/hooks/skill_guard.py --audit            # every installed skill by verdict
python tools/hooks/skill_guard.py --explain write-paper
```

Detail: #[[file:.agents/skills/medpaper-pipeline/SKILL.md]]

Reference material, loaded when relevant:
#[[file:reference/figure-standards.md]]
#[[file:reference/table-standards.md]]
