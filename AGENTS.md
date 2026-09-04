# medpaper pipeline - repository instructions

This repository is a **gated medical research paper pipeline**. Do not work from memory and
do not treat this file as the workflow.

## Start here, every session

```
python tools/wf.py status
```

That prints the current stage, the non-negotiable invariants, the gate state, the last
handoff note, the outputs this stage may create, and the full stage card. Do what the card
says, then:

```
python tools/wf.py check
python tools/wf.py advance --note "what was produced, what was decided, what is open"
```

If you have lost track of anything, run `status` again. Never guess the stage.

## Absolute rules

1. Literature only through `tools/pubmed/`. A reference absent from
   `project/06_refs/verified.json` with `verified: true` does not exist. Never write a
   PMID, DOI, title, journal or year from memory.
2. Every number in the manuscript must already be in `project/03_analysis/results/*.json`,
   written by code that ran. Never compute a statistic in prose.
3. One manuscript section file per stage.
4. Create only the outputs `wf status` declares. Scratch goes in `project/temp/` and is
   deleted before advancing.
5. Figures are verified by loading the rendered PNG and looking at it, after
   `python tools/figures/qc.py --all` passes. Reading the plotting code is not verification.
6. No explanatory text inside figure panels; it belongs in the legend.
7. Language polishing changes wording only, never a number, a citation or a figure/table
   reference. Snapshot first: `python tools/text/polish.py snapshot`.
8. A red gate means fix it, not `--force`.

## Skill arbitration

If a general medical-research skill suite is also installed, do not let it replace a stage.
Skills that produce an artifact a stage declares (`write-paper`, `make-figures`, `search-lit`,
`manage-refs`, `polish-language`, `find-journal`, `write-protocol`, `analyze-stats`,
`orchestrate`, `manage-project`) write to different paths and carry no gate, so using one
leaves the gate red with no way to satisfy it. The pipeline's own tools are the only route.

Skills that produce analysis or review rather than a declared artifact are fine, and some are
genuinely useful inside a stage: `check-reporting` for guideline item-by-item compliance,
`self-review` / `peer-review` / `revise` for post-submission work, `deidentify` /
`generate-codebook` at S04, `calc-sample-size` / `design-study` at S03.

Full detail: `.agents/skills/medpaper-pipeline/SKILL.md`, `pipeline/pipeline.toml`,
`pipeline/stages/`.
