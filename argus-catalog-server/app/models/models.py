"""SQLAlchemy ORM models for ML Model Registry.

Modeled after Unity Catalog OSS's RegisteredModel / ModelVersion pattern.
MLflow uses the UC-compatible API (/api/2.1/unity-catalog/) to register models,
which internally maps to these tables.

Tables:
  - catalog_registered_models: ML model metadata with version counter
  - catalog_model_versions: Versioned model artifacts with status lifecycle

Status lifecycle:
  PENDING_REGISTRATION → READY (success) or FAILED_REGISTRATION (failure)

Naming convention:
  MLflow requires 3-part names: {catalog}.{schema}.{model_name}
  Example: "argus.ml.iris_classifier"
  This full 3-part name is stored in the `name` column.
"""

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func,
)

from app.core.database import Base


class RegisteredModel(Base):
    """Registered ML model.

    Each model has a unique 3-part name (catalog.schema.model_name) that serves
    as the primary lookup key for MLflow integration. The `max_version_number`
    field tracks the highest version ever created and is atomically incremented
    when a new version is registered.

    Soft delete: setting status='deleted' hides the model from listings
    while preserving referential integrity.
    """

    __tablename__ = "catalog_registered_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 3-part name: catalog.schema.model (e.g. "argus.ml.iris_classifier")
    name = Column(String(255), nullable=False, unique=True)
    # URN: {name}.{ENV}.model (e.g. "argus.ml.iris_classifier.PROD.model")
    urn = Column(String(500), nullable=False, unique=True)
    # Optional link to a data platform (nullable — ML models may not belong to a platform)
    platform_id = Column(Integer, ForeignKey("catalog_platforms.id", ondelete="SET NULL"),
                         nullable=True)
    description = Column(Text)
    owner = Column(String(200))
    # "local" (file://) or "s3" (s3://)
    storage_type = Column(String(20), nullable=False, default="local")
    # Base artifact storage path (file:///var/lib/... or s3://bucket/prefix)
    storage_location = Column(String(1000))
    # S3 bucket name (when storage_type="s3")
    bucket_name = Column(String(255))
    # Tracks the highest version number created (auto-incremented per version)
    max_version_number = Column(Integer, nullable=False, default=0)
    # "active" or "deleted" (soft delete)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(200))
    updated_by = Column(String(200))


class ModelVersion(Base):
    """Model version with status lifecycle and artifact tracking.

    Each version is identified by (model_id, version) and goes through:
      PENDING_REGISTRATION → READY or FAILED_REGISTRATION

    Audit fields added for operational visibility:
      - status_message: Human-readable reason for failure
      - artifact_count: Number of files at finalize time (0 = suspicious)
      - artifact_size: Total bytes at finalize time (0 = suspicious)
      - finished_at: When finalize was called (NULL = never finalized)

    These fields allow operators to determine whether a version completed
    successfully just by looking at the database:
      READY + artifact_count>0 + finished_at≠NULL → success
      FAILED + status_message="..." → known failure
      PENDING + finished_at=NULL + old created_at → stuck/abandoned
    """

    __tablename__ = "catalog_model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_registered_models.id", ondelete="CASCADE"),
                      nullable=False)
    # Auto-incremented per model (1, 2, 3, ...)
    version = Column(Integer, nullable=False)
    # MLflow artifact source URI (e.g. "models:/m-abc123")
    source = Column(String(1000))
    # MLflow run ID that produced this model version
    run_id = Column(String(255))
    # Optional link to the MLflow run UI
    run_link = Column(String(1000))
    description = Column(Text)
    # Status lifecycle: PENDING_REGISTRATION → READY | FAILED_REGISTRATION
    status = Column(String(30), nullable=False, default="PENDING_REGISTRATION")
    # Human-readable failure reason (e.g. "Model deleted during registration")
    status_message = Column(Text)
    # Version-specific artifact path (file:///.../{name}/versions/{ver}/)
    storage_location = Column(String(1000))
    # Number of artifact files counted at finalize time
    artifact_count = Column(Integer, default=0)
    # Total artifact size in bytes counted at finalize time
    artifact_size = Column(Integer, default=0)
    # Timestamp when finalize was called (NULL = never finalized)
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(200))
    updated_by = Column(String(200))
    # Stage lifecycle: NONE → STAGING → PRODUCTION → ARCHIVED
    stage = Column(String(20), default="NONE")
    stage_changed_at = Column(DateTime(timezone=True))
    stage_changed_by = Column(String(200))


class ModelDatasetLineage(Base):
    """Link between a model and the dataset used for training/evaluation."""

    __tablename__ = "catalog_model_dataset_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_registered_models.id", ondelete="CASCADE"), nullable=False)
    model_version = Column(Integer)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(30), nullable=False, default="TRAINING_DATA")  # TRAINING_DATA, EVALUATION_DATA, FEATURE_SOURCE
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelMetric(Base):
    """Per-version performance metric for a model."""

    __tablename__ = "catalog_model_metrics"
    __table_args__ = (UniqueConstraint("model_id", "version", "metric_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_registered_models.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    metric_key = Column(String(100), nullable=False)
    metric_value = Column(Numeric(15, 6), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelCard(Base):
    """Structured model card with governance fields."""

    __tablename__ = "catalog_model_card"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("catalog_registered_models.id", ondelete="CASCADE"), nullable=False, unique=True)
    purpose = Column(Text)
    performance = Column(Text)
    limitations = Column(Text)
    training_data = Column(Text)
    framework = Column(String(200))
    license = Column(String(200))
    contact = Column(String(200))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CatalogModel(Base):
    """Parsed model metadata extracted from MLflow artifact files at finalize time.

    When a model version transitions to READY, the server reads MLmodel (YAML),
    requirements.txt, conda.yaml, and python_env.yaml from the artifact directory
    and stores their contents and key metadata fields in this table.

    Columns from MLmodel YAML:
      predict_fn, python_version, serialization_format, sklearn_version,
      mlflow_version, mlflow_model_id, model_size_bytes, utc_time_created, time_created
    Columns from text files:
      requirements, conda, python_env
    """

    __tablename__ = "catalog_models"
    __table_args__ = (UniqueConstraint("model_name", "version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version_id = Column(
        Integer,
        ForeignKey("catalog_model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False)

    # --- Fields parsed from MLmodel YAML ---
    predict_fn = Column(String(100))
    python_version = Column(String(20))
    serialization_format = Column(String(50))
    sklearn_version = Column(String(20))
    mlflow_version = Column(String(20))
    mlflow_model_id = Column(String(100))
    model_size_bytes = Column(BigInteger)
    utc_time_created = Column(String(50))
    # utc_time_created converted to server local timezone
    time_created = Column(DateTime(timezone=True))

    # --- Raw file contents ---
    requirements = Column(Text)
    conda = Column(Text)
    python_env = Column(Text)

    # --- OCI manifest ---
    manifest = Column(Text)
    config = Column(Text)
    content_digest = Column(String(100))

    # --- Source info ---
    source_type = Column(String(50))  # mlflow, huggingface, local, oras

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelDownloadLog(Base):
    """Download log for model usage tracking.

    Records every time a model version is loaded, pulled, or downloaded.
    Used for daily/weekly/monthly usage statistics.
    """

    __tablename__ = "catalog_model_download_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(255), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    # 'load' (MLflow), 'pull' (SDK), 'download' (single file)
    download_type = Column(String(20), nullable=False)
    client_ip = Column(String(45))
    user_agent = Column(String(500))
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
