"""SQLAlchemy ORM models for ML Studio training jobs."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class ArgusMLJob(Base):
    """An ML training job submitted via ML Studio.

    Columns:
        id:              Auto-incremented primary key.
        workspace_id:    Workspace context.
        name:            User-given job name.
        status:          pending | running | completed | failed.
        task_type:       classification | regression | timeseries.
        target_column:   Target column name.
        metric:          Evaluation metric (f1, accuracy, rmse, etc.).
        algorithm:       auto | xgboost | lightgbm | random_forest | linear.
        data_source:     JSON: {type, path/table, bucket}.
        config:          JSON: {features, exclude, time_limit, test_split, ...}.
        results:         JSON: {leaderboard, best_model, feature_importance, metrics}.
        error_message:   Error details if failed.
        progress:        0-100 percentage.
        author_user_id:  User who started the job.
        author_username: Denormalized.
        created_at:      When job was created.
        updated_at:      Last update.
        completed_at:    When job finished.
    """

    __tablename__ = "argus_ml_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    task_type = Column(String(30), nullable=False)
    target_column = Column(String(255), nullable=False)
    metric = Column(String(50), nullable=False, default="auto")
    algorithm = Column(String(50), nullable=False, default="auto")
    data_source = Column(JSONB, nullable=False)
    config = Column(JSONB)
    results = Column(JSONB)
    error_message = Column(Text)
    progress = Column(Integer, nullable=False, default=0)
    author_user_id = Column(Integer, nullable=False)
    author_username = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
