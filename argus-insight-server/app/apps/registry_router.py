"""App registry (catalog) API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.apps.models import ArgusApp
from app.apps.schemas import AppCreateRequest, AppResponse, AppUpdateRequest
from app.core.auth import AdminUser
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/registry", tags=["apps-registry"])


@router.get("", response_model=list[AppResponse])
async def list_apps(session: AsyncSession = Depends(get_session)):
    """List all registered apps."""
    result = await session.execute(select(ArgusApp).order_by(ArgusApp.id))
    return [AppResponse.model_validate(app) for app in result.scalars().all()]


@router.post("", response_model=AppResponse, status_code=201)
async def create_app(
    req: AppCreateRequest,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Register a new app type. Admin only."""
    existing = await session.execute(
        select(ArgusApp).where(ArgusApp.app_type == req.app_type)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"App '{req.app_type}' already exists")

    app = ArgusApp(**req.model_dump())
    session.add(app)
    await session.commit()
    await session.refresh(app)
    logger.info("App registered: %s", req.app_type)
    return AppResponse.model_validate(app)


@router.put("/{app_type}", response_model=AppResponse)
async def update_app(
    app_type: str,
    req: AppUpdateRequest,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Update an app definition. Admin only."""
    result = await session.execute(
        select(ArgusApp).where(ArgusApp.app_type == app_type)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_type}' not found")

    for field, value in req.model_dump(exclude_none=True).items():
        setattr(app, field, value)

    await session.commit()
    await session.refresh(app)
    logger.info("App updated: %s", app_type)
    return AppResponse.model_validate(app)


@router.delete("/{app_type}", status_code=204)
async def delete_app(
    app_type: str,
    _admin: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete an app definition. Admin only."""
    result = await session.execute(
        select(ArgusApp).where(ArgusApp.app_type == app_type)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_type}' not found")

    await session.delete(app)
    await session.commit()
    logger.info("App deleted: %s", app_type)
