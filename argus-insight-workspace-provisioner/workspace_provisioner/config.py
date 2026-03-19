"""Workspace provisioning configuration models.

Pydantic models for service-level settings that are passed from
argus-insight-ui's Settings page when creating a workspace.
Each model provides sensible defaults while allowing full override.

Usage:
    # From UI request (partial override)
    config = ProvisioningConfig(
        minio=MinioConfig(storage_size="100Gi"),
        airflow=AirflowConfig(image="apache/airflow:2.10.4-python3.11"),
    )

    # All defaults
    config = ProvisioningConfig()
"""

from pydantic import BaseModel, Field


class ResourceConfig(BaseModel):
    """CPU/Memory resource requests and limits for a K8s container."""

    cpu_request: str = "250m"
    cpu_limit: str = "2"
    memory_request: str = "512Mi"
    memory_limit: str = "2Gi"


class MinioConfig(BaseModel):
    """MinIO deployment settings."""

    image: str = Field(
        default="minio/minio:RELEASE.2025-02-28T09-55-16Z",
        description="MinIO server container image",
    )
    storage_size: str = Field(
        default="50Gi",
        description="PVC size for MinIO data volume",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory resource configuration",
    )


class AirflowConfig(BaseModel):
    """Airflow deployment settings."""

    image: str = Field(
        default="apache/airflow:2.10.4-python3.11",
        description="Airflow container image",
    )
    postgres_image: str = Field(
        default="postgres:16-alpine",
        description="PostgreSQL image for Airflow metadata DB",
    )
    git_sync_image: str = Field(
        default="alpine/git:latest",
        description="Git-sync sidecar image",
    )
    git_sync_interval: int = Field(
        default=60,
        description="Git-sync interval in seconds",
    )
    dags_storage_size: str = Field(
        default="10Gi",
        description="PVC size for DAGs volume",
    )
    logs_storage_size: str = Field(
        default="20Gi",
        description="PVC size for logs volume",
    )
    db_storage_size: str = Field(
        default="10Gi",
        description="PVC size for PostgreSQL data volume",
    )
    webserver_resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory for the webserver container",
    )
    scheduler_resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory for the scheduler container",
    )


class MlflowConfig(BaseModel):
    """MLflow deployment settings."""

    image: str = Field(
        default="ghcr.io/mlflow/mlflow:v2.19.0",
        description="MLflow tracking server image",
    )
    postgres_image: str = Field(
        default="postgres:16-alpine",
        description="PostgreSQL image for MLflow backend store",
    )
    db_storage_size: str = Field(
        default="10Gi",
        description="PVC size for PostgreSQL data volume",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory for the MLflow server container",
    )


class KServeConfig(BaseModel):
    """KServe model serving deployment settings."""

    controller_image: str = Field(
        default="kserve/kserve-controller:v0.14.1",
        description="KServe controller container image",
    )
    default_runtime: str = Field(
        default="kserve-mlserver",
        description="Default InferenceService runtime (e.g., kserve-mlserver, kserve-triton)",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory for the KServe controller container",
    )


class ProvisioningConfig(BaseModel):
    """Top-level provisioning configuration.

    Aggregates all service-level settings for workspace provisioning.
    Passed from argus-insight-ui when creating a workspace.
    Fields not provided by the UI will use their defaults.
    """

    minio: MinioConfig = Field(
        default_factory=MinioConfig,
        description="MinIO deployment settings",
    )
    airflow: AirflowConfig = Field(
        default_factory=AirflowConfig,
        description="Airflow deployment settings",
    )
    mlflow: MlflowConfig = Field(
        default_factory=MlflowConfig,
        description="MLflow deployment settings",
    )
    kserve: KServeConfig = Field(
        default_factory=KServeConfig,
        description="KServe model serving settings",
    )
