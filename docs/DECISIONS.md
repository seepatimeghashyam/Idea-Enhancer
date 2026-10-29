# Idea Enhancer — Decision Log

This file records approved project decisions. Each entry uses the template from the [AI Team Protocol](AI_TEAM_PROTOCOL.md) Section 8.

All decisions here have been explicitly approved by the project owner. Planned or deferred items are marked as such — they are not approved implementations.

---

## Decision 001: Frontend Technology

- **Decision ID:** D-001
- **Date:** 2026-10-27
- **Question:** What frontend technology should V1 use?
- **Decision approved:** HTML5, Tailwind CSS, and vanilla JavaScript.
- **Options considered:**
  - A. HTML5 + Tailwind CSS + vanilla JavaScript (selected)
  - B. React + Vite + TypeScript
- **Reason:** Matches the existing README and GitHub Issue #4. Avoids adding a build system and keeps the frontend simple for a student team. React is not needed for V1 scope.
- **Affected files/modules:** `index.html`, `script.js`, frontend-only assets.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If V1 UI complexity exceeds what vanilla JS can maintain cleanly.

---

## Decision 002: Backend Framework

- **Decision ID:** D-002
- **Date:** 2026-10-27
- **Question:** What backend framework should serve the API?
- **Decision approved:** Python with FastAPI.
- **Options considered:**
  - A. Python + FastAPI (selected)
  - B. Node.js + Express
- **Reason:** Matches the README and Issue #3. Python is required for the search pipeline (rank-bm25, sentence-transformers, ChromaDB). A single language backend avoids unnecessary complexity.
- **Affected files/modules:** `src/main.py`, API modules.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** Not expected for V1.

---

## Decision 003: Keyword Retrieval

- **Decision ID:** D-003
- **Date:** 2026-10-27
- **Question:** What library should provide BM25 keyword retrieval?
- **Decision approved:** `rank-bm25` Python package.
- **Options considered:**
  - A. `rank-bm25` (selected)
  - B. Elasticsearch / OpenSearch
  - C. Custom BM25 implementation
- **Reason:** Lightweight, no external service required, sufficient for the dataset size. Matches the protocol.
- **Affected files/modules:** `src/database.py`, core search modules.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If dataset grows beyond what in-memory BM25 can handle.

---

## Decision 004: Embedding Model

- **Decision ID:** D-004
- **Date:** 2026-10-27
- **Question:** Which sentence-transformer model should be used for ChromaDB vector embeddings?
- **Decision approved:** `BAAI/bge-small-en-v1.5` (384-dimensional, ~130 MB).
- **Options considered:**
  - A. `BAAI/bge-small-en-v1.5` (selected)
  - B. `all-MiniLM-L6-v2` (384-dim, ~90 MB, slightly lower quality)
  - C. Defer until benchmarked on actual dataset
- **Reason:** Good quality-to-size ratio for a student project. Well-documented. Same dimensionality as the alternative but better retrieval quality on standard benchmarks.
- **Affected files/modules:** `src/database.py`, ChromaDB index build, `.env.example`.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If the model produces poor results on the actual dataset after evaluation, or if download size is a constraint.

> **Important:** The same model and configuration must be used for both corpus embedding and query embedding. Changing the model requires rebuilding the entire ChromaDB index.

---

## Decision 005: Semantic Search Storage

- **Decision ID:** D-005
- **Date:** 2026-10-27
- **Question:** What vector database should store and search embeddings?
- **Decision approved:** ChromaDB with local persistent storage.
- **Options considered:**
  - A. ChromaDB local persistent (selected)
  - B. FAISS
  - C. Pinecone / cloud vector DB
- **Reason:** ChromaDB provides built-in persistence, metadata filtering, and Python-native API. No external service or account required. Index is rebuildable from the canonical CSV.
- **Affected files/modules:** `src/database.py`, core search modules, `.gitignore` (already includes `chroma_db/`).
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If ChromaDB performance is insufficient for the dataset size.

---

## Decision 006: Ranking Fusion

- **Decision ID:** D-006
- **Date:** 2026-10-27
- **Question:** How should BM25 and vector search results be combined?
- **Decision approved:** Reciprocal Rank Fusion (RRF).
- **Options considered:**
  - A. Reciprocal Rank Fusion (selected)
  - B. Linear score combination
  - C. Learned-to-rank model
- **Reason:** RRF is simple, deterministic, and does not require score calibration between retrieval methods. Well-established in information retrieval.
- **Affected files/modules:** `src/database.py`, core search modules.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If evaluation shows RRF produces poor ranking quality.

> **Important:** RRF scores are ranking-fusion values, not similarity percentages. Do not display an RRF score as "X% similar" or normalize it into a percentage without a separately designed and evaluated scoring method.

---

## Decision 007: Canonical Dataset Schema

- **Decision ID:** D-007
- **Date:** 2026-10-27
- **Question:** What columns should the canonical `data/historical_projects.csv` use?
- **Decision approved:** `project_id, title, abstract, tech_stack, domain, source_type, source_url, year`
- **Options considered:**
  - A. Full schema with traceability fields (selected)
  - B. Minimal schema matching existing CSV columns (`id, title, domain, abstract, technologies`)
- **Reason:** Traceability fields (`source_type`, `source_url`) are essential for provenance. The existing CSVs must be cleaned and merged regardless, so adopting the full schema costs little extra effort.
- **Affected files/modules:** `data/historical_projects.csv`, `src/database.py`, API response mapping.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If additional required fields are identified during data pipeline implementation.

### Column definitions

| Column | Type | Required | Description |
|---|---|---|---|
| `project_id` | string | yes | Stable unique identifier for each project record. |
| `title` | string | yes | Project title. |
| `abstract` | string | yes | Project description or abstract. |
| `tech_stack` | string | no | Comma-separated list of technologies (within a quoted CSV field). |
| `domain` | string | no | Project domain or category. |
| `source_type` | string | yes | Provenance label (e.g., `rvce`, `global`, `historical`). |
| `source_url` | string | no | URL to the original source, where available. |
| `year` | integer | no | Year of the project, where known. |

Unknown optional fields should be left empty (not filled with placeholder values).

---

## Decision 008: LLM Enhancement — Deferred

- **Decision ID:** D-008
- **Date:** 2026-10-27
- **Question:** Which LLM provider and model should be used for `POST /enhance`?
- **Decision approved:** Deferred until `POST /search` works with real data.
- **Options considered:**
  - A. Google Gemini API
  - B. OpenAI GPT API
  - C. Local/open-source model (e.g., Ollama)
  - D. Defer (selected)
- **Reason:** The search pipeline must be functional and validated before adding LLM integration. Deferral avoids premature API key management and cost.
- **Affected files/modules:** `src/main.py` (`/enhance` endpoint), LLM service module.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** When `POST /search` returns real results from the canonical dataset.

---

## Decision 009: Dependency Management

- **Decision ID:** D-009
- **Date:** 2026-10-27
- **Question:** How should Python dependencies be tracked?
- **Decision approved:** `requirements.txt` with version range constraints.
- **Options considered:**
  - A. `requirements.txt` (selected)
  - B. `pyproject.toml` with pip
- **Reason:** Simplest option for a student team using different editors and tools. Version ranges (not exact pins) are used as constraints; exact pins will be established when the team verifies a working environment.
- **Affected files/modules:** `requirements.txt` (root).
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If the team adopts a tool that benefits from `pyproject.toml` (e.g., a build system).

---

## Decision 010: CSV Consolidation Strategy

- **Decision ID:** D-010
- **Date:** 2026-10-27
- **Question:** How should raw project datasets be consolidated into the canonical dataset?
- **Decision approved:** Raw CSV records may be incorporated into the canonical dataset (`data/historical_projects.csv`) only after their provenance and permitted use have been established. Preserve originals under `data/raw/` when their provenance and permitted use are established. Do not invent metadata, silently discard uncertain records, or merge unverified sources unconditionally. Document malformed rows and unresolved data-quality issues.
- **Options considered:**
  - A. Curate and consolidate verified records into a single canonical CSV, preserving verified originals under `data/raw/` (selected)
  - B. Merge all raw files unconditionally without verifying provenance or licensing
  - C. Keep separate unmerged source files with normalized columns
- **Reason:** A single validated canonical file simplifies core search ingestion while ensuring legal, ethical, and traceability standards. Preserving raw files retains provenance, while prohibiting unconditional merging and silent record discarding protects data integrity.
- **Affected files/modules:** `data/historical_projects.csv`, `data/raw/`, data cleaning and validation scripts.
- **Approved by:** Shyam (project owner)
- **Condition to revisit:** If separate source files require independent update or indexing cycles.

> **Status (2026-10-29):** A conservative 1,998-record search-ready CSV is installed at data/historical_projects.csv and passes structural validation. This is a partial implementation: source-level provenance review and a reproducible full ingestion/cleaning pipeline remain incomplete. See [Dataset Readiness](DATASET_READINESS.md).
