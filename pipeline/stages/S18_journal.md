# S18 - Journal selection by acceptance probability, then the real guidelines

## Purpose
Choose where to send it, ranked by the chance of acceptance rather than by impact factor
or quartile. Then fetch the live author instructions instead of recalling them.

## Procedure
1. Read the finished manuscript and `project/07_manuscript/review_report.md` first. The
   shortlist must be informed by the peer review report's recommended journal profile,
   design strength, sample size, novelty, and geographic generalisability.
   **Target requirement**: Must be **SCIE-indexed**. Lower-impact journals (Q3/Q4, IF 1–3)
   are fully acceptable; the governing criterion is **high acceptance probability** and
   rapid, reliable editorial turnaround.
2. Search for candidate venues. Look for journals that recently published work of the same
   design and scale on adjacent questions - that is the strongest signal a paper of this
   type is in scope:
```bash
uv run python tools/pubmed/client.py search --query "<topic> <design>" --retmax 100 --journals
```
   This reports the journal distribution across retrieved hits. Use it, plus the journals
   already in `library.json`, as the candidate pool.
3. Write `project/08_submission/journal_shortlist.md` with headings
   `Ranking basis`, `Shortlist`, `Reject-fallback cascade`.
   For each of 5-8 candidates give: journal, publisher, SCIE indexing status (verified),
   impact factor / quartile, scope fit in one sentence, evidence that it publishes this
   design and scale (cite retrieved papers), realistic acceptance odds with reasoning
   (prioritising high-acceptance venues), APC, typical time to first decision, and the
   main reason it might reject this paper.
   Rank strictly by **acceptance probability x scope fit**.
   `Reject-fallback cascade`: if #1 rejects, where next, and what would have to change.
4. Present the shortlist to the user and wait. The user chooses.
5. Once chosen, fetch the actual author instructions from the journal's own site, snapshot
   the raw page under `project/08_submission/cache/`, and write
   `project/08_submission/target_journal.json`:
```json
{"journal": "", "issn": "", "publisher": "", "scie_indexed": true,
 "guidelines_url": "", "guidelines_fetched_at": "", "chosen_by_user": true}
```
6. Write `project/08_submission/guidelines_extract.md`. It must quote the exact
   constraints, include the source URL, and cover at minimum:
   `Word limits`, `Reference style`, `Figure` requirements (format, resolution, colour
   mode, dimensions), `Table` requirements, `Required statements`, `Submission items`.
   Add abstract structure, reference count caps, supplementary file rules, cover letter
   expectations, and any reporting-checklist the journal mandates.
7. Reconcile the manuscript against the guidelines and record the deltas: word counts over
   limit, too many references, figure count, abstract headings that differ, missing
   statements. Fix what is mechanical; raise what needs a decision.

## Outputs
- `08_submission/journal_shortlist.md`
- `08_submission/target_journal.json`
- `08_submission/guidelines_extract.md`
- (plus the raw snapshot under `08_submission/cache/`)

## Hard rules
- Never state a journal's word limit, reference style, APC or turnaround time from memory.
  Fetch it, snapshot it, quote it.
- Do not rank by quartile. A Q1 journal that rejects this design in a week is worse than a
  Q3 journal that publishes it.
- Verify SCIE indexing rather than assuming; flag predatory or questionable venues.
- The user chooses the journal. Do not advance before they have.

## Close
Mechanical deltas (word counts, spelling variant, abstract headings, reference caps) are
fixed in the next stage, S19, which is a single polish pass already aimed at this journal.
Record what needs fixing rather than fixing it here.

```
python tools/wf.py decide journal_chosen "<journal name>" --why "<the user's choice and the acceptance-odds reasoning behind the ranking>"
python tools/wf.py check
python tools/wf.py advance --note "target: <journal>; guidelines fetched <date>; deltas for S19 to fix: <...>"
```
