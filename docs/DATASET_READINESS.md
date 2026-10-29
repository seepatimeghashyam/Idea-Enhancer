# Canonical dataset readiness

**Checked:** 2026-10-29
**Search input:** data/historical_projects.csv
**Source review artifacts:** data/historical_projects_quality_report.md and data/historical_projects_row_audit.csv

## Current state

The installed search-ready file contains 1,998 records with the canonical eight-column schema. The standard-library validator reported zero blocking structural errors and 1,819 review warnings. The Core Search loader loaded all 1,998 records. A real POST /search smoke request returned HTTP 200 and five matches using BM25, the approved BAAI embedding model, a temporary Chroma index, RRF, the API gateway, and the public response formatter.

The smoke test verifies that the path runs end to end. It does not establish that the returned matches are relevant or independently verified. The temporary vector index used for the check was outside the repository; normal local runs build a persistent index from the canonical CSV.

## Review findings

- The supplied quality report says all 510 institutional abstracts were replaced with “Description not independently verified.” because the provided summaries were not established as source text. Do not present these placeholder descriptions as official project abstracts.
- 1,786 of 1,998 search-ready records have an empty technology stack. This is unknown data, not a negative claim about the project.
- The search-ready CSV and row audit both show 212 records with a non-empty technology stack; the quality report has been corrected to match.
- 505 institutional records share a KSCST PDF URL. The supplied report says this is a shared compendium, so URL repetition is a review warning rather than grounds to discard records.
- Two retraction-related records, RVCE-PUB-0362 and RVCE-PUB-0458, are excluded from the search-ready file and remain represented in the row audit.
- URL checks in the supplied report establish syntax/category only. They do not confirm that links are reachable, that the source contains the shown record, or that reuse is permitted.
- The search-ready copy has 510 institutional projects, 733 open-source repositories, and 755 research papers. These are records in the provided CSV; they are not live integrations with those source systems.

The validator's warnings are prompts for human review. It does not delete records or reject the dataset because URLs or descriptions repeat.

## Remaining work outside the smoke test

1. Verify a sample of each source type against its linked source and confirm the intended reuse conditions.
2. Build a small, human-labeled query/relevance set and evaluate BM25, vector search, and RRF before making relevance or uniqueness claims.
3. Decide how records with unverified institutional descriptions should be surfaced to users; do not invent replacement summaries.
4. Make dataset updates reproducible and retain source snapshots and audit artifacts when provenance permits.
