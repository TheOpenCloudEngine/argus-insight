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
    dags_sub_path: str = Field(
        default="airflow-dags",
        description="Subdirectory in the Git repo containing DAG files",
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
    pip_index_url: str = Field(
        default="https://pypi.org/simple",
        description="Python pip index URL for DAG dependencies",
    )


class MlflowConfig(BaseModel):
    """MLflow deployment settings."""

    # MLflow server
    image: str = Field(
        default="ghcr.io/mlflow/mlflow:v2.19.0",
        description="MLflow tracking server image",
    )
    port: int = Field(
        default=5000,
        description="MLflow server listening port",
    )
    serve_artifacts: bool = Field(
        default=True,
        description="Enable artifact proxy serving",
    )
    artifact_root_prefix: str = Field(
        default="mlflow-artifacts",
        description="S3 artifact root path prefix",
    )
    resources: ResourceConfig = Field(
        default_factory=ResourceConfig,
        description="CPU/Memory for the MLflow server container",
    )

    # PostgreSQL backend store
    postgres_image: str = Field(
        default="postgres:16-alpine",
        description="PostgreSQL image for MLflow backend store",
    )
    db_storage_size: str = Field(
        default="10Gi",
        description="PVC size for PostgreSQL data volume",
    )
    db_name: str = Field(
        default="mlflow",
        description="PostgreSQL database name",
    )
    db_user: str = Field(
        default="mlflow",
        description="PostgreSQL username",
    )
    db_cpu_request: str = Field(
        default="100m",
        description="PostgreSQL CPU request",
    )
    db_cpu_limit: str = Field(
        default="500m",
        description="PostgreSQL CPU limit",
    )
    db_memory_request: str = Field(
        default="256Mi",
        description="PostgreSQL memory request",
    )
    db_memory_limit: str = Field(
        default="512Mi",
        description="PostgreSQL memory limit",
    )

    # Ingress
    ingress_class: str = Field(
        default="nginx",
        description="Kubernetes Ingress class name",
    )
    proxy_body_size: str = Field(
        default="256m",
        description="Maximum upload size for model files",
    )
    proxy_read_timeout: int = Field(
        default=600,
        description="Nginx Ingress proxy read timeout in seconds",
    )

    # Health check
    liveness_initial_delay: int = Field(
        default=30,
        description="Liveness probe initial delay in seconds",
    )
    readiness_initial_delay: int = Field(
        default=15,
        description="Readiness probe initial delay in seconds",
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


class JupyterLabConfig(BaseModel):
    """JupyterLab deployment settings."""

    image: str = Field(
        default="quay.io/jupyter/scipy-notebook:2025-03-17",
        description="JupyterLab container image",
    )
    cpu_request: str = Field(default="500m", description="CPU request")
    cpu_limit: str = Field(default="2", description="CPU limit")
    memory_request: str = Field(default="1Gi", description="Memory request")
    memory_limit: str = Field(default="4Gi", description="Memory limit")
    workspace_path: str = Field(default="/workspace", description="Workspace S3 bucket mount path")
    user_data_path: str = Field(default="/data", description="Personal S3 bucket mount path")
    default_kernel: str = Field(default="python3", description="Default Jupyter kernel")
    pip_index_url: str = Field(default="https://pypi.org/simple", description="Python pip index URL")
    install_packages: list[str] = Field(default_factory=list, description="Additional pip packages to install on startup")
    s3fs_image: str = Field(default="efrecon/s3fs:1.94", description="s3fs FUSE mount sidecar image")


class JupyterTensorFlowConfig(JupyterLabConfig):
    """JupyterLab TensorFlow deployment settings."""

    image: str = Field(
        default="quay.io/jupyter/tensorflow-notebook:2025-03-17",
        description="JupyterLab TensorFlow container image",
    )
    memory_request: str = Field(default="2Gi", description="Memory request")
    memory_limit: str = Field(default="8Gi", description="Memory limit")


class JupyterPySparkConfig(JupyterLabConfig):
    """JupyterLab PySpark deployment settings."""

    image: str = Field(
        default="quay.io/jupyter/pyspark-notebook:2025-03-17",
        description="JupyterLab PySpark container image",
    )
    memory_request: str = Field(default="2Gi", description="Memory request")
    memory_limit: str = Field(default="8Gi", description="Memory limit")


class H2OAutoMLConfig(BaseModel):
    """H2O AutoML deployment settings."""

    image: str = Field(
        default="h2oai/h2o-open-source-k8s:latest",
        description="H2O AutoML container image",
    )
    cpu_request: str = Field(default="1", description="CPU request")
    cpu_limit: str = Field(default="4", description="CPU limit")
    memory_request: str = Field(default="2Gi", description="Memory request")
    memory_limit: str = Field(default="8Gi", description="Memory limit")
    java_max_heap: str = Field(default="6g", description="JVM max heap (-Xmx)")


class LabelStudioConfig(BaseModel):
    """Label Studio deployment settings."""

    image: str = Field(
        default="heartexlabs/label-studio:latest",
        description="Label Studio container image",
    )
    cpu_request: str = Field(default="250m", description="CPU request")
    cpu_limit: str = Field(default="2", description="CPU limit")
    memory_request: str = Field(default="512Mi", description="Memory request")
    memory_limit: str = Field(default="2Gi", description="Memory limit")
    storage_size: str = Field(default="10Gi", description="Data PVC size")


class FeastConfig(BaseModel):
    """Feast Feature Store deployment settings."""

    image: str = Field(
        default="feastdev/feature-server:latest",
        description="Feast feature server image",
    )
    cpu_request: str = Field(default="250m", description="CPU request")
    cpu_limit: str = Field(default="1", description="CPU limit")
    memory_request: str = Field(default="256Mi", description="Memory request")
    memory_limit: str = Field(default="1Gi", description="Memory limit")


class SeldonCoreConfig(BaseModel):
    """Seldon Core deployment settings."""

    image: str = Field(
        default="seldonio/seldon-core-operator:1.18.1",
        description="Seldon Core operator image",
    )
    cpu_request: str = Field(default="250m", description="CPU request")
    cpu_limit: str = Field(default="1", description="CPU limit")
    memory_request: str = Field(default="256Mi", description="Memory request")
    memory_limit: str = Field(default="512Mi", description="Memory limit")


class VllmConfig(BaseModel):
    """vLLM LLM serving deployment settings."""

    image: str = Field(default="vllm/vllm-openai:latest", description="vLLM container image")
    model: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", description="HuggingFace model ID")
    cpu_request: str = Field(default="2", description="CPU request")
    cpu_limit: str = Field(default="4", description="CPU limit")
    memory_request: str = Field(default="8Gi", description="Memory request")
    memory_limit: str = Field(default="16Gi", description="Memory limit")
    gpu_count: int = Field(default=1, description="Number of GPUs")
    max_model_len: int = Field(default=4096, description="Max model context length")
    hf_token: str = Field(default="", description="HuggingFace API token for gated models")


class OllamaConfig(BaseModel):
    """Ollama local LLM deployment settings."""

    image: str = Field(default="ollama/ollama:latest", description="Ollama container image")
    cpu_request: str = Field(default="1", description="CPU request")
    cpu_limit: str = Field(default="4", description="CPU limit")
    memory_request: str = Field(default="4Gi", description="Memory request")
    memory_limit: str = Field(default="8Gi", description="Memory limit")
    storage_size: str = Field(default="50Gi", description="Model storage PVC size")


class LangServeConfig(BaseModel):
    """LangServe Agent API deployment settings."""

    image: str = Field(default="python:3.11-slim", description="LangServe container image")
    cpu_request: str = Field(default="500m", description="CPU request")
    cpu_limit: str = Field(default="2", description="CPU limit")
    memory_request: str = Field(default="512Mi", description="Memory request")
    memory_limit: str = Field(default="2Gi", description="Memory limit")
    s3fs_image: str = Field(default="efrecon/s3fs:1.94", description="s3fs sidecar image")
    agent_path: str = Field(
        default="/workspace/agents/default",
        description="Path to agent code directory (must contain server.py)",
    )
    pip_index_url: str = Field(default="https://pypi.org/simple", description="Python pip index URL")
    disable_auth: bool = Field(
        default=False,
        description="Disable Ingress auth — API accessible without authentication",
    )


class ChromaDBConfig(BaseModel):
    """ChromaDB vector database deployment settings."""

    image: str = Field(default="chromadb/chroma:latest", description="ChromaDB container image")
    cpu_request: str = Field(default="250m", description="CPU request")
    cpu_limit: str = Field(default="1", description="CPU limit")
    memory_request: str = Field(default="512Mi", description="Memory request")
    memory_limit: str = Field(default="2Gi", description="Memory limit")
    storage_size: str = Field(default="20Gi", description="Data PVC size")


class RedisConfig(BaseModel):
    """Redis deployment settings."""

    image: str = Field(default="redis:7-alpine", description="Redis container image")
    cpu_request: str = Field(default="100m", description="CPU request")
    cpu_limit: str = Field(default="500m", description="CPU limit")
    memory_request: str = Field(default="128Mi", description="Memory request")
    memory_limit: str = Field(default="1Gi", description="Memory limit")
    storage_size: str = Field(default="5Gi", description="Data PVC size")
    maxmemory: str = Field(default="512mb", description="Redis maxmemory setting")


class RStudioServerConfig(BaseModel):
    """RStudio Server deployment settings."""

    image: str = Field(
        default="rocker/tidyverse:4.4.3",
        description="RStudio Server container image",
    )
    cpu_request: str = Field(default="500m", description="CPU request")
    cpu_limit: str = Field(default="2", description="CPU limit")
    memory_request: str = Field(default="1Gi", description="Memory request")
    memory_limit: str = Field(default="4Gi", description="Memory limit")
    workspace_path: str = Field(default="/workspace", description="Workspace S3 bucket mount path")
    user_data_path: str = Field(default="/data", description="Personal S3 bucket mount path")
    s3fs_image: str = Field(default="efrecon/s3fs:1.94", description="s3fs FUSE mount sidecar image")
    install_packages: list[str] = Field(
        default_factory=list,
        description="Additional R packages to install on startup via install.packages()",
    )


class MilvusConfig(BaseModel):
    """Milvus Vector Database deployment settings."""

    image: str = Field(
        default="milvusdb/milvus:v2.5.6",
        description="Milvus Standalone container image",
    )
    attu_image: str = Field(
        default="zilliz/attu:v2.4.12",
        description="Attu Web UI sidecar image",
    )
    storage_size: str = Field(
        default="30Gi",
        description="Persistent data volume size",
    )
    resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="4",
            memory_request="2Gi", memory_limit="8Gi",
        ),
        description="CPU/Memory for the Milvus container",
    )


class MindsdbConfig(BaseModel):
    """MindsDB AI-in-Database deployment settings."""

    image: str = Field(
        default="mindsdb/mindsdb:latest",
        description="MindsDB container image",
    )
    storage_size: str = Field(
        default="20Gi",
        description="Persistent data volume size for models and metadata",
    )
    resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="4",
            memory_request="2Gi", memory_limit="8Gi",
        ),
        description="CPU/Memory for the MindsDB container",
    )


class Neo4jConfig(BaseModel):
    """Neo4j Graph Database deployment settings."""

    image: str = Field(
        default="neo4j:5.26-community",
        description="Neo4j container image (Community Edition)",
    )
    storage_size: str = Field(
        default="20Gi",
        description="Persistent data volume size",
    )
    resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="2",
            memory_request="1Gi", memory_limit="4Gi",
        ),
        description="CPU/Memory for the Neo4j container",
    )


class MinioWorkspaceConfig(BaseModel):
    """MinIO Workspace Bucket settings."""

    bucket_prefix: str = Field(
        default="workspace-",
        description="Bucket name prefix (e.g., workspace-aaa)",
    )
    create_user_per_member: bool = Field(
        default=True,
        description="Create a MinIO user per workspace member",
    )
    default_policy: str = Field(
        default="readwrite",
        description="Default bucket policy for members (readwrite or readonly)",
    )


class VScodeServerConfig(BaseModel):
    """VS Code Server deployment settings."""

    image: str = Field(
        default="codercom/code-server:4.96.4",
        description="code-server container image",
    )
    cpu_request: str = Field(
        default="500m",
        description="CPU request for the code-server container",
    )
    cpu_limit: str = Field(
        default="1",
        description="CPU limit for the code-server container",
    )
    memory_request: str = Field(
        default="512Mi",
        description="Memory request for the code-server container",
    )
    memory_limit: str = Field(
        default="2Gi",
        description="Memory limit for the code-server container",
    )
    workspace_path: str = Field(
        default="/workspace",
        description="Workspace S3 bucket mount path inside the container",
    )
    user_data_path: str = Field(
        default="/data",
        description="Personal S3 bucket mount path inside the container",
    )
    color_theme: str = Field(
        default="Default Dark Modern",
        description="Default VS Code color theme",
    )
    editor_font_size: int = Field(
        default=14,
        description="Editor font size in pixels",
    )
    terminal_font_size: int = Field(
        default=13,
        description="Terminal font size in pixels",
    )
    minimap_enabled: bool = Field(
        default=False,
        description="Enable editor minimap",
    )
    pip_index_url: str = Field(
        default="https://pypi.org/simple",
        description="Python pip index URL (e.g., internal Nexus mirror)",
    )
    install_python: bool = Field(
        default=True,
        description="Automatically install Python on startup",
    )
    s3fs_image: str = Field(
        default="efrecon/s3fs:1.94",
        description="s3fs FUSE mount sidecar image",
    )
    s3_bucket_pattern: str = Field(
        default="user-{username}",
        description="S3 bucket naming pattern ({username} is replaced)",
    )
    s3fs_enabled: bool = Field(
        default=True,
        description="Enable s3fs sidecar for persistent S3-backed storage",
    )
    proxy_read_timeout: int = Field(
        default=3600,
        description="Nginx Ingress proxy read timeout in seconds",
    )
    proxy_send_timeout: int = Field(
        default=3600,
        description="Nginx Ingress proxy send timeout in seconds",
    )
    ingress_class: str = Field(
        default="nginx",
        description="Kubernetes Ingress class name",
    )
    default_extensions: list[str] = Field(
        default_factory=list,
        description="VS Code extensions to install on first launch (e.g., ms-python.python)",
    )


class TrinoConfig(BaseModel):
    """Trino distributed SQL query engine deployment settings."""

    coordinator_image: str = Field(
        default="trinodb/trino:latest",
        description="Trino coordinator/worker container image",
    )
    worker_replicas: int = Field(
        default=1,
        description="Number of Trino worker replicas",
    )
    coordinator_resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="2",
            memory_request="2Gi", memory_limit="4Gi",
        ),
        description="CPU/Memory for the coordinator",
    )
    worker_resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="2",
            memory_request="2Gi", memory_limit="4Gi",
        ),
        description="CPU/Memory for each worker",
    )


class StarRocksConfig(BaseModel):
    """StarRocks MPP analytics database deployment settings."""

    fe_image: str = Field(
        default="starrocks/fe-ubuntu:latest",
        description="StarRocks Frontend container image",
    )
    be_image: str = Field(
        default="starrocks/be-ubuntu:latest",
        description="StarRocks Backend container image",
    )
    be_replicas: int = Field(
        default=1,
        description="Number of Backend replicas",
    )
    fe_storage_size: str = Field(
        default="10Gi",
        description="PVC size for FE metadata",
    )
    be_storage_size: str = Field(
        default="50Gi",
        description="PVC size for BE data",
    )
    fe_resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="500m", cpu_limit="2",
            memory_request="2Gi", memory_limit="4Gi",
        ),
        description="CPU/Memory for Frontend",
    )
    be_resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="1", cpu_limit="4",
            memory_request="4Gi", memory_limit="8Gi",
        ),
        description="CPU/Memory for each Backend",
    )


class PostgresqlConfig(BaseModel):
    """PostgreSQL deployment settings."""

    image: str = Field(
        default="postgres:17-bookworm",
        description="PostgreSQL container image",
    )
    storage_size: str = Field(
        default="20Gi",
        description="Persistent data volume size",
    )
    db_name: str = Field(
        default="argus",
        description="Default database name",
    )
    db_user: str = Field(
        default="argus",
        description="Database username",
    )
    resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="250m", cpu_limit="2",
            memory_request="512Mi", memory_limit="2Gi",
        ),
        description="CPU/Memory for the PostgreSQL container",
    )


class MariadbConfig(BaseModel):
    """MariaDB deployment settings."""

    image: str = Field(
        default="mariadb:11",
        description="MariaDB container image",
    )
    storage_size: str = Field(
        default="20Gi",
        description="Persistent data volume size",
    )
    db_name: str = Field(
        default="argus",
        description="Default database name",
    )
    db_user: str = Field(
        default="argus",
        description="Database username",
    )
    resources: ResourceConfig = Field(
        default_factory=lambda: ResourceConfig(
            cpu_request="250m", cpu_limit="2",
            memory_request="512Mi", memory_limit="2Gi",
        ),
        description="CPU/Memory for the MariaDB container",
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
