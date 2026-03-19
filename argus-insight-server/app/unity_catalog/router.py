"""Unity Catalog proxy router.

Forwards all requests under /unity-catalog/{path} to the real
Unity Catalog server configured in Settings > Argus.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.unity_catalog.service import proxy_to_uc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unity-catalog", tags=["unity-catalog"])


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_unity_catalog(
    path: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Generic proxy – forward any UC API request to the real server."""
    body = await request.body() or None
    content_type = request.headers.get("content-type")

    try:
        status, data = await proxy_to_uc(
            session=session,
            method=request.method,
            path=path,
            query_string=str(request.query_params),
            body=body,
            content_type=content_type,
        )
    except ValueError as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    except Exception as exc:
        logger.exception("UC proxy error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": f"Failed to connect to Unity Catalog: {exc}"},
        )

    return JSONResponse(status_code=status, content=data)
