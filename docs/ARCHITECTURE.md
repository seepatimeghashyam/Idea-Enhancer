# Idea Enhancer — Architecture Document

This document describes the approved system architecture for Idea Enhancer V1. It reflects approved decisions only. Components marked as **planned** or **deferred** are not yet implemented.

> **Implementation status (2026-10-29):** The frontend, FastAPI POST /search route, API gateway, BM25/vector retrieval, RRF fusion, dataset loader, and public response mapping are implemented. The supplied 1,998-record search-ready CSV has passed structural checks and a real /search smoke test. Source-level verification and relevance evaluation remain incomplete. LLM enhancement remains deferred. See [Dataset Readiness](DATASET_READINESS.md) and the [Decision Log](DECISIONS.md).

---

## System Overview

Idea Enhancer helps engineering students investigate a project idea before investing time in building it. It searches indexed project records, returns traceable matches with ranking evidence, and may generate a constrained improvement suggestion based on retrieved evidence.

The system is **not** a plagiarism detector and cannot prove universal originality. It can only describe what was or was not found in the sources actually indexed.

---

## Architecture Diagram

The current request flow is:

```
Student → Frontend → FastAPI POST /search → Core Search
    ├── Canonical CSV → BM25 Search ─┐
    ├── Canonical CSV → ChromaDB Search ─┤→ RRF Fusion → Traceable matches
    └── LLM enhancement (deferred)
```

---

## Approved Technology Stack

| Layer | Technology | Status |
|---|---|---|
| Frontend | HTML5, Tailwind CSS, vanilla JavaScript | Implemented; demo/live modes and light/dark theme |
| Backend / API | Python, FastAPI | Implemented; POST /search |
| Keyword retrieval | BM25 via rank-bm25 | Implemented |
| Semantic retrieval | ChromaDB with BAAI/bge-small-en-v1.5 embeddings | Implemented; local model and index required |
| Ranking fusion | Reciprocal Rank Fusion (RRF) | Implemented |
| Dataset | data/historical_projects.csv | 1,998 search-ready rows; provenance and relevance review remain |
| LLM enhancement | Provider TBD | Deferred until search pipeline works |
| Relational database | Not required for V1 | — |

### Explicitly excluded from V1 (unless approved)

- React, Vue, or other frontend frameworks
- Node.js, Express, or a second backend server
- MySQL, MongoDB, or other relational/document databases
- External dataset integrations (GitHub API, paper sources)

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
    │ HTTP (POST /search, POST /enhance)
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
```

### Key architectural rules

1. **Core Search does not serve HTTP.** It exposes Python functions that the API layer calls.
2. **API layer does not implement search logic.** It validates requests, calls Core Search, and formats responses.
3. **Frontend does not call Core Search directly.** It communicates only through the HTTP API.
4. **No module invents response fields.** All response fields are defined in the [API Contract](API_CONTRACT.md).
5. **LLM is called from the backend only.** API keys are never exposed to the browser.

---

## Data Flow — Search Request

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
  - `EMBEDDING_MODEL` — sentence-transformer model name
  - `CHROMA_DB_PATH` — path to ChromaDB persistent storage
  - `LLM_API_KEY` — deferred until LLM provider is approved

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
