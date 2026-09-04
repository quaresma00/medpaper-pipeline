# S19 - De-AI pass and academic-English polish

## Purpose
Turn correct drafts into publishable prose: strip the patterns that read as machine-written,
bring the language up to SCI standard, and enforce the target journal's house style. Nothing
enters the submission bundle before this.

This runs after the journal is chosen so there is exactly one polish pass, already
conforming to that journal's spelling variant, word limits and abstract structure.

## Snapshot first. This is not optional.
```
python tools/text/polish.py snapshot
```
It copies every section to `07_manuscript/prepolish/` and records, per file, the multiset of
numbers, the set of citekeys and the set of figure/table references. Polishing rewrites
sentences, which is the easiest place in the whole pipeline to lose a value or a citation
without noticing. The gate diffs against this snapshot and will not let you past if
anything changed.

## Procedure

1. **See what needs fixing.**
```
python tools/text/polish.py lint
```
   Four groups: tier-A AI phrases (blocking), tier-B phrases (conventional but overused -
   your call), structural tells (blocking where flagged), and house-style defects (blocking).
   Detail lands in `07_manuscript/polish_report.json`.

2. **Remove the AI tells.** Rewrite the clause; do not delete the sentence to silence the
   check. What the linter catches, and what to do instead:
   - Inflated verbs: `utilize` -> use, `leverage` -> use, `demonstrate` -> show where it
     reads better.
   - Empty intensifiers: "plays a crucial role", "underscores the importance", "holds
     promise", "paves the way". Say what actually happens instead.
   - Framing filler: "it is worth noting that", "it is important to note that", "in the
     realm of", "in today's rapidly evolving". Delete and state the fact.
   - Marketing register: "cutting-edge", "seamlessly", "revolutionize", "game-changer".
     Never appropriate in a clinical paper.
   - Structural rhythm: em-dash overuse, every paragraph the same length, chains of
     "Furthermore / Moreover / Additionally", relentless three-item lists, "not only ... but
     also". Vary the sentence shape and cut the connectives that carry no logic.
   - Stacked hedges: "may potentially suggest that it could possibly". One hedge, or none.
   - Bullet lists and bold text inside narrative sections. Journals want continuous prose.

3. **Polish the English.** Section by section, in this order: Abstract, Introduction,
   Methods, Results, Discussion. Per section:
   - One idea per sentence. Break anything over ~40 words.
   - Put the subject early. Passive voice is fine in Methods, weak elsewhere.
   - Tense: Methods and Results in the past tense; established knowledge in the present.
   - Hedging calibrated to the design. An observational study shows associations; say
     "associated with", never "causes", "proves" or "demonstrates causation".
   - Cut redundancy: "in order to" -> "to", "due to the fact that" -> "because",
     "a total of 1284 patients" -> "1284 patients", "it has been reported that X" -> cite X.
   - Terminology fixed once and reused. Do not alternate between synonyms for the same
     variable - a reviewer reads that as two different things.
   - Non-native patterns: article use before countable/uncountable nouns, "researches" ->
     "research", "the both" -> "both", comparatives without a referent ("higher" - than what).

4. **House style.** The linter settles these definitively; fix all of them:
   abbreviations defined on first use, once, and reused at least twice (each of Abstract and
   body has its own scope); one spelling variant throughout (match the journal); en dash in
   numeric ranges; consistent `P` case and `P value` spelling; `P < 0.001` never `P = 0.000`;
   space between value and unit (`5 mg`), consistent percent style; no sentence starting with
   a numeral; "data were", not "data was"; consistent italics for statistical symbols.

5. **Fit the journal.** Re-read `08_submission/guidelines_extract.md` and conform:
   abstract structure and word cap, main-text word cap, reference cap, required subsection
   headings, spelling variant, whether first person is accepted. Cut content to fit; do not
   compress into denser jargon. If cutting removes something a reviewer needs, move it to the
   supplement and say so in the log.

6. **Prove nothing was broken.**
```
python tools/text/polish.py diff
python tools/text/polish.py lint
```
   `diff` must report that every number, citekey and figure/table reference survived. If it
   reports a loss, restore that text from `07_manuscript/prepolish/` and redo those sentences.

7. **Log it.** Write `project/07_manuscript/polish_log.md`:
   - `AI patterns removed` - pattern, where, and the replacement wording
   - `Language changes by section` - what kind of edit, and why
   - `House style decisions` - spelling variant chosen and on whose authority, abbreviation
     list, symbol conventions
   - `Cut to meet journal limits` - what was removed or moved to the supplement, with counts
     before and after
   - `Read by eye` - which sections you actually reread end to end after editing
   - `Tier-B phrases kept` - each one and why it is right here

8. **Confirm the human-judgement part.** The linter cannot tell whether the prose now reads
   like a person wrote it. Reread each section end to end, then record:
```
python tools/wf.py decide polish_reviewed YES --why "<per section: what you changed, what you deliberately kept, and how it reads now>"
```

## Outputs
- `07_manuscript/polish_report.json`
- `07_manuscript/polish_log.md`
- (plus the edited section files and the `07_manuscript/prepolish/` snapshot)

## Hard rules
- **Wording only.** Never change a number, a citation, or a figure/table reference. If a
  number is wrong, that is a data problem: loop to S05 and fix it at the source.
- Do not silence a finding by deleting the sentence that triggered it.
- Do not add a claim, a hedge that changes the strength of a conclusion, or a reference
  during polishing. This stage adds no content.
- A genuine exception to a tier-A pattern goes in `07_manuscript/polish_allowlist.tsv` as
  `pattern<TAB>reason` - for example when quoting a guideline verbatim.
- Do not re-run `snapshot --force` to make `diff` pass. That destroys the audit trail.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "polish done; <n> tier-A patterns removed; spelling=<US|UK>; words abstract/main <a>/<b>; facts preserved"
```
