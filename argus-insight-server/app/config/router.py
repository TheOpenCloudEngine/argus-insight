"""Infrastructure configuration API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.config import service
from app.config.schemas import (
    CheckPathRequest,
    CheckPathResponse,
    InfraConfigResponse,
    UpdateInfraCategoryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/configuration", response_model=InfraConfigResponse)
async def get_configuration(
    session: AsyncSession = Depends(get_session),
) -> InfraConfigResponse:
    """Fetch the full infrastructure configuration."""
    return await service.get_infra_config(session)


@router.put("/configuration/category", status_code=204)
async def update_category(
    body: UpdateInfraCategoryRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Update settings within a single infrastructure category."""
    try:
        await service.update_infra_category(session, body.category, body.items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/check-path", response_model=CheckPathResponse)
async def check_path(body: CheckPathRequest) -> CheckPathResponse:
    """Check if a file path exists on the server."""
    exists = Path(body.path).is_file()
    return CheckPathResponse(path=body.path, exists=exists)
