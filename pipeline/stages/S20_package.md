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
2. Re-read `08_submission/guidelines_extract.md` to extract the target journal's specific
   formatting requirements (e.g. font size 12pt vs 11pt, line spacing Double vs 1.5, margins).
3. **Render the entire bundle to publication-grade Word documents**:
   Execute the dedicated medical Word compilation pipeline:
   ```bash
   uv run python tools/docx/render_package.py --project project --csl <journal>.csl
   ```
   This engine automatically:
   - **Enforces journal typography**: Generates a dynamic reference docx template applying
     **Times New Roman**, **pure black (#000000)** headings (no blue/accent colors), zero list-bullet
     outlines, and the journal's exact requested font size and line spacing.
   - **Assembles full manuscript**: Sequentially links Title Page, Abstract (with clean Keywords at end),
     Introduction, Methods, Results, Discussion, Statements, and an explicit `# References` section.
   - **Appends Figure Legends to manuscript end**: Automatically reads `05_figures/legends.md`,
     ensures each legend conforms to the 4-element medical standard (80–150 words, concise bold title,
     panel guide, statistical markers, alphabetical abbreviations, without bloated methods text),
     and appends the `# Figure Legends` section directly after References inside `manuscript.docx`.
   - **Compiles Word documents**:
     - `project/08_submission/bundle/manuscript.docx`
     - `project/08_submission/bundle/cover_letter.docx`
     - `project/08_submission/bundle/supplementary_materials.docx` (if supplementary methods or files exist)
4. Copy in the display items in the required formats: figures at the required resolution
   and colour mode (TIFF masters from `05_figures/out/`), tables as the journal wants them
   (editable tables in manuscript file or separate supplementary files).
5. Write `project/08_submission/bundle/cover_letter.md` (and render to `cover_letter.docx`): what the study asked, what it
   found, why it fits this journal specifically, the statements the journal wants in the
   letter (originality, no concurrent submission, all authors approved), suggested
   reviewers if requested, and the corresponding author block (with email, phone, physical address).
6. Write `project/08_submission/bundle/SUBMISSION_CHECKLIST.md`: every guideline
   requirement as a line item with its status and the file that satisfies it. Anything the
   user must do in the submission portal (ORCID login, funder selection, reviewer
   suggestions, licence choice) goes in a `For the user to complete in the portal` section.

7. **User Human-in-the-Loop Review & Confirmation (Mandatory Pause)**:
   - Present the compiled submission bundle clearly to the user:
     "The complete submission bundle is compiled in `project/08_submission/bundle/`. Please open the Word files locally, inspect the layout, and make any human edits or formatting adjustments as you see fit."
   - **Mandatory Interactive Stop**: Do NOT proceed automatically. The agent must pause and explicitly ask the user:
     "**请确认您是否已完成人工审核与修改？确认 OK 吗？**"
   - Only after the user confirms completion may the agent proceed to Step 8.

8. **Independent Submission Auditor Subagent (Full Compliance & Consistency Audit)**:
   - Once the user confirms OK, the agent invokes an independent subagent (Role: `Submission Package Auditor`).
   - The Auditor subagent runs `uv run python tools/audit/audit_submission.py --project project` for baseline scanning and reads:
     * `08_submission/guidelines_extract.md` (journal author instructions and limits);
     * `08_submission/journal_profile.json` (journal metadata);
     * All bundle files (`manuscript.docx` / assembled markdown, `cover_letter.docx`, tables, figure manifests, checklist).
   - **The Auditor rigorously evaluates three core dimensions**:
     1. **Journal Guidelines Compliance**: Word count limits (abstract, main text), structured abstract headings, display item caps (maximum figures/tables allowed), reference count limits, typography, and mandatory declaration statements (Ethics, Consent, COI, Data Availability, Abbreviations).
     2. **Omissions & Completeness Check**: Are any journal-mandated components missing? (e.g. required statement phrases in Cover Letter, corresponding author phone/email/address, reporting guideline checklist, supplementary methodology).
     3. **Cross-Consistency & Alignment**:
        - *Display items*: Do all Figure and Table citations in the prose (Figure 1, Table 1, Figure S1...) match actual files and captions? Are there any orphan figures/tables never cited?
        - *Data alignment*: Do the key empirical numbers, sample sizes, and effect sizes in Abstract and Results match the numbers in the Tables and Figure data?
        - *Metadata alignment*: Do author names, affiliations, and corresponding details match 100% between Title Page and Cover Letter?
        - *Citations*: Are all in-text citation keys matched in the References section with zero dangling unresolved keys?
   - Save the comprehensive audit verdict to `project/08_submission/bundle/AUDIT_REPORT.md`.

9. Write `project/08_submission/bundle/manifest.json`. Every file in the bundle must be
   listed, with the guideline rule that requires it (including `AUDIT_REPORT.md` under `role: "audit_report"`):
```json
{"built_at": "", "journal": "",
 "items": [{"role": "manuscript", "file": "08_submission/bundle/manuscript.docx",
            "required_by": "guidelines_extract.md > Submission items"},
           {"role": "cover_letter", "file": "08_submission/bundle/cover_letter.docx",
            "required_by": "guidelines_extract.md > Submission items"},
           {"role": "audit_report", "file": "08_submission/bundle/AUDIT_REPORT.md",
            "required_by": "Workflow verification > Independent guidelines compliance & consistency audit"}]}
```
   Roles the gate requires: `title_page`, `manuscript`, `cover_letter`, `figures`,
   `tables`, `checklist`. Add `supplementary`, `checklist_form`, `audit_report` as required.
10. Final tidy: `uv run python tools/wf.py clean --apply`, then resolve anything the orphan scan
    reports. The `no_orphans` gate runs here.

## Outputs
- `08_submission/bundle/manuscript.docx`
- `08_submission/bundle/cover_letter.docx`
- `08_submission/bundle/manifest.json`
- `08_submission/bundle/SUBMISSION_CHECKLIST.md`
- `08_submission/bundle/AUDIT_REPORT.md`
- (plus rendered figures, tables and optional supplementary_materials.docx)

## Hard rules
- Every bundle file appears in `manifest.json`, and every manifest entry exists on disk.
- No file in the bundle that no guideline rule asks for.
- Citations must resolve. If `pandoc --citeproc` emits an unresolved-key warning, the
  bundle is not done.
- **Never bypass human review**: the agent must pause and obtain explicit user confirmation before launching the auditor subagent.
- **Independent Auditor Report required**: `08_submission/bundle/AUDIT_REPORT.md` must be generated by the auditor subagent and achieve a `PASSED` verdict before advancing.
- Do not fabricate a reviewer's affiliation or email when suggesting reviewers. Provide
  names and let the user supply contact details, or leave it for the portal.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "bundle complete for <journal>; human review confirmed; audit report PASSED; <n> items"
```
