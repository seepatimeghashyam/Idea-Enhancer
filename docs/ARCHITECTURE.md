# Idea Enhancer — Architecture Document

This document describes the approved system architecture for Idea Enhancer V1. It reflects approved decisions only. Components marked as **planned** or **deferred** are not yet implemented.

> **Implementation status (2026-11-04):** Offline historical search remains available through `POST /search` and the Core Search BM25/ChromaDB/RRF pipeline. The independent MVP adds `POST /live-search`, OpenAlex/GitHub adapters, candidate normalization, bounded BM25/dense/RRF reranking, and a two-mode frontend. Provider behavior is fixture-tested; a fixed human-labelled live relevance benchmark and sustained real-provider verification remain pending. LLM enhancement remains deferred. See [Live Search](LIVE_SEARCH.md), [Dataset Readiness](DATASET_READINESS.md), and the [Decision Log](DECISIONS.md).

---

## System Overview

Idea Enhancer helps engineering students investigate a project idea before investing time in building it. It searches indexed project records and external research providers, returning traceable matches with ranking evidence. A constrained improvement suggestion based on retrieved evidence is a future possibility; LLM enhancement is not implemented.

The system is **not** a plagiarism detector and cannot prove universal originality. It can only describe what was or was not found in the local dataset or external providers that actually responded to a search.

---

## Architecture Diagram

The application has two explicit request flows:

```
Student → Frontend → FastAPI
    ├── Offline Demo → POST /search → canonical CSV → BM25 + ChromaDB → RRF
    └── Live Research → POST /live-search
          ├── OpenAlex ─┐
          ├── GitHub ───┴→ normalized candidate pool → BM25 + BGE embeddings → RRF
          └──────────────────────────────────────────────→ evidence + source states
```

---

## Approved Technology Stack

| Layer | Technology | Status |
|---|---|---|
| Frontend | HTML5, Tailwind CSS, vanilla JavaScript | Implemented; demo/live modes and light/dark theme |
| Backend / API | Python, FastAPI | Implemented; POST /search and POST /live-search |
| Keyword retrieval | BM25 via rank-bm25 | Implemented |
| Semantic retrieval | ChromaDB with BAAI/bge-small-en-v1.5 embeddings | Implemented; local model and index required |
| Ranking fusion | Reciprocal Rank Fusion (RRF) | Implemented |
| Live discovery | OpenAlex Works API and GitHub Repository Search API | Implemented; internet required; GitHub token optional |
| Live dense retrieval | BAAI/bge-small-en-v1.5 in bounded in-memory candidate pool | Implemented; model required for hybrid mode; BM25 degradation is explicit |
| Live evaluation | Fixed snapshot metrics and 0–3 human relevance grades | Tool implemented; reviewed live labels are not yet available |
| Dataset | data/historical_projects.csv | 1,998 search-ready rows; provenance and relevance review remain |
| LLM enhancement | Provider TBD | Deferred until search pipeline works |
| Relational database | Not required for V1 | — |

### Explicitly excluded from this MVP

- React, Vue, or other frontend frameworks
- Node.js, Express, or a second backend server
- MySQL, MongoDB, or other relational/document databases
- Persistent external candidate index or provider-result history
- LLM-based suggestions or idea generation

---

## Module Architecture

### Module boundaries and ownership

| Module | Owner | Entry files | Responsibilities |
|---|---|---|---|
| **Data** | Data Lead | `data/historical_projects.csv`, cleaning/validation scripts | Curate, clean, and validate the canonical dataset |
| **Core Search** | Core Backend Lead | `src/database.py` (public interface), `src/core/` modules | BM25 retrieval, ChromaDB vector search, RRF fusion, evidence checks |
| **API** | API & LLM Lead | `src/main.py`, API/LLM service modules | FastAPI endpoints, request validation, orchestration, LLM integration |
| **Frontend** | Frontend UI Lead | `index.html`, `script.js`, frontend assets | User interface, input validation, API communication, result display |

### Dependency flow

```
Frontend (HTML/JS)
    │
    │ HTTP (POST /search, POST /live-search)
    ▼
API Layer (FastAPI - src/main.py)
    │
    │ Python function calls
    ▼
Core Search (src/database.py)
    │
    ├── BM25 Index (in-memory, from CSV)
    ├── ChromaDB Index (local persistent, from CSV)
    └── RRF Fusion (combines BM25 + vector ranks)
    │
    │ reads
    ▼
Canonical Dataset (data/historical_projects.csv)

Live Research (separate API route)
    ├── OpenAlex Works API
    ├── GitHub Repository Search API
    └── in-memory normalized candidate pool → BM25 + dense → RRF
```

### Key architectural rules

1. **Core Search does not serve HTTP.** It exposes Python functions that the API layer calls.
2. **API layer does not implement search logic.** It validates requests, calls Core Search, and formats responses.
3. **Frontend does not call Core Search directly.** It communicates only through the HTTP API.
4. **No module invents response fields.** All response fields are defined in the [API Contract](API_CONTRACT.md).
5. **LLM is called from the backend only.** API keys are never exposed to the browser.

---

## Data Flow — Offline Demo (`POST /search`)

1. Student submits an idea through the frontend form.
2. Frontend validates input (non-empty, minimum length) and sends `POST /search` to the API.
3. API validates the request against the contract schema.
4. API calls Core Search with the query text and `top_k` parameter.
5. Core Search runs BM25 keyword retrieval against the tokenized corpus.
6. Core Search runs ChromaDB vector retrieval using the same embedding model as indexing.
7. Core Search applies Reciprocal Rank Fusion to combine both ranked lists.
8. Core Search applies basic evidence/overlap checks on the fused results.
9. Core Search returns structured match records to the API.
10. API formats the response per the API contract and returns it to the frontend.
11. Frontend renders result cards with match details and evidence.

## Data Flow — Live Research (`POST /live-search`)

1. The API validates the idea and `top_k` using the same request bounds as offline search.
2. OpenAlex and GitHub are queried concurrently with bounded timeouts, one retry, and bounded candidate counts.
3. Each provider independently returns `success`, `empty`, or a typed failure state. Both unavailable produces HTTP 503; one available produces partial results; provider success with no candidates is an honest empty result.
4. Provider records are normalized into `CandidateRecord`; IDs remain provider-specific, deduplication uses stable provider IDs, and missing metadata remains unknown.
5. BM25 and the lazy BGE encoder rank the in-memory pool. RRF combines ranks. If dense embedding fails or is disabled, BM25 results are returned with a degraded state.
6. Deterministic text evidence and repeated terms are attached; the UI reports source status, provenance, ranking signals, and source links.

Provider text is external and untrusted. It is returned as JSON text and rendered with DOM text nodes. No provider request occurs at import time. Live candidates are request-scoped and are not persisted.

---

## Data Architecture

### Canonical dataset

- **Location:** `data/historical_projects.csv`
- **Schema:** `project_id, title, abstract, tech_stack, domain, source_type, source_url, year` (see [Decision D-007](DECISIONS.md#decision-007-canonical-dataset-schema))
- **Raw sources:** Preserved under `data/raw/` with provenance documentation.

### Vector index

- **Storage:** Local persistent ChromaDB directory (`chroma_db/`, gitignored).
- **Embedding model:** `BAAI/bge-small-en-v1.5` (384-dimensional).
- **Rebuild:** The index must be rebuildable from the canonical CSV at any time. It is not the only copy of source records.
- **Model consistency:** The same model and configuration must be used for both corpus embedding and query embedding. Changing the model requires a full index rebuild.

### BM25 index

- **Storage:** In-memory, built at application startup from the canonical CSV.
- **Tokenization:** Standard tokenization via `rank-bm25`. Exact preprocessing to be documented by the Core Search owner.

---

## Configuration

- **Environment variables:** Defined in `.env.example` (not committed with real values).
- **Key variables:**
  - `EMBEDDING_MODEL` and `CHROMA_DB_PATH` — model and persistent index for Offline Demo.
  - `LIVE_DENSE_SEARCH` and `LIVE_EMBEDDING_MODEL` — enable and select the live candidate reranker; disabling dense search returns explicitly degraded BM25-only results.
  - `GITHUB_TOKEN` — optional server-side GitHub API token; never expose it in frontend configuration.
  - `CORS_ALLOWED_ORIGINS` — comma-separated exact HTTPS origins for a separately hosted frontend; localhost remains allowed for development.
  - `LLM_API_KEY` — not currently used; LLM integration remains deferred.

---

## Scoring Semantics

> **Critical:** RRF scores are ranking-fusion values, not similarity percentages. An `rrf_score` of `0.03` does not mean "3% similar." Do not display RRF scores as percentages or normalize them into percentages without a separately designed and evaluated scoring method.

The API response includes distinct ranking fields:
- `bm25_rank` — position in the BM25 result list
- `vector_rank` — position in the ChromaDB result list
- `rrf_score` — Reciprocal Rank Fusion score (higher = better combined rank, but not a percentage)

These are documented in the [API Contract](API_CONTRACT.md).

---

## Implementation Phases

| Phase | Scope | Owner | Dependencies |
|---|---|---|---|
| 0. Foundation | Documentation, dependency manifest, project setup | Project Owner | None |
| 1. Data Pipeline | Clean, merge, validate canonical CSV | Data Lead | Phase 0 |
| 2. Core Search | BM25 + ChromaDB + RRF retrieval pipeline | Core Backend Lead | Phase 1 (canonical CSV) |
| 3. API Layer | FastAPI endpoints, request/response handling | API & LLM Lead | Phase 2 (search functions) |
| 4. Frontend | Input form, result display, error handling | Frontend UI Lead | Phase 0 (can start in parallel) |
| 5. Integration | End-to-end connection and smoke testing | All | Phases 2–4 |
| 6. LLM Enhancement | `/enhance` endpoint with approved LLM | API & LLM Lead | Phase 5 + LLM decision |

> **Status (2026-10-29):** Phases 0–5 have working implementations, and the real-data /search path has passed a smoke test. Phase 1 is only partially complete because source-level verification and a labeled relevance evaluation are still missing. Phase 6 remains deferred.
