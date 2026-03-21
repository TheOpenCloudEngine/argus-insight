"""Client for Argus Catalog Server REST API."""

import logging

import requests

logger = logging.getLogger(__name__)


class CatalogClient:
    """Thin wrapper around the Argus Catalog Server REST API."""

    def __init__(self, settings):
        self.base_url = settings.catalog_base_url.rstrip("/")
        self.timeout = settings.catalog_timeout
        self.session = requests.Session()

    # ----- Platforms -----

    def get_platforms(self) -> list[dict]:
        res = self.session.get(f"{self.base_url}/platforms", timeout=self.timeout)
        res.raise_for_status()
        return res.json()

    def get_platform_by_name(self, name: str) -> dict | None:
        platforms = self.get_platforms()
        for p in platforms:
            if p["name"] == name:
                return p
        return None

    # ----- Datasets -----

    def list_datasets(
        self,
        platform: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict:
        params = {"page": page, "page_size": page_size}
        if platform:
            params["platform"] = platform
        res = self.session.get(
            f"{self.base_url}/datasets", params=params, timeout=self.timeout
        )
        res.raise_for_status()
        return res.json()

    def get_dataset_by_urn(self, urn: str) -> dict | None:
        res = self.session.get(
            f"{self.base_url}/datasets/urn/{urn}", timeout=self.timeout
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    def create_dataset(self, payload: dict) -> dict:
        res = self.session.post(
            f"{self.base_url}/datasets",
            json=payload,
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()

    def update_dataset(self, dataset_id: int, payload: dict) -> dict:
        res = self.session.put(
            f"{self.base_url}/datasets/{dataset_id}",
            json=payload,
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()

    def update_schema_fields(self, dataset_id: int, fields: list[dict]) -> list[dict]:
        res = self.session.put(
            f"{self.base_url}/datasets/{dataset_id}/schema",
            json=fields,
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()
