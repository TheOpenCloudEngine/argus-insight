"""AI metadata generation API endpoints.

Provides endpoints for LLM-powered automatic generation of dataset/column
descriptions, tag suggestions, and PII detection.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import (
    AIStatsResponse,
    ApplyRejectResponse,
    BulkGenerateRequest,
    BulkGenerateResponse,
    GenerateAllResponse,
    GenerateColumnsResponse,
    GenerateDescriptionResponse,
    GenerateRequest,
    PIIDetectionResponse,
    SuggestionItem,
    TagSuggestionResponse,
)
from app.ai.service import (
    apply_suggestion,
    bulk_generate,
    detect_pii,
    generate_all_for_dataset,
    generate_column_descriptions,
    generate_dataset_description,
    get_ai_stats,
    get_suggestions,
    reject_suggestion,
    suggest_tags,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Dataset-level generation
# ---------------------------------------------------------------------------

@router.post("/datasets/{dataset_id}/describe", response_model=GenerateDescriptionResponse)
async def api_generate_description(
    dataset_id: int,
    body: GenerateRequest = GenerateRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Generate a table description using AI."""
    try:
        result = await generate_dataset_description(
            session, dataset_id,
            apply=body.apply, force=body.force, language=body.language,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/{dataset_id}/describe-columns", response_model=GenerateColumnsResponse)
async def api_generate_column_descriptions(
    dataset_id: int,
    body: GenerateRequest = GenerateRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Generate column descriptions using AI."""
    try:
        result = await generate_column_descriptions(
            session, dataset_id,
            apply=body.apply, force=body.force, language=body.language,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/{dataset_id}/suggest-tags", response_model=TagSuggestionResponse)
async def api_suggest_tags(
    dataset_id: int,
    body: GenerateRequest = GenerateRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Suggest tags for a dataset using AI."""
    try:
        result = await suggest_tags(
            session, dataset_id,
            apply=body.apply, language=body.language,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/{dataset_id}/detect-pii", response_model=PIIDetectionResponse)
async def api_detect_pii(
    dataset_id: int,
    body: GenerateRequest = GenerateRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Detect PII columns in a dataset using AI."""
    try:
        result = await detect_pii(
            session, dataset_id, apply=body.apply,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/{dataset_id}/generate-all", response_model=GenerateAllResponse)
async def api_generate_all(
    dataset_id: int,
    body: GenerateRequest = GenerateRequest(),
    session: AsyncSession = Depends(get_session),
):
    """Run all AI generation tasks for a dataset."""
    try:
        result = await generate_all_for_dataset(
            session, dataset_id,
            apply=body.apply, force=body.force, language=body.language,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Bulk generation
# ---------------------------------------------------------------------------

@router.post("/bulk-generate", response_model=BulkGenerateResponse)
async def api_bulk_generate(
    body: BulkGenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Bulk generate metadata for multiple datasets."""
    try:
        result = await bulk_generate(
            session,
            generation_types=body.generation_types,
            apply=body.apply,
            language=body.language,
            platform_id=body.platform_id,
            empty_only=body.empty_only,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Suggestion management
# ---------------------------------------------------------------------------

@router.get("/datasets/{dataset_id}/suggestions", response_model=list[SuggestionItem])
async def api_get_suggestions(
    dataset_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get unapplied AI suggestions for a dataset."""
    return await get_suggestions(session, dataset_id)


@router.post("/suggestions/{suggestion_id}/apply", response_model=ApplyRejectResponse)
async def api_apply_suggestion(
    suggestion_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Apply a specific AI suggestion."""
    try:
        return await apply_suggestion(session, suggestion_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/suggestions/{suggestion_id}/reject", response_model=ApplyRejectResponse)
async def api_reject_suggestion(
    suggestion_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reject and delete a specific AI suggestion."""
    try:
        return await reject_suggestion(session, suggestion_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=AIStatsResponse)
async def api_get_ai_stats(session: AsyncSession = Depends(get_session)):
    """Return AI generation statistics and coverage metrics."""
    return await get_ai_stats(session)
