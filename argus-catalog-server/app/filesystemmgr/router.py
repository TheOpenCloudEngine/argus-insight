"""Local filesystem browser API endpoints.

Provides REST API for browsing and managing the local Linux filesystem:
  - Directory listing
  - File/directory creation, deletion, rename
  - File upload and download
  - File preview (parquet, xlsx, docx, pptx)
  - File metadata (stat)
"""

import logging
import mimetypes

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.filesystemmgr import service
from app.filesystemmgr.schemas import (
    CreateFolderRequest,
    CreateFolderResponse,
    DeleteRequest,
    DeleteResponse,
    DocumentPreviewResponse,
    FileStatResponse,
    ListDirectoryResponse,
    RenameRequest,
    RenameResponse,
    TablePreviewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filesystem", tags=["filesystem"])


# =========================================================================== #
# List directory
# =========================================================================== #


@router.get("/list", response_model=ListDirectoryResponse)
async def list_directory(
    path: str = Query("/", description="Absolute directory path"),
):
    """List files and directories under the given path."""
    try:
        return await service.list_directory(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("list_directory error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# File metadata (stat)
# =========================================================================== #


@router.get("/stat", response_model=FileStatResponse)
async def file_stat(
    path: str = Query(..., description="Absolute file or directory path"),
):
    """Get detailed metadata for a file or directory."""
    try:
        return await service.file_stat(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("file_stat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# Download
# =========================================================================== #


@router.get("/download")
async def download_file(
    path: str = Query(..., description="Absolute file path"),
):
    """Download a file."""
    try:
        data, filename = await service.read_file(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except IsADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("download error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =========================================================================== #
# Upload
# =========================================================================== #


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    path: str = Query(..., description="Destination directory path"),
):
    """Upload a file to the specified directory."""
    try:
        content = await file.read()
        filename = file.filename or "uploaded_file"
        saved_path = await service.save_uploaded_file(path, filename, content)
        return {"path": saved_path, "size": len(content)}
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("upload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# Create folder
# =========================================================================== #


@router.post("/folders", response_model=CreateFolderResponse)
async def create_folder(body: CreateFolderRequest):
    """Create a new directory."""
    try:
        return await service.create_folder(body.path)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("create_folder error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# Delete
# =========================================================================== #


@router.post("/delete", response_model=DeleteResponse)
async def delete_paths(body: DeleteRequest):
    """Delete files or directories."""
    try:
        return await service.delete_paths(body.paths)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("delete error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# Rename / Move
# =========================================================================== #


@router.post("/rename", response_model=RenameResponse)
async def rename(body: RenameRequest):
    """Rename or move a file/directory."""
    try:
        return await service.rename(body.source_path, body.destination_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("rename error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================== #
# File Preview
# =========================================================================== #

_PREVIEW_FORMATS = {
    "parquet": "table",
    "xlsx": "table",
    "xls": "table",
    "docx": "document",
    "pptx": "document",
}


@router.get(
    "/preview",
    response_model=TablePreviewResponse | DocumentPreviewResponse,
)
async def preview_file(
    path: str = Query(..., description="Absolute file path"),
    sheet: str | None = Query(None, description="Sheet name (xlsx/xls only)"),
    max_rows: int = Query(1000, ge=1, le=10000, description="Max rows for tabular preview"),
):
    """Preview a file by converting it on the server.

    Supported formats:
      - **parquet** -> tabular JSON (columns + rows)
      - **xlsx / xls** -> tabular JSON with sheet selection
      - **docx** -> HTML
      - **pptx** -> HTML with slide data
    """
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext not in _PREVIEW_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported preview format: .{ext}. "
            f"Supported: {', '.join(_PREVIEW_FORMATS.keys())}",
        )

    try:
        if ext == "parquet":
            return await service.preview_parquet(path, max_rows=max_rows)
        if ext in ("xlsx", "xls"):
            return await service.preview_xlsx(path, sheet=sheet, max_rows=max_rows)
        if ext == "docx":
            return await service.preview_docx(path)
        if ext == "pptx":
            return await service.preview_pptx(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("preview error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
