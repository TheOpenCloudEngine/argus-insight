"""OCI Model Hub API endpoints.

HuggingFace-style model registry with README, tags, lineage, lifecycle.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.oci_hub import service
from app.oci_hub.schemas import (
    HuggingFaceImportRequest,
    ImportResponse,
    LineageCreate,
    LineageResponse,
    OciModelCreate,
    OciModelDetail,
    OciModelUpdate,
    OciModelVersionResponse,
    PaginatedOciModels,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oci-models", tags=["oci-model-hub"])


# ---------------------------------------------------------------------------
# Server Info (for import guide code examples)
# ---------------------------------------------------------------------------

@router.get("/server-info")
async def get_server_info():
    """Return server host and port for code examples in the import guide."""
    from app.core.config import settings
    import socket
    # Get actual hostname/IP — 0.0.0.0 is not useful for clients
    host = settings.host
    if host == "0.0.0.0":
        try:
            host = socket.gethostbyname(socket.gethostname())
        except Exception:
            host = "localhost"
    return {"host": host, "port": settings.port}


@router.get("/stats")
async def get_hub_stats(session: AsyncSession = Depends(get_session)):
    """Get OCI Model Hub dashboard statistics."""
    logger.info("GET /oci-models/stats")
    return await service.get_hub_stats(session)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedOciModels)
async def list_models(
    search: str | None = Query(None),
    task: str | None = Query(None),
    framework: str | None = Query(None),
    language: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """List OCI models with optional filters."""
    logger.info("GET /oci-models: search=%s, task=%s, framework=%s, page=%d", search, task, framework, page)
    return await service.list_models(session, search=search, task=task, framework=framework,
                                     language=language, status=status, page=page, page_size=page_size)


@router.post("", response_model=OciModelDetail)
async def create_model(
    req: OciModelCreate, session: AsyncSession = Depends(get_session),
):
    """Register a new OCI model."""
    logger.info("POST /oci-models: name=%s", req.name)
    try:
        return await service.create_model(session, req)
    except ValueError as e:
        logger.warning("OCI model creation conflict: %s", e)
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{name}", response_model=OciModelDetail)
async def get_model(
    name: str, session: AsyncSession = Depends(get_session),
):
    """Get full model detail with README, tags, lineage."""
    logger.info("GET /oci-models/%s", name)
    detail = await service.get_model_detail(session, name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return detail


@router.patch("/{name}", response_model=OciModelDetail)
async def update_model(
    name: str, req: OciModelUpdate, session: AsyncSession = Depends(get_session),
):
    """Update model metadata."""
    logger.info("PATCH /oci-models/%s", name)
    result = await service.update_model(session, name, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return result


@router.delete("/{name}")
async def delete_model(
    name: str, session: AsyncSession = Depends(get_session),
):
    """Delete a model and all associated data."""
    logger.info("DELETE /oci-models/%s", name)
    if not await service.delete_model(session, name):
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

class ReadmeBody(BaseModel):
    readme: str

@router.put("/{name}/readme")
async def update_readme(
    name: str, body: ReadmeBody, session: AsyncSession = Depends(get_session),
):
    """Update model README (Markdown)."""
    logger.info("PUT /oci-models/%s/readme", name)
    if not await service.update_readme(session, name, body.readme):
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@router.post("/{name}/tags/{tag_id}")
async def add_tag(
    name: str, tag_id: int, session: AsyncSession = Depends(get_session),
):
    """Add a tag to a model."""
    logger.info("POST /oci-models/%s/tags/%d", name, tag_id)
    if not await service.add_tag(session, name, tag_id):
        raise HTTPException(status_code=404, detail="Model or tag not found")
    return {"status": "ok"}


@router.delete("/{name}/tags/{tag_id}")
async def remove_tag(
    name: str, tag_id: int, session: AsyncSession = Depends(get_session),
):
    """Remove a tag from a model."""
    logger.info("DELETE /oci-models/%s/tags/%d", name, tag_id)
    if not await service.remove_tag(session, name, tag_id):
        raise HTTPException(status_code=404, detail="Model or tag not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

@router.get("/{name}/lineage", response_model=list[LineageResponse])
async def get_lineage(
    name: str, session: AsyncSession = Depends(get_session),
):
    """Get lineage entries for a model."""
    detail = await service.get_model_detail(session, name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    # Re-query lineage properly typed
    from app.oci_hub.models import OciModel, OciModelLineage
    from sqlalchemy import select
    m = (await session.execute(select(OciModel).where(OciModel.name == name))).scalars().first()
    entries = (await session.execute(
        select(OciModelLineage).where(OciModelLineage.model_id == m.id)
    )).scalars().all()
    return [LineageResponse.model_validate(e) for e in entries]


@router.post("/{name}/lineage", response_model=LineageResponse)
async def add_lineage(
    name: str, req: LineageCreate, session: AsyncSession = Depends(get_session),
):
    """Add a lineage entry."""
    logger.info("POST /oci-models/%s/lineage: %s -> %s", name, req.relation_type, req.source_id)
    result = await service.add_lineage(
        session, name,
        source_type=req.source_type, source_id=req.source_id,
        source_name=req.source_name, relation_type=req.relation_type,
        description=req.description,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    return result


@router.delete("/{name}/lineage/{lineage_id}")
async def remove_lineage(
    name: str, lineage_id: int, session: AsyncSession = Depends(get_session),
):
    """Remove a lineage entry."""
    logger.info("DELETE /oci-models/%s/lineage/%d", name, lineage_id)
    if not await service.remove_lineage(session, lineage_id):
        raise HTTPException(status_code=404, detail="Lineage entry not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Versions + Finalize
# ---------------------------------------------------------------------------

@router.get("/{name}/versions", response_model=list[OciModelVersionResponse])
async def list_versions(
    name: str, session: AsyncSession = Depends(get_session),
):
    """List all versions for a model."""
    return await service.list_versions(session, name)


class FinalizeVersionRequest(BaseModel):
    readme: str | None = None

@router.post("/{name}/versions/{version}/finalize", response_model=OciModelVersionResponse)
async def finalize_version(
    name: str, version: int,
    body: FinalizeVersionRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Finalize a pushed version: scan S3 files, generate manifest, create version record, update model stats."""
    logger.info("POST /oci-models/%s/versions/%d/finalize", name, version)
    try:
        result = await service.finalize_push(session, name, version, readme=body.readme if body else None)
        if not result:
            raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Finalize error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/import/huggingface", response_model=ImportResponse)
async def import_huggingface(
    req: HuggingFaceImportRequest, session: AsyncSession = Depends(get_session),
):
    """Import a model from HuggingFace Hub."""
    logger.info("POST /oci-models/import/huggingface: %s", req.hf_model_id)
    try:
        return await service.import_from_huggingface(
            session, hf_model_id=req.hf_model_id, name=req.name,
            description=req.description, owner=req.owner,
            task=req.task, framework=req.framework, language=req.language,
            revision=req.revision,
        )
    except Exception as e:
        logger.error("HF import failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
