# Idea Enhancer

Idea Enhancer helps engineering students search project records for traceable prior-art overlap before investing time in a build. Search results are evidence from the indexed corpus, not proof of originality or plagiarism.

## Current MVP state

- The responsive HTML/Tailwind/vanilla JavaScript frontend supports clearly labelled demo modes and live search, including validation, loading, timeout, empty-result, unavailable, and server-error states.
- The FastAPI POST /search route is connected through the API-owned gateway to Core Search.
- Core Search loads the canonical CSV, runs BM25 and ChromaDB vector retrieval, fuses ranks with RRF, and maps canonical evidence to the public response.
- The supplied conservative search-ready dataset is installed at data/historical_projects.csv. Its quality limitations are documented in [Dataset Readiness](docs/DATASET_READINESS.md).
- A sun/moon control switches between the warm light theme and ambient dark theme.
- POST /enhance and LLM-generated recommendations remain deferred until search quality is evaluated and an LLM provider is approved.

## Run locally

Start the API from the repository root:

    python -m uvicorn src.main:app --reload

In a second terminal, serve the frontend from the repository root:

    python -m http.server 5500

Open http://localhost:5500, select Live search, and submit an idea with at least 10 characters. The first search builds the local vector index and may take a while. EMBEDDING_MODEL and CHROMA_DB_PATH can be set in the process environment or in a local .env copied from .env.example.

Run tests with:

    python -m pytest tests -q

## Stack

- Frontend: HTML, Tailwind CSS CDN, vanilla JavaScript
- API: Python and FastAPI
- Retrieval: rank-bm25, ChromaDB, BAAI/bge-small-en-v1.5
- Fusion: Reciprocal Rank Fusion (RRF)

RRF values are ordering values, not similarity percentages. Dataset records and their source URLs still require source-level review before results are described as independently verified.
