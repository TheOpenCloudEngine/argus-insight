"""Catalog API connector — pulls metadata from argus-catalog-server.

Fetches datasets, models, glossary terms, and standard terms
from the catalog server and converts them to IngestItems.
"""

import json
import logging

import httpx

from app.source.base import IngestItem, SourceConnector

logger = logging.getLogger(__name__)


class CatalogConnector(SourceConnector):
    """Fetch data from argus-catalog-server REST API."""

    def __init__(self, config: dict) -> None:
        self._base_url = config.get("base_url", "http://localhost:4600/api/v1")
        self._entity_type = config.get("entity_type", "datasets")
        self._auth_token = config.get("auth_token", "")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30,
            )
        return self._client

    async def fetch_all(self) -> list[IngestItem]:
        if self._entity_type == "datasets":
            return await self._fetch_datasets()
        elif self._entity_type == "models":
            return await self._fetch_models()
        elif self._entity_type == "glossary":
            return await self._fetch_glossary()
        elif self._entity_type == "standards":
            return await self._fetch_standards()
        else:
            logger.warning("Unknown entity type: %s", self._entity_type)
            return []

    async def _fetch_datasets(self) -> list[IngestItem]:
        """Fetch all datasets with schema info."""
        client = await self._get_client()
        items = []
        offset = 0
        limit = 100

        while True:
            resp = await client.get("/catalog/datasets", params={"limit": limit, "offset": offset})
            resp.raise_for_status()
            data = resp.json()
            datasets = data.get("datasets", data) if isinstance(data, dict) else data
            if not datasets:
                break

            for ds in datasets:
                # Build rich source text
                parts = [ds.get("name", "")]
                if ds.get("description"):
                    parts.append(ds["description"])
                if ds.get("qualified_name"):
                    parts.append(ds["qualified_name"])
                if ds.get("platform_type"):
                    parts.append(ds["platform_type"])
                if ds.get("platform_name"):
                    parts.append(ds["platform_name"])

                # Include tags
                for tag in ds.get("tags", []):
                    tag_name = tag.get("name", "") if isinstance(tag, dict) else str(tag)
                    if tag_name:
                        parts.append(tag_name)

                # Include owners
                for owner in ds.get("owners", []):
                    owner_name = (
                        owner.get("owner_name", "") if isinstance(owner, dict) else str(owner)
                    )
                    if owner_name:
                        parts.append(owner_name)

                items.append(
                    IngestItem(
                        external_id=f"dataset:{ds.get('id', '')}",
                        title=ds.get("name", ""),
                        source_text=" | ".join(parts),
                        metadata_json=json.dumps(
                            {
                                "id": ds.get("id"),
                                "platform_type": ds.get("platform_type"),
                                "status": ds.get("status"),
                            },
                            ensure_ascii=False,
                        ),
                        source_type="catalog_api",
                        source_url=f"{self._base_url}/catalog/datasets/{ds.get('id')}",
                    )
                )

            if len(datasets) < limit:
                break
            offset += limit

        logger.info("Fetched %d datasets from catalog", len(items))
        return items

    async def _fetch_models(self) -> list[IngestItem]:
        client = await self._get_client()
        resp = await client.get("/models/", params={"limit": 500})
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", data) if isinstance(data, dict) else data

        items = []
        for m in models:
            parts = [m.get("name", "")]
            if m.get("description"):
                parts.append(m["description"])
            if m.get("comment"):
                parts.append(m["comment"])

            items.append(
                IngestItem(
                    external_id=f"model:{m.get('name', '')}",
                    title=m.get("name", ""),
                    source_text=" | ".join(parts),
                    source_type="catalog_api",
                )
            )
        logger.info("Fetched %d models from catalog", len(items))
        return items

    async def _fetch_glossary(self) -> list[IngestItem]:
        client = await self._get_client()
        resp = await client.get("/catalog/glossary", params={"limit": 500})
        resp.raise_for_status()
        terms = resp.json() if isinstance(resp.json(), list) else resp.json().get("terms", [])

        items = []
        for t in terms:
            parts = [t.get("name", "")]
            if t.get("description"):
                parts.append(t["description"])
            if t.get("category"):
                parts.append(t["category"])

            items.append(
                IngestItem(
                    external_id=f"glossary:{t.get('id', '')}",
                    title=t.get("name", ""),
                    source_text=" | ".join(parts),
                    source_type="catalog_api",
                )
            )
        logger.info("Fetched %d glossary terms from catalog", len(items))
        return items

    async def _fetch_standards(self) -> list[IngestItem]:
        client = await self._get_client()
        resp = await client.get("/standards/terms", params={"limit": 500})
        resp.raise_for_status()
        terms = resp.json() if isinstance(resp.json(), list) else resp.json().get("terms", [])

        items = []
        for t in terms:
            parts = [t.get("term_name", t.get("name", ""))]
            if t.get("english_name"):
                parts.append(t["english_name"])
            if t.get("abbreviation"):
                parts.append(t["abbreviation"])
            if t.get("description"):
                parts.append(t["description"])

            items.append(
                IngestItem(
                    external_id=f"standard:{t.get('id', '')}",
                    title=t.get("term_name", t.get("name", "")),
                    source_text=" | ".join(parts),
                    source_type="catalog_api",
                )
            )
        logger.info("Fetched %d standard terms from catalog", len(items))
        return items

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
