"""Abstract base class for embedding providers — reused from catalog-server."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def provider_name(self) -> str: ...

    async def close(self) -> None:
        pass
