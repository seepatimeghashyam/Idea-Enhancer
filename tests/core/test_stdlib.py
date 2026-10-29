"""Dependency-free smoke tests for environments without the optional pytest package."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.contracts import RetrievalHit
from src.core.dataset_loader import DatasetLoadError, load_project_records
from src.core.engine import CoreSearchEngine
from src.core.fusion import FusionError, fuse_rankings
from src.database import configure_search_engine, search_projects


FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_core_projects.csv"


class FakeRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


class CoreSearchSmokeTests(unittest.TestCase):
    def test_synthetic_records_and_shared_retrievers_flow_through_rrf(self) -> None:
        records = load_project_records(FIXTURE)
        bm25 = FakeRetriever([RetrievalHit("SYNTHETIC-001", 1), RetrievalHit("SYNTHETIC-002", 2)])
        vector = FakeRetriever([RetrievalHit("SYNTHETIC-003", 1), RetrievalHit("SYNTHETIC-001", 2)])
        engine = CoreSearchEngine(records, bm25, vector)

        matches = engine.search("  crop disease monitoring  ", 2)

        self.assertEqual(bm25.calls, [("crop disease monitoring", 2)])
        self.assertEqual(vector.calls, [("crop disease monitoring", 2)])
        self.assertEqual(matches[0].project.project_id, "SYNTHETIC-001")
        self.assertAlmostEqual(matches[0].rrf_score, 1 / 61 + 1 / 62)
        self.assertEqual(matches[0].bm25_rank, 1)
        self.assertEqual(matches[0].vector_rank, 2)
        self.assertEqual(matches[0].shared_elements, ["crop", "disease"])
        self.assertEqual(matches[0].verification_status, "checked")
        self.assertEqual([match.rank for match in matches], [1, 2])

    def test_fusion_rejects_duplicate_retriever_ids(self) -> None:
        records = {record.project_id: record for record in load_project_records(FIXTURE)}
        with self.assertRaisesRegex(FusionError, "duplicate project_id"):
            fuse_rankings(
                [RetrievalHit("SYNTHETIC-001", 1), RetrievalHit("SYNTHETIC-001", 2)],
                [],
                records,
                top_k=5,
            )

    def test_public_facade_maps_canonical_fields_without_fabricated_source(self) -> None:
        engine = CoreSearchEngine(
            load_project_records(FIXTURE),
            FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)]),
            FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)]),
        )
        configure_search_engine(engine)
        try:
            result = search_projects("crop disease monitoring", 5)[0]
        finally:
            configure_search_engine(None)

        self.assertEqual(result["abstract"], "MOCK ONLY: detect crop disease with image analysis")
        self.assertEqual(result["tech_stack"], "Raspberry Pi")
        self.assertIsNone(result["source_url"])
        self.assertEqual(result["rank"], 1)
        self.assertIn("rrf_score", result)
        self.assertIn("verification_status", result)

    def test_loader_rejects_invalid_year_and_missing_dataset(self) -> None:
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.csv"
            invalid.write_text(
                "project_id,title,abstract,source_type,year\nSYNTHETIC-X,MOCK ONLY title,MOCK ONLY abstract,MOCK ONLY,nope\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(DatasetLoadError, "year must be a whole number"):
                load_project_records(invalid)
            with self.assertRaisesRegex(DatasetLoadError, "Canonical dataset not found"):
                load_project_records(Path(directory) / "missing.csv")


if __name__ == "__main__":
    unittest.main()
