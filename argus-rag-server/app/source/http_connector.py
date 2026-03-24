"""HTTP URL connector — fetches content from web URLs and ingests for embedding.

Supports fetching:
- JSON API responses (array of objects)
- Plain text / HTML (single document)
- Multiple URLs (one document per URL)

Config example:
{
    "urls": ["https://example.com/api/items"],
    "method": "GET",
    "headers": {"Authorization": "Bearer xxx"},
    "response_type": "json_array",   // json_array, json_object, text
    "id_field": "id",                // for json_array: field to use as external_id
    "title_field": "name",           // for json_array: field for title
    "text_fields": ["name", "desc"], // for json_array: fields to embed
    "text_separator": " | "
}
"""

import json
import logging
from hashlib import md5

import httpx

from app.source.base import IngestItem, SourceConnector

logger = logging.getLogger(__name__)


class HTTPConnector(SourceConnector):
    """Fetch content from HTTP URLs and produce IngestItems."""

    def __init__(self, config: dict) -> None:
        self._urls = config.get("urls", [])
        if isinstance(self._urls, str):
            self._urls = [self._urls]
        self._method = config.get("method", "GET").upper()
        self._headers = config.get("headers", {})
        self._body = config.get("body")
        self._response_type = config.get("response_type", "json_array")
        self._id_field = config.get("id_field", "")
        self._title_field = config.get("title_field", "")
        self._text_fields = config.get("text_fields", [])
        self._text_separator = config.get("text_separator", " | ")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=30,
                follow_redirects=True,
            )
        return self._client

    async def fetch_all(self) -> list[IngestItem]:
        if not self._urls:
            raise ValueError("No URLs configured for http source")

        items: list[IngestItem] = []
        client = await self._get_client()

        for url in self._urls:
            try:
                if self._method == "POST":
                    resp = await client.post(url, json=self._body)
                else:
                    resp = await client.get(url)
                resp.raise_for_status()

                if self._response_type == "json_array":
                    items.extend(self._parse_json_array(resp.json(), url))
                elif self._response_type == "json_object":
                    items.extend(self._parse_json_object(resp.json(), url))
                else:
                    items.append(self._parse_text(resp.text, url))
            except Exception as e:
                logger.warning("HTTP fetch failed for %s: %s", url, e)

        logger.info("HTTP connector fetched %d items from %d URLs", len(items), len(self._urls))
        return items

    async def preview(self, max_rows: int = 10) -> dict:
        """Fetch the first URL and return preview data."""
        if not self._urls:
            raise ValueError("No URLs configured")

        client = await self._get_client()
        url = self._urls[0]

        if self._method == "POST":
            resp = await client.post(url, json=self._body)
        else:
            resp = await client.get(url)
        resp.raise_for_status()

        if self._response_type in ("json_array", "json_object"):
            data = resp.json()
            if isinstance(data, list):
                rows = data[:max_rows]
            elif isinstance(data, dict):
                # Try to find an array inside
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        rows = v[:max_rows]
                        break
                else:
                    rows = [data]
            else:
                rows = []

            columns = list(rows[0].keys()) if rows else []
            serialized = [
                {
                    k: v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
                    for k, v in r.items()
                }
                for r in rows
            ]
            return {
                "columns": columns,
                "rows": serialized,
                "total_rows": len(rows),
                "url": url,
                "response_type": self._response_type,
            }
        else:
            text = resp.text[:2000]
            return {
                "columns": ["content"],
                "rows": [{"content": text}],
                "total_rows": 1,
                "url": url,
                "response_type": "text",
            }

    def _parse_json_array(self, data, url: str) -> list[IngestItem]:
        """Parse JSON array response (or dict with array inside)."""
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    data = v
                    break
            else:
                return [self._parse_json_object(data, url)]

        items = []
        for idx, obj in enumerate(data):
            if not isinstance(obj, dict):
                continue
            ext_id = str(obj.get(self._id_field, idx)) if self._id_field else str(idx)
            title = str(obj.get(self._title_field, "")) if self._title_field else ""

            text_cols = self._text_fields or list(obj.keys())
            parts = []
            for f in text_cols:
                val = obj.get(f)
                if val is not None and str(val).strip():
                    parts.append(str(val))
            source_text = (
                self._text_separator.join(parts) if parts else json.dumps(obj, ensure_ascii=False)
            )

            items.append(
                IngestItem(
                    external_id=f"http:{ext_id}",
                    title=title,
                    source_text=source_text,
                    metadata_json=json.dumps(obj, ensure_ascii=False, default=str),
                    source_type="http",
                    source_url=url,
                )
            )
        return items

    def _parse_json_object(self, data: dict, url: str) -> list[IngestItem]:
        text = json.dumps(data, ensure_ascii=False, default=str)
        return [
            IngestItem(
                external_id=f"http:{md5(url.encode()).hexdigest()[:12]}",
                title=url.split("/")[-1],
                source_text=text[:5000],
                metadata_json=text[:10000],
                source_type="http",
                source_url=url,
            )
        ]

    def _parse_text(self, text: str, url: str) -> IngestItem:
        return IngestItem(
            external_id=f"http:{md5(url.encode()).hexdigest()[:12]}",
            title=url.split("/")[-1],
            source_text=text[:10000],
            source_type="http",
            source_url=url,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
