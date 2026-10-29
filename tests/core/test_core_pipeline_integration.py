"""Offline integration coverage for the real Core Search retrieval pipeline."""

from __future__ import annotations

import unittest
import sys
from typing import Any

from src.core.contracts import ProjectRecord, RetrievalHit
from src.core.engine import CoreSearchEngine


QUERY = "SOLAR IRRIGATION SENSOR"
RRF_CONSTANT = 60


def synthetic_records() -> list[ProjectRecord]:
    """Return labelled in-memory records with deliberately sparse metadata."""

    return [
        ProjectRecord(
            project_id="SYNTH_BOTH",
            title="Solar irrigation sensor prototype",
            abstract="MOCK ONLY: synthetic record returned by both test retrievers.",
            tech_stack=None,
            domain=None,
            source_type="synthetic",
            source_url=None,
            year=None,
        ),
        ProjectRecord(
            project_id="SYNTH_BM25_ONLY",
            title="Solar irrigation planning prototype",
            abstract="MOCK ONLY: synthetic keyword-only record.",
            tech_stack=None,
            domain=None,
            source_type="synthetic",
            source_url=None,
            year=None,
        ),
        ProjectRecord(
            project_id="SYNTH_VECTOR_ONLY",
            title="Farm water coordination prototype",
            abstract="MOCK ONLY: synthetic vector-only record with no query token overlap.",
            tech_stack=None,
            domain=None,
            source_type="synthetic",
            source_url=None,
            year=None,
        ),
    ]


class RecordingBM25Retriever:
    """Record engine inputs while delegating retrieval to the real BM25 class."""

    def __init__(self, records: list[ProjectRecord]) -> None:
        from src.core.bm25_retriever import BM25Retriever

        self.search_calls: list[tuple[str, int]] = []
        self.last_hits: list[RetrievalHit] = []
        self._retriever = BM25Retriever(records)

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        self.search_calls.append((query, top_k))
        self.last_hits = self._retriever.search(query, top_k)
        return self.last_hits


class DeterministicFakeEmbedder:
    """Return fixed vectors and record the normalized query sent by the retriever."""

    def __init__(self) -> None:
        self.query_inputs: list[str] = []

    def encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(texts, str):
            self.query_inputs.append(texts)
            return [1.0, 0.0]
        return [[0.0, 1.0] for _ in texts]


class FakeCollection:
    """Small in-memory Chroma-shaped collection with deterministic ranked IDs."""

    def __init__(self, response_order: list[str]) -> None:
        self.response_order = list(response_order)
        self.ids: list[str] = []
        self.added_documents: list[str] = []
        self.last_n_results: int | None = None
        self.last_returned_ids: list[str] = []

    def add(self, *, ids: list[str], embeddings: list[list[float]], documents: list[str]) -> None:
        del embeddings  # The fake collection only needs IDs for deterministic lookup.
        self.ids = list(ids)
        self.added_documents = list(documents)

    def query(self, *, query_embeddings: list[list[float]], n_results: int) -> dict[str, list[list[str]]]:
        if query_embeddings != [[1.0, 0.0]]:
            raise AssertionError("The deterministic query embedding was not forwarded.")
        self.last_n_results = n_results
        available = set(self.ids)
        ordered = [project_id for project_id in self.response_order if project_id in available]
        self.last_returned_ids = ordered[:n_results]
        return {"ids": [self.last_returned_ids]}


class FakeChromaClient:
    """Create disposable in-memory collections and track collection replacement."""

    def __init__(self, response_order: list[str]) -> None:
        self.response_order = list(response_order)
        self.collections: dict[str, FakeCollection] = {}
        self.deleted_names: list[str] = []

    def delete_collection(self, name: str) -> None:
        self.deleted_names.append(name)
        if name not in self.collections:
            raise KeyError(name)
        del self.collections[name]

    def create_collection(self, *, name: str, metadata: dict[str, str]) -> FakeCollection:
        if metadata != {"hnsw:space": "cosine"}:
            raise AssertionError("Vector collection must retain cosine distance configuration.")
        collection = FakeCollection(self.response_order)
        self.collections[name] = collection
        return collection


class FailingChromaClient:
    """Represent an unavailable vector-index dependency."""

    def delete_collection(self, name: str) -> None:
        raise KeyError(name)

    def create_collection(self, *, name: str, metadata: dict[str, str]) -> Any:
        raise ConnectionError("synthetic Chroma dependency unavailable")


class CorePipelineIntegrationTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Keep the API facade's lazy-import contract independent of test order.
        sys.modules.pop("src.core.vector_retriever", None)
        sys.modules.pop("src.core.bm25_retriever", None)

    def make_pipeline(
        self,
        response_order: list[str] | None = None,
    ) -> tuple[CoreSearchEngine, RecordingBM25Retriever, Any, DeterministicFakeEmbedder, FakeChromaClient]:
        from src.core.vector_retriever import VectorRetriever

        records = synthetic_records()
        bm25 = RecordingBM25Retriever(records)
        embedder = DeterministicFakeEmbedder()
        client = FakeChromaClient(
            response_order or ["SYNTH_VECTOR_ONLY", "SYNTH_BOTH"]
        )
        vector = VectorRetriever(
            records,
            embedder=embedder,
            chroma_client=client,
            collection_name="synthetic_core_pipeline",
        )
        return CoreSearchEngine(records, bm25, vector), bm25, vector, embedder, client

    def test_real_retrievers_fuse_with_rrf_and_keep_rank_provenance(self) -> None:
        engine, bm25, _vector, embedder, client = self.make_pipeline()

        matches = engine.search(f"  {QUERY}  ", top_k=3)

        # The engine trims once before dispatch; the vector retriever receives the
        # same trimmed query, while BM25 performs its real tokenization/scoring.
        normalized_query = QUERY
        self.assertEqual(bm25.search_calls, [(normalized_query, 3)])
        self.assertEqual(
            [hit.project_id for hit in bm25.last_hits],
            ["SYNTH_BOTH", "SYNTH_BM25_ONLY"],
        )
        self.assertEqual(embedder.query_inputs, [normalized_query])
        collection = client.collections["synthetic_core_pipeline"]
        self.assertEqual(collection.last_n_results, 3)
        self.assertEqual(collection.last_returned_ids, ["SYNTH_VECTOR_ONLY", "SYNTH_BOTH"])

        by_id = {match.project.project_id: match for match in matches}
        self.assertEqual([match.project.project_id for match in matches], [
            "SYNTH_BOTH", "SYNTH_VECTOR_ONLY", "SYNTH_BM25_ONLY"
        ])
        self.assertEqual(len(by_id), len(matches))
        self.assertEqual([match.rank for match in matches], [1, 2, 3])

        self.assertEqual(by_id["SYNTH_BOTH"].bm25_rank, 1)
        self.assertEqual(by_id["SYNTH_BOTH"].vector_rank, 2)
        self.assertAlmostEqual(
            by_id["SYNTH_BOTH"].rrf_score,
            1 / (RRF_CONSTANT + 1) + 1 / (RRF_CONSTANT + 2),
        )
        self.assertEqual(by_id["SYNTH_VECTOR_ONLY"].bm25_rank, None)
        self.assertEqual(by_id["SYNTH_VECTOR_ONLY"].vector_rank, 1)
        self.assertAlmostEqual(by_id["SYNTH_VECTOR_ONLY"].rrf_score, 1 / (RRF_CONSTANT + 1))
        self.assertEqual(by_id["SYNTH_BM25_ONLY"].bm25_rank, 2)
        self.assertEqual(by_id["SYNTH_BM25_ONLY"].vector_rank, None)
        self.assertAlmostEqual(by_id["SYNTH_BM25_ONLY"].rrf_score, 1 / (RRF_CONSTANT + 2))

    def test_top_k_is_applied_to_both_retrievers_and_final_results(self) -> None:
        engine, bm25, _vector, _embedder, client = self.make_pipeline()

        matches = engine.search(QUERY, top_k=2)

        self.assertEqual(bm25.search_calls, [(QUERY, 2)])
        self.assertLessEqual(len(bm25.last_hits), 2)
        self.assertEqual(client.collections["synthetic_core_pipeline"].last_n_results, 2)
        self.assertLessEqual(
            len(client.collections["synthetic_core_pipeline"].last_returned_ids),
            2,
        )
        self.assertEqual(len(matches), 2)
        self.assertEqual([match.rank for match in matches], [1, 2])

    def test_rebuilding_vector_index_removes_stale_records(self) -> None:
        from src.core.vector_retriever import VectorRetriever

        stale = ProjectRecord(
            "SYNTH_STALE", "Old prototype", "MOCK ONLY stale", None, None,
            "synthetic", None, None,
        )
        replacement = ProjectRecord(
            "SYNTH_REPLACEMENT", "New prototype", "MOCK ONLY replacement", None, None,
            "synthetic", None, None,
        )
        client = FakeChromaClient(["SYNTH_STALE", "SYNTH_REPLACEMENT"])
        vector = VectorRetriever(
            [stale],
            embedder=DeterministicFakeEmbedder(),
            chroma_client=client,
            collection_name="synthetic_rebuild",
        )
        vector.rebuild_index([replacement])

        hits = vector.search(QUERY, top_k=5)

        self.assertIn("synthetic_rebuild", client.deleted_names)
        self.assertEqual(client.collections["synthetic_rebuild"].ids, ["SYNTH_REPLACEMENT"])
        self.assertEqual([(hit.project_id, hit.rank) for hit in hits], [("SYNTH_REPLACEMENT", 1)])

    def test_unknown_optional_metadata_is_preserved_without_inference(self) -> None:
        engine, _bm25, _vector, _embedder, _client = self.make_pipeline()

        matches = engine.search(QUERY, top_k=3)

        both = next(match for match in matches if match.project.project_id == "SYNTH_BOTH")
        self.assertIsNone(both.project.tech_stack)
        self.assertIsNone(both.project.domain)
        self.assertIsNone(both.project.source_url)
        self.assertIsNone(both.project.year)
        self.assertEqual(both.project.source_type, "synthetic")

    def test_unavailable_vector_dependency_raises_instead_of_becoming_no_match(self) -> None:
        from src.core.vector_retriever import VectorIndexUnavailableError, VectorRetriever

        records = synthetic_records()
        bm25 = RecordingBM25Retriever(records)
        vector = VectorRetriever(
            records,
            embedder=DeterministicFakeEmbedder(),
            chroma_client=FailingChromaClient(),
            collection_name="synthetic_unavailable_index",
            auto_build=False,
        )
        engine = CoreSearchEngine(records, bm25, vector)

        with self.assertRaises(VectorIndexUnavailableError):
            engine.search(QUERY, top_k=3)

        self.assertEqual(bm25.search_calls, [(QUERY, 3)])


if __name__ == "__main__":
    unittest.main()
