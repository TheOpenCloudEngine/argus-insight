"""Ollama embedding provider."""

import logging

import httpx

from app.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_id: str = "bge-m3",
    ) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)
        self._dim: int | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            resp = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model_id, "prompt": text},
            )
            resp.raise_for_status()
            vec = resp.json().get("embedding", [])
            if self._dim is None and vec:
                self._dim = len(vec)
            results.append(vec)
        return results

    def dimension(self) -> int:
        return self._dim or 384

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "ollama"

    async def close(self) -> None:
        await self._client.aclose()
