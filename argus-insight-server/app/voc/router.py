"""VOC issue tracker API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminUser, CurrentUser
from app.core.database import get_session
from app.voc import service
from app.voc.schemas import (
    PaginatedVocIssueResponse,
    VocAssigneeChangeRequest,
    VocCommentCreateRequest,
    VocCommentResponse,
    VocDashboardResponse,
    VocIssueCreateRequest,
    VocIssueResponse,
    VocIssueUpdateRequest,
    VocPriorityChangeRequest,
    VocStatusChangeRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voc", tags=["voc"])


# ---------------------------------------------------------------------------
# Issue endpoints (all authenticated users)
# ---------------------------------------------------------------------------

@router.post("/issues", response_model=VocIssueResponse)
async def create_issue(
    req: VocIssueCreateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Create a new VOC issue."""
    return await service.create_issue(
        session, req,
        author_user_id=int(user.sub),
        author_username=user.username,
    )


@router.get("/issues", response_model=PaginatedVocIssueResponse)
async def list_issues(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    workspace_id: int | None = Query(None),
    assignee_id: int | None = Query(None),
    author_id: int | None = Query(None),
    mine: bool = Query(False),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List VOC issues with filters.

    Non-admin users can only see their own issues.
    """
    if user.is_admin:
        effective_author = int(user.sub) if mine else author_id
    else:
        effective_author = int(user.sub)
    return await service.list_issues(
        session,
        page=page,
        page_size=page_size,
        status=status,
        category=category,
        priority=priority,
        workspace_id=workspace_id,
        assignee_id=assignee_id,
        author_id=effective_author,
        search=search,
    )


@router.get("/issues/{issue_id}", response_model=VocIssueResponse)
async def get_issue(
    issue_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get a VOC issue by ID. Non-admin users can only view their own issues."""
    issue = await service.get_issue(session, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not user.is_admin and issue.author_user_id != int(user.sub):
        raise HTTPException(status_code=403, detail="Access denied")
    return issue


@router.put("/issues/{issue_id}", response_model=VocIssueResponse)
async def update_issue(
    issue_id: int,
    req: VocIssueUpdateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Update a VOC issue (author only, open status only)."""
    try:
        result = await service.update_issue(session, issue_id, req, int(user.sub))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result


@router.delete("/issues/{issue_id}")
async def delete_issue(
    issue_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a VOC issue (author or admin)."""
    try:
        ok = await service.delete_issue(session, issue_id, int(user.sub), user.is_admin)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin-only management endpoints
# ---------------------------------------------------------------------------

@router.patch("/issues/{issue_id}/status", response_model=VocIssueResponse)
async def change_status(
    issue_id: int,
    req: VocStatusChangeRequest,
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Change VOC issue status (admin only)."""
    result = await service.change_status(
        session, issue_id, req.status.value, int(user.sub), user.username,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result


@router.patch("/issues/{issue_id}/assignee", response_model=VocIssueResponse)
async def change_assignee(
    issue_id: int,
    req: VocAssigneeChangeRequest,
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Assign or unassign a user to a VOC issue (admin only)."""
    result = await service.change_assignee(
        session, issue_id,
        req.assignee_user_id, req.assignee_username,
        int(user.sub), user.username,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result


@router.patch("/issues/{issue_id}/priority", response_model=VocIssueResponse)
async def change_priority(
    issue_id: int,
    req: VocPriorityChangeRequest,
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Change VOC issue priority (admin only)."""
    result = await service.change_priority(
        session, issue_id, req.priority.value, int(user.sub), user.username,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Issue not found")
    return result


# ---------------------------------------------------------------------------
# Comment endpoints
# ---------------------------------------------------------------------------

@router.get("/issues/{issue_id}/comments", response_model=list[VocCommentResponse])
async def list_comments(
    issue_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Get all comments for a VOC issue."""
    return await service.list_comments(session, issue_id)


@router.post("/issues/{issue_id}/comments", response_model=VocCommentResponse)
async def create_comment(
    issue_id: int,
    req: VocCommentCreateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Add a comment to a VOC issue."""
    # Verify issue exists
    issue = await service.get_issue(session, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return await service.create_comment(
        session, issue_id,
        body=req.body,
        body_plain=req.body_plain,
        parent_id=req.parent_id,
        author_user_id=int(user.sub),
        author_username=user.username,
    )


@router.delete("/issues/{issue_id}/comments/{comment_id}")
async def delete_comment(
    issue_id: int,
    comment_id: int,
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Delete a comment (soft-delete, admin only)."""
    ok = await service.delete_comment(session, comment_id, int(user.sub), True)
    if not ok:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Dashboard (admin only)
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=VocDashboardResponse)
async def get_dashboard(
    user: AdminUser,
    session: AsyncSession = Depends(get_session),
):
    """Get VOC statistics dashboard."""
    return await service.get_dashboard(session)
