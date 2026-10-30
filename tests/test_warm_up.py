"""Warm-up runs only for the real gateway and cannot fail app startup."""

import threading

from fastapi.testclient import TestClient

from src import main
from tests.mock_core_search import MockCoreSearchGateway


def test_injected_gateway_does_not_warm_up(monkeypatch) -> None:
    called = threading.Event()
    monkeypatch.setattr(main, "warm_up_search", called.set)
    with TestClient(main.create_app(MockCoreSearchGateway())):
        pass
    assert not called.is_set()


def test_default_gateway_warms_up_in_background(monkeypatch) -> None:
    called = threading.Event()
    monkeypatch.setattr(main, "warm_up_search", called.set)
    monkeypatch.delenv("IDEA_ENHANCER_WARMUP", raising=False)
    with TestClient(main.create_app()):
        assert called.wait(timeout=2)


def test_warm_up_can_be_disabled(monkeypatch) -> None:
    called = threading.Event()
    monkeypatch.setattr(main, "warm_up_search", called.set)
    monkeypatch.setenv("IDEA_ENHANCER_WARMUP", "0")
    with TestClient(main.create_app()):
        pass
    assert not called.is_set()


def test_warm_up_failure_is_logged_not_raised(monkeypatch) -> None:
    from src import database

    def boom():
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(database, "_get_engine", boom)
    main.warm_up_search()
