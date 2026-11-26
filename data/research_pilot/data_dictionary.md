# Research Pilot — Data Dictionary and Review Instructions

This directory (`data/research_pilot/`) contains a **20-record pilot collection** of candidate research and engineering project references prepared for human review. It is strictly separate from the canonical production dataset (`data/historical_projects.csv`).

---

## 1. Field Definitions (`pilot_candidates.csv` / `pilot_candidates.json`)

| Field | Type | Required | Description |
|---|---|---|---|
| `candidate_id` | string | yes | Stable pilot identifier (`PILOT-001` through `PILOT-020`). |
| `title` | string | yes | Title or `owner/repo` name exactly as returned by the authoritative source. |
| `description` | string | yes | Short factual repository description or reconstructed abstract excerpt (<= 450 chars). |
| `source_type` | string | yes | Category of source: `open_source_repository`, `research_paper`, or `public_dataset`. |
| `provider` | string | yes | Discovery/metadata provider queried: `github`, `openalex`, or `zenodo`. |
| `source_url` | string | yes | Canonical `https://` URL or DOI URL (`https://doi.org/...`). |
| `author_or_creator` | string | yes | Repository owner login, paper authors (up to 3 + `et al.`), or dataset creators. |
| `publication_or_release_date` | string | yes | Publication date (`YYYY-MM-DD`) for papers/datasets, or `created:YYYY-MM-DD; pushed:YYYY-MM-DD` for GitHub repositories. |
| `collection_date` | string | yes | UTC date (`YYYY-MM-DD`) when the metadata was retrieved. |
| `topic` | string | yes | Engineering topic slice assigned for pilot diversity. |
| `license` | string | yes | Explicit SPDX/standard license identifier when reported by the source; `unknown` when absent, `NOASSERTION`, or `other-oa`. |
| `human_relevance` | string | yes | Review status; initialized to `pending` for all records. |
| `evidence_checked` | string | yes | Exact API endpoint/record ID, HTTP status, and metadata fields verified during collection. |

---

## 2. Human Review Instructions (`review_sheet.csv`)

`review_sheet.csv` is a neutral review sheet that omits all ranking scores or retrieval positions.

### How to review each candidate

1. Open the `source_url` in your browser to inspect the original repository, paper landing page, or dataset record.
2. Verify that the title, description, and license match what is shown on the source page.
3. Fill in the three blank reviewer columns:
   - `relevance_grade_0_to_3`:
     - `0` — Not relevant: no meaningful connection to student engineering project discovery.
     - `1` — Weakly related: adjacent domain or overly broad foundational tool with limited project-idea value.
     - `2` — Substantially related: useful reference implementation, survey, or dataset for investigating a project idea.
     - `3` — Highly relevant: strong, concrete engineering project reference with clear scope and traceability.
   - `reviewer_rationale`: Short 1–2 sentence note explaining the grade.
   - `reviewer_confidence`: `low`, `medium`, or `high`.
4. Update `human_relevance` from `pending` to `reviewed` (or `rejected` / `needs_second_review`).
5. Do **not** infer missing licenses or modify `data/historical_projects.csv` directly without project-owner approval.
