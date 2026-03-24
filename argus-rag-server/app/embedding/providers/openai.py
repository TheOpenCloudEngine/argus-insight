"""OpenAI embedding provider."""

import logging

import httpx

from app.embedding.base import EmbeddingProvider

logger = logging.getLogger(__name__)

_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model_id: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"input": texts, "model": self._model_id},
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items]

    def dimension(self) -> int:
        return _DIMENSIONS.get(self._model_id, 1536)

    def model_name(self) -> str:
        return self._model_id

    def provider_name(self) -> str:
        return "openai"

    async def close(self) -> None:
        await self._client.aclose()
