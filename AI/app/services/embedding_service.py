"""Embedding service for retrieval chunks."""

from __future__ import annotations

import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._local_model = None

    @property
    def model_name(self) -> str:
        return settings.embedding_model_name

    def is_configured(self) -> bool:
        return bool(settings.embedding_model_name)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                base_url=settings.embedding_base_url,
                api_key=settings.embedding_api_key or "no-key",
            )
        return self._client

    def embed_texts(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        if not self.is_configured():
            logger.warning("Embedding service is not configured; skipping chunk embeddings")
            return []
        prepared_texts = self._prepare_texts(texts, input_type)
        if not settings.embedding_base_url:
            return self._embed_texts_local(prepared_texts)
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

    def _prepare_texts(self, texts: list[str], input_type: str) -> list[str]:
        model_name = settings.embedding_model_name.lower()
        if "multilingual-e5" not in model_name:
            return texts
        prefix = "query: " if input_type == "query" else "passage: "
        return [
            text if text.lower().startswith(("query: ", "passage: ")) else f"{prefix}{text}"
            for text in texts
        ]

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading local embedding model: %s on %s",
                settings.embedding_model_name,
                settings.embedding_device,
            )
            self._local_model = SentenceTransformer(
                settings.embedding_model_name,
                device=settings.embedding_device,
            )
        return self._local_model

    def _embed_texts_local(self, texts: list[str]) -> list[list[float]]:
        try:
            model = self._get_local_model()
            if hasattr(model, "max_seq_length"):
                model.max_seq_length = min(getattr(model, "max_seq_length", 512), 512)
            batch_size = max(int(settings.embedding_batch_size or 16), 1)
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = [embedding.tolist() for embedding in embeddings]
            if vectors and len(vectors[0]) != settings.embedding_dimensions:
                logger.warning(
                    "Local embedding dimension mismatch: expected %s, got %s",
                    settings.embedding_dimensions,
                    len(vectors[0]),
                )
            return vectors
        except Exception as exc:
            logger.warning("Local embedding generation failed; skipping vector persistence: %s", exc)
            return []


embedding_service = EmbeddingService()
