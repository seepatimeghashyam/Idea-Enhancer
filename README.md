# Idea Enhancer

Idea Enhancer helps engineering students evaluate proposed project ideas against historical project records and discover related academic papers and open-source repositories through live search.

## Current MVP state

- The responsive HTML/Tailwind/vanilla JavaScript frontend has two separate modes: Offline Demo searches the local historical CSV; Live Research queries OpenAlex and GitHub.
- `POST /search` preserves the historical Core Search contract. `POST /live-search` reports provider states and ranks external candidates through the app's BM25, dense embedding, and RRF pipeline.
- Dense ranking uses `BAAI/bge-small-en-v1.5` when available. If the model cannot load, live results are explicitly marked as keyword-only degraded results; if both providers fail, live search returns unavailable and never falls back to historical records.
- The supplied conservative search-ready dataset is installed at `data/historical_projects.csv`. Its quality limitations are documented in [Dataset Readiness](docs/DATASET_READINESS.md).
- A sun/moon control switches between the warm light theme and ambient dark theme.
- Candidate metadata and source links are shown only when returned by a provider. Search order is not a similarity percentage, originality guarantee, or verification of source claims.
- LLM-generated recommendations remain deferred.

## Run locally

Install the dependencies from `requirements.txt`, then start the API from the repository root:

    python -m uvicorn src.main:app --reload

In a second terminal, serve the frontend from the repository root:

    python -m http.server 5500

Open http://localhost:5500. Choose **Offline Demo** to search the supplied local dataset or **Live Research** to search external sources. Live search requires internet access. The first semantic search may download the embedding model; set `LIVE_DENSE_SEARCH=0` to use explicitly degraded BM25-only live ranking. GitHub accepts unauthenticated requests; an optional `GITHUB_TOKEN` raises its rate limit. Copy `.env.example` to `.env` for local configuration. `EMBEDDING_MODEL` and `CHROMA_DB_PATH` configure offline search; `LIVE_EMBEDDING_MODEL` and `LIVE_DENSE_SEARCH` configure live ranking.

## Start on the prepared demo laptop

Double-click `Run Idea Enhancer.cmd`. It opens the API and frontend in separate windows, then opens http://localhost:5500. Keep both server windows open while presenting. Close both windows to stop the app.

Choose **Offline Demo** for a predictable walkthrough using the local historical dataset. Choose **Live Research** to query OpenAlex and GitHub. The first semantic search may take longer while the model loads. Keep the API and frontend server windows open while presenting. Search matches are evidence leads, not proof of similarity, originality, or independent source verification.

The launcher uses the Ubuntu WSL environment prepared on the demonstration laptop. It is a presentation shortcut; fresh developers should follow the dependency installation instructions above and in [Live Search](docs/LIVE_SEARCH.md).

Run tests with:

    python -m pytest tests -q

## Stack

- Frontend: HTML, Tailwind CSS CDN, vanilla JavaScript
- API: Python and FastAPI
- Retrieval: rank-bm25, ChromaDB, BAAI/bge-small-en-v1.5
- Fusion: Reciprocal Rank Fusion (RRF)
- Live discovery: OpenAlex Works API and GitHub Repository Search API via `httpx`

## Developer docs

- [Live Research setup, providers, states, and evaluation](docs/LIVE_SEARCH.md)
- [API contract](docs/API_CONTRACT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Decision log](docs/DECISIONS.md)

RRF values are ordering values, not similarity percentages. Dataset records and their source URLs still require source-level review before results are described as independently verified.
