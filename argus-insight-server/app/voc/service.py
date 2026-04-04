"""Business logic for the VOC issue tracker."""

import logging
from datetime import datetime, timezone

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.voc.models import ArgusVocComment, ArgusVocIssue
from app.voc.schemas import (
    PaginatedVocIssueResponse,
    VocCommentResponse,
    VocDashboardResponse,
    VocIssueCreateRequest,
    VocIssueResponse,
    VocIssueUpdateRequest,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _comment_count(session: AsyncSession, issue_id: int) -> int:
    result = await session.execute(
        select(func.count(ArgusVocComment.id)).where(
            ArgusVocComment.issue_id == issue_id,
            ArgusVocComment.is_deleted.is_(False),
        )
    )
    return result.scalar() or 0


def _issue_to_response(issue: ArgusVocIssue, comment_count: int = 0) -> VocIssueResponse:
    return VocIssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        category=issue.category,
        priority=issue.priority,
        status=issue.status,
        author_user_id=issue.author_user_id,
        author_username=issue.author_username,
        assignee_user_id=issue.assignee_user_id,
        assignee_username=issue.assignee_username,
        workspace_id=issue.workspace_id,
        workspace_name=issue.workspace_name,
        service_id=issue.service_id,
        service_name=issue.service_name,
        resource_detail=issue.resource_detail,
        comment_count=comment_count,
        resolved_at=issue.resolved_at,
        closed_at=issue.closed_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _comment_to_response(c: ArgusVocComment) -> VocCommentResponse:
    return VocCommentResponse(
        id=c.id,
        issue_id=c.issue_id,
        parent_id=c.parent_id,
        author_user_id=c.author_user_id,
        author_username=c.author_username,
        body=c.body,
        body_plain=c.body_plain,
        is_system=c.is_system,
        is_deleted=c.is_deleted,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def _create_system_comment(
    session: AsyncSession,
    issue_id: int,
    body: str,
    actor_user_id: int,
    actor_username: str | None,
) -> None:
    """Insert an auto-generated system comment."""
    comment = ArgusVocComment(
        issue_id=issue_id,
        author_user_id=actor_user_id,
        author_username=actor_username or "System",
        body=body,
        body_plain=body,
        is_system=True,
    )
    session.add(comment)


# ---------------------------------------------------------------------------
# Issue CRUD
# ---------------------------------------------------------------------------

async def create_issue(
    session: AsyncSession,
    req: VocIssueCreateRequest,
    author_user_id: int,
    author_username: str | None,
) -> VocIssueResponse:
    issue = ArgusVocIssue(
        title=req.title,
        description=req.description,
        category=req.category.value,
        priority=req.priority.value,
        status="open",
        author_user_id=author_user_id,
        author_username=author_username,
        workspace_id=req.workspace_id,
        workspace_name=req.workspace_name,
        service_id=req.service_id,
        service_name=req.service_name,
        resource_detail=req.resource_detail,
    )
    session.add(issue)
    await session.commit()
    await session.refresh(issue)
    logger.info("VOC issue created: id=%d title=%s author=%s", issue.id, issue.title, author_username)
    return _issue_to_response(issue)


async def get_issue(session: AsyncSession, issue_id: int) -> VocIssueResponse | None:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None
    count = await _comment_count(session, issue.id)
    return _issue_to_response(issue, count)


async def update_issue(
    session: AsyncSession,
    issue_id: int,
    req: VocIssueUpdateRequest,
    actor_user_id: int,
) -> VocIssueResponse | None:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None
    if issue.author_user_id != actor_user_id:
        raise PermissionError("Only the author can edit this issue")
    if issue.status != "open":
        raise ValueError("Can only edit issues in 'open' status")

    for field in ("title", "description", "category", "priority",
                   "workspace_id", "workspace_name", "service_id",
                   "service_name", "resource_detail"):
        value = getattr(req, field, None)
        if value is not None:
            if hasattr(value, "value"):
                value = value.value
            setattr(issue, field, value)

    await session.commit()
    await session.refresh(issue)
    count = await _comment_count(session, issue.id)
    return _issue_to_response(issue, count)


async def delete_issue(
    session: AsyncSession, issue_id: int, actor_user_id: int, is_admin: bool,
) -> bool:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return False
    if issue.author_user_id != actor_user_id and not is_admin:
        raise PermissionError("Only the author or an admin can delete this issue")
    await session.delete(issue)
    await session.commit()
    logger.info("VOC issue deleted: id=%d", issue_id)
    return True


async def list_issues(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    workspace_id: int | None = None,
    assignee_id: int | None = None,
    author_id: int | None = None,
    search: str | None = None,
) -> PaginatedVocIssueResponse:
    query = select(ArgusVocIssue)

    if status:
        statuses = [s.strip() for s in status.split(",")]
        query = query.where(ArgusVocIssue.status.in_(statuses))
    if category:
        categories = [c.strip() for c in category.split(",")]
        query = query.where(ArgusVocIssue.category.in_(categories))
    if priority:
        priorities = [p.strip() for p in priority.split(",")]
        query = query.where(ArgusVocIssue.priority.in_(priorities))
    if workspace_id is not None:
        query = query.where(ArgusVocIssue.workspace_id == workspace_id)
    if assignee_id is not None:
        query = query.where(ArgusVocIssue.assignee_user_id == assignee_id)
    if author_id is not None:
        query = query.where(ArgusVocIssue.author_user_id == author_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            ArgusVocIssue.title.ilike(pattern) | ArgusVocIssue.description.ilike(pattern)
        )

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    # Fetch page
    query = query.order_by(ArgusVocIssue.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    issues = result.scalars().all()

    # Batch comment counts
    items = []
    for issue in issues:
        count = await _comment_count(session, issue.id)
        items.append(_issue_to_response(issue, count))

    return PaginatedVocIssueResponse(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Status / Assignee / Priority changes
# ---------------------------------------------------------------------------

async def change_status(
    session: AsyncSession,
    issue_id: int,
    new_status: str,
    actor_user_id: int,
    actor_username: str | None,
) -> VocIssueResponse | None:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None

    old_status = issue.status
    issue.status = new_status

    now = datetime.now(timezone.utc)
    if new_status == "resolved":
        issue.resolved_at = now
    elif new_status == "closed":
        issue.closed_at = now

    await _create_system_comment(
        session, issue.id,
        f"Status changed: {old_status} → {new_status}",
        actor_user_id, actor_username,
    )
    await session.commit()
    await session.refresh(issue)
    count = await _comment_count(session, issue.id)
    logger.info("VOC #%d status: %s → %s by %s", issue_id, old_status, new_status, actor_username)
    return _issue_to_response(issue, count)


async def change_assignee(
    session: AsyncSession,
    issue_id: int,
    assignee_user_id: int | None,
    assignee_username: str | None,
    actor_user_id: int,
    actor_username: str | None,
) -> VocIssueResponse | None:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None

    issue.assignee_user_id = assignee_user_id
    issue.assignee_username = assignee_username

    body = f"Assignee set: {assignee_username}" if assignee_username else "Assignee removed"
    await _create_system_comment(session, issue.id, body, actor_user_id, actor_username)
    await session.commit()
    await session.refresh(issue)
    count = await _comment_count(session, issue.id)
    logger.info("VOC #%d assignee → %s by %s", issue_id, assignee_username, actor_username)
    return _issue_to_response(issue, count)


async def change_priority(
    session: AsyncSession,
    issue_id: int,
    new_priority: str,
    actor_user_id: int,
    actor_username: str | None,
) -> VocIssueResponse | None:
    result = await session.execute(
        select(ArgusVocIssue).where(ArgusVocIssue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None

    old_priority = issue.priority
    issue.priority = new_priority

    await _create_system_comment(
        session, issue.id,
        f"Priority changed: {old_priority} → {new_priority}",
        actor_user_id, actor_username,
    )
    await session.commit()
    await session.refresh(issue)
    count = await _comment_count(session, issue.id)
    return _issue_to_response(issue, count)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

async def list_comments(
    session: AsyncSession, issue_id: int,
) -> list[VocCommentResponse]:
    result = await session.execute(
        select(ArgusVocComment)
        .where(ArgusVocComment.issue_id == issue_id)
        .order_by(ArgusVocComment.created_at.asc())
    )
    return [_comment_to_response(c) for c in result.scalars().all()]


async def create_comment(
    session: AsyncSession,
    issue_id: int,
    body: str,
    body_plain: str | None,
    parent_id: int | None,
    author_user_id: int,
    author_username: str | None,
) -> VocCommentResponse:
    comment = ArgusVocComment(
        issue_id=issue_id,
        parent_id=parent_id,
        author_user_id=author_user_id,
        author_username=author_username,
        body=body,
        body_plain=body_plain,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return _comment_to_response(comment)


async def delete_comment(
    session: AsyncSession,
    comment_id: int,
    actor_user_id: int,
    is_admin: bool,
) -> bool:
    result = await session.execute(
        select(ArgusVocComment).where(ArgusVocComment.id == comment_id)
    )
    comment = result.scalars().first()
    if not comment:
        return False
    if comment.author_user_id != actor_user_id and not is_admin:
        raise PermissionError("Only the author or an admin can delete this comment")
    comment.is_deleted = True
    comment.body = "<p><em>This comment has been deleted.</em></p>"
    comment.body_plain = "This comment has been deleted."
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

async def get_dashboard(session: AsyncSession) -> VocDashboardResponse:
    # Total
    total = (await session.execute(
        select(func.count(ArgusVocIssue.id))
    )).scalar() or 0

    # By status
    rows = (await session.execute(
        select(ArgusVocIssue.status, func.count(ArgusVocIssue.id))
        .group_by(ArgusVocIssue.status)
    )).all()
    by_status = {r[0]: r[1] for r in rows}

    # By category
    rows = (await session.execute(
        select(ArgusVocIssue.category, func.count(ArgusVocIssue.id))
        .group_by(ArgusVocIssue.category)
    )).all()
    by_category = {r[0]: r[1] for r in rows}

    # By priority
    rows = (await session.execute(
        select(ArgusVocIssue.priority, func.count(ArgusVocIssue.id))
        .group_by(ArgusVocIssue.priority)
    )).all()
    by_priority = {r[0]: r[1] for r in rows}

    # Average resolution time (hours) for resolved/closed issues
    avg_hours = (await session.execute(
        select(
            func.avg(
                extract("epoch", ArgusVocIssue.resolved_at - ArgusVocIssue.created_at) / 3600
            )
        ).where(ArgusVocIssue.resolved_at.isnot(None))
    )).scalar()

    return VocDashboardResponse(
        total=total,
        by_status=by_status,
        by_category=by_category,
        by_priority=by_priority,
        avg_resolution_hours=round(avg_hours, 1) if avg_hours else None,
    )
