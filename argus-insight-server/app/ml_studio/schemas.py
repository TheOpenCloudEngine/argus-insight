"""Pydantic schemas for ML Studio."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIMESERIES = "timeseries"


class AlgorithmChoice(str, Enum):
    AUTO = "auto"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    RANDOM_FOREST = "random_forest"
    LINEAR = "linear"


# ---------------------------------------------------------------------------
# Data preview
# ---------------------------------------------------------------------------

class DataPreviewRequest(BaseModel):
    workspace_id: int
    source_type: str = Field(..., description="minio | database")
    path: str = Field(..., description="S3 path or table name")
    bucket: str | None = None


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    missing: int = 0
    unique: int = 0
    sample_values: list[str] = []


class DataPreviewResponse(BaseModel):
    columns: list[ColumnInfo] = []
    row_count: int = 0
    sample_rows: list[dict] = []


# ---------------------------------------------------------------------------
# Training job
# ---------------------------------------------------------------------------

class TrainRequest(BaseModel):
    workspace_id: int
    name: str = Field(default="Untitled Job", max_length=255)
    task_type: TaskType
    target_column: str
    metric: str = "auto"
    algorithm: AlgorithmChoice = AlgorithmChoice.AUTO
    data_source: dict = Field(..., description="{type, path, bucket}")
    feature_columns: list[str] | None = None
    exclude_columns: list[str] | None = None
    time_limit_seconds: int = Field(default=300, ge=30, le=3600)
    test_split: float = Field(default=0.2, ge=0.05, le=0.5)


class LeaderboardEntry(BaseModel):
    rank: int
    model_name: str
    metrics: dict[str, float] = {}
    training_time_seconds: float = 0


class TrainJobResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    status: str
    task_type: str
    target_column: str
    metric: str
    algorithm: str
    progress: int = 0
    data_source: dict = {}
    config: dict | None = None
    results: dict | None = None
    error_message: str | None = None
    author_username: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TrainJobListResponse(BaseModel):
    jobs: list[TrainJobResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
