# Idea Enhancer — API Contract

This document defines the approved HTTP API contract for Idea Enhancer V1. All modules (frontend, API, core search) must use these definitions. Do not change request/response fields, route names, or error formats without a Decision Request and project-owner approval.

> **Implementation status (2026-10-29):** POST /search is implemented with the request, success, validation, unavailable, and internal-error envelopes below. The live route has been smoke-tested against the supplied canonical CSV. POST /enhance remains deferred; its schema below is only a proposal.

---

## General Conventions

### Base URL

The API server runs locally during development. The frontend API adapter should use a configurable base URL, defaulting to `http://localhost:8000`.

### Content type

All requests and responses use `Content-Type: application/json`.

### Error convention

All error responses use a consistent envelope:

```json
{
  "status": "error",
  "error_code": "DESCRIPTIVE_ERROR_CODE",
  "message": "Human-readable description of what went wrong.",
  "details": null
}
```

- `error_code`: machine-readable string (e.g., `VALIDATION_ERROR`, `SEARCH_FAILED`, `INTERNAL_ERROR`).
- `message`: human-readable explanation safe to display to the user.
- `details`: optional object with additional context (e.g., field-level validation errors). `null` when not applicable.

### HTTP status codes

| Code | Meaning | When used |
|---|---|---|
| 200 | Success | Successful search or enhancement |
| 422 | Validation Error | Missing/invalid request fields |
| 500 | Internal Server Error | Unexpected server failure |
| 503 | Service Unavailable | Search index not ready or dependency failure; response message is generic and diagnostics stay in server logs |

Unavailable responses use a generic client-safe message; the API logs the underlying initialization reason:

```json
{
  "status": "error",
  "error_code": "SEARCH_UNAVAILABLE",
  "message": "Search is temporarily unavailable. Please try again shortly.",
  "details": null
}
```

---

## `POST /search`

Search the indexed project database for ideas related to the submitted text.

### Request

```json
{
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "top_k": 5
}
```

| Field | Type | Required | Constraints | Default |
|---|---|---|---|---|
| `idea` | string | yes | Non-empty after trimming; minimum 10 characters; maximum 2000 characters | — |
| `top_k` | integer | no | Minimum 1, maximum 20 | 5 |

#### Validation rules

- `idea` must be a non-empty string after leading/trailing whitespace is trimmed.
- If `idea` is shorter than 10 characters (after trimming), return 422 with `error_code: "VALIDATION_ERROR"`.
- If `idea` exceeds 2000 characters (after trimming), return 422 with `error_code: "VALIDATION_ERROR"`.
- If `top_k` is provided but outside the allowed range, clamp it to the nearest bound (1 or 20) and include a warning in the response.
- If `idea` is missing or not a string, return 422.

### Success Response (200)

```json
{
  "status": "success",
  "query": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "result_count": 2,
  "matches": [
    {
      "project_id": "rvce_042",
      "title": "Smart Crop Monitoring System",
      "description_excerpt": "Text excerpt from the actual indexed abstract field",
      "source_type": "institutional_project",
      "source_url": null,
      "year": 2024,
      "domain": "IoT/Agriculture",
      "technologies": ["Raspberry Pi", "CNN", "Python"],
      "rank": 1,
      "bm25_rank": 1,
      "vector_rank": 3,
      "rrf_score": 0.0323,
      "shared_elements": ["Raspberry Pi", "crop monitoring", "CNN"],
      "verification_status": "checked"
    },
    {
      "project_id": "global_107",
      "title": "Plant Disease Detection Using Deep Learning",
      "description_excerpt": "Text excerpt from the actual indexed abstract field",
      "source_type": "open_source_repository",
      "source_url": "https://example.com/record",
      "year": 2023,
      "domain": "AI/Agriculture",
      "technologies": ["CNN", "TensorFlow", "Python"],
      "rank": 2,
      "bm25_rank": 4,
      "vector_rank": 1,
      "rrf_score": 0.0298,
      "shared_elements": ["disease detection", "CNN"],
      "verification_status": "checked"
    }
  ],
  "message": null,
  "warnings": []
}
```

> **Note:** All values above are illustrative examples. Project IDs, titles, excerpts, and URLs do not reference real records. The implemented API must return data from the actual indexed dataset.

### Response field definitions

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"success"` for 200 responses. |
| `query` | string | The submitted idea text (trimmed). |
| `result_count` | integer | Number of matches returned (0 to `top_k`). |
| `matches` | array | Ordered list of match objects, best rank first. Empty array if no matches found. |
| `message` | string or null | Optional message (e.g., informational notes). `null` when not applicable. |
| `warnings` | array of strings | Any non-fatal warnings (e.g., `top_k` was clamped). Empty array when none. |

### Match object fields

| Field | Type | Source | Description |
|---|---|---|---|
| `project_id` | string | dataset `project_id` | Stable unique identifier from the canonical dataset. |
| `title` | string | dataset `title` | Project title from the indexed record. |
| `description_excerpt` | string | dataset `abstract` | Excerpt from the project's abstract. This is a transformation of the dataset's `abstract` field — it may be truncated for display. |
| source_type | string | dataset source_type | Provenance label, such as institutional_project, open_source_repository, or research_paper. |
| `source_url` | string or null | dataset `source_url` | URL to the original source record. `null` when not available. |
| `year` | integer or null | dataset `year` | Project year from the indexed record. `null` when not available. |
| `domain` | string or null | dataset `domain` | Project domain or category. `null` when not available. |
| `technologies` | array of strings or null | dataset `tech_stack` | Parsed from the comma-separated `tech_stack` field. `null` when not available. |
| `rank` | integer | computed | Final position in the fused result list (1-based). |
| `bm25_rank` | integer or null | computed | Position in the BM25 result list (1-based). `null` if this result was not in the BM25 top results. |
| `vector_rank` | integer or null | computed | Position in the ChromaDB vector result list (1-based). `null` if this result was not in the vector top results. |
| `rrf_score` | number | computed | Reciprocal Rank Fusion score. **This is a ranking-fusion value, not a similarity percentage.** See [Scoring Semantics](#scoring-semantics). |
| shared_elements | array of strings | computed | Exact lexical terms found in common between the query and the record's title, abstract, technology stack, or domain. This is not a semantic relevance score. |
| verification_status | string | computed | Result of the lexical overlap check only: checked (one or more shared terms found), insufficient (the check found none), or unchecked (no check was performed). It does not mean the linked source was independently verified. |

### Dataset-to-API field mapping

| Dataset column | API response field | Transformation |
|---|---|---|
| `project_id` | `project_id` | Direct pass-through |
| `title` | `title` | Direct pass-through |
| `abstract` | `description_excerpt` | May be truncated for display |
| `tech_stack` | `technologies` | Split comma-separated string into array; `null` if empty |
| `domain` | `domain` | Direct pass-through; `null` if empty |
| `source_type` | `source_type` | Direct pass-through |
| `source_url` | `source_url` | Direct pass-through; `null` if empty |
| `year` | `year` | Direct pass-through; `null` if empty |

### No matches response (200)

When the retrievers return no candidates, the API returns a success response with an empty matches array. This describes the current search output; it is not a relevance-threshold decision:

```json
{
  "status": "success",
  "query": "A quantum teleportation device for household pets",
  "result_count": 0,
  "matches": [],
  "message": "No records were returned from the current search.",
  "warnings": []
}
```

> **Important:** The absence of matches does not prove the idea is original or that no similar record exists in the indexed sources. The system has no calibrated relevance cutoff for deciding that a nearest result is “close.”

### Validation error response (422)

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "The 'idea' field must contain at least 10 characters.",
  "details": {
    "field": "idea",
    "constraint": "min_length",
    "min_length": 10,
    "actual_length": 3
  }
}
```

### Server error response (500)

```json
{
  "status": "error",
  "error_code": "SEARCH_FAILED",
  "message": "An internal error occurred while processing the search. Please try again.",
  "details": null
}
```

---

## `POST /enhance`

> **Status: DEFERRED.** This endpoint is not approved for implementation until `POST /search` works with real data and an LLM provider is approved. The schema below is a proposal for future approval — not a committed contract.

Generate a constrained improvement suggestion based on the submitted idea and a specific matched project.

### Proposed request (not yet approved)

```json
{
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "match_project_id": "rvce_042"
}
```

### Proposed response (not yet approved)

```json
{
  "status": "success",
  "match_project_id": "rvce_042",
  "suggestion": "LLM-generated text based on actual retrieved evidence.",
  "basis": ["Evidence elements used to generate the suggestion"],
  "confidence": "limited"
}
```

The final schema will be approved when the LLM provider decision (D-008) is revisited.

---

## Scoring Semantics

### RRF score is not a similarity percentage

The `rrf_score` field uses the standard Reciprocal Rank Fusion formula:

$$\text{RRF}(d) = \sum_{r \in R} \frac{1}{k + r(d)}$$

where $k$ is a constant (typically 60), $R$ is the set of ranking systems, and $r(d)$ is the rank of document $d$ in ranking system $r$.

This produces a **ranking-fusion value** that reflects combined rank position, not semantic similarity. Key rules:

- **Do not** display `rrf_score = 0.03` as "3% similar."
- **Do not** normalize RRF scores into a 0–100 percentage scale.
- **Do not** invent a "similarity percentage" by applying an arbitrary transformation.
- **Do** display the RRF score as a ranking indicator, or use it only for ordering.
- If a human-readable relevance indicator is needed in the future, it must be separately designed, evaluated, and approved as a new decision.

### Distinct ranking fields

The API response provides three separate ranking indicators per match:

| Field | Source | Meaning |
|---|---|---|
| `bm25_rank` | BM25 retrieval | Position based on keyword overlap |
| `vector_rank` | ChromaDB retrieval | Position based on semantic embedding similarity |
| `rrf_score` | Fusion | Combined ranking value (not a percentage) |

These fields must remain distinct. No module should collapse them into a single "similarity score" without an approved design.

---

## Frontend Integration Notes

- The frontend should use a single API adapter module that constructs requests and parses responses per this contract.
- The frontend must not invent response fields or assume fields not defined here.
- Mock/demo fixtures used during frontend development must be clearly labelled as `MOCK/DEMO` and kept in a separate file.
- The `source_url` field should only be rendered as a clickable link when it is a non-null, valid URL.
- Display `message` to the user when it is non-null (e.g., the no-match message).
- Display `warnings` entries if present (e.g., `top_k` was clamped).
