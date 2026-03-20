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
    ObjectStorageInitRequest,
    ObjectStorageInitResponse,
    ObjectStorageTestRequest,
    ObjectStorageTestResponse,
    PrometheusTestRequest,
    PrometheusTestResponse,
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

    # If argus category contains prometheus keys, push config to all REGISTERED agents
    if body.category == "argus" and service._PROMETHEUS_KEYS & body.items.keys():
        # Fetch the full argus config to send complete prometheus values
        argus_config = await service.get_infra_category_items(session, "argus")
        argus_config.update(body.items)
        await service.push_prometheus_config_to_agents(session, argus_config)


@router.post("/object-storage/test", response_model=ObjectStorageTestResponse)
async def test_object_storage(body: ObjectStorageTestRequest) -> ObjectStorageTestResponse:
    """Test Object Storage connectivity by listing buckets."""
    result = await service.test_object_storage(
        body.endpoint, body.access_key, body.secret_key, body.region,
    )
    return ObjectStorageTestResponse(**result)


@router.post("/object-storage/initialize", response_model=ObjectStorageInitResponse)
async def initialize_object_storage(body: ObjectStorageInitRequest) -> ObjectStorageInitResponse:
    """Initialize Object Storage by ensuring the 'global' bucket exists."""
    result = await service.initialize_object_storage(
        body.endpoint, body.access_key, body.secret_key, body.region,
    )
    return ObjectStorageInitResponse(**result)


@router.post("/prometheus/test", response_model=PrometheusTestResponse)
async def test_prometheus(body: PrometheusTestRequest) -> PrometheusTestResponse:
    """Test connectivity to Prometheus Push Gateway."""
    result = await service.test_prometheus(body.host, body.port)
    return PrometheusTestResponse(**result)


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
