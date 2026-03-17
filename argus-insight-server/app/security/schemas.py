"""Pydantic schemas for security / certificate management API."""

from pydantic import BaseModel, Field


class CaCertStatusResponse(BaseModel):
    """Status of the CA certificate file."""

    exists: bool = Field(description="Whether the CA certificate file exists")
    filename: str = Field(default="", description="Name of the CA certificate file")
    cert_path: str = Field(default="", description="Full path to the CA certificate directory")


class CaCertViewResponse(BaseModel):
    """Content of the CA certificate file."""

    raw: str = Field(description="Raw PEM content of the certificate")
    decoded: str = Field(description="Decoded certificate information (openssl x509 -text)")


class CaCertUploadResponse(BaseModel):
    """Response after uploading a CA certificate."""

    success: bool
    filename: str
    path: str


class CaCertDeleteResponse(BaseModel):
    """Response after deleting a CA certificate."""

    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Error response with detail message."""

    detail: str
