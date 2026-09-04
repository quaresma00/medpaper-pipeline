# medpaper on Google Antigravity

A 20-stage medical research paper pipeline with enforced gates. The workflow is not a
prompt: it lives in `pipeline/` and a CLI hands the agent one stage at a time, so it does
not decay as the context window compacts.

## Install

```bash
unzip medpaper-antigravity.zip
cd medpaper-antigravity
python bootstrap.py
```

`bootstrap.py` creates `.venv`, installs the pinned dependencies, wires the adapters,
scaffolds `project/`, then runs `doctor` and the self test. Python 3.11+ is required for the
driver (`tomllib`); the driver itself has no third-party dependencies.

Open the folder as the workspace in Antigravity. Set these before running searches:

```bash
export NCBI_API_KEY=...                  # raises PubMed from 3 to 10 requests/second
export NCBI_API_EMAIL=you@example.org    # required by Unpaywall for full-text retrieval
```

On Windows PowerShell use `$env:NCBI_API_KEY = "..."`.

## What Antigravity reads

The bundle covers both the IDE and the CLI, because they look in different places.

| File | Read by | Role |
|---|---|---|
| `.agent/rules/medpaper-pipeline.md` | IDE | Workspace rule, injected as passive context |
| `.agent/workflows/medpaper-resume.md` | IDE | Slash command: `/medpaper-resume` |
| `.agents/AGENTS.md` | CLI (`agy`) | Project rules, merged at session start |
| `.agents/skills/medpaper-pipeline/SKILL.md` | CLI + IDE | The skill, loaded on demand |
| `AGENTS.md` | both, as a fallback | Same content at the repo root |

Rules are passive constraints; workflows are procedures you trigger. Both are wired, so you
can either let the rule guide the agent or invoke `/medpaper-resume` explicitly.

To make the rule and skill available in every workspace rather than just this one, copy
them to the global locations: `~/.gemini/config/` for the CLI, or use the `+Global` option
in the IDE's rules panel. Keep the pipeline itself in the project - it is per-paper state,
not a global preference.

All adapter files are short and say the same thing: run `python tools/wf.py status` and obey
the stage card. None contains the workflow, so editing a stage never means editing an
adapter.

## Use

Put your research idea file in `project/00_input/`, then in Antigravity:

```
/medpaper-resume
```

or, in plain chat:

```
Run python tools/wf.py status and start the pipeline.
My research idea is in project/00_input/idea.md
```

From then on the loop is always the same:

```bash
python tools/wf.py status                     # where am I, what is blocking, full stage card
#   ... do the work the card describes ...
python tools/wf.py check                      # run the stage's gate
python tools/wf.py advance --note "..."       # close the stage
```

`status` prints the invariants, the progress map, the gate state, the last handoff note, the
outputs this stage may create, and the whole stage card. After a context compaction that one
command restores everything. The agent should never infer the current stage from the
conversation.

## Commands

| Command | Purpose |
|---|---|
| `wf tree -v` | Whole pipeline with outputs and gates |
| `wf card S11` | Read any stage card |
| `wf check S09` | Run any gate without advancing |
| `wf decide NAME VALUE --why "..."` | Record a gated decision (rationale >= 40 chars) |
| `wf loop --to S05_analysis --why "..."` | Reopen an earlier stage |
| `wf clean [--apply]` | Report scratch and undeclared files |
| `wf config set intro_words_max 600` | Override a target for this project |
| `wf doctor` | Environment and wiring check |

Prefix each with `python tools/wf.py`.

## What the gates stop

- **Fabricated references.** Every search caches its raw API payload; a citekey absent from
  `project/06_refs/verified.json` with `verified: true` fails the gate.
- **Fabricated statistics.** Every number in the manuscript must already exist in
  `project/03_analysis/results/*.json`, written by code that ran.
- **Running ahead.** Later stages' outputs cannot exist yet; one manuscript section per stage.
- **Unverified figures.** Deterministic QC plus a recorded decision that the PNG was opened
  and looked at. Reading the plotting code does not count.
- **Corrupted polishing.** S19 snapshots the manuscript, then requires the multiset of
  numbers, the set of citekeys and the set of figure/table references to be unchanged.

## Notes for Antigravity specifically

- **Browser and artifact features are not needed.** Everything runs through the terminal and
  the filesystem. If the agent proposes browsing for a citation, redirect it to
  `tools/pubmed/client.py` - only the cached API payload satisfies the gate.
- **Command approval.** The agent will run `python tools/wf.py ...` frequently. Allow-listing
  `python tools/wf.py` and `python tools/figures/qc.py` removes most approval prompts without
  granting anything broad.
- **Network access is required** for PubMed, Crossref, Unpaywall and the S18 guideline fetch.
  Without it, stages S02, S05, S07, S13, S15 and S18 fail at the gate rather than inventing
  data, which is the intended behaviour.
- **Looking at figures.** S11 requires the agent to load the rendered PNG as an image. If the
  model cannot take image input in your setup, `python tools/figures/qc.py --crop "Figure 1"
  --cols 2 --cell B` writes a cropped panel you can inspect yourself; the gate then needs
  your confirmation via `wf decide figures_visually_confirmed YES --why "..."`.

## Verify the install

```bash
python tools/wf.py doctor              # expect: 20/20 stage cards, 36/36 gate checks
.venv/bin/python tools/selftest.py     # expect: 78/78  (Windows: .venv\Scripts\python.exe)
.venv/bin/python tools/selftest.py --online   # 81/81, exercises the live APIs
```
