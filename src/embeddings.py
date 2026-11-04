"""Process-wide lazy and serialized access to sentence-transformer models."""

from __future__ import annotations

from threading import Lock
from typing import Any

_model_lock = Lock()
_inference_lock = Lock()
_models: dict[tuple[str, str], "SynchronizedSentenceTransformer"] = {}


class SynchronizedSentenceTransformer:
    """Serialize inference on a shared model across offline and live requests."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def encode(self, *args: Any, **kwargs: Any) -> Any:
        with _inference_lock:
            return self._model.encode(*args, **kwargs)

    def get_sentence_embedding_dimension(self) -> int | None:
        return self._model.get_sentence_embedding_dimension()


def get_sentence_transformer(model_name: str, device: str = "cpu") -> SynchronizedSentenceTransformer:
    """Load each configured model once per process, only when first requested."""
    key = (model_name, device)
    with _model_lock:
        if key in _models:
            return _models[key]
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as error:
            raise RuntimeError("sentence-transformers is not available") from error
        model = SentenceTransformer(model_name, device=device)
        synchronized = SynchronizedSentenceTransformer(model)
        _models[key] = synchronized
        return synchronized
