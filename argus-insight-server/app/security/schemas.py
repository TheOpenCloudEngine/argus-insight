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


class CaKeyStatusResponse(BaseModel):
    """Status of the CA key file."""

    exists: bool = Field(description="Whether the CA key file exists")
    filename: str = Field(default="", description="Name of the CA key file")
    cert_path: str = Field(default="", description="Full path to the CA certificate directory")


class CaKeyViewResponse(BaseModel):
    """Content of the CA key file."""

    raw: str = Field(description="Raw PEM content of the key")
    decoded: str = Field(description="Decoded key information (openssl rsa -text)")


class CaKeyUploadResponse(BaseModel):
    """Response after uploading a CA key."""

    success: bool
    filename: str
    path: str


class CaKeyDeleteResponse(BaseModel):
    """Response after deleting a CA key."""

    success: bool
    message: str


class GenerateSelfSignedCaRequest(BaseModel):
    """Request to generate a self-signed CA certificate and key."""

    country: str = Field(default="KR", description="Country code (C)")
    state: str = Field(default="Gyeonggi-do", description="State/Province (ST)")
    locality: str = Field(default="Yongin-si", description="City/Locality (L)")
    organization: str = Field(
        default="Open Cloud Engine Community", description="Organization name (O)"
    )
    org_unit: str = Field(default="Platform Engineering", description="Organizational Unit (OU)")
    common_name: str = Field(
        default="Open Cloud Engine Community CA", description="Common Name (CN)"
    )
    days: int = Field(default=3650, ge=1, le=36500, description="Certificate validity in days")
    key_bits: int = Field(default=4096, description="RSA key size in bits")


class GenerateSelfSignedCaResponse(BaseModel):
    """Response after generating a self-signed CA."""

    success: bool
    cert_filename: str
    key_filename: str
    cert_path: str
    key_path: str


class ErrorResponse(BaseModel):
    """Error response with detail message."""

    detail: str
