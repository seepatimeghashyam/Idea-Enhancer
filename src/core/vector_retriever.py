"""Semantic and vector retrieval implementation using ChromaDB and sentence-transformers."""

from __future__ import annotations

import hashlib
import json
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


def _load_environment() -> None:
    """Load optional local configuration without importing it at module load."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


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
        self._owns_chroma_client = chroma_client is None
        self._collection_name = collection_name or "idea_enhancer_vector_index"
        self._persist_directory = persist_directory
        self._collection: Any = None
        self._is_indexed = False

        if auto_build and self._records:
            self.build_index()

    def close(self) -> None:
        """Release a Chroma client owned by this retriever, if one was opened."""
        client = self._chroma_client
        self._collection = None
        self._chroma_client = None
        self._is_indexed = False
        if self._owns_chroma_client and client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _get_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        _load_environment()
        model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
        try:
            from src.embeddings import get_sentence_transformer

            self._embedder = get_sentence_transformer(model_name, "cpu")
            return self._embedder
        except Exception as err:
            raise VectorIndexUnavailableError(
                f"Failed to load sentence-transformers embedding model '{model_name}': {err}"
            ) from err

    def _get_client(self) -> Any:
        if self._chroma_client is not None:
            return self._chroma_client
        _load_environment()
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

    def _index_signature(self, texts: list[str]) -> tuple[str, str]:
        _load_environment()
        model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
        record_texts = sorted(zip((record.project_id for record in self._records), texts))
        serialized = json.dumps(
            {"model": model_name, "records": record_texts},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return model_name, hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _existing_index_matches(
        self,
        collection: Any,
        texts: list[str],
        model_name: str,
        signature: str,
    ) -> bool:
        """Check persisted index provenance, verifying legacy collections by content."""
        try:
            if collection.count() != len(self._records):
                return False
            metadata = getattr(collection, "metadata", None) or {}
            if metadata.get("dataset_sha256") == signature and metadata.get("embedding_model") == model_name:
                return True

            # Collections created before signatures were added are accepted only
            # after checking every id, document, and stored embedding.
            stored = collection.get(include=["documents", "embeddings"])
            stored_ids = stored.get("ids") or []
            stored_documents = stored.get("documents") or []
            stored_embeddings = stored.get("embeddings")
            if (
                len(stored_ids) != len(self._records)
                or len(stored_documents) != len(self._records)
                or stored_embeddings is None
                or len(stored_embeddings) != len(self._records)
                or any(embedding is None for embedding in stored_embeddings)
            ):
                return False
            expected = dict(zip((record.project_id for record in self._records), texts))
            if dict(zip(stored_ids, stored_documents)) != expected:
                return False

            return True
        except Exception as error:
            logger.debug("Existing Chroma collection could not be validated: %s", error)
            return False

    def build_index(self, force: bool = False) -> None:
        """Reuse an unchanged persisted index, otherwise build from canonical records."""
        if not self._records:
            self._is_indexed = True
            return

        client = self._get_client()
        texts = [build_search_text(record) for record in self._records]
        ids = [record.project_id for record in self._records]
        model_name, signature = self._index_signature(texts)
        metadata = {
            "hnsw:space": "cosine",
            "dataset_sha256": signature,
            "embedding_model": model_name,
        }

        if not force:
            try:
                existing = client.get_collection(self._collection_name)
            except Exception:
                existing = None
            if existing is not None and self._existing_index_matches(existing, texts, model_name, signature):
                self._collection = existing
                self._is_indexed = True
                logger.info("Reusing validated Chroma collection '%s'.", self._collection_name)
                return

        embedder = self._get_embedder()

        try:
            try:
                client.delete_collection(self._collection_name)
            except Exception:
                pass
            self._collection = client.create_collection(
                name=self._collection_name,
                metadata=metadata,
            )
        except Exception as err:
            raise VectorIndexUnavailableError(
                f"Failed to create ChromaDB collection '{self._collection_name}': {err}"
            ) from err

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
        self.build_index(force=True)

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
