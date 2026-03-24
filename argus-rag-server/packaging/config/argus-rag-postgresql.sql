-- Argus RAG Server - PostgreSQL DDL
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_collections (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL UNIQUE,
    description         TEXT,
    embedding_model     VARCHAR(200) NOT NULL DEFAULT 'paraphrase-multilingual-MiniLM-L12-v2',
    embedding_dimension INTEGER NOT NULL DEFAULT 384,
    chunk_strategy      VARCHAR(50) NOT NULL DEFAULT 'paragraph',
    chunk_max_size      INTEGER NOT NULL DEFAULT 512,
    chunk_overlap       INTEGER NOT NULL DEFAULT 50,
    document_template   TEXT,
    document_count      INTEGER NOT NULL DEFAULT 0,
    chunk_count         INTEGER NOT NULL DEFAULT 0,
    status              VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag_documents (
    id              SERIAL PRIMARY KEY,
    collection_id   INTEGER NOT NULL REFERENCES rag_collections(id) ON DELETE CASCADE,
    external_id     VARCHAR(500) NOT NULL,
    title           VARCHAR(500),
    source_text     TEXT NOT NULL,
    metadata_json   TEXT,
    source_type     VARCHAR(50),
    source_url      VARCHAR(1000),
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    is_embedded     VARCHAR(10) NOT NULL DEFAULT 'false',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_collection ON rag_documents(collection_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_ext_id ON rag_documents(collection_id, external_id);

CREATE TABLE IF NOT EXISTS rag_document_chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    collection_id   INTEGER NOT NULL REFERENCES rag_collections(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,
    embedding       vector(384),
    model_name      VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_document ON rag_document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunk_collection ON rag_document_chunks(collection_id);

CREATE TABLE IF NOT EXISTS rag_data_sources (
    id              SERIAL PRIMARY KEY,
    collection_id   INTEGER NOT NULL REFERENCES rag_collections(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    source_type     VARCHAR(50) NOT NULL,
    config_json     TEXT,
    sync_mode       VARCHAR(30) NOT NULL DEFAULT 'manual',
    sync_schedule   VARCHAR(100),
    status          VARCHAR(30) NOT NULL DEFAULT 'active',
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_collection ON rag_data_sources(collection_id);

CREATE TABLE IF NOT EXISTS rag_sync_jobs (
    id              SERIAL PRIMARY KEY,
    collection_id   INTEGER NOT NULL REFERENCES rag_collections(id) ON DELETE CASCADE,
    data_source_id  INTEGER,
    job_type        VARCHAR(50) NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'running',
    total_items     INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    error_items     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_job_collection ON rag_sync_jobs(collection_id);
