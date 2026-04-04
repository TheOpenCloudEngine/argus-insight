"""SQLAlchemy ORM models for ML Studio."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class ArgusMLPipeline(Base):
    """A saved ML pipeline (DAG) from the Modeler."""

    __tablename__ = "argus_ml_pipelines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    pipeline_json = Column(JSONB, nullable=False)
    author_user_id = Column(Integer, nullable=False)
    author_username = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArgusMLJob(Base):
    """An ML training job submitted via ML Studio."""

    __tablename__ = "argus_ml_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    source = Column(String(20), nullable=False, default="wizard")  # wizard | modeler
    status = Column(String(20), nullable=False, default="pending")
    task_type = Column(String(30), nullable=False)
    target_column = Column(String(255), nullable=False, default="")
    metric = Column(String(50), nullable=False, default="auto")
    algorithm = Column(String(50), nullable=False, default="auto")
    data_source = Column(JSONB, nullable=False)
    config = Column(JSONB)
    results = Column(JSONB)
    error_message = Column(Text)
    progress = Column(Integer, nullable=False, default=0)
    pipeline_id = Column(Integer, nullable=True)  # linked pipeline (modeler only)
    generated_code = Column(Text, nullable=True)   # Python code (modeler only)
    author_user_id = Column(Integer, nullable=False)
    author_username = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
