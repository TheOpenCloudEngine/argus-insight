"""ORM models for Collection, Document, DocumentChunk, DataSource, SyncJob."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class Collection(Base):
    """A named group of documents with shared embedding config."""

    __tablename__ = "rag_collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    # Embedding config per collection
    embedding_model = Column(
        String(200),
        nullable=False,
        default="paraphrase-multilingual-MiniLM-L12-v2",
    )
    embedding_dimension = Column(Integer, nullable=False, default=384)
    # Chunking config
    chunk_strategy = Column(String(50), nullable=False, default="paragraph")
    chunk_max_size = Column(Integer, nullable=False, default=512)
    chunk_overlap = Column(Integer, nullable=False, default=50)
    # Document template — how source_text is assembled from metadata
    document_template = Column(Text, nullable=True)
    # Stats (denormalized for dashboard)
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Document(Base):
    """A single document within a collection (pre-chunking)."""

    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # External identifier — unique within collection (e.g., dataset_id, file path)
    external_id = Column(String(500), nullable=False)
    title = Column(String(500), nullable=True)
    source_text = Column(Text, nullable=False)
    # Metadata (JSON): arbitrary key-value pairs for filtering
    metadata_json = Column(Text, nullable=True)
    # Source tracking
    source_type = Column(String(50), nullable=True)  # catalog_api, file, manual
    source_url = Column(String(1000), nullable=True)
    # Status
    chunk_count = Column(Integer, nullable=False, default=0)
    is_embedded = Column(String(10), nullable=False, default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DocumentChunk(Base):
    """A chunk of a document with its embedding vector."""

    __tablename__ = "rag_document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    # pgvector embedding — dimension varies per collection
    embedding = Column(Vector(384) if Vector else Text, nullable=True)
    # Provenance
    model_name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base):
    """External data source configuration for a collection."""

    __tablename__ = "rag_data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False)  # catalog_api, file_upload, git
    # Connection config (JSON)
    config_json = Column(Text, nullable=True)
    # Sync settings
    sync_mode = Column(String(30), nullable=False, default="manual")  # manual, webhook, schedule
    sync_schedule = Column(String(100), nullable=True)  # cron expression
    status = Column(String(30), nullable=False, default="active")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SyncJob(Base):
    """History of sync/embedding jobs."""

    __tablename__ = "rag_sync_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer,
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source_id = Column(Integer, nullable=True)
    job_type = Column(String(50), nullable=False)  # sync, embed, reindex, delete
    status = Column(String(30), nullable=False, default="running")  # running, completed, failed
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    error_items = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
