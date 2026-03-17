"""Object file manager schemas."""

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Common
# --------------------------------------------------------------------------- #

class ObjectInfo(BaseModel):
    """Metadata for a single S3 object."""

    key: str
    size: int
    last_modified: str
    etag: str | None = None
    storage_class: str | None = None
    content_type: str | None = None


class FolderInfo(BaseModel):
    """A common prefix (virtual folder)."""

    prefix: str
    name: str


# --------------------------------------------------------------------------- #
# ListObjectsV2
# --------------------------------------------------------------------------- #

class ListObjectsRequest(BaseModel):
    """Query parameters for listing objects."""

    prefix: str = Field("", description="Prefix filter (folder path)")
    delimiter: str = Field("/", description="Delimiter for hierarchy")
    continuation_token: str | None = Field(None, description="Pagination token")
    max_keys: int = Field(1000, ge=1, le=1000, description="Max items per page")


class ListObjectsResponse(BaseModel):
    """Response from ListObjectsV2."""

    folders: list[FolderInfo]
    objects: list[ObjectInfo]
    next_continuation_token: str | None = None
    is_truncated: bool = False
    key_count: int = 0


# --------------------------------------------------------------------------- #
# HeadObject
# --------------------------------------------------------------------------- #

class HeadObjectResponse(BaseModel):
    """Metadata returned by HeadObject."""

    key: str
    size: int
    last_modified: str
    etag: str | None = None
    content_type: str | None = None
    storage_class: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# CopyObject
# --------------------------------------------------------------------------- #

class CopyObjectRequest(BaseModel):
    """Request to copy an object."""

    source_key: str = Field(..., description="Source object key")
    destination_key: str = Field(..., description="Destination object key")
    source_bucket: str | None = Field(None, description="Source bucket (default: same bucket)")


class CopyObjectResponse(BaseModel):
    """Response from CopyObject."""

    key: str
    etag: str | None = None


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #

class DeleteObjectsRequest(BaseModel):
    """Request to delete multiple objects."""

    keys: list[str] = Field(..., min_length=1, max_length=1000, description="Object keys to delete")


class DeleteObjectsResponse(BaseModel):
    """Response from DeleteObjects."""

    deleted: list[str]
    errors: list[dict] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Create folder
# --------------------------------------------------------------------------- #

class CreateFolderRequest(BaseModel):
    """Request to create a virtual folder (0-byte object with trailing /)."""

    key: str = Field(..., description="Folder key (must end with /)")


class CreateFolderResponse(BaseModel):
    """Response from creating a folder."""

    key: str


# --------------------------------------------------------------------------- #
# Presigned URL (download)
# --------------------------------------------------------------------------- #

class PresignedUrlResponse(BaseModel):
    """A presigned download URL."""

    url: str
    expires_in: int


# --------------------------------------------------------------------------- #
# Upload (presigned PUT or multipart initiation)
# --------------------------------------------------------------------------- #

class PresignedUploadUrlResponse(BaseModel):
    """A presigned upload URL."""

    url: str
    key: str
    expires_in: int


class MultipartUploadInitResponse(BaseModel):
    """Response when initiating a multipart upload."""

    upload_id: str
    key: str


class MultipartUploadPartUrl(BaseModel):
    """Presigned URL for uploading one part."""

    part_number: int
    url: str


class MultipartUploadUrlsRequest(BaseModel):
    """Request presigned URLs for multipart upload parts."""

    upload_id: str = Field(..., description="Multipart upload ID")
    key: str = Field(..., description="Object key")
    part_numbers: list[int] = Field(
        ..., min_length=1, max_length=10000, description="Part numbers to sign"
    )


class MultipartUploadUrlsResponse(BaseModel):
    """Presigned URLs for multipart parts."""

    parts: list[MultipartUploadPartUrl]


class CompletedPart(BaseModel):
    """A completed part reference."""

    part_number: int = Field(..., alias="PartNumber")
    etag: str = Field(..., alias="ETag")

    model_config = {"populate_by_name": True}


class CompleteMultipartRequest(BaseModel):
    """Request to complete a multipart upload."""

    upload_id: str
    key: str
    parts: list[CompletedPart]


class CompleteMultipartResponse(BaseModel):
    """Response from completing a multipart upload."""

    key: str
    etag: str | None = None


class AbortMultipartRequest(BaseModel):
    """Request to abort a multipart upload."""

    upload_id: str
    key: str


# --------------------------------------------------------------------------- #
# Object Tagging
# --------------------------------------------------------------------------- #

class Tag(BaseModel):
    """A single key-value tag."""

    key: str = Field(..., alias="Key")
    value: str = Field(..., alias="Value")

    model_config = {"populate_by_name": True}


class TaggingResponse(BaseModel):
    """Object tags."""

    key: str
    tags: list[Tag]


class PutTaggingRequest(BaseModel):
    """Request to set tags on an object."""

    tags: list[Tag]


# --------------------------------------------------------------------------- #
# S3 Select
# --------------------------------------------------------------------------- #

class S3SelectRequest(BaseModel):
    """Request for S3 Select query."""

    key: str = Field(..., description="Object key to query")
    expression: str = Field(
        ..., description="SQL expression (e.g. SELECT * FROM s3object LIMIT 10)"
    )
    input_format: str = Field("CSV", description="Input format: CSV, JSON, or Parquet")
    output_format: str = Field("JSON", description="Output format: CSV or JSON")
    compression: str = Field("NONE", description="Compression: NONE, GZIP, BZIP2")
    csv_header: str = Field("USE", description="CSV header usage: USE, IGNORE, NONE")


class S3SelectResponse(BaseModel):
    """Response from S3 Select."""

    records: list[str]
    stats: dict | None = None


# --------------------------------------------------------------------------- #
# File Preview
# --------------------------------------------------------------------------- #


class TablePreviewResponse(BaseModel):
    """Tabular preview for Parquet, XLSX/XLS files."""

    format: str = Field(..., description="Source format: parquet, xlsx, xls")
    columns: list[str] = Field(default_factory=list, description="Column names")
    rows: list[list] = Field(default_factory=list, description="Row data (list of lists)")
    total_rows: int = Field(0, description="Total rows in the source")
    sheet_names: list[str] = Field(default_factory=list, description="Sheet names (xlsx/xls only)")
    active_sheet: str = Field("", description="Active sheet name (xlsx/xls only)")


class DocumentPreviewResponse(BaseModel):
    """Document preview for DOCX, PPTX files."""

    format: str = Field(..., description="Source format: docx, pptx")
    html: str = Field("", description="Converted HTML content")
    slides: list[dict] | None = Field(None, description="Slide data (pptx only)")
