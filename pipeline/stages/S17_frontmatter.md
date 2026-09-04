# S17 - Front matter: authors, title page, abstract, statements

## Purpose
Collect the administrative material only the user can supply, then write the title page,
Abstract and required statements. The Abstract is written last on purpose - it is derived
from finished sections, so its numbers cannot drift.

## This stage needs the user
Ask for, and do not guess:
- every author's full name as it should be published, ORCID, degrees, and the exact
  affiliation string(s) per author, in the intended author order;
- the corresponding author's email, postal address and phone;
- funding sources with grant numbers;
- conflicts of interest per author;
- ethics approval body and protocol number, and the consent statement;
- data and code availability position;
- acknowledgements;
- author contributions (CRediT roles), if the journal asks for them;
- any preprint already posted, and whether the work was presented at a conference.

Write it verbatim to `project/00_input/author_info.json`:
```json
{"authors": [{"name": "", "orcid": "", "degrees": "", "affiliation_ids": [1], "credit": []}],
 "affiliations": [{"id": 1, "text": ""}],
 "corresponding": {"name": "", "email": "", "address": "", "phone": ""},
 "funding": "", "conflicts": "", "ethics_approval": "", "consent": "",
 "data_availability": "", "code_availability": "", "acknowledgements": "",
 "preprint": null, "prior_presentation": null}
```
Never invent an affiliation, an ORCID, or a grant number. Leave `""` and ask again.

## Procedure
1. `project/07_manuscript/title_page.md`: title, running title, author list with
   superscript affiliation markers, affiliations, corresponding author block, word counts,
   figure/table counts, keywords (MeSH-derived where possible).
   Offer the user 3 title options and let them choose; note the choice in the handoff.
2. `project/07_manuscript/abstract.md`: structured to the design
   (Background / Methods / Results / Conclusions, or the journal's headings once known at
   S18 - revisit then if they differ). Every number copied from `results.md`, which means
   from a results JSON. The Abstract's primary result must be identical to the Results'.
3. `project/07_manuscript/statements.md`: ethics, consent, funding, conflicts, data
   availability, code availability, author contributions, acknowledgements, AI-use
   disclosure. Assemble from `author_info.json`; do not compose ethics text the user did
   not provide.

## Outputs
- `00_input/author_info.json`
- `07_manuscript/title_page.md`
- `07_manuscript/abstract.md`
- `07_manuscript/statements.md`

## Hard rules
- Abstract numbers must trace to results JSON (gate enforces it).
- No conclusion in the Abstract that is not in the Discussion's conclusion.
- If the user has not supplied ethics information, the manuscript cannot be submitted.
  Say that plainly rather than drafting placeholder ethics text.
- Disclose AI assistance honestly if the journal requires it. Most now do.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "front matter complete; title chosen: <...>; outstanding from user: <...>"
```
