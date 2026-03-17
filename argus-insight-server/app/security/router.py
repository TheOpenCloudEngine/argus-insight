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
    CaKeyDeleteResponse,
    CaKeyStatusResponse,
    CaKeyUploadResponse,
    CaKeyViewResponse,
    GenerateSelfSignedCaRequest,
    GenerateSelfSignedCaResponse,
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


# --------------------------------------------------------------------------- #
# CA Key endpoints
# --------------------------------------------------------------------------- #


@router.get("/ca-key/status", response_model=CaKeyStatusResponse)
async def ca_key_status(
    session: AsyncSession = Depends(get_session),
) -> CaKeyStatusResponse:
    """Check if the CA key file exists."""
    result = await service.get_ca_key_status(session)
    return CaKeyStatusResponse(**result)


@router.post("/ca-key/upload", response_model=CaKeyUploadResponse)
async def ca_key_upload(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> CaKeyUploadResponse:
    """Upload a CA key file."""
    logger.info("CA key upload requested: filename=%s", file.filename)
    content = await file.read()
    try:
        result = await service.upload_ca_key(session, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return CaKeyUploadResponse(**result)


@router.get("/ca-key/view", response_model=CaKeyViewResponse)
async def ca_key_view(
    session: AsyncSession = Depends(get_session),
) -> CaKeyViewResponse:
    """View the CA key content and decoded information."""
    try:
        result = await service.view_ca_key(session)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaKeyViewResponse(**result)


@router.delete("/ca-key", response_model=CaKeyDeleteResponse)
async def ca_key_delete(
    session: AsyncSession = Depends(get_session),
) -> CaKeyDeleteResponse:
    """Delete the CA key file."""
    logger.info("CA key deletion requested")
    try:
        result = await service.delete_ca_key(session)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CaKeyDeleteResponse(**result)


# --------------------------------------------------------------------------- #
# Self-Signed CA generation
# --------------------------------------------------------------------------- #


@router.post("/ca/generate", response_model=GenerateSelfSignedCaResponse)
async def ca_generate_self_signed(
    body: GenerateSelfSignedCaRequest,
    session: AsyncSession = Depends(get_session),
) -> GenerateSelfSignedCaResponse:
    """Generate a self-signed CA certificate and key."""
    logger.info(
        "Self-signed CA generation requested: CN=%s, days=%d, bits=%d",
        body.common_name, body.days, body.key_bits,
    )
    try:
        result = await service.generate_self_signed_ca(
            session,
            country=body.country,
            state=body.state,
            locality=body.locality,
            organization=body.organization,
            org_unit=body.org_unit,
            common_name=body.common_name,
            days=body.days,
            key_bits=body.key_bits,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return GenerateSelfSignedCaResponse(**result)
