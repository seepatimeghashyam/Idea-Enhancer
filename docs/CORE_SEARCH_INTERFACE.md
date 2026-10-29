# Core Search Shared Interface

This document is the implementation handoff for the two retrieval modules and the Core Search integration layer. It follows the existing architecture: canonical CSV records flow into BM25 and ChromaDB retrieval, then rank-only output is fused with Reciprocal Rank Fusion (RRF). This module does not serve HTTP and does not change the public API response contract.

## Shared data structures

`src/core/contracts.py` defines:

- `ProjectRecord`: canonical fields `project_id`, `title`, `abstract`, `tech_stack`, `domain`, `source_type`, `source_url`, and `year`. Blank optional values map to `None`; source metadata must never be invented.
- `RetrievalHit`: `project_id` plus `rank`, where rank is a positive, 1-based integer.
- `Retriever`: the common protocol `search(query: str, top_k: int) -> list[RetrievalHit]`.
- `SearchMatch`: canonical record, final rank, each retriever's optional rank, `rrf_score`, `shared_elements`, and a verification status (`checked`, `unchecked`, or `insufficient`).

Both retrievers must accept the same trimmed query and `top_k`, return no more than `top_k` hits, and order those hits by their 1-based rank. Do not return raw scores: BM25 scores and vector distances have different scales and are not compared during fusion.

The common `build_search_text(record)` helper joins only `title`, `abstract`, `tech_stack`, and `domain`. Both retrievers must use this content. IDs, URLs, and provenance fields are excluded from searchable text.

## Dataset loader

`load_project_records()` reads `data/historical_projects.csv`. Required headers are `project_id`, `title`, `abstract`, and `source_type`; `tech_stack`, `domain`, `source_url`, and `year` are optional columns. Missing or blank optional values become `None`. A present year must parse as an integer.

The loader rejects empty/duplicate project IDs, missing required values or headers, malformed row widths, malformed CSV, invalid years, missing files, and datasets with no records. Errors identify the row or file problem. It never drops a malformed row or edits the dataset. Data cleaning belongs in a separate preparation step.

## Retrieval modules and integration

The integration boundary expects contributor-owned classes with these constructors and methods:

```python
BM25Retriever(records: Sequence[ProjectRecord])
VectorRetriever(records: Sequence[ProjectRecord])

retriever.search(query: str, top_k: int) -> list[RetrievalHit]
```

The vector retriever owns ChromaDB and `BAAI/bge-small-en-v1.5` setup. It must not download or initialize that model at module import time; report missing/unbuilt index state as an initialization or availability error. Tests inject fakes and do not import either retriever module.

`CoreSearchEngine` receives canonical records and both retrievers by dependency injection. It validates direct calls to the approved query and `top_k` bounds, calls both retrievers with the same normalized query and limit, fuses their ranks, then adds evidence fields.

`src/database.py` exposes `search_projects(idea: str, top_k: int = 5) -> list[dict]`. It loads the canonical dataset and lazily initializes the real retrievers on the first call. It raises `CoreSearchUnavailable` if the dataset, modules, or indexes are unavailable. A real search returning no hits is a valid empty list; unavailable search is never represented as an empty success.

The returned dictionaries use canonical fields (`abstract`, `tech_stack`) plus `project_id`, `title`, `source_type`, `source_url`, `year`, `domain`, `rank`, `bm25_rank`, `vector_rank`, `rrf_score`, `shared_elements`, and `verification_status`.

### API-owned adapter boundary

The API gateway has a separate `SearchGateway.search(idea, top_k) -> SearchOutcome` interface. Its `SearchOutcome` contains `matches` and `warnings`, and its `CoreSearchUnavailable` exception is a different API-owned type from `src.database.CoreSearchUnavailable`. The API-owned gateway adapter must call `search_projects`, wrap the returned list of dictionaries in `SearchOutcome` (with any adapter warnings), and translate Core Search availability failures into the gateway's `CoreSearchUnavailable` so the API can return its established unavailable response. Do not make Core Search import API modules or share exception classes across this boundary.

The existing API formatter maps canonical `abstract` to `description_excerpt` and `tech_stack` to `technologies`; it owns that public response mapping, and its fields and routes remain unchanged.

## Fusion rules

For each unique project in either ranking:

```text
rrf_score = sum(1 / (rrf_constant + rank))
```

The default `rrf_constant` is 60. Only retrievers containing that project contribute. Missing retriever ranks are `None`. Return at most `top_k`, ordered by descending RRF score. Ties resolve by earliest rank from either list, then BM25 rank, vector rank, and project ID. Duplicate project IDs, duplicate ranks, invalid ranks, and IDs absent from the canonical dataset are rejected; they are never double-counted. RRF is an ordering value, not a percentage or similarity score.

## Evidence semantics and open decision

The current evidence helper performs exact, case-insensitive lexical token overlap using only the query and the record's title, abstract, stack, and domain. It removes common stop words and very short tokens. `shared_elements` lists the overlapping terms in query order. `checked` means this documented lexical check ran and found overlap; `insufficient` means it ran and found none. `unchecked` is reserved for results where no evidence inspection was performed.

This check does not establish semantic equivalence, plagiarism, or originality. It has no relevance threshold. The project has not approved a threshold for deciding that a query has “no close match”; empty retriever output means only that neither retriever returned a hit, not that the idea is unique.

## Synthetic tests

Core tests use clearly labelled records in `tests/fixtures/` or temporary CSV files. They must run without network access, a ChromaDB index, or the embedding model. Do not add synthetic records to `data/historical_projects.csv` or use realistic source URLs in fixtures.
