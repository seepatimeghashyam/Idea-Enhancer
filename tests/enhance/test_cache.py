"""Tests for in-memory enhance caching."""

import time
from src.enhance.cache import EnhanceCache, compute_cache_key
from src.enhance.contracts import MatchInput


def test_compute_cache_key_deterministic() -> None:
    matches = [
        MatchInput(project_id="p2", title="P2"),
        MatchInput(project_id="p1", title="P1"),
    ]
    key1 = compute_cache_key("Smart Crop Monitoring", matches)
    # Order of matches shouldn't alter key because IDs are sorted
    key2 = compute_cache_key("   smart  crop monitoring   ", list(reversed(matches)))
    assert key1 == key2


def test_cache_set_and_get() -> None:
    cache = EnhanceCache(default_ttl_seconds=60)
    data = {"idea": "Test idea", "status": "success", "cached": False}
    cache.set("key_123", data)

    cached = cache.get("key_123")
    assert cached is not None
    assert cached["idea"] == "Test idea"
    assert cached["cached"] is True


def test_cache_expiration() -> None:
    # 0 second TTL expires immediately
    cache = EnhanceCache(default_ttl_seconds=0)
    cache.set("key_exp", {"status": "success"})
    time.sleep(0.01)
    assert cache.get("key_exp") is None


def test_cache_clear() -> None:
    cache = EnhanceCache()
    cache.set("k1", {"val": 1})
    cache.set("k2", {"val": 2})
    cache.clear()
    assert cache.get("k1") is None
    assert cache.get("k2") is None
