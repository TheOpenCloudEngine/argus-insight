"""Comment service — CRUD operations with nested reply support.

Pagination counts only top-level comments (parent_id IS NULL).
Replies are fetched in bulk via root_id and nested into the response tree.
reply_count is denormalized for performance (updated on create/delete).
"""

import logging
from collections import defaultdict

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.comments.models import Comment
from app.comments.schemas import CommentCreate, CommentResponse, CommentUpdate, PaginatedComments

logger = logging.getLogger(__name__)


def _to_response(comment: Comment) -> CommentResponse:
    """Convert ORM Comment to response schema (without replies — added later)."""
    return CommentResponse(
        id=comment.id,
        entity_type=comment.entity_type,
        entity_id=comment.entity_id,
        parent_id=comment.parent_id,
        root_id=comment.root_id,
        depth=comment.depth,
        content=comment.content,
        content_plain=comment.content_plain,
        category=comment.category,
        author_name=comment.author_name,
        author_email=comment.author_email,
        author_avatar=comment.author_avatar,
        reply_count=comment.reply_count,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_deleted=comment.is_deleted,
    )


def _build_reply_tree(
    root_comments: list[CommentResponse],
    all_replies: list[CommentResponse],
) -> list[CommentResponse]:
    """Nest replies into their parent comments to build a tree structure.

    Uses a dict lookup by id for O(n) assembly instead of recursive queries.
    """
    by_id: dict[int, CommentResponse] = {}
    for c in root_comments:
        by_id[c.id] = c

    # Sort replies by depth then created_at for correct ordering
    sorted_replies = sorted(all_replies, key=lambda r: (r.depth, r.created_at))

    for reply in sorted_replies:
        by_id[reply.id] = reply
        parent = by_id.get(reply.parent_id)
        if parent:
            parent.replies.append(reply)

    return root_comments


async def list_comments(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    page: int = 1,
    page_size: int = 10,
) -> PaginatedComments:
    """List comments with pagination on top-level comments only.

    Replies are fetched in bulk and nested into the response.
    Page size applies to top-level comments; replies don't count toward it.
    """
    # Count top-level comments (visible: not deleted, or deleted but has replies)
    count_q = (
        select(func.count())
        .where(
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.parent_id.is_(None),
            # Show if: not deleted, OR deleted but still has replies
            ((Comment.is_deleted == False) | (Comment.reply_count > 0)),
        )
    )
    total = (await session.execute(count_q)).scalar() or 0

    # Fetch top-level comments (paginated)
    # Include deleted comments that still have replies (shown as "deleted comment")
    offset = (page - 1) * page_size
    top_q = (
        select(Comment)
        .where(
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.parent_id.is_(None),
            ((Comment.is_deleted == False) | (Comment.reply_count > 0)),
        )
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    top_result = await session.execute(top_q)
    top_comments = [_to_response(c) for c in top_result.scalars().all()]

    if not top_comments:
        return PaginatedComments(items=[], total=total, page=page, page_size=page_size)

    # Fetch all replies (include deleted ones that have their own replies)
    root_ids = [c.id for c in top_comments]
    reply_q = (
        select(Comment)
        .where(
            Comment.root_id.in_(root_ids),
            ((Comment.is_deleted == False) | (Comment.reply_count > 0)),
        )
        .order_by(Comment.created_at.asc())
    )
    reply_result = await session.execute(reply_q)
    all_replies = [_to_response(r) for r in reply_result.scalars().all()]

    # Build tree
    items = _build_reply_tree(top_comments, all_replies)

    logger.info(
        "Listed comments: entity=%s/%s, page=%d, top=%d, replies=%d",
        entity_type, entity_id, page, len(top_comments), len(all_replies),
    )
    return PaginatedComments(items=items, total=total, page=page, page_size=page_size)


async def create_comment(
    session: AsyncSession,
    req: CommentCreate,
) -> CommentResponse:
    """Create a comment or reply.

    For replies: resolves root_id and depth from parent, increments parent's reply_count.
    """
    parent_id = req.parent_id
    root_id = None
    depth = 0

    if parent_id:
        # Resolve parent to get root_id and depth
        parent = await session.get(Comment, parent_id)
        if not parent:
            raise ValueError(f"Parent comment {parent_id} not found")
        if parent.is_deleted:
            raise ValueError(f"Cannot reply to deleted comment {parent_id}")

        root_id = parent.root_id or parent.id  # If parent is top-level, root_id = parent.id
        depth = parent.depth + 1

        # Increment parent's reply_count
        await session.execute(
            update(Comment)
            .where(Comment.id == parent_id)
            .values(reply_count=Comment.reply_count + 1)
        )

    comment = Comment(
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        parent_id=parent_id,
        root_id=root_id,
        depth=depth,
        content=req.content,
        content_plain=req.content_plain,
        category=req.category,
        author_name=req.author_name,
        author_email=req.author_email,
        author_avatar=req.author_avatar,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    logger.info(
        "Comment created: id=%d, entity=%s/%s, author=%s, parent=%s, category=%s",
        comment.id, req.entity_type, req.entity_id, req.author_name, parent_id, req.category,
    )
    return _to_response(comment)


async def update_comment(
    session: AsyncSession,
    comment_id: int,
    req: CommentUpdate,
) -> CommentResponse | None:
    """Update a comment's content or category."""
    comment = await session.get(Comment, comment_id)
    if not comment or comment.is_deleted:
        return None

    comment.content = req.content
    if req.content_plain is not None:
        comment.content_plain = req.content_plain
    if req.category is not None:
        comment.category = req.category

    await session.commit()
    await session.refresh(comment)
    logger.info("Comment updated: id=%d", comment_id)
    return _to_response(comment)


async def delete_comment(
    session: AsyncSession,
    comment_id: int,
) -> bool:
    """Soft-delete a comment. Decrements parent's reply_count if it's a reply."""
    comment = await session.get(Comment, comment_id)
    if not comment or comment.is_deleted:
        return False

    comment.is_deleted = True

    # Decrement parent's reply_count
    if comment.parent_id:
        await session.execute(
            update(Comment)
            .where(Comment.id == comment.parent_id)
            .values(reply_count=func.greatest(Comment.reply_count - 1, 0))
        )

    await session.commit()
    logger.info("Comment soft-deleted: id=%d, entity=%s/%s", comment_id, comment.entity_type, comment.entity_id)
    return True


async def get_comment_count(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
) -> int:
    """Get total comment count (top-level only, excluding deleted) for an entity."""
    result = await session.execute(
        select(func.count()).where(
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.parent_id.is_(None),
            Comment.is_deleted == False,
        )
    )
    return result.scalar() or 0
