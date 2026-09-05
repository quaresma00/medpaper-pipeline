# S17 - Front matter, Full Manuscript Assembly & Independent SCIE Peer Review

## Purpose
1. Synthesize the optimal scientific title automatically and draft the title page, Abstract and statements (author personal details are deferred to S20 submission packaging).
2. Assemble the full manuscript into a single file (`project/07_manuscript/manuscript_complete.md`).
3. Subject the full manuscript, supplementary methods, and tables to an independent review subagent to evaluate **SCIE publication feasibility and acceptance probability** (aiming for high acceptance probability, low-impact SCIE venues fully acceptable).
4. Perform actionable revisions based on the review report before proceeding.

## Procedure

### Step 1: Automated Title Selection & Deferred Authorship
- **Do NOT ask the user for author details or title choices at this stage.**
- **Title**: Automatically formulate the single most suitable, precise medical title following standard ICMJE/PICO guidelines (`[Exposure/Intervention] and [Outcome] in [Population]: A [Study Design] Study`). Write title and running title directly.
- **Author info placeholder**: Generate `project/00_input/author_info.json` using standard placeholders so the pipeline runs uninterrupted:
  ```json
  {"authors": [{"name": "[Authors to be provided at S20 packaging]", "orcid": "", "degrees": "", "affiliation_ids": [1], "credit": []}],
   "affiliations": [{"id": 1, "text": "[Affiliations to be provided at S20 packaging]"}],
   "corresponding": {"name": "[Corresponding author info at S20]", "email": "", "address": "", "phone": ""},
   "funding": "To be confirmed at S20", "conflicts": "None declared",
   "ethics_approval": "Approved by institutional review board / Not applicable (de-identified data)",
   "consent": "Waived / Informed consent obtained",
   "data_availability": "Available upon reasonable request from the corresponding author",
   "code_availability": "Available from the authors", "acknowledgements": "",
   "preprint": null, "prior_presentation": null}
  ```
- Write `project/07_manuscript/title_page.md`: title, running title, author placeholders, word counts,
  figure/table counts, and **Reference count**.
  - *Reference count rule*: Must count the **actual unique citekeys referenced in the text** (Introduction,
    Methods, Results, Discussion). Absolutely NEVER write the total size of the reference library (e.g. 50).
- Write `project/07_manuscript/statements.md`: ethics, consent, funding, conflicts, data availability,
  code availability, author contributions, acknowledgements, and **Abbreviations**.
  - *Abbreviations section*: Centralize the complete manuscript abbreviations list under `### Abbreviations`.
    Format as an alphabetical semicolon-separated block (e.g. `FDA, Food and Drug Administration; OR, odds ratio; CI, confidence interval.`).
    With this section present, figure legends do NOT need to repeat an Abbreviations block.
- Write `project/07_manuscript/abstract.md`: structured (Background, Methods, Results, Conclusions). Every number copied from `results.md` (provable via results JSON).
- **Keywords Rule**: Keywords must be placed **at the very end of `abstract.md`** (never before Abstract or on a standalone page).
  - Select exactly 3–5 clean, canonical medical terms (e.g. `Keywords: Stents, Biliary strictures, Adverse events, Postmarket surveillance.`).
  - **Strict syntax cleaning**: Never copy raw MeSH qualifiers or codes with slashes (`/`), ampersands (`&`), or semicolons (`;`). Slashes like `Biliary Tract / surgery` are prohibited; clean to `Biliary tract surgery` or `Biliary tract`. Separate keywords solely with commas.

### Step 2: Assemble Complete Manuscript (`manuscript_complete.md`)
Combine the finalized sections in standard publication order into `project/07_manuscript/manuscript_complete.md`:
1. Title Page (`title_page.md`)
2. Structured Abstract & Keywords (`abstract.md`)
3. Introduction (`introduction.md`)
4. Methods (`methods.md`)
5. Results (`results.md`)
6. Discussion (`discussion.md`)
7. Statements & Declarations (`statements.md`)

### Step 3: Independent Subagent Review (SCIE Publication Audit)
Deliver `manuscript_complete.md`, `supplementary_methods.md` (if present), and table files (`04_tables/`) to an independent reviewer subagent (or execute an objective peer review pass) acting as a rigorous SCI peer reviewer and journal editor.

The subagent evaluates **whether this paper meets SCIE publication standards**:
- **Core goal**: Maximize **acceptance probability**. Lower-impact SCIE journals (IF 1–3, Q3/Q4) are completely acceptable, provided the publication probability is high and reliable.
- **Review Dimensions**:
  1. Study design validity, internal consistency, and sample adequacy
  2. Methodological transparency and statistical appropriateness
  3. Novelty/clinical interest relative to low-to-mid tier SCIE journals
  4. Clarity of figures/tables and coherence of findings
  5. Potential fatal flaws (methodological confounders, lack of novelty, overclaims)
- **Output Report**: Save to `project/07_manuscript/review_report.md` with sections:
  - `Overall Verdict`: `READY_FOR_SUBMISSION` / `REVISE_BEFORE_SUBMISSION` / `HIGH_REJECTION_RISK`
  - `Estimated SCIE Acceptance Probability`: (e.g. High >40%, Moderate 20-40%, Marginal 10-20%, Low <10%)
    *(Note: in typical medical publishing, base SCIE acceptance rates sit around 15–25%. A paper with >=10% acceptance odds in a well-chosen low-tier SCIE journal is worth pursuing via targeted revisions).*
  - `Target SCIE Journal Tier & Profile`: Recommended journal profile for high acceptance odds
  - `Major Deficiencies & Required Revisions`: Concrete, prioritized list of items to fix
  - `Fatal Flaws (if any)`: Irreversible issues that would justify stopping the pipeline

### Step 4: Decision Gate & Revision Loop
- **If Acceptance Probability is critically low (<10%) or Fatal Flaws exist**:
  Stop the pipeline. Irreversible flaws (e.g., severe unmitigated confounding, fatal design bias, complete lack of novelty, falsification risks) mean the paper has virtually zero chance of SCIE publication. Present the findings plainly to the user with the exact reasons. Record `wf decide publishability_verdict STOP --why "..."` and do not advance.
- **If Acceptance Probability is >= 10% (even if revisions required)**:
  Perform targeted revisions on the affected section files (e.g. tightening discussion, clarifying methods, qualifying conclusions) to address the reviewer's concerns, then refresh `project/07_manuscript/manuscript_complete.md`.
  Record `wf decide publishability_verdict GO --why "..."`.

## Outputs
- `00_input/author_info.json`
- `07_manuscript/title_page.md`
- `07_manuscript/abstract.md`
- `07_manuscript/statements.md`
- `07_manuscript/manuscript_complete.md`
- `07_manuscript/review_report.md`

## Hard rules
- Title must be chosen automatically by the agent based on PICO/design standards. Do not pause to offer choices.
- Do not interrogate the user for personal author details at this stage; use placeholders.
- Abstract numbers must trace to results JSON.
- An independent review report must be produced and recorded at `07_manuscript/review_report.md`.
- If the reviewer identifies high rejection risk with irreversible flaws, stop the pipeline.

## Close
```bash
uv run python tools/wf.py check
uv run python tools/wf.py advance --note "front matter and full manuscript assembled; SCIE review completed; acceptance probability: <...>; verdict: GO/STOP"
```

