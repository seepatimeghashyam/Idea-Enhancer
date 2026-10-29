# Idea Enhancer dataset quality and cleanup report

## Decision

I recommend `historical_projects_search_ready.csv` for the first honest search MVP, and retaining `historical_projects_cleaned.csv` as the full cleaned candidate/archive. The search-ready file is deliberately conservative: it avoids using unverified stack labels as retrieval evidence, makes the institutional-project synopsis limitation visible, and excludes retracted/retraction-notice records from positive search results.

This is a **structural and conservative evidence cleanup, not a claim that every one of the 2,000 source records has been independently verified**. The row audit records what was changed.

## Input and schema

- Uploaded file: `histroical_project  3.csv.xls`
- Actual format: UTF-8 CSV despite the `.xls` extension.
- Records read: 2,000
- Required schema: `project_id,title,abstract,tech_stack,domain,source_type,source_url,year`
- Source-type counts: `institutional_project` 510, `open_source_repository` 733, `research_paper` 757
- Blank cells across the eight fields: none.
- Duplicate project IDs: 0.
- Duplicate titles (case-insensitive): 0.
- Malformed CSV field counts: 0.
- Years are four-digit integers within the checked range: yes.
- URL syntax and host-category checks: 2,000 pass, 0 need review.
- URL host checks are syntax/category checks only; they do not constitute an HTTP reachability check or individual source-content verification.

## Mechanical fixes in `historical_projects_cleaned.csv`

- Decoded HTML entities in 27 records (for example `&amp;` becomes `&`).
- Removed repeated technology tokens within a record in 417 rows, preserving the first occurrence and original order.
- Canonicalized 248 legacy `http://arxiv.org/` URLs to `https://arxiv.org/`.
- Trimmed and normalized whitespace.
- Preserved all 2,000 records and the approved eight-column schema. The only content changes in this full-copy file are HTML decoding, whitespace normalization, repeated exact stack-token removal, and safe arXiv URL scheme canonicalization.

## Search-safe adjustments in `historical_projects_search_ready.csv`

- Records retained: 1,998.
- Excluded 2 retraction-related records: RVCE-PUB-0362, RVCE-PUB-0458. They remain in the full cleaned copy and row audit.
- Institutional project records: replaced all 510 supplied abstracts with `Description not independently verified.` because the KSCST listing links confirm project-list provenance, while the supplied summaries are not established as source text. The 500 repeated generic capstone-style abstracts are a particularly strong signal of generated enrichment, not original per-project summaries.
- Institutional tech-stack labels are retained only when explicitly visible in the project title. Stack labels inferred only from generated descriptions are removed.
- Repository and paper tech-stack labels are retained only when their technology is textually supported in the supplied title/abstract (using conservative aliases). This does not prove correctness, but it prevents unsupported stack labels from silently influencing ranking.
- Rows with at least one stack label remaining: 212 of 1,998 (recomputed directly from the search-ready CSV and cross-checked against the row audit).
- Technology labels removed by evidence filtering after deduplication: 9,904.
- Remaining stack labels by source type: `institutional_project` 13/3,056, `open_source_repository` 154/3,504, `research_paper` 60/3,571.

## Significant quality risks found

1. **Repeated templated institutional descriptions.** 500 institutional abstracts use the same `... applied engineering capstone project developed at ...` / `... integrated architecture utilizing ...` template. These are not appropriate to present as official abstracts without a source synopsis.
2. **Highly repetitive repository stacks.** 417 repository rows contained duplicated language tokens such as `Python, Python` or `Go, Go`. Beyond the exact duplicates, several full stack combinations occur very often; these combinations should not be assumed repository-verified just because the source URL is a GitHub URL.
3. **Research-paper `tech_stack` values need provenance.** Most assigned stacks were not supported by the record's title/abstract text. The search-ready version strips unsubstantiated labels rather than inventing confidence.
4. **Two retraction-related records.** Excluded only from the MVP search copy; retained in the full copy for traceability.
5. **Shared KSCST PDF URLs.** 505 institutional rows point to one official 48th-series PDF. Sharing a source URL is not itself an error because one official compendium can contain many project listings; project IDs, titles, institutions, and the exact page/record still require source-level verification.

## Important implementation note

`historical_projects_search_ready.csv` keeps the exact canonical columns required by the project loader. It is suitable for an MVP search smoke test because it avoids relying on unverified technology-stack claims. It is not a replacement for a later verified ingestion process. Before calling results “verified matches,” inspect the linked source record and establish evidence for the specific title/summary shown.

## Output files

- `historical_projects_cleaned.csv` — full 2,000-row copy with only deterministic cleanup.
- `historical_projects_search_ready.csv` — conservative 1,998-row search corpus.
- `historical_projects_row_audit.csv` — 2,000 row-by-row records of flags, original/corrected stack values, and MVP decisions.
