"""리니지 변경 알림 API 엔드포인트.

엔드포인트:
- GET    /alerts/summary              벨 배지용 미해결 알림 건수
- GET    /alerts                      알림 목록 (필터: status, severity, dataset_id)
- GET    /alerts/{id}                 알림 상세
- PUT    /alerts/{id}/status          알림 상태 변경
- POST   /alerts/rules                알림 규칙 생성
- GET    /alerts/rules                알림 규칙 목록
- GET    /alerts/rules/{id}           알림 규칙 상세
- PUT    /alerts/rules/{id}           알림 규칙 수정
- DELETE /alerts/rules/{id}           알림 규칙 삭제
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.alert import service
from app.alert.schemas import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSummary,
    AlertUpdateStatus,
    PaginatedAlerts,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# 알림 요약 (벨 배지용)
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(session: AsyncSession = Depends(get_session)):
    """미해결(OPEN) 알림의 심각도별 건수를 반환."""
    return await service.get_alert_summary(session)


# ---------------------------------------------------------------------------
# Alert Rule CRUD
# ---------------------------------------------------------------------------

@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_rule(
    data: AlertRuleCreate, session: AsyncSession = Depends(get_session),
):
    """알림 규칙을 생성한다."""
    result = await service.create_rule(session, data)
    await session.commit()
    return result


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_rules(session: AsyncSession = Depends(get_session)):
    """알림 규칙 목록을 조회한다."""
    return await service.list_rules(session)


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    """알림 규칙 상세를 조회한다."""
    rule = await service.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return await service._build_rule_response(session, rule)


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: int, data: AlertRuleUpdate, session: AsyncSession = Depends(get_session),
):
    """알림 규칙을 수정한다."""
    result = await service.update_rule(session, rule_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.commit()
    return result


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    """알림 규칙을 삭제한다."""
    deleted = await service.delete_rule(session, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedAlerts)
async def list_alerts(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    dataset_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """알림 목록을 조회한다."""
    return await service.list_alerts(session, status, severity, dataset_id, page, page_size)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, session: AsyncSession = Depends(get_session)):
    """알림 상세를 조회한다."""
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
    """알림 상태를 변경한다 (확인/해결/무시)."""
    result = await service.update_alert_status(session, alert_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    await session.commit()
    return result
