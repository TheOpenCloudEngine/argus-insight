"""AI generation ORM models.

Tracks every AI-generated metadata suggestion for audit, revert, and cost tracking.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AIGenerationLog(Base):
    """Log of AI-generated metadata suggestions.

    Records every generation for audit trail, preview/apply workflow,
    and token usage tracking.
    """

    __tablename__ = "catalog_ai_generation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False)       # dataset, column, tag, pii
    entity_id = Column(Integer, nullable=False)             # dataset_id or schema_field_id
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"),
                        nullable=False)
    field_name = Column(String(500))                        # column name (for column-level)
    generation_type = Column(String(30), nullable=False)    # description, tag_suggestion, pii_detection
    generated_text = Column(Text, nullable=False)
    applied = Column(Boolean, default=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
