# S15 - Deep-read the papers that carry the Discussion

## Purpose
Abstracts are enough to frame the Introduction. They are not enough to compare methods and
effect sizes with prior work. Fetch and read ~5 full texts properly.

## Procedure
1. Select the papers that the Discussion genuinely depends on. Typically:
   - the closest prior study on the same question (whatever the direction of its result),
   - the study that most disagrees with your finding,
   - the methodological reference your approach stands on,
   - the largest or most authoritative study in the area,
   - the paper a reviewer will ask "why does your result differ from this one".
   Selection is by argumentative need, not by impact factor.
2. Fetch open-access full text. Legal open-access routes only:
```
python tools/pubmed/fulltext.py --citekey smith2023 --citekey lee2021
```
   It tries Europe PMC / PMC, Unpaywall, OpenAlex and Crossref, saves the PDF or XML to
   `06_refs/fulltext/`, and records which route worked. If nothing is open access, record
   `"fulltext": "<url>"` with `"access": "paywalled"` and note that only the abstract was
   available - never pretend to have read a paywalled full text.
3. Read each one and write structured notes to `06_refs/deepread/<citekey>.md`:
```markdown
# <citekey> - <short title>
## Design and population
## What they did differently from us
## Their key numbers
## How this supports or contradicts our finding
## What a reviewer would take from this
```
   Notes must be substantive; the gate rejects notes under 400 characters as evidence that
   no real read happened.
4. Index them in `project/06_refs/deepread/deepread_index.json`:
```json
{"selected": [{"citekey": "", "pmid": "", "reason": "why this paper carries part of the Discussion",
  "access": "oa|paywalled", "fulltext": "06_refs/fulltext/<file>.pdf",
  "notes": "06_refs/deepread/<citekey>.md"}]}
```
5. Update `03_analysis/notes.md` -> `Discussion points` with what the deep reads changed.
   If a deep read overturned an assumption, that is the most valuable output of this stage.

## Outputs
- `06_refs/deepread/deepread_index.json`
- (plus per-paper notes and fetched full texts)

## Hard rules
- Every selected citekey must already be in `library.json`.
- Every selection needs a recorded reason. "Highly cited" is not a reason.
- If a paper turns out not to matter, remove it from the index and record why - the gate at
  S16 requires every indexed paper to be cited in the Discussion.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "<n> deep reads: <citekeys>; changed my view on: <...>"
```
