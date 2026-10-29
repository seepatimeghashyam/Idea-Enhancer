"""Semantic and vector retrieval implementation using ChromaDB and sentence-transformers."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Backward-compatibility shim for Python < 3.10 where slots=True is unsupported in dataclasses
if sys.version_info < (3, 10):
    import dataclasses

    _orig_dataclass = dataclasses.dataclass

    def _compat_dataclass(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("slots", None)
        return _orig_dataclass(*args, **kwargs)

    dataclasses.dataclass = _compat_dataclass  # type: ignore[assignment]

from src.core.contracts import ProjectRecord, RetrievalHit, build_search_text

DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_CHROMA_PATH = "./chroma_db"
logger = logging.getLogger(__name__)


class VectorRetrieverError(RuntimeError):
    """Base error for vector retriever failures."""


class DuplicateProjectIDError(ValueError):
    """Raised when duplicate project identifiers are supplied to the retriever."""


class VectorIndexUnavailableError(VectorRetrieverError):
    """Raised when the vector index or embedding model cannot be initialized or accessed."""


class VectorRetriever:
    """Semantic vector retriever using ChromaDB and BAAI/bge-small-en-v1.5 embeddings."""

    def __init__(
        self,
        records: Sequence[ProjectRecord],
        embedder: Any = None,
        chroma_client: Any = None,
        collection_name: str | None = None,
        persist_directory: str | Path | None = None,
        auto_build: bool = True,
    ) -> None:
        self._records_map: dict[str, ProjectRecord] = {}
        for r in records:
            if r.project_id in self._records_map:
                raise DuplicateProjectIDError(f"Duplicate project ID found: {r.project_id!r}")
            self._records_map[r.project_id] = r

        self._records = list(records)
        self._embedder = embedder
        self._chroma_client = chroma_client
        self._collection_name = collection_name or "idea_enhancer_vector_index"
        self._persist_directory = persist_directory
        self._collection: Any = None
        self._is_indexed = False

        if auto_build and self._records:
            self.build_index()

    def _get_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(DEFAULT_MODEL_NAME)
            return self._embedder
        except Exception as err:
            raise VectorIndexUnavailableError(
                f"Failed to load sentence-transformers embedding model '{DEFAULT_MODEL_NAME}': {err}"
            ) from err

    def _get_client(self) -> Any:
        if self._chroma_client is not None:
            return self._chroma_client
        persist_path = self._persist_directory or os.getenv("CHROMA_DB_PATH", DEFAULT_CHROMA_PATH)
        try:
            import chromadb
            from chromadb.config import Settings

            self._chroma_client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=Settings(anonymized_telemetry=False),
            )
            return self._chroma_client
        except Exception as err:
            raise VectorIndexUnavailableError(
                f"Failed to initialize ChromaDB persistent client at '{persist_path}': {err}"
            ) from err

    def build_index(self) -> None:
        """Build or rebuild the vector index from the canonical records."""
        if not self._records:
            self._is_indexed = True
            return

        client = self._get_client()
        embedder = self._get_embedder()

        try:
            try:
                client.delete_collection(self._collection_name)
            except Exception:
                pass
            self._collection = client.create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as err:
            raise VectorIndexUnavailableError(
                f"Failed to create ChromaDB collection '{self._collection_name}': {err}"
            ) from err

        texts = [build_search_text(record) for record in self._records]
        ids = [record.project_id for record in self._records]

        try:
            embeddings = self._encode_texts(embedder, texts)
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
            )
            self._is_indexed = True
        except Exception as err:
            raise VectorIndexUnavailableError(f"Failed to index project records in ChromaDB: {err}") from err

    def rebuild_index(self, records: Sequence[ProjectRecord] | None = None) -> None:
        """Rebuild index with new or existing records, clearing stale entries."""
        if records is not None:
            new_map: dict[str, ProjectRecord] = {}
            for r in records:
                if r.project_id in new_map:
                    raise DuplicateProjectIDError(f"Duplicate project ID found: {r.project_id!r}")
                new_map[r.project_id] = r
            self._records_map = new_map
            self._records = list(records)
        self.build_index()

    def _encode_texts(self, embedder: Any, texts: list[str]) -> list[list[float]]:
        if hasattr(embedder, "encode"):
            raw = embedder.encode(texts)
            if hasattr(raw, "tolist"):
                return raw.tolist()
            return list(raw)
        if callable(embedder):
            raw = embedder(texts)
            if hasattr(raw, "tolist"):
                return raw.tolist()
            return list(raw)
        raise VectorIndexUnavailableError("Configured embedder has no encode method and is not callable.")

    def _encode_query(self, embedder: Any, query: str) -> list[float]:
        if hasattr(embedder, "encode"):
            raw = embedder.encode(query)
            if hasattr(raw, "tolist"):
                return raw.tolist()
            return list(raw)
        if callable(embedder):
            raw = embedder([query])
            if isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
                raw = raw[0]
            if hasattr(raw, "tolist"):
                return raw.tolist()
            return list(raw)
        raise VectorIndexUnavailableError("Configured embedder has no encode method and is not callable.")

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        """Perform semantic retrieval and return at most top_k candidates ordered by 1-based rank."""
        trimmed_query = query.strip()
        if not trimmed_query or not self._records or top_k <= 0:
            return []

        if not self._is_indexed:
            self.build_index()

        if self._collection is None:
            return []

        embedder = self._get_embedder()
        try:
            query_vector = self._encode_query(embedder, trimmed_query)
            limit = min(top_k, len(self._records))
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
            )
        except Exception as err:
            raise VectorIndexUnavailableError(f"Query execution failed in vector search: {err}") from err

        raw_ids: list[str] = []
        if results and "ids" in results and results["ids"] and len(results["ids"]) > 0:
            raw_ids = results["ids"][0]

        hits: list[RetrievalHit] = []
        seen_ids: set[str] = set()
        rank = 1
        for pid in raw_ids:
            if pid in self._records_map and pid not in seen_ids:
                seen_ids.add(pid)
                hits.append(RetrievalHit(project_id=pid, rank=rank))
                rank += 1
                if len(hits) >= top_k:
                    break

        return hits
