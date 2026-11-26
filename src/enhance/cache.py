"""Thread-safe in-memory cache for POST /enhance with TTL."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional, Sequence
from src.enhance.contracts import MatchInput


def compute_cache_key(idea: str, matches: Sequence[MatchInput]) -> str:
    """Generate a deterministic SHA-256 hash key for an idea and matched projects."""
    normalized_idea = " ".join(idea.strip().lower().split())
    sorted_ids = sorted(m.project_id.strip() for m in matches if m.project_id)
    key_payload = json.dumps({"idea": normalized_idea, "matches": sorted_ids}, sort_keys=True)
    return hashlib.sha256(key_payload.encode("utf-8")).hexdigest()


class EnhanceCache:
    """Thread-safe LRU/TTL in-memory cache."""

    def __init__(self, default_ttl_seconds: int = 3600, max_entries: int = 250):
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached payload if present and not expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, data = entry
            if time.time() > expires_at:
                del self._cache[key]
                return None
            # Return copy with cached: True
            data_copy = dict(data)
            data_copy["cached"] = True
            return data_copy

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        """Store payload with expiration timestamp."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.time() + ttl
        with self._lock:
            # Simple eviction if at capacity
            if len(self._cache) >= self.max_entries and key not in self._cache:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (expires_at, dict(value))

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
