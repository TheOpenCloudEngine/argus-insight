"""Infrastructure configuration API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.settings import service
from app.settings.schemas import (
    CheckPathRequest,
    CheckPathResponse,
    DockerRegistryTestRequest,
    DockerRegistryTestResponse,
    InfraConfigResponse,
    UnityCatalogInitRequest,
    UnityCatalogInitResponse,
    UnityCatalogTestRequest,
    UnityCatalogTestResponse,
    UpdateInfraCategoryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


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


@router.post("/docker-registry/test", response_model=DockerRegistryTestResponse)
async def test_docker_registry(body: DockerRegistryTestRequest) -> DockerRegistryTestResponse:
    """Test connectivity to a Docker Registry."""
    result = await service.test_docker_registry(body.url, body.username, body.password)
    return DockerRegistryTestResponse(**result)


@router.post("/unity-catalog/test", response_model=UnityCatalogTestResponse)
async def test_unity_catalog(body: UnityCatalogTestRequest) -> UnityCatalogTestResponse:
    """Test connectivity to a Unity Catalog server."""
    result = await service.test_unity_catalog(body.url, body.access_token)
    return UnityCatalogTestResponse(**result)


@router.post("/unity-catalog/initialize", response_model=UnityCatalogInitResponse)
async def initialize_unity_catalog(body: UnityCatalogInitRequest) -> UnityCatalogInitResponse:
    """Initialize Unity Catalog with 'global' metastore and 'default' catalog."""
    result = await service.initialize_unity_catalog(body.url, body.access_token)
    return UnityCatalogInitResponse(**result)


@router.post("/check-path", response_model=CheckPathResponse)
async def check_path(body: CheckPathRequest) -> CheckPathResponse:
    """Check if a file path exists on the server."""
    exists = Path(body.path).is_file()
    return CheckPathResponse(path=body.path, exists=exists)
