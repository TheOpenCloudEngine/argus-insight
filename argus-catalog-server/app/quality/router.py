"""Data quality API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.quality import service
from app.quality.schemas import (
    ProfileResponse, QualityRuleCreate, QualityRuleResponse,
    QualityRuleUpdate, QualityResultResponse, QualityScoreResponse,
    RunCheckResponse,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality", tags=["quality"])


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------

@router.post("/datasets/{dataset_id}/profile", response_model=ProfileResponse)
async def profile_dataset(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Run data profiling on a dataset (direct SQL to source DB)."""
    try:
        result = await service.profile_dataset(session, dataset_id)
        await session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/datasets/{dataset_id}/profile", response_model=ProfileResponse)
async def get_profile(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Get the latest profile for a dataset."""
    result = await service.get_latest_profile(session, dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="No profile found. Run profiling first.")
    return result


# ---------------------------------------------------------------------------
# Quality Rules
# ---------------------------------------------------------------------------

@router.post("/rules", response_model=QualityRuleResponse, status_code=201)
async def create_rule(data: QualityRuleCreate, session: AsyncSession = Depends(get_session)):
    """Create a quality check rule."""
    result = await service.create_rule(session, data)
    await session.commit()
    return result


@router.get("/rules", response_model=list[QualityRuleResponse])
async def list_rules(dataset_id: int = Query(...), session: AsyncSession = Depends(get_session)):
    """List quality rules for a dataset."""
    return await service.list_rules(session, dataset_id)


@router.put("/rules/{rule_id}", response_model=QualityRuleResponse)
async def update_rule(rule_id: int, data: QualityRuleUpdate, session: AsyncSession = Depends(get_session)):
    """Update a quality rule."""
    result = await service.update_rule(session, rule_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.commit()
    return result


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a quality rule."""
    if not await service.delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Run Check
# ---------------------------------------------------------------------------

@router.post("/datasets/{dataset_id}/check", response_model=RunCheckResponse)
async def run_check(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Run all active quality rules for a dataset."""
    result = await service.run_quality_check(session, dataset_id)
    await session.commit()
    return result


# ---------------------------------------------------------------------------
# Results & Scores
# ---------------------------------------------------------------------------

@router.get("/datasets/{dataset_id}/results", response_model=list[QualityResultResponse])
async def get_results(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Get latest quality check results for a dataset."""
    return await service.get_latest_results(session, dataset_id)


@router.get("/datasets/{dataset_id}/score", response_model=QualityScoreResponse)
async def get_score(dataset_id: int, session: AsyncSession = Depends(get_session)):
    """Get the latest quality score for a dataset."""
    result = await service.get_latest_score(session, dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="No score found. Run quality check first.")
    return result


@router.get("/datasets/{dataset_id}/score/history", response_model=list[QualityScoreResponse])
async def get_score_history(
    dataset_id: int,
    limit: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get quality score history for a dataset."""
    return await service.get_score_history(session, dataset_id, limit)
