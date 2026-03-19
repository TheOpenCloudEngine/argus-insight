"""Unity Catalog proxy service.

Reads the Unity Catalog URL and access token from the argus settings
and forwards requests to the real Unity Catalog server.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings.models import ArgusConfiguration

logger = logging.getLogger(__name__)

UC_API_PREFIX = "/api/2.1/unity-catalog"


async def _get_uc_config(session: AsyncSession) -> tuple[str, str]:
    """Return (url, access_token) from the argus configuration category."""
    result = await session.execute(
        select(ArgusConfiguration).where(
            ArgusConfiguration.category == "argus",
            ArgusConfiguration.config_key.in_(
                ["unity_catalog_url", "unity_catalog_access_token"]
            ),
        )
    )
    rows = {r.config_key: r.config_value for r in result.scalars().all()}
    url = (rows.get("unity_catalog_url") or "").strip()
    token = (rows.get("unity_catalog_access_token") or "").strip()
    return url, token


async def proxy_to_uc(
    session: AsyncSession,
    method: str,
    path: str,
    query_string: str = "",
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, dict | list | str]:
    """Proxy a request to the Unity Catalog server.

    Returns (status_code, response_body).
    Raises ValueError when UC is not configured.
    """
    url, token = await _get_uc_config(session)
    if not url:
        raise ValueError("Unity Catalog URL is not configured")

    base = url.rstrip("/")
    target = f"{base}{UC_API_PREFIX}/{path}"
    if query_string:
        target = f"{target}?{query_string}"

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type

    logger.debug("UC proxy %s %s", method, target)

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        resp = await client.request(
            method=method,
            url=target,
            headers=headers,
            content=body,
        )

    try:
        data = resp.json()
    except Exception:
        data = resp.text

    return resp.status_code, data
