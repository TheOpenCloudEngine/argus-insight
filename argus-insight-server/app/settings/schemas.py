"""Pydantic schemas for infrastructure configuration API."""

from pydantic import BaseModel, Field


class InfraConfigItem(BaseModel):
    """A single infrastructure configuration entry."""

    config_key: str
    config_value: str
    description: str | None = None


class InfraCategoryResponse(BaseModel):
    """Configuration items grouped by category."""

    category: str
    items: dict[str, str] = Field(
        description="Key-value pairs for this category",
    )


class InfraConfigResponse(BaseModel):
    """Full infrastructure configuration returned to the UI."""

    categories: list[InfraCategoryResponse] = Field(
        description="Configuration grouped by category",
    )


class UpdateInfraCategoryRequest(BaseModel):
    """Request to update settings within a single category."""

    category: str = Field(description="Category identifier (e.g. network)")
    items: dict[str, str] = Field(
        description="Key-value pairs to update",
    )


class DockerRegistryTestRequest(BaseModel):
    """Request to test Docker Registry connectivity."""

    url: str = Field(description="Docker Registry URL")
    username: str = Field(default="", description="Registry username")
    password: str = Field(default="", description="Registry password")


class DockerRegistryTestResponse(BaseModel):
    """Response from Docker Registry connectivity test."""

    success: bool
    message: str


class UnityCatalogTestRequest(BaseModel):
    """Request to test Unity Catalog connectivity."""

    url: str = Field(description="Unity Catalog URL")
    access_token: str = Field(default="", description="Unity Catalog access token")


class UnityCatalogTestResponse(BaseModel):
    """Response from Unity Catalog connectivity test."""

    success: bool
    message: str


class UnityCatalogInitRequest(BaseModel):
    """Request to initialize Unity Catalog with default metastore and catalog."""

    url: str = Field(description="Unity Catalog URL")
    access_token: str = Field(default="", description="Unity Catalog access token")


class UnityCatalogInitResponse(BaseModel):
    """Response from Unity Catalog initialization."""

    success: bool
    message: str


class CheckPathRequest(BaseModel):
    """Request to check if a file path exists on the server."""

    path: str = Field(description="File path to check")


class CheckPathResponse(BaseModel):
    """Response indicating whether the path exists."""

    path: str
    exists: bool
