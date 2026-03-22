"""Alert API endpoints for lineage change notifications."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert import service
from app.alert.schemas import (
    AlertResponse,
    AlertSummary,
    AlertUpdateStatus,
    PaginatedAlerts,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Alert summary (for bell badge)
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(session: AsyncSession = Depends(get_session)):
    """Get open alert counts by severity for the notification badge."""
    return await service.get_alert_summary(session)


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedAlerts)
async def list_alerts(
    status: str | None = Query(None, description="Filter: OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED"),
    severity: str | None = Query(None, description="Filter: INFO, WARNING, BREAKING"),
    dataset_id: int | None = Query(None, description="Filter by source or affected dataset"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List lineage alerts with optional filters."""
    return await service.list_alerts(session, status, severity, dataset_id, page, page_size)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, session: AsyncSession = Depends(get_session)):
    """Get a single alert by ID."""
    alert = await service.get_alert(session, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return await service._build_alert_response(session, alert)


@router.put("/{alert_id}/status", response_model=AlertResponse)
async def update_alert_status(
    alert_id: int,
    data: AlertUpdateStatus,
    session: AsyncSession = Depends(get_session),
):
    """Update alert status (acknowledge, resolve, dismiss)."""
    result = await service.update_alert_status(session, alert_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    await session.commit()
    return result


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    data: SubscriptionCreate, session: AsyncSession = Depends(get_session),
):
    """Create an alert subscription."""
    result = await service.create_subscription(session, data)
    await session.commit()
    return result


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    user_id: str | None = Query(None, description="Filter by user ID"),
    session: AsyncSession = Depends(get_session),
):
    """List alert subscriptions."""
    return await service.list_subscriptions(session, user_id)


@router.delete("/subscriptions/{sub_id}", status_code=204)
async def delete_subscription(sub_id: int, session: AsyncSession = Depends(get_session)):
    """Delete an alert subscription."""
    deleted = await service.delete_subscription(session, sub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await session.commit()
