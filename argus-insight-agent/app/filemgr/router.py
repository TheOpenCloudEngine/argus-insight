"""File and directory management API routes."""

from fastapi import APIRouter, HTTPException

from app.filemgr.schemas import (
    ArchiveCreateRequest,
    ChmodRequest,
    ChownRequest,
    DirCreateRequest,
    DirDeleteRequest,
    FileDownloadResponse,
    FileInfo,
    FileUploadRequest,
    LinkCreateRequest,
    OperationResult,
)
from app.filemgr.service import (
    chmod,
    chown,
    create_archive,
    create_directory,
    create_link,
    delete_directory,
    delete_file,
    download_file,
    get_file_info,
    upload_file,
)

router = APIRouter(prefix="/file", tags=["file"])


# ---------------------------------------------------------------------------
# Directory operations
# ---------------------------------------------------------------------------


@router.post("/directory", response_model=OperationResult)
async def dir_create(request: DirCreateRequest) -> OperationResult:
    """Create a directory."""
    return create_directory(request.path, request.parents, request.mode)


@router.delete("/directory", response_model=OperationResult)
async def dir_delete(request: DirDeleteRequest) -> OperationResult:
    """Delete a directory."""
    return delete_directory(request.path, request.recursive)


# ---------------------------------------------------------------------------
# Ownership / permissions
# ---------------------------------------------------------------------------


@router.put("/chown", response_model=OperationResult)
async def file_chown(request: ChownRequest) -> OperationResult:
    """Change ownership of a file or directory."""
    return await chown(request.path, request.owner, request.group, request.recursive)


@router.put("/chmod", response_model=OperationResult)
async def file_chmod(request: ChmodRequest) -> OperationResult:
    """Change permissions of a file or directory."""
    return await chmod(request.path, request.mode, request.recursive)


# ---------------------------------------------------------------------------
# Symbolic link
# ---------------------------------------------------------------------------


@router.post("/link", response_model=OperationResult)
async def file_link(request: LinkCreateRequest) -> OperationResult:
    """Create a symbolic link."""
    return create_link(request.target, request.link_path)


# ---------------------------------------------------------------------------
# File info
# ---------------------------------------------------------------------------


@router.get("/info", response_model=FileInfo)
async def file_info(path: str) -> FileInfo:
    """Get file or directory metadata."""
    try:
        return get_file_info(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# File upload / download / delete
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=OperationResult)
async def file_upload(request: FileUploadRequest) -> OperationResult:
    """Upload a file."""
    return upload_file(request.path, request.content, request.is_base64, request.mode)


@router.get("/download", response_model=FileDownloadResponse)
async def file_download(path: str) -> FileDownloadResponse:
    """Download a file (base64-encoded content)."""
    try:
        return download_file(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/file", response_model=OperationResult)
async def file_delete(path: str) -> OperationResult:
    """Delete a file."""
    return delete_file(path)


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


@router.post("/archive", response_model=OperationResult)
async def file_archive(request: ArchiveCreateRequest) -> OperationResult:
    """Compress a directory into an archive file."""
    return await create_archive(request)
