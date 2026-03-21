"""Local filesystem browser schemas."""

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Common
# --------------------------------------------------------------------------- #


class FileInfo(BaseModel):
    """Metadata for a single file."""

    key: str = Field(description="Absolute path")
    name: str = Field(description="Display name (basename)")
    size: int = Field(0, description="Size in bytes")
    last_modified: str = Field("", description="Last modified timestamp (ISO 8601)")
    owner: str = Field("", description="File owner")
    group: str = Field("", description="File group")
    permissions: str = Field("", description="Permission string (e.g. rwxr-xr-x)")


class FolderInfo(BaseModel):
    """Metadata for a directory."""

    key: str = Field(description="Absolute path (with trailing /)")
    name: str = Field(description="Display name (basename)")
    owner: str = Field("", description="Directory owner")
    group: str = Field("", description="Directory group")
    permissions: str = Field("", description="Permission string (e.g. rwxr-xr-x)")


# --------------------------------------------------------------------------- #
# List directory
# --------------------------------------------------------------------------- #


class ListDirectoryResponse(BaseModel):
    """Response from listing a directory."""

    folders: list[FolderInfo] = Field(default_factory=list)
    files: list[FileInfo] = Field(default_factory=list)
    current_path: str = Field(description="Absolute path of the listed directory")


# --------------------------------------------------------------------------- #
# Create folder
# --------------------------------------------------------------------------- #


class CreateFolderRequest(BaseModel):
    """Request to create a new directory."""

    path: str = Field(..., description="Absolute path of the new directory")


class CreateFolderResponse(BaseModel):
    """Response from creating a directory."""

    path: str


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #


class DeleteRequest(BaseModel):
    """Request to delete files or directories."""

    paths: list[str] = Field(
        ..., min_length=1, max_length=1000, description="Absolute paths to delete"
    )


class DeleteResponse(BaseModel):
    """Response from deletion."""

    deleted: list[str]
    errors: list[dict] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Rename / Move
# --------------------------------------------------------------------------- #


class RenameRequest(BaseModel):
    """Request to rename or move a file/directory."""

    source_path: str = Field(..., description="Source absolute path")
    destination_path: str = Field(..., description="Destination absolute path")


class RenameResponse(BaseModel):
    """Response from rename/move."""

    source: str
    destination: str


# --------------------------------------------------------------------------- #
# File metadata (stat)
# --------------------------------------------------------------------------- #


class FileStatResponse(BaseModel):
    """Detailed file/directory metadata."""

    path: str
    name: str
    is_directory: bool
    size: int = 0
    last_modified: str = ""
    last_accessed: str = ""
    created: str = ""
    owner: str = ""
    group: str = ""
    permissions: str = ""
    permissions_octal: str = ""
    inode: int = 0
    hard_links: int = 0
    symlink_target: str | None = None


# --------------------------------------------------------------------------- #
# File Preview
# --------------------------------------------------------------------------- #


class TablePreviewResponse(BaseModel):
    """Tabular preview for Parquet, XLSX/XLS files."""

    format: str = Field(..., description="Source format: parquet, xlsx, xls")
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    total_rows: int = 0
    sheet_names: list[str] = Field(default_factory=list)
    active_sheet: str = ""


class DocumentPreviewResponse(BaseModel):
    """Document preview for DOCX, PPTX files."""

    format: str = Field(..., description="Source format: docx, pptx")
    html: str = ""
    slides: list[dict] | None = None
