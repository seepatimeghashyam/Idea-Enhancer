# Idea Enhancer

Idea Enhancer is a student project similarity and research-discovery tool that evaluates proposed engineering ideas against existing projects, academic research and open-source repositories. Search results are evidence from the indexed corpus, not proof of originality or plagiarism.

## Current MVP state

- The responsive HTML/Tailwind/vanilla JavaScript frontend supports clearly labelled demo modes and live search, including validation, loading, timeout, empty-result, unavailable, and server-error states.
- The FastAPI POST /search route is connected through the API-owned gateway to Core Search.
- Core Search loads the canonical CSV, runs BM25 and ChromaDB vector retrieval, fuses ranks with RRF, and maps canonical evidence to the public response.
- The supplied conservative search-ready dataset is installed at `data/historical_projects.csv`. Its quality limitations are documented in [Dataset Readiness](docs/DATASET_READINESS.md).
- A sun/moon control switches between the warm light theme and ambient dark theme.
- POST /enhance and LLM-generated recommendations remain deferred until search quality is evaluated and an LLM provider is approved.

## Run locally

Start the API from the repository root:

    python -m uvicorn src.main:app --reload

In a second terminal, serve the frontend from the repository root:

    python -m http.server 5500

Open http://localhost:5500, select Live search, and submit an idea with at least 10 characters. The first search builds the local vector index and may take a moment. `EMBEDDING_MODEL` and `CHROMA_DB_PATH` can be set in the process environment or in a local `.env` copied from `.env.example`.

## Start on the prepared demo laptop

Double-click `Run Idea Enhancer.cmd`. It opens the API and frontend in separate windows, then opens http://localhost:5500. Keep both server windows open while presenting. Close both windows to stop the app.

Choose **Demo mode** for a quick, predictable walkthrough. Choose **Live search** to query the local dataset; run one live search before presenting because the first search after startup builds the vector index and can take longer. Search matches are evidence leads, not proof of similarity or independently verified project records.

This launcher uses the Ubuntu WSL environment already prepared on this laptop. It is a presentation shortcut, not a fresh-install method for other computers. Standard development dependencies are listed in `requirements.txt`.

Run tests with:

    python -m pytest tests -q

## Stack

- Frontend: HTML, Tailwind CSS CDN, vanilla JavaScript
- API: Python and FastAPI
- Retrieval: rank-bm25, ChromaDB, BAAI/bge-small-en-v1.5
- Fusion: Reciprocal Rank Fusion (RRF)

RRF values are ordering values, not similarity percentages. Dataset records and their source URLs still require source-level review before results are described as independently verified.
