"""Local SentenceTransformer embedding provider."""

import asyncio
import logging

from app.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_id: str = "paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self._model_id = model_id
        self._model = None
        self._dim: int | None = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading SentenceTransformer model: %s", self._model_id)
            self._model = SentenceTransformer(self._model_id)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("Model loaded: %s (dim=%d)", self._model_id, self._dim)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=True)
        )
        return [e.tolist() for e in embeddings]

    def dimension(self) -> int:
        if self._dim is None:
            self._load_model()
        return self._dim or 384

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "local"

    async def close(self) -> None:
        self._model = None
        logger.info("Local embedding provider closed")
