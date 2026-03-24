"""Pydantic schemas for Collection API."""

from datetime import datetime

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    chunk_strategy: str = "paragraph"
    chunk_max_size: int = 512
    chunk_overlap: int = 50
    document_template: str | None = None


class CollectionUpdate(BaseModel):
    description: str | None = None
    chunk_strategy: str | None = None
    chunk_max_size: int | None = None
    chunk_overlap: int | None = None
    document_template: str | None = None


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    embedding_model: str
    embedding_dimension: int
    chunk_strategy: str
    chunk_max_size: int
    chunk_overlap: int
    document_template: str | None = None
    document_count: int
    chunk_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=500)
    title: str | None = None
    source_text: str = Field(..., min_length=1)
    metadata_json: str | None = None
    source_type: str | None = None
    source_url: str | None = None


class DocumentResponse(BaseModel):
    id: int
    collection_id: int
    external_id: str
    title: str | None = None
    source_text: str
    metadata_json: str | None = None
    source_type: str | None = None
    chunk_count: int
    is_embedded: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentBulkIngest(BaseModel):
    """Bulk ingest multiple documents into a collection."""

    documents: list[DocumentCreate] = Field(..., min_length=1)


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_type: str = Field(..., description="catalog_api, file_upload, git")
    config_json: str | None = None
    sync_mode: str = "manual"
    sync_schedule: str | None = None


class DataSourceResponse(BaseModel):
    id: int
    collection_id: int
    name: str
    source_type: str
    config_json: str | None = None
    sync_mode: str
    sync_schedule: str | None = None
    status: str
    last_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SyncJobResponse(BaseModel):
    id: int
    collection_id: int
    data_source_id: int | None = None
    job_type: str
    status: str
    total_items: int
    processed_items: int
    error_items: int
    error_message: str | None = None
    duration_ms: int | None = None
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
