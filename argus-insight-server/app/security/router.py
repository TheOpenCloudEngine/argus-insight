"""Security / certificate management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.security import service
from app.security.schemas import (
    CaCertDeleteResponse,
    CaCertStatusResponse,
    CaCertUploadResponse,
    CaCertViewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/ca/status", response_model=CaCertStatusResponse)
async def ca_cert_status(
    session: AsyncSession = Depends(get_session),
) -> CaCertStatusResponse:
    """Check if the CA certificate file exists."""
    result = await service.get_ca_cert_status(session)
    return CaCertStatusResponse(**result)


@router.post("/ca/upload", response_model=CaCertUploadResponse)
async def ca_cert_upload(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> CaCertUploadResponse:
    """Upload a CA certificate file."""
    logger.info("CA certificate upload requested: filename=%s", file.filename)
    content = await file.read()
    try:
        result = await service.upload_ca_cert(session, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return CaCertUploadResponse(**result)


@router.get("/ca/view", response_model=CaCertViewResponse)
async def ca_cert_view(
    session: AsyncSession = Depends(get_session),
) -> CaCertViewResponse:
    """View the CA certificate content and decoded information."""
    try:
        result = await service.view_ca_cert(session)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaCertViewResponse(**result)


@router.delete("/ca", response_model=CaCertDeleteResponse)
async def ca_cert_delete(
    session: AsyncSession = Depends(get_session),
) -> CaCertDeleteResponse:
    """Delete the CA certificate file."""
    logger.info("CA certificate deletion requested")
    try:
        result = await service.delete_ca_cert(session)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CaCertDeleteResponse(**result)
