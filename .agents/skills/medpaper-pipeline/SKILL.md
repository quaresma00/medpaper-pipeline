---
name: medpaper-pipeline
description: Drives a gated, resumable medical/clinical research paper pipeline from a research idea through feasibility, data acquisition, exploratory analysis, figure and table production, IMRAD writing, journal selection and a submission-ready bundle. Use whenever the task involves a medical research idea, a clinical manuscript, a research protocol, literature retrieval via PubMed, publication-grade figures or three-line tables, journal selection, or a submission package. Do not follow the workflow from memory - run `python tools/wf.py status` and obey the stage card it prints.
compatibility: Requires Python 3.11+ for the driver. Figure and table production additionally need matplotlib, numpy and openpyxl. Network access is required for PubMed, Crossref and Unpaywall. Set NCBI_API_KEY to raise the E-utilities rate limit.
metadata:
  version: "1.0.0"
  entrypoint: "python tools/wf.py status"
---

# medpaper pipeline

## Master Template & Dispatch Rule

The official and authoritative master template of this pipeline is strictly anchored at:
`F:\workspace\medpapaer\gemini`

When this skill is invoked:
1. **Existing paper project**: If the current workspace already contains `pipeline/` and `tools/wf.py`, resume the pipeline immediately by running:
   ```bash
   uv run python tools/wf.py status
   ```
2. **New / Empty project**: If the current workspace lacks the pipeline files, do NOT fail or invent files. Automatically copy the complete purified engine structure (`pipeline/`, `tools/`, `project/`, `reference/`, `.agent/`, `.agents/`, `requirements.txt`, `.gitignore`) directly from the master template at `F:\workspace\medpapaer\gemini` into the current workspace, run:
   ```bash
   uv run python tools/wf.py init
   ```
   and proceed to Stage S01.

This repository holds a 20-stage research pipeline. The workflow is **not** in this file
and must not be reconstructed from memory. It lives in `pipeline/pipeline.toml` and
`pipeline/stages/*.md`, and a CLI hands you exactly one stage at a time.

That indirection is the point. A long prompt degrades as context is compacted; a state
file on disk does not. Anything you need to know is one command away, always current.

## The only loop you need

```bash
uv run python tools/wf.py status                 # where am I, what is blocking, full stage card
<do the work described on the card>
uv run python tools/wf.py check                  # run the stage's gate
<fix what it reports>
uv run python tools/wf.py advance --note "..."   # closes the stage; refuses on a red gate
```

**Run `status` first, every session, before anything else.** It prints the invariants, the
progress map, the gate state, the last handoff note, the declared outputs, and the whole
stage card. After a context reset that single command restores everything that matters.

Never infer the current stage from the conversation, from which files exist, or from what
you remember doing. Ask the CLI.

## Other commands

| Command | Use |
|---|---|
| `wf init` | First time only: scaffold `project/` and create the run state |
| `wf doctor` | Environment and wiring check; run when something behaves oddly |
| `wf card [STAGE]` | Print any stage card (e.g. `wf card S11`) |
| `wf check [STAGE]` | Run a gate without advancing |
| `wf tree -v` | Whole pipeline with per-stage outputs and gates |
| `wf decide NAME VALUE --why "..."` | Record a gated decision plus its rationale |
| `wf note "..."` | Append to the handoff log |
| `wf loop --to S05_analysis --why "..."` | Deliberately reopen an earlier stage |
| `wf clean [--apply]` | Report scratch and undeclared files; delete scratch |
| `wf config set KEY VALUE` | Override a target (word counts, reference counts, caps) |
| `wf invariants` | Reprint the non-negotiable rules |

## Non-negotiable rules

These are also printed by `wf status`, and several are mechanically enforced.

1. **Literature comes from the API, never from memory.** Use `tools/pubmed/`. Every search
   caches its raw payload and appends to `06_refs/cache/scan_manifest.json`. A reference
   that is not in `06_refs/verified.json` with `verified: true` does not exist. Never state
   a PMID, DOI, title, journal, year or finding you did not retrieve.
2. **No number without provenance.** Every figure in the manuscript, tables and abstract
   must already exist in `03_analysis/results/*.json`, written there by code that ran.
   Never compute a statistic in prose. The gate extracts numeric tokens and rejects
   unmatched ones.
3. **One manuscript section per stage.** Never emit Methods and Results together.
4. **Nothing outside the declared outputs.** `wf status` lists what this stage may create.
   Scratch work goes in `project/temp/` and is deleted before advancing.
5. **Figures are verified by looking at them.** Deterministic QC first
   (`tools/figures/qc.py`), then load the rendered PNG as an image. Reading the plotting
   code is not verification, and saying you verified without loading the image is a
   fabrication.
6. **No explanatory prose inside figure panels.** Key visual guide goes in the legend (concise 40–80 words, visual guide only; strictly NO duplication of Methods/Results and NO abbreviations block). Full abbreviations across all text, figures, and tables belong centrally to `statements.md`. Removals from panels are logged to `05_figures/moved_to_legend.md`.
7. **Language polishing changes wording only.** Never a number, never a citation, never a
   figure/table reference. Snapshot before the pass
   (`python tools/text/polish.py snapshot`); the gate diffs against it.
8. **A red gate means stop and fix, not `--force`.** `--force` exists for a deliberate,
   recorded override; it writes the violation into the handoff log.

## Do not let another skill replace a stage

A general medical-research skill suite may also be installed. Skills that produce an artifact
a stage declares write to different paths and carry no gate, so substituting one leaves the
gate red with nothing that can satisfy it:

| Do not use | Use instead |
|---|---|
| `write-paper` | S08, S09, S14, S16 |
| `orchestrate`, `manage-project`, `intake-project` | `wf status`, `wf init`, S01 |
| `search-lit`, `medsci-lit-api` | `tools/pubmed/client.py` |
| `make-figures` | S11 + `tools/figures/` |
| `manage-refs`, `verify-refs` | S13 + `tools/pubmed/verify.py` |
| `polish-language`, `humanize` | S19 + `tools/text/polish.py` |
| `find-journal`, `sync-submission` | S18, S20 |
| `write-protocol`, `analyze-stats` | S03/S06, S05 |

Complementary and worth using inside a stage: `check-reporting` (guideline compliance item by
item, which the pipeline does not do), `self-review` / `peer-review` / `revise` (post
submission), `deidentify` / `generate-codebook` / `clean-data` at S04, `calc-sample-size` /
`design-study` / `define-variables` at S03, and the imaging/ML skills, which are a different
domain entirely.

The test: does the skill produce an artifact a stage declares? Then it must not be used unless
its output lands at the declared path and passes that stage's gate. Does it produce analysis
or a review? Then it is fine anywhere.

The full classification is in `reference/skill_policy.toml`, enforced by a `PreToolUse` hook
so a blocked skill cannot be activated at all:

```
python tools/hooks/skill_guard.py --audit              # every installed skill by verdict
python tools/hooks/skill_guard.py --explain write-paper
```

## Where things are

```
pipeline/pipeline.toml      the workflow definition (single source of truth)
pipeline/stages/*.md        one instruction card per stage
tools/wf.py                 the driver
tools/pubmed/               PubMed / Crossref / Unpaywall clients, library builder, verifier
tools/tables/threeline.py   three-line xlsx writer
tools/figures/style.py      journal rcParams + panel-first figure builder
tools/figures/qc.py         deterministic figure QC
tools/text/polish.py        de-AI + academic-English linter, fact-preservation diff
reference/                  figure and table standards, loaded on demand
project/                    the paper being written; folder per phase
project/.wf/state.json      run state
project/.wf/handoff.md       append-only handoff log; read it when resuming
```

## Handoff discipline

Before advancing, record what a stranger would need to pick this up: what was produced,
what was decided and why, and what is still open. `wf advance` refuses without it. This is
what makes the pipeline survive a context reset, a new session, or a different IDE.
