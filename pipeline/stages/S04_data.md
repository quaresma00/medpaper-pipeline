# S04 - Acquire data, codebook, provenance

## Purpose
Get the real data in place with an auditable trail, and describe it before analysing it.

## Procedure
1. Execute the retrieval steps from `02_data/acquisition_plan.md`. Raw files land in
   `project/02_data/raw/` and are then treated as read-only. Never edit a raw file.
2. Any cleaning, recoding or merging happens in a script under `03_analysis/code/`
   that writes to `02_data/derived/`. No manual spreadsheet edits.
3. Write `project/02_data/provenance.md`: where each raw file came from, the URL or
   query, the retrieval timestamp, the release/version, the file hash, the licence, and
   who is allowed to see it. Include an explicit `Exhaustion & Completeness Audit` section.
4. Output the verifiable census manifest to `project/02_data/data_census.json`:
```json
{
  "strategy": "FULL_CENSUS",
  "actual_raw_rows": 0,
  "exhaustion_verified": true,
  "retrieval_method": "API_PAGINATION",
  "source_hash": "sha256 of raw file(s)"
}
```
   Set `strategy` to `FULL_CENSUS` (default) or `APPROVED_SAMPLING`.
   If `FULL_CENSUS`, `exhaustion_verified` must be `true`.
5. Generate the codebook. For every variable: role, type, units, level meanings,
   range or quantiles, and missingness. If a coded variable's level meanings are unknown,
   mark it `[NEEDS DICTIONARY]` - do not infer what `2` means.
   Write it to `project/02_data/codebook.md`.
6. Dump the machine-readable summary from executed code to
   `project/03_analysis/results/dataset_summary.json`:
```json
{
  "n_rows": 0, "n_cols": 0,
  "variables": [{"name": "", "role": "", "type": "", "missing_pct": 0.0}],
  "missingness": {"any_missing_rows_pct": 0.0},
  "study_period": {"start": null, "end": null},
  "source_hash": "sha256 of the raw input(s)",
  "built_by": "03_analysis/code/<script>",
  "built_at": ""
}
```
   `n_rows` must strictly match `actual_raw_rows` from `data_census.json`.
7. Delete scratch files from `project/temp/`.

## Outputs
- `02_data/codebook.md`
- `02_data/provenance.md`
- `02_data/data_census.json`
- `03_analysis/results/dataset_summary.json`

## Hard rules
- STRICT ZERO TRUNCATION: Never use `nrows=`, `.head(N)`, `[:N]`, `.sample()`, or early-break
  loops to shortcut data acquisition. Public datasets and APIs must be ingested in full.
- PROGRESS VISIBILITY: Batch downloads and API pagination must print progress (tqdm or
  batch counts/percentages). Never execute silent long-running loops.
- If the data contains identifiers, de-identify before any of it reaches a prompt, and
  record what was removed in `provenance.md`.
- No plotting in this stage.
- Never hand-type a count into the codebook; read it from the summary JSON.

## Close
```
python tools/wf.py check
python tools/wf.py advance --note "n=<rows>x<cols>; source=<x>; blockers=<missingness/dictionary gaps>"
```
