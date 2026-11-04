"""Process-wide lazy cache for sentence-transformers model instances."""

from __future__ import annotations

from threading import Lock
from typing import Any

_model_lock = Lock()
_models: dict[tuple[str, str], Any] = {}


def get_sentence_transformer(model_name: str, device: str = "cpu") -> Any:
    """Load each configured model once per process, only when first requested."""
    with _model_lock:
        key = (model_name, device)
        if key in _models:
            return _models[key]
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as error:
            raise RuntimeError("sentence-transformers is not available") from error
        model = SentenceTransformer(model_name, device=device)
        _models[key] = model
        return model
