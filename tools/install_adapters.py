#!/usr/bin/env python3
"""Sync the skill into every supported agent IDE's discovery path.

One source of truth: .agents/skills/medpaper-pipeline/SKILL.md
Everything else is generated. Re-run after editing it.

    python tools/install_adapters.py            # sync all detected targets
    python tools/install_adapters.py --list
    python tools/install_adapters.py --only kiro --only claude
    python tools/install_adapters.py --check    # report drift, change nothing

Why copies rather than symlinks: on Windows symlinks need Developer Mode or elevation,
and several of these tools read the file before any link resolution hook could run.
A copy plus a drift check is boring and reliable.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SRC = ROOT / ".agents" / "skills" / "medpaper-pipeline"

# Agent Skills standard (agentskills.io): a directory containing SKILL.md.
# Paths verified against each tool's documented workspace discovery location.
SKILL_TARGETS = {
    "codex":       ".agents/skills/medpaper-pipeline",       # source of truth
    "antigravity": ".agents/skills/medpaper-pipeline",       # shares .agents/ with Codex
    "kiro":        ".kiro/skills/medpaper-pipeline",
    "claude":      ".claude/skills/medpaper-pipeline",
}

POINTER = """\
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
"""

STEERING = """\
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
"""

KIRO_HOOK = """\
{
  "version": "v1",
  "hooks": [
    {
      "name": "medpaper: show pipeline state on session start",
      "trigger": "SessionStart",
      "description": "Prints the current pipeline stage, gate state and last handoff note at the start of every session, so the agent never has to guess where the work stopped.",
      "action": {
        "type": "command",
        "command": "python tools/wf.py status --brief",
        "timeout": 60
      }
    }
  ]
}
"""

KIRO_SKILL_GUARD = """\
{
  "version": "v1",
  "hooks": [
    {
      "name": "medpaper: block skills that replace a pipeline stage",
      "trigger": "PreToolUse",
      "matcher": "disclose_context",
      "description": "Refuses activation of skills that would substitute for a pipeline stage and leave its gate unsatisfiable (write-paper, orchestrate, make-figures, search-lit and others), and asks for confirmation on skills that merely overlap a stage. Decisions come from reference/skill_policy.toml.",
      "action": {
        "type": "command",
        "command": "python tools/hooks/skill_guard.py",
        "timeout": 30
      }
    }
  ]
}
"""

WORKFLOW = """\
---
description: Resume or start the medpaper research pipeline at the correct stage
---

Run `python tools/wf.py status` and follow the stage card it prints, exactly.

Then `python tools/wf.py check`, fix everything it reports, and close the stage with
`python tools/wf.py advance --note "..."`.

Do not skip stages, do not work from memory, and do not create files the stage does not
declare.
"""

# Non-skill pointer files, keyed by the tool that reads them.
FILE_TARGETS = {
    "codex":       [("AGENTS.md", POINTER)],
    "antigravity": [(".agents/AGENTS.md", POINTER),
                    (".agent/rules/medpaper-pipeline.md", POINTER)],
    "kiro":        [(".kiro/steering/medpaper-pipeline.md", STEERING),
                    (".kiro/hooks/medpaper-status.json", KIRO_HOOK),
                    (".kiro/hooks/medpaper-skill-guard.json", KIRO_SKILL_GUARD)],
    "claude":      [("CLAUDE.md", POINTER)],
}


def copy_skill(dest_rel: str, check: bool) -> tuple[str, str]:
    dest = ROOT / dest_rel
    if dest.resolve() == SKILL_SRC.resolve():
        return dest_rel, "source"
    src_files = [p for p in SKILL_SRC.rglob("*") if p.is_file()]
    if check:
        if not dest.exists():
            return dest_rel, "MISSING"
        for p in src_files:
            d = dest / p.relative_to(SKILL_SRC)
            if not d.exists() or not filecmp.cmp(p, d, shallow=False):
                return dest_rel, "STALE"
        return dest_rel, "ok"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_SRC, dest)
    return dest_rel, f"synced ({len(src_files)} file(s))"


def write_file(rel: str, content: str, check: bool) -> tuple[str, str]:
    p = ROOT / rel
    if check:
        if not p.exists():
            return rel, "MISSING"
        return rel, "ok" if p.read_text(encoding="utf-8") == content else "STALE"
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    return rel, "updated" if existed else "created"


def bundle_target() -> str | None:
    """Which IDE this checkout is for, if it was built by tools/package.py.

    A distributed bundle ships only one IDE's adapters, so syncing all four would recreate
    the others and defeat that. The development repo has no marker and syncs everything.
    """
    marker = ROOT / ".medpaper-target"
    if not marker.exists():
        return None
    name = marker.read_text(encoding="utf-8").strip()
    return name if name in SKILL_TARGETS else None


def main() -> int:
    ap = argparse.ArgumentParser(description="sync the skill into each IDE's discovery path")
    ap.add_argument("--only", action="append", default=[],
                    choices=sorted(SKILL_TARGETS), help="restrict to these targets")
    ap.add_argument("--all", action="store_true",
                    help="sync every target even in a single-IDE bundle")
    ap.add_argument("--check", action="store_true", help="report drift without writing")
    ap.add_argument("--list", action="store_true", help="show the target map and exit")
    args = ap.parse_args()

    if args.list:
        for name in sorted(SKILL_TARGETS):
            print(f"{name}")
            print(f"  skill  {SKILL_TARGETS[name]}/SKILL.md")
            for rel, _ in FILE_TARGETS.get(name, []):
                print(f"  file   {rel}")
        return 0

    if not (SKILL_SRC / "SKILL.md").exists():
        print(f"error: source skill missing at {SKILL_SRC / 'SKILL.md'}", file=sys.stderr)
        return 1

    marked = None if args.all else bundle_target()
    names = args.only or ([marked] if marked else sorted(SKILL_TARGETS))
    if marked and not args.only:
        print(f"bundle target: {marked}  (from .medpaper-target; use --all to override)\n")
    rows: list[tuple[str, str, str]] = []
    done_skills: set[str] = set()
    done_files: set[str] = set()

    for name in names:
        rel = SKILL_TARGETS[name]
        if rel not in done_skills:
            done_skills.add(rel)
            r, status = copy_skill(rel, args.check)
            rows.append((name, f"{r}/", status))
        for frel, content in FILE_TARGETS.get(name, []):
            if frel in done_files:
                continue
            done_files.add(frel)
            r, status = write_file(frel, content, args.check)
            rows.append((name, r, status))

    w1 = max(len(r[0]) for r in rows)
    w2 = max(len(r[1]) for r in rows)
    bad = 0
    for name, target, status in rows:
        if status in ("MISSING", "STALE"):
            bad += 1
        print(f"{name:<{w1}}  {target:<{w2}}  {status}")

    if args.check:
        print("\n" + ("adapters are in sync" if bad == 0
                      else f"{bad} adapter(s) out of sync - run without --check"))
        return 0 if bad == 0 else 2

    print("\nsynced. The workflow itself lives in pipeline/; these files only point at it,")
    print("so editing a stage card never requires touching an adapter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
