"""Comment API endpoints.

Provides CRUD for the polymorphic comment system.
Comments are attached to any entity via entity_type + entity_id.
Pagination counts top-level comments only; replies are nested in response.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments import service
from app.comments.schemas import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    PaginatedComments,
)
from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("", response_model=PaginatedComments)
async def list_comments(
    entity_type: str = Query(..., description="Entity type (dataset, model, glossary, ...)"),
    entity_id: str = Query(..., description="Entity identifier"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """List comments for an entity with pagination (top-level only, replies nested)."""
    logger.info("GET /comments: entity=%s/%s, page=%d", entity_type, entity_id, page)
    return await service.list_comments(session, entity_type, entity_id, page, page_size)


@router.post("", response_model=CommentResponse)
async def create_comment(
    req: CommentCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new comment or reply."""
    logger.info("POST /comments: entity=%s/%s, author=%s, parent=%s",
                req.entity_type, req.entity_id, req.author_name, req.parent_id)
    try:
        return await service.create_comment(session, req)
    except ValueError as e:
        logger.warning("Comment creation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    req: CommentUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a comment's content or suggestion flag."""
    logger.info("PUT /comments/%d", comment_id)
    result = await service.update_comment(session, comment_id, req)
    if not result:
        logger.warning("Comment not found for update: %d", comment_id)
        raise HTTPException(status_code=404, detail="Comment not found")
    return result


@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete a comment."""
    logger.info("DELETE /comments/%d", comment_id)
    if not await service.delete_comment(session, comment_id):
        logger.warning("Comment not found for delete: %d", comment_id)
        raise HTTPException(status_code=404, detail="Comment not found")
    logger.info("Comment deleted: %d", comment_id)
    return {"status": "ok", "message": f"Comment {comment_id} deleted"}


@router.get("/count")
async def get_comment_count(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Get comment count for an entity (top-level only)."""
    count = await service.get_comment_count(session, entity_type, entity_id)
    return {"count": count}
