# S20 - Assemble the submission bundle

## Purpose
Produce a folder the user can upload without editing anything. Every item present, in the
journal's required format, traceable to the rule that demanded it.

The manuscript arriving here has already been de-AI'd and language-polished at S19 with the
facts verified intact. Do not rewrite prose in this stage; assemble it.

## This stage needs the user
Now that the target journal is confirmed, collect the real administrative details:
- author names, intended order, ORCIDs, and institutional affiliations;
- corresponding author's email, address, and phone;
- exact funding agency and grant numbers (if any);
- confirmed conflicts of interest and specific ethics approval / IRB numbers.
Update `project/00_input/author_info.json` with these real details, replacing the S17 placeholders,
and refresh `project/07_manuscript/title_page.md` and `project/07_manuscript/statements.md` accordingly.

## Procedure
1. Collect and verify real author and administrative details from the user, updating `author_info.json`.
2. Re-read `08_submission/guidelines_extract.md` and build the item list from it. The
   journal's requirements drive the bundle, not a generic template.
3. Render the manuscript in the journal's expected shape. Assemble the section files in
   order and resolve the pandoc citations against `06_refs/refs.bib` using the journal's
   CSL style:
```
pandoc project/07_manuscript/title_page.md project/07_manuscript/abstract.md \
       project/07_manuscript/introduction.md project/07_manuscript/methods.md \
       project/07_manuscript/results.md project/07_manuscript/discussion.md \
       project/07_manuscript/statements.md \
       --citeproc --bibliography=project/06_refs/refs.bib \
       --csl=<journal>.csl \
       -o project/08_submission/bundle/manuscript.docx
```
   Fetch the CSL from the Zotero style repository for the journal, or the closest
   publisher-level style, and record which one was used and why.
4. Copy in the display items in the required formats: figures at the required resolution
   and colour mode (TIFF masters from `05_figures/out/`), tables as the journal wants them
   (many want editable tables in the manuscript file, not xlsx - convert if so, and keep
   the xlsx as the source), supplementary material as a single file if required.
5. If `07_manuscript/supplementary_methods.md` exists, include it as part of the
   supplementary material file. Many journals want a single combined supplementary PDF;
   if so, prepend it before supplementary tables and figures.
6. Write `project/08_submission/bundle/cover_letter.md`: what the study asked, what it
   found, why it fits this journal specifically, the statements the journal wants in the
   letter (originality, no concurrent submission, all authors approved), suggested
   reviewers if requested, and the corresponding author block.
7. Write `project/08_submission/bundle/SUBMISSION_CHECKLIST.md`: every guideline
   requirement as a line item with its status and the file that satisfies it. Anything the
   user must do in the submission portal (ORCID login, funder selection, reviewer
   suggestions, licence choice) goes in a `For the user to complete in the portal` section.
8. Write `project/08_submission/bundle/manifest.json`. Every file in the bundle must be
   listed, with the guideline rule that requires it:
```json
{"built_at": "", "journal": "",
 "items": [{"role": "manuscript", "file": "08_submission/bundle/manuscript.docx",
            "required_by": "guidelines_extract.md > Submission items"}]}
```
   Roles the gate requires: `title_page`, `manuscript`, `cover_letter`, `figures`,
   `tables`, `checklist`. Add `supplementary`, `checklist_form` (e.g. STROBE), `coi_forms`
   as the journal demands.
9. Final tidy: `python tools/wf.py clean --apply`, then resolve anything the orphan scan
   reports. The `no_orphans` gate runs here.

## Outputs
- `08_submission/bundle/manifest.json`
- `08_submission/bundle/SUBMISSION_CHECKLIST.md`
- `08_submission/bundle/cover_letter.md`
- (plus the rendered manuscript, figures, tables and supplementary files)

## Hard rules
- Every bundle file appears in `manifest.json`, and every manifest entry exists on disk.
- No file in the bundle that no guideline rule asks for.
- Citations must resolve. If `pandoc --citeproc` emits an unresolved-key warning, the
  bundle is not done.
- Do not fabricate a reviewer's affiliation or email when suggesting reviewers. Provide
  names and let the user supply contact details, or leave it for the portal.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "bundle complete for <journal>; <n> items; user still needs to: <...>"
```
