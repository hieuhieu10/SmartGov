"""Embedding service for retrieval chunks."""

from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def model_name(self) -> str:
        return settings.embedding_model_name

    def is_configured(self) -> bool:
        return bool(settings.embedding_base_url and settings.embedding_model_name)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=settings.embedding_base_url,
                api_key=settings.embedding_api_key or "no-key",
            )
        return self._client

    def _is_huggingface_url(self) -> bool:
        host = urlparse(settings.embedding_base_url).netloc.lower()
        return host in {
            "huggingface.co",
            "www.huggingface.co",
            "api-inference.huggingface.co",
            "router.huggingface.co",
        }

    def _huggingface_api_url(self) -> str:
        parsed = urlparse(settings.embedding_base_url)
        path = parsed.path.strip("/")
        if parsed.netloc.lower() in {"api-inference.huggingface.co", "router.huggingface.co"} and path.startswith("models/"):
            model_id = path.removeprefix("models/")
        elif parsed.netloc.lower() in {"huggingface.co", "www.huggingface.co"} and path:
            model_id = "/".join(path.split("/")[:2])
        else:
            model_id = settings.embedding_model_name
        return f"https://router.huggingface.co/hf-inference/models/{model_id}/pipeline/feature-extraction"

    def embed_texts(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        if not self.is_configured():
            logger.warning("Embedding service is not configured; skipping chunk embeddings")
            return []
        prepared_texts = self._prepare_texts(texts, input_type)
        if not settings.embedding_base_url:
            logger.warning("Remote embedding base URL is not configured; skipping embeddings")
            return []
        if self._is_huggingface_url():
            return self._embed_texts_huggingface(prepared_texts)
        try:
            client = self._get_client()
            vectors: list[list[float]] = []
            batch_size = max(int(settings.embedding_batch_size or 16), 1)

            for start in range(0, len(prepared_texts), batch_size):
                batch = prepared_texts[start:start + batch_size]
                response = client.embeddings.create(
                    model=settings.embedding_model_name,
                    input=batch,
                )
                vectors.extend([list(item.embedding) for item in response.data])

            if vectors and len(vectors[0]) != settings.embedding_dimensions:
                logger.warning(
                    "Embedding dimension mismatch: expected %s, got %s",
                    settings.embedding_dimensions,
                    len(vectors[0]),
                )

            return vectors
        except Exception as exc:
            logger.warning("Embedding generation failed; skipping vector persistence: %s", exc)
            return []

    def _embed_texts_huggingface(self, texts: list[str]) -> list[list[float]]:
        try:
            # Model PhoBERT giới hạn 256 token; HF không tự truncate mà trả 400
            # ("index out of range in self"). Cắt phía client để không bao giờ vượt.
            max_chars = max(int(settings.embedding_max_chars or 800), 100)
            texts = [text[:max_chars] for text in texts]
            vectors: list[list[float]] = []
            batch_size = max(int(settings.embedding_batch_size or 16), 1)
            headers = {"Accept": "application/json"}
            if settings.embedding_api_key:
                headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

            with httpx.Client(timeout=60.0) as client:
                for start in range(0, len(texts), batch_size):
                    batch = texts[start:start + batch_size]
                    response = client.post(
                        self._huggingface_api_url(),
                        headers=headers,
                        json={
                            "inputs": batch,
                            "options": {"wait_for_model": True},
                        },
                    )
                    response.raise_for_status()
                    vectors.extend(self._coerce_huggingface_vectors(response.json(), len(batch)))

            if vectors and len(vectors[0]) != settings.embedding_dimensions:
                logger.warning(
                    "HuggingFace embedding dimension mismatch: expected %s, got %s",
                    settings.embedding_dimensions,
                    len(vectors[0]),
                )
            return [self._normalize(vector) for vector in vectors]
        except Exception as exc:
            logger.warning("HuggingFace embedding generation failed; skipping vector persistence: %s", exc)
            return []

    def _coerce_huggingface_vectors(self, payload: Any, expected_count: int) -> list[list[float]]:
        if hasattr(payload, "tolist"):
            payload = payload.tolist()

        if isinstance(payload, dict):
            if "error" in payload:
                raise RuntimeError(str(payload["error"]))
            for key in ("embeddings", "data"):
                if key in payload:
                    return self._coerce_huggingface_vectors(payload[key], expected_count)

        if not isinstance(payload, list):
            return []

        if self._is_vector(payload):
            return [self._float_vector(payload)]

        if expected_count == 1 and payload and all(self._is_vector(item) for item in payload):
            return [self._mean_pool(payload)]

        vectors: list[list[float]] = []
        for item in payload:
            if self._is_vector(item):
                vectors.append(self._float_vector(item))
            elif isinstance(item, list) and item and all(self._is_vector(token) for token in item):
                vectors.append(self._mean_pool(item))
            elif isinstance(item, dict):
                vectors.extend(self._coerce_huggingface_vectors(item, 1))
        return vectors

    @staticmethod
    def _is_vector(value: Any) -> bool:
        return isinstance(value, list) and bool(value) and all(isinstance(item, (int, float)) for item in value)

    @staticmethod
    def _float_vector(value: list[Any]) -> list[float]:
        return [float(item) for item in value]

    def _mean_pool(self, token_vectors: list[list[Any]]) -> list[float]:
        vectors = [self._float_vector(vector) for vector in token_vectors if self._is_vector(vector)]
        if not vectors:
            return []
        dimensions = len(vectors[0])
        pooled = [0.0] * dimensions
        for vector in vectors:
            if len(vector) != dimensions:
                continue
            for index, value in enumerate(vector):
                pooled[index] += value
        return [value / len(vectors) for value in pooled]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return vector
        return [value / norm for value in vector]

    def _prepare_texts(self, texts: list[str], input_type: str) -> list[str]:
        model_name = settings.embedding_model_name.lower()
        if "multilingual-e5" not in model_name:
            return texts
        prefix = "query: " if input_type == "query" else "passage: "
        return [
            text if text.lower().startswith(("query: ", "passage: ")) else f"{prefix}{text}"
            for text in texts
        ]


embedding_service = EmbeddingService()
