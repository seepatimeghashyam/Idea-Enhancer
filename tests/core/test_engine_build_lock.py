"""Concurrent first searches should initialize the default engine only once."""

import threading
import time
from pathlib import Path

from src import database
from src.core.contracts import RetrievalHit
from src.core.dataset_loader import load_project_records
from src.core.engine import CoreSearchEngine
from tests.core.test_engine import FakeRetriever


FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_core_projects.csv"


def test_concurrent_first_requests_build_the_engine_once(monkeypatch) -> None:
    builds: list[int] = []

    def slow_factory(records):
        builds.append(1)
        time.sleep(0.2)
        return CoreSearchEngine(records, FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)]), FakeRetriever([]))

    database.configure_search_engine(None)
    monkeypatch.setattr(database, "_cached_engine", None)
    monkeypatch.setattr(database, "CANONICAL_DATASET_PATH", FIXTURE)
    monkeypatch.setattr(database, "_make_default_engine", slow_factory)

    errors: list[BaseException] = []

    def worker() -> None:
        try:
            database.search_projects("crop disease monitoring system", 3)
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(builds) == 1
