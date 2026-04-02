"""SQLAlchemy ORM models for the VOC (Voice of Customer) issue tracker."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class ArgusVocIssue(Base):
    """A VOC issue submitted by any platform user.

    Columns:
        id:                Auto-incremented primary key.
        title:             Short summary of the issue.
        description:       Detailed description (HTML from rich-text editor).
        category:          resource_request | service_issue | feature_request | account | general.
        priority:          critical | high | medium | low.
        status:            open | in_progress | resolved | rejected | closed.
        author_user_id:    User who created this issue.
        author_username:   Denormalized for display after user deletion.
        assignee_user_id:  Admin assigned to handle this issue (nullable).
        assignee_username: Denormalized for display.
        workspace_id:      Optional workspace context.
        workspace_name:    Preserved even if workspace is deleted.
        service_id:        Optional workspace service context.
        service_name:      Preserved even if service is deleted.
        resource_detail:   JSON for resource-request specifics.
        resolved_at:       When status moved to resolved.
        closed_at:         When status moved to closed.
        created_at:        Creation timestamp.
        updated_at:        Last modification timestamp.
    """

    __tablename__ = "argus_voc_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(30), nullable=False, default="general")
    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="open")

    author_user_id = Column(Integer, nullable=False)
    author_username = Column(String(100))

    assignee_user_id = Column(Integer)
    assignee_username = Column(String(100))

    workspace_id = Column(Integer)
    workspace_name = Column(String(100))
    service_id = Column(Integer)
    service_name = Column(String(100))

    resource_detail = Column(JSONB)

    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusVocComment(Base):
    """A comment on a VOC issue (user or system-generated).

    Columns:
        id:                Auto-incremented primary key.
        issue_id:          Parent VOC issue.
        parent_id:         Parent comment for threading (nullable = top-level).
        author_user_id:    Comment author.
        author_username:   Denormalized for display.
        body:              Comment body (HTML from rich-text editor).
        body_plain:        Plain text version for search.
        is_system:         True for auto-generated status-change comments.
        is_deleted:        Soft-delete flag.
        created_at:        Creation timestamp.
        updated_at:        Last modification timestamp.
    """

    __tablename__ = "argus_voc_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, nullable=False, index=True)
    parent_id = Column(Integer)
    author_user_id = Column(Integer, nullable=False)
    author_username = Column(String(100))
    body = Column(Text, nullable=False)
    body_plain = Column(Text)
    is_system = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
