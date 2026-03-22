"""Comment ORM model.

Polymorphic comment system that can attach to any entity (dataset, model, glossary, etc.)
via entity_type + entity_id. Supports nested replies with root_id for efficient querying.

Hierarchy:
  - parent_id=NULL, root_id=NULL → top-level comment (pagination target)
  - parent_id=X, root_id=X      → direct reply to comment X
  - parent_id=Y, root_id=X      → reply to reply Y, under root comment X
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func,
)

from app.core.database import Base


class Comment(Base):
    __tablename__ = "catalog_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Polymorphic entity reference (no FK — works with any entity)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)

    # Hierarchy
    parent_id = Column(Integer, ForeignKey("catalog_comments.id", ondelete="CASCADE"))
    root_id = Column(Integer, ForeignKey("catalog_comments.id", ondelete="CASCADE"))
    depth = Column(Integer, nullable=False, default=0)

    # Content
    content = Column(Text, nullable=False)
    content_plain = Column(Text)
    # Comment category: general, suggestion, feature, bug
    category = Column(String(20), nullable=False, default="general")

    # Author
    author_name = Column(String(100), nullable=False)
    author_email = Column(String(255))
    author_avatar = Column(String(500))

    # Denormalized reply count (updated on reply create/delete)
    reply_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False)
