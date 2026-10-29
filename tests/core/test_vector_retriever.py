"""Unit tests for the semantic/vector retrieval module using deterministic fake embeddings."""

from __future__ import annotations

import sys
import tempfile
import unittest
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

from src.core.contracts import ProjectRecord, RetrievalHit


class DeterministicFakeEmbedder:
    """Provides predictable low-dimensional vectors for testing without sentence-transformers."""

    def __init__(self, keyword_map: dict[str, list[float]] | None = None) -> None:
        self.keyword_map = keyword_map or {}

    def encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(texts, str):
            return self._encode_single(texts)
        return [self._encode_single(t) for t in texts]

    def _encode_single(self, text: str) -> list[float]:
        lower = text.lower()
        for kw, vec in self.keyword_map.items():
            if kw.lower() in lower:
                return vec
        # Fallback deterministic 4D vector
        val = float(sum(ord(c) for c in text) % 50) / 100.0
        return [val, 1.0 - val, 0.0, 0.0]


def make_record(
    project_id: str,
    title: str = "Test Title",
    abstract: str = "Test Abstract",
    tech_stack: str | None = "Python, FastAPI",
    domain: str | None = "AI",
    source_type: str = "synthetic",
    source_url: str | None = None,
    year: int | None = 2024,
) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        title=title,
        abstract=abstract,
        tech_stack=tech_stack,
        domain=domain,
        source_type=source_type,
        source_url=source_url,
        year=year,
    )


class VectorRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        from src.core.vector_retriever import (
            DuplicateProjectIDError,
            VectorIndexUnavailableError,
            VectorRetriever,
        )

        self.VectorRetriever = VectorRetriever
        self.DuplicateProjectIDError = DuplicateProjectIDError
        self.VectorIndexUnavailableError = VectorIndexUnavailableError

        self.fake_embedder = DeterministicFakeEmbedder(
            keyword_map={
                "agriculture": [1.0, 0.0, 0.0, 0.0],
                "robotics": [0.0, 1.0, 0.0, 0.0],
                "blockchain": [0.0, 0.0, 1.0, 0.0],
            }
        )

    def tearDown(self) -> None:
        sys.modules.pop("src.core.vector_retriever", None)

    def _make_ephemeral_client(self) -> Any:
        import chromadb
        from chromadb.config import Settings

        return chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))

    def test_indexing_known_synthetic_records_and_retrieval(self) -> None:
        records = [
            make_record("P1", title="Smart Agriculture Crop Sensor"),
            make_record("P2", title="Industrial Robotics Arm Control"),
            make_record("P3", title="Blockchain Ledger for Logistics"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_known_records",
        )
        hits = retriever.search("agriculture monitoring", top_k=2)

        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0].project_id, "P1")
        self.assertEqual(hits[0].rank, 1)

    def test_expected_retrieval_ordering_with_deterministic_embeddings(self) -> None:
        records = [
            make_record("A1", title="Advanced Agriculture Machine"),
            make_record("R1", title="Autonomous Robotics Drone"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_ordering",
        )

        hits = retriever.search("robotics automation", top_k=2)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].project_id, "R1")
        self.assertEqual(hits[0].rank, 1)
        self.assertEqual(hits[1].project_id, "A1")
        self.assertEqual(hits[1].rank, 2)

    def test_ordered_contiguous_one_based_ranks(self) -> None:
        records = [
            make_record("P1", title="Agriculture A"),
            make_record("P2", title="Agriculture B"),
            make_record("P3", title="Agriculture C"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_contiguous_ranks",
        )
        hits = retriever.search("agriculture", top_k=3)

        self.assertEqual(len(hits), 3)
        self.assertEqual([h.rank for h in hits], [1, 2, 3])

    def test_top_k_limits(self) -> None:
        records = [
            make_record("P1", title="Robotics 1"),
            make_record("P2", title="Robotics 2"),
            make_record("P3", title="Robotics 3"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_top_k",
        )
        hits = retriever.search("robotics", top_k=1)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].rank, 1)

    def test_empty_corpus_and_empty_or_whitespace_query(self) -> None:
        empty_retriever = self.VectorRetriever(
            [],
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_empty_corpus",
        )
        self.assertEqual(empty_retriever.search("robotics", top_k=5), [])

        records = [make_record("P1", title="Robotics Project")]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_empty_query",
        )
        self.assertEqual(retriever.search("", top_k=5), [])
        self.assertEqual(retriever.search("   ", top_k=5), [])
        self.assertEqual(retriever.search("robotics", top_k=0), [])
        self.assertEqual(retriever.search("robotics", top_k=-2), [])

    def test_missing_optional_metadata(self) -> None:
        records = [
            make_record(
                "P_OPT",
                title="Minimal Agriculture Project",
                abstract="Just basic abstract",
                tech_stack=None,
                domain=None,
                source_url=None,
                year=None,
            )
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_missing_meta",
        )
        hits = retriever.search("agriculture", top_k=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].project_id, "P_OPT")

    def test_duplicate_project_ids_are_rejected(self) -> None:
        records = [
            make_record("DUP_1", title="Project Alpha"),
            make_record("DUP_1", title="Project Duplicate"),
        ]
        with self.assertRaises(self.DuplicateProjectIDError):
            self.VectorRetriever(
                records,
                embedder=self.fake_embedder,
                chroma_client=self._make_ephemeral_client(),
                collection_name="test_dup",
            )

    def test_rebuilding_removes_stale_records(self) -> None:
        records_v1 = [
            make_record("OLD_1", title="Agriculture System V1"),
            make_record("OLD_2", title="Robotics System V1"),
        ]
        retriever = self.VectorRetriever(
            records_v1,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_rebuild",
        )
        hits_v1 = retriever.search("agriculture", top_k=2)
        self.assertEqual(hits_v1[0].project_id, "OLD_1")

        records_v2 = [
            make_record("NEW_1", title="Agriculture System V2"),
        ]
        retriever.rebuild_index(records_v2)
        hits_v2 = retriever.search("agriculture", top_k=2)

        self.assertEqual(len(hits_v2), 1)
        self.assertEqual(hits_v2[0].project_id, "NEW_1")
        all_ids = [h.project_id for h in hits_v2]
        self.assertNotIn("OLD_1", all_ids)

    def test_unknown_ids_returned_by_malformed_collection_are_filtered(self) -> None:
        class MalformedCollection:
            def query(self, *args: Any, **kwargs: Any) -> dict[str, list[list[str]]]:
                return {"ids": [["GHOST_ID", "REAL_ID"]]}

        class MockClient:
            def delete_collection(self, name: str) -> None:
                pass

            def create_collection(self, *args: Any, **kwargs: Any) -> Any:
                return MalformedCollection()

        records = [make_record("REAL_ID", title="Real Agriculture System")]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=MockClient(),
            auto_build=False,
        )
        retriever._collection = MalformedCollection()
        retriever._is_indexed = True

        hits = retriever.search("agriculture", top_k=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].project_id, "REAL_ID")
        self.assertEqual(hits[0].rank, 1)

    def test_duplicate_ids_returned_by_malformed_collection_are_deduplicated(self) -> None:
        """Ensure duplicate IDs returned by a malformed ChromaDB result are never returned as duplicate hits."""
        class DuplicateIdsCollection:
            def query(self, *args: Any, **kwargs: Any) -> dict[str, list[list[str]]]:
                return {"ids": [["P1", "P1", "P2", "P2"]]}

        class MockClient:
            def delete_collection(self, name: str) -> None:
                pass

            def create_collection(self, *args: Any, **kwargs: Any) -> Any:
                return DuplicateIdsCollection()

        records = [
            make_record("P1", title="Agriculture System 1"),
            make_record("P2", title="Agriculture System 2"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=MockClient(),
            auto_build=False,
        )
        retriever._collection = DuplicateIdsCollection()
        retriever._is_indexed = True

        hits = retriever.search("agriculture", top_k=5)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].project_id, "P1")
        self.assertEqual(hits[0].rank, 1)
        self.assertEqual(hits[1].project_id, "P2")
        self.assertEqual(hits[1].rank, 2)

    def test_persistent_storage_configuration(self) -> None:
        """Verify that a custom or configured persistent directory initializes PersistentClient correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            records = [make_record("P_PERSIST", title="Persistent Agriculture Record")]
            retriever = self.VectorRetriever(
                records,
                embedder=self.fake_embedder,
                persist_directory=tmpdir,
                collection_name="test_persist_collection",
            )
            hits = retriever.search("agriculture", top_k=1)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].project_id, "P_PERSIST")
            # Verify persistent storage directory has contents created by ChromaDB
            self.assertTrue(any(Path(tmpdir).iterdir()))

    def test_model_or_client_initialization_failure(self) -> None:
        class FailingClient:
            def create_collection(self, *args: Any, **kwargs: Any) -> Any:
                raise ConnectionError("ChromaDB connection refused")

        records = [make_record("P1", title="Title")]
        with self.assertRaises(self.VectorIndexUnavailableError):
            self.VectorRetriever(
                records,
                embedder=self.fake_embedder,
                chroma_client=FailingClient(),
                collection_name="test_fail",
            )

    def test_repeated_queries_produce_deterministic_results(self) -> None:
        records = [
            make_record("P1", title="Agriculture Crop System"),
            make_record("P2", title="Agriculture Soil Monitor"),
        ]
        retriever = self.VectorRetriever(
            records,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_deterministic",
        )
        first_run = retriever.search("agriculture", top_k=2)
        second_run = retriever.search("agriculture", top_k=2)

        self.assertEqual([h.project_id for h in first_run], [h.project_id for h in second_run])
        self.assertEqual([h.rank for h in first_run], [h.rank for h in second_run])

    def test_every_returned_id_maps_to_canonical_records(self) -> None:
        canonical = [
            make_record("P10", title="Agriculture"),
            make_record("P20", title="Robotics"),
            make_record("P30", title="Blockchain"),
        ]
        retriever = self.VectorRetriever(
            canonical,
            embedder=self.fake_embedder,
            chroma_client=self._make_ephemeral_client(),
            collection_name="test_mapping",
        )
        hits = retriever.search("robotics blockchain", top_k=3)

        known_ids = {r.project_id for r in canonical}
        for hit in hits:
            self.assertIn(hit.project_id, known_ids)


if __name__ == "__main__":
    unittest.main()
