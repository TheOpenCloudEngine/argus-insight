"""HTTP client for argus-catalog-server.

All catalog API interactions go through this client. It handles authentication
token forwarding, error mapping, and response parsing.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CatalogClient:
    """Async HTTP client for the Argus Catalog Server API."""

    def __init__(self, auth_token: str | None = None) -> None:
        self._base_url = f"{settings.catalog_base_url}{settings.catalog_api_prefix}"
        self._timeout = settings.catalog_timeout
        self._auth_token = auth_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | None:
        client = await self._get_client()
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    async def get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, json: dict | None = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)

    # ----- Convenience methods for common catalog operations -----

    async def search_datasets(self, query: str, limit: int = 20, offset: int = 0) -> dict:
        """Search datasets using hybrid search (keyword + semantic)."""
        return await self.get(
            "/catalog/search/hybrid",
            params={"q": query, "limit": limit, "offset": offset},
        )

    async def list_datasets(
        self,
        platform_id: int | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List datasets with optional filters."""
        params: dict = {"limit": limit, "offset": offset}
        if platform_id:
            params["platform_id"] = platform_id
        if search:
            params["search"] = search
        return await self.get("/catalog/datasets", params=params)

    async def get_dataset(self, dataset_id: int) -> dict:
        """Get full dataset detail."""
        return await self.get(f"/catalog/datasets/{dataset_id}")

    async def get_dataset_schema(self, dataset_id: int) -> list:
        """Get column/field schema for a dataset."""
        return await self.get(f"/catalog/datasets/{dataset_id}/schema")

    async def get_dataset_lineage(self, dataset_id: int) -> dict:
        """Get lineage graph for a dataset."""
        return await self.get(f"/catalog/datasets/{dataset_id}/lineage")

    async def get_platform(self, platform_id: int) -> dict:
        """Get platform details."""
        return await self.get("/catalog/platforms")

    async def get_platform_config(self, platform_id: int) -> dict:
        """Get platform connection configuration."""
        return await self.get(f"/catalog/platforms/{platform_id}/configuration")

    async def get_platform_metadata(self, platform_id: int) -> dict:
        """Get platform capabilities (data types, features)."""
        return await self.get(f"/catalog/platforms/{platform_id}/metadata")

    async def list_pipelines(self, limit: int = 50, offset: int = 0) -> dict:
        """List registered data pipelines."""
        return await self.get("/catalog/pipelines", params={"limit": limit, "offset": offset})

    async def register_pipeline(self, pipeline_data: dict) -> dict:
        """Register a new data pipeline."""
        return await self.post("/catalog/pipelines", json=pipeline_data)

    async def register_lineage(self, lineage_data: dict) -> dict:
        """Register a lineage relationship."""
        return await self.post("/catalog/lineage", json=lineage_data)

    async def get_quality_profile(self, dataset_id: int) -> dict:
        """Get the latest quality profile for a dataset."""
        return await self.get(f"/quality/datasets/{dataset_id}/profile")

    async def run_profiling(self, dataset_id: int) -> dict:
        """Trigger data profiling on a dataset."""
        return await self.post(f"/quality/datasets/{dataset_id}/profile")

    async def get_quality_score(self, dataset_id: int) -> dict:
        """Get quality score for a dataset."""
        return await self.get(f"/quality/datasets/{dataset_id}/score")

    async def run_quality_check(self, dataset_id: int) -> dict:
        """Execute quality rules on a dataset."""
        return await self.post(f"/quality/datasets/{dataset_id}/check")

    async def list_quality_rules(self, dataset_id: int) -> list:
        """List quality rules for a dataset."""
        return await self.get("/quality/rules", params={"dataset_id": dataset_id})

    async def search_glossary(self, search: str | None = None, limit: int = 50) -> list:
        """Search glossary terms."""
        params: dict = {"limit": limit}
        if search:
            params["search"] = search
        return await self.get("/catalog/glossary", params=params)

    async def get_standard_terms(self, dictionary_id: int | None = None, limit: int = 100) -> list:
        """Get standard terms."""
        params: dict = {"limit": limit}
        if dictionary_id:
            params["dictionary_id"] = dictionary_id
        return await self.get("/standards/terms", params=params)

    async def list_standard_dictionaries(self) -> list:
        """List all standard dictionaries."""
        return await self.get("/standards/dictionaries")

    async def search_standard_words(
        self,
        dictionary_id: int,
        word_type: str | None = None,
        limit: int = 100,
    ) -> list:
        """Search standard words in a dictionary."""
        params: dict = {"dictionary_id": dictionary_id, "limit": limit}
        if word_type:
            params["word_type"] = word_type
        return await self.get("/standards/words", params=params)

    async def search_standard_terms(
        self,
        dictionary_id: int,
        search: str | None = None,
        limit: int = 100,
    ) -> list:
        """Search standard terms with optional keyword filter."""
        params: dict = {"dictionary_id": dictionary_id, "limit": limit}
        if search:
            params["search"] = search
        return await self.get("/standards/terms", params=params)

    async def analyze_term(self, dictionary_id: int, term_name: str) -> dict:
        """Analyze a term name using morpheme decomposition."""
        return await self.get(
            "/standards/terms/analyze",
            params={"dictionary_id": dictionary_id, "term_name": term_name},
        )

    async def get_dataset_compliance(self, dictionary_id: int, dataset_id: int) -> dict:
        """Get compliance stats for a dataset against a standard dictionary."""
        return await self.get(
            "/standards/compliance",
            params={"dictionary_id": dictionary_id, "dataset_id": dataset_id},
        )

    async def get_dataset_term_mapping(self, dictionary_id: int, dataset_id: int) -> dict:
        """Get full term mapping status for all columns in a dataset."""
        return await self.get(
            "/standards/mappings/dataset",
            params={"dictionary_id": dictionary_id, "dataset_id": dataset_id},
        )

    async def auto_map_dataset(self, dictionary_id: int, dataset_id: int) -> dict:
        """Auto-map dataset columns to standard terms."""
        return await self.post(
            "/standards/mappings/auto-map",
            json={"dictionary_id": dictionary_id, "dataset_id": dataset_id},
        )

    async def get_catalog_stats(self) -> dict:
        """Get catalog dashboard statistics."""
        return await self.get("/catalog/stats")

    async def get_alerts_summary(self) -> dict:
        """Get unresolved alert count by severity."""
        return await self.get("/alerts/summary")

    async def list_alerts(self, status: str | None = None, limit: int = 20) -> list:
        """List alerts with optional status filter."""
        params: dict = {"limit": limit}
        if status:
            params["status"] = status
        return await self.get("/alerts", params=params)
