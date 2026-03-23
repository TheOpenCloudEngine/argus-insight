-- Argus Catalog Server - PostgreSQL DDL
-- Auto-generated from database schema

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Platform Registry
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    logo_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT now(),
    platform_id VARCHAR(36) NOT NULL UNIQUE,
    type VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- Platform Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_configurations (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL UNIQUE REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Dataset
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_datasets (
    id SERIAL PRIMARY KEY,
    urn VARCHAR(500) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id),
    description TEXT,
    origin VARCHAR(50) NOT NULL,
    qualified_name VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    table_type VARCHAR(100),
    storage_format VARCHAR(100),
    platform_properties TEXT,
    is_synced VARCHAR(5) DEFAULT 'false'
);

-- ---------------------------------------------------------------------------
-- Dataset Properties
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_properties (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    property_key VARCHAR(100) NOT NULL,
    property_value TEXT NOT NULL,
    UNIQUE (dataset_id, property_key)
);

-- ---------------------------------------------------------------------------
-- Dataset Schema
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_schemas (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    field_path VARCHAR(500) NOT NULL,
    field_type VARCHAR(100) NOT NULL,
    native_type VARCHAR(100),
    description TEXT,
    nullable VARCHAR(5),
    ordinal INT NOT NULL,
    is_primary_key VARCHAR(5) DEFAULT 'false',
    is_indexed VARCHAR(5) DEFAULT 'false',
    is_unique VARCHAR(5) DEFAULT 'false',
    is_partition_key VARCHAR(5) DEFAULT 'false',
    is_distribution_key VARCHAR(5) DEFAULT 'false'
);

-- ---------------------------------------------------------------------------
-- Schema Snapshots (change history)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_schema_snapshots (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    synced_at TIMESTAMPTZ DEFAULT now(),
    schema_json TEXT NOT NULL,
    field_count INT,
    change_summary VARCHAR(500),
    changes_json TEXT
);

-- ---------------------------------------------------------------------------
-- Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Dataset-Tag Mapping
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_tags (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Glossary Terms
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_glossary_terms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    source VARCHAR(100),
    parent_id INT REFERENCES catalog_glossary_terms(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Dataset-Glossary Mapping
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_glossary_terms (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    term_id INT NOT NULL REFERENCES catalog_glossary_terms(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Ownership
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_owners (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    owner_name VARCHAR(200) NOT NULL,
    owner_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Platform Metadata - Data Types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_data_types (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    type_category VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, type_name)
);

-- ---------------------------------------------------------------------------
-- Platform Metadata - Table Types
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_table_types (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    type_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, type_name)
);

-- ---------------------------------------------------------------------------
-- Platform Metadata - Storage Formats
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_storage_formats (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    format_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    is_default VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, format_name)
);

-- ---------------------------------------------------------------------------
-- Platform Metadata - Features
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_platform_features (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES catalog_platforms(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    value_type VARCHAR(50) NOT NULL,
    is_required VARCHAR(5),
    ordinal INT NOT NULL,
    UNIQUE (platform_id, feature_key)
);

-- ---------------------------------------------------------------------------
-- User Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(30),
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    role_id INT NOT NULL REFERENCES argus_roles(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Role Management
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    role_id VARCHAR(50) NOT NULL
);

CREATE UNIQUE INDEX idx_argus_roles_role_id ON argus_roles USING btree (role_id);

-- ---------------------------------------------------------------------------
-- ML Model Registry - Registered Models
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_registered_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    urn VARCHAR(500) NOT NULL UNIQUE,
    platform_id INT REFERENCES catalog_platforms(id) ON DELETE SET NULL,
    description TEXT,
    owner VARCHAR(200),
    storage_location VARCHAR(1000),
    max_version_number INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
    bucket_name VARCHAR(255)
);

-- ---------------------------------------------------------------------------
-- ML Model Registry - Model Versions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_model_versions (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL,
    version INT NOT NULL,
    source VARCHAR(1000),
    run_id VARCHAR(255),
    run_link VARCHAR(1000),
    description TEXT,
    status VARCHAR(30) NOT NULL,
    status_message TEXT,
    storage_location VARCHAR(1000),
    artifact_count INT,
    artifact_size INT,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by VARCHAR(200),
    updated_by VARCHAR(200),
    UNIQUE (model_id, version)
);

-- ---------------------------------------------------------------------------
-- ML Model Registry - Model Metadata
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_models (
    id SERIAL PRIMARY KEY,
    model_version_id INT NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    predict_fn VARCHAR(100),
    python_version VARCHAR(20),
    serialization_format VARCHAR(50),
    sklearn_version VARCHAR(20),
    mlflow_version VARCHAR(20),
    mlflow_model_id VARCHAR(100),
    model_size_bytes BIGINT,
    utc_time_created VARCHAR(50),
    time_created TIMESTAMPTZ,
    requirements TEXT,
    conda TEXT,
    python_env TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    manifest TEXT,
    config TEXT,
    content_digest VARCHAR(100),
    source_type VARCHAR(50),
    UNIQUE (model_name, version)
);

-- ---------------------------------------------------------------------------
-- Model Download Log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_model_download_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_catalog_model_download_log_downloaded_at ON catalog_model_download_log USING btree (downloaded_at);
CREATE INDEX IF NOT EXISTS ix_catalog_model_download_log_model_name ON catalog_model_download_log USING btree (model_name);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Models
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    description TEXT,
    readme TEXT,
    task VARCHAR(50),
    framework VARCHAR(50),
    language VARCHAR(50),
    license VARCHAR(100),
    source_type VARCHAR(50),
    source_id VARCHAR(500),
    source_revision VARCHAR(100),
    bucket VARCHAR(255),
    storage_prefix VARCHAR(500),
    owner VARCHAR(200),
    version_count INT NOT NULL,
    total_size BIGINT,
    download_count INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Versions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_versions (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    version INT NOT NULL,
    manifest TEXT,
    content_digest VARCHAR(100),
    file_count INT,
    total_size BIGINT,
    metadata jsonb,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (model_id, version)
);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Tags
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_tags (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES catalog_tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (model_id, tag_id)
);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Lineage
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_lineage (
    id SERIAL PRIMARY KEY,
    model_id INT NOT NULL REFERENCES catalog_oci_models(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    relation_type VARCHAR(30) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- OCI Model Hub - Download Log
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_oci_model_download_log (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version INT NOT NULL,
    download_type VARCHAR(20) NOT NULL,
    client_ip VARCHAR(45),
    user_agent VARCHAR(500),
    downloaded_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_catalog_oci_model_download_log_downloaded_at ON catalog_oci_model_download_log USING btree (downloaded_at);
CREATE INDEX IF NOT EXISTS ix_catalog_oci_model_download_log_model_name ON catalog_oci_model_download_log USING btree (model_name);

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_comments (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    parent_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    root_id INT REFERENCES catalog_comments(id) ON DELETE CASCADE,
    depth INT NOT NULL,
    content TEXT NOT NULL,
    content_plain TEXT,
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(255),
    author_avatar VARCHAR(500),
    reply_count INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    is_deleted BOOLEAN NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'general'
);

CREATE INDEX IF NOT EXISTS ix_catalog_comments_entity_id ON catalog_comments USING btree (entity_id);
CREATE INDEX IF NOT EXISTS ix_catalog_comments_entity_type ON catalog_comments USING btree (entity_type);

-- ---------------------------------------------------------------------------
-- Configuration
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_configuration (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Collector - Hive Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_hive_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL,
    short_username VARCHAR(128),
    username VARCHAR(256),
    operation_name VARCHAR(64),
    start_time BIGINT,
    end_time BIGINT,
    duration_ms BIGINT,
    query TEXT,
    status VARCHAR(16) NOT NULL,
    error_msg TEXT,
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hive_query_history_query_id ON argus_collector_hive_query_history USING btree (query_id);
CREATE INDEX IF NOT EXISTS idx_hive_query_history_status ON argus_collector_hive_query_history USING btree (status);

-- ---------------------------------------------------------------------------
-- Collector - Impala Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_impala_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_type VARCHAR(32),
    query_state VARCHAR(32),
    statement TEXT,
    database VARCHAR(256),
    username VARCHAR(256),
    coordinator_host VARCHAR(512),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_ms BIGINT,
    rows_produced BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Collector - Trino Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_trino_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    query_state VARCHAR(32),
    query_type VARCHAR(32),
    statement TEXT,
    plan TEXT,
    username VARCHAR(256),
    principal VARCHAR(256),
    source VARCHAR(256),
    catalog VARCHAR(256),
    schema VARCHAR(256),
    remote_client_address VARCHAR(256),
    create_time TIMESTAMPTZ,
    execution_start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    wall_time_ms BIGINT,
    cpu_time_ms BIGINT,
    physical_input_bytes BIGINT,
    physical_input_rows BIGINT,
    output_bytes BIGINT,
    output_rows BIGINT,
    peak_memory_bytes BIGINT,
    error_code VARCHAR(128),
    error_message TEXT,
    inputs_json TEXT,
    output_json TEXT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trino_query_history_platform_id ON argus_collector_trino_query_history USING btree (platform_id);
CREATE INDEX IF NOT EXISTS idx_trino_query_history_query_id ON argus_collector_trino_query_history USING btree (query_id);
CREATE INDEX IF NOT EXISTS idx_trino_query_history_username ON argus_collector_trino_query_history USING btree (username);

-- ---------------------------------------------------------------------------
-- Collector - StarRocks Query History
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_collector_starrocks_query_history (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(256) NOT NULL UNIQUE,
    statement TEXT,
    digest VARCHAR(64),
    username VARCHAR(256),
    authorized_user VARCHAR(256),
    client_ip VARCHAR(64),
    database VARCHAR(256),
    catalog VARCHAR(256),
    state VARCHAR(16),
    error_code VARCHAR(512),
    query_time_ms BIGINT,
    scan_rows BIGINT,
    scan_bytes BIGINT,
    return_rows BIGINT,
    cpu_cost_ns BIGINT,
    mem_cost_bytes BIGINT,
    pending_time_ms BIGINT,
    is_query INT,
    fe_ip VARCHAR(128),
    event_timestamp BIGINT,
    platform_id VARCHAR(100),
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_platform_id ON argus_collector_starrocks_query_history USING btree (platform_id);
CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_query_id ON argus_collector_starrocks_query_history USING btree (query_id);
CREATE INDEX IF NOT EXISTS idx_starrocks_query_history_username ON argus_collector_starrocks_query_history USING btree (username);

-- ---------------------------------------------------------------------------
-- Lineage - Query Lineage (per-query source→target table mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_query_lineage (
    id SERIAL PRIMARY KEY,
    query_hist_id INT,
    source_table VARCHAR(512) NOT NULL,
    target_table VARCHAR(512) NOT NULL,
    source_dataset_id INT,
    target_dataset_id INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Lineage - Column Lineage (per-query source→target column mapping)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_column_lineage (
    id SERIAL PRIMARY KEY,
    query_lineage_id INT NOT NULL,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL DEFAULT 'DIRECT'
);

-- ---------------------------------------------------------------------------
-- Lineage - Data Pipeline (ETL/CDC/file-export pipeline registry)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_data_pipeline (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    pipeline_type VARCHAR(64) NOT NULL,
    schedule VARCHAR(100),
    owner VARCHAR(200),
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Lineage (aggregated dataset-to-dataset relationships)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_lineage (
    id SERIAL PRIMARY KEY,
    source_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    target_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    relation_type VARCHAR(32) NOT NULL,
    lineage_source VARCHAR(32) NOT NULL,
    pipeline_id INT REFERENCES argus_data_pipeline(id) ON DELETE SET NULL,
    description TEXT,
    created_by VARCHAR(200),
    query_count INT NOT NULL,
    last_query_id VARCHAR(256),
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source_dataset_id, target_dataset_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_dataset_lineage_pipeline ON argus_dataset_lineage USING btree (pipeline_id);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_source ON argus_dataset_lineage USING btree (source_dataset_id);
CREATE INDEX IF NOT EXISTS idx_dataset_lineage_target ON argus_dataset_lineage USING btree (target_dataset_id);

-- ---------------------------------------------------------------------------
-- Lineage - Dataset Column Mapping (cross-platform column-level lineage)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_dataset_column_mapping (
    id SERIAL PRIMARY KEY,
    dataset_lineage_id INT NOT NULL REFERENCES argus_dataset_lineage(id) ON DELETE CASCADE,
    source_column VARCHAR(256) NOT NULL,
    target_column VARCHAR(256) NOT NULL,
    transform_type VARCHAR(64) NOT NULL,
    transform_expr VARCHAR(500),
    UNIQUE (dataset_lineage_id, source_column, target_column)
);

CREATE INDEX IF NOT EXISTS idx_dataset_column_mapping_lineage ON argus_dataset_column_mapping USING btree (dataset_lineage_id);

-- ---------------------------------------------------------------------------
-- Alert - Lineage Alert (schema change impact events)
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Alert - Alert Rule (what to watch, when to trigger, who to notify)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_rule (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    description TEXT,
    scope_type VARCHAR(32) NOT NULL,
    scope_id INT,
    trigger_type VARCHAR(64) NOT NULL,
    trigger_config TEXT DEFAULT '{}',
    severity_override VARCHAR(16),
    channels VARCHAR(200) NOT NULL DEFAULT 'IN_APP',
    notify_owners VARCHAR(5) NOT NULL DEFAULT 'true',
    webhook_url VARCHAR(500),
    subscribers VARCHAR(2000),
    is_active VARCHAR(5) NOT NULL DEFAULT 'true',
    created_by VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alert_rule_scope ON argus_alert_rule (scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_alert_rule_active ON argus_alert_rule (is_active);

-- ---------------------------------------------------------------------------
-- Alert - Lineage Alert (schema change impact events)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_lineage_alert (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    source_dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    affected_dataset_id INT REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    lineage_id INT REFERENCES argus_dataset_lineage(id) ON DELETE SET NULL,
    rule_id INT REFERENCES argus_alert_rule(id) ON DELETE SET NULL,
    change_summary VARCHAR(500) NOT NULL,
    change_detail TEXT,
    status VARCHAR(20) NOT NULL,
    resolved_by VARCHAR(200),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lineage_alert_affected ON argus_lineage_alert USING btree (affected_dataset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_alert_source ON argus_lineage_alert USING btree (source_dataset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_alert_status ON argus_lineage_alert USING btree (status);
CREATE INDEX IF NOT EXISTS idx_lineage_alert_rule ON argus_lineage_alert USING btree (rule_id);

-- ---------------------------------------------------------------------------
-- Alert - Notification Log (delivery records)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS argus_alert_notification (
    id SERIAL PRIMARY KEY,
    alert_id INT NOT NULL REFERENCES argus_lineage_alert(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    recipient VARCHAR(200) NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    status VARCHAR(20) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_notification_alert ON argus_alert_notification USING btree (alert_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Dictionary (표준 사전)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_dictionary (
    id SERIAL PRIMARY KEY,
    dict_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    effective_date DATE,
    expiry_date DATE,
    created_by VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Data Standard - Word (표준 단어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_word (
    id SERIAL PRIMARY KEY,
    dictionary_id INT NOT NULL REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    word_name VARCHAR(100) NOT NULL,
    word_english VARCHAR(100) NOT NULL,
    word_abbr VARCHAR(50) NOT NULL,
    description TEXT,
    word_type VARCHAR(20) NOT NULL DEFAULT 'GENERAL',
    is_forbidden VARCHAR(5) DEFAULT 'false',
    synonym_group_id INT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (dictionary_id, word_name)
);

CREATE INDEX IF NOT EXISTS idx_std_word_dict ON catalog_standard_word (dictionary_id);
CREATE INDEX IF NOT EXISTS idx_std_word_type ON catalog_standard_word (word_type);

-- ---------------------------------------------------------------------------
-- Data Standard - Code Group (코드 그룹)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_code_group (
    id SERIAL PRIMARY KEY,
    dictionary_id INT NOT NULL REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    group_name VARCHAR(200) NOT NULL,
    group_english VARCHAR(200),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (dictionary_id, group_name)
);

-- ---------------------------------------------------------------------------
-- Data Standard - Code Value (코드 값)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_code_value (
    id SERIAL PRIMARY KEY,
    code_group_id INT NOT NULL REFERENCES catalog_code_group(id) ON DELETE CASCADE,
    code_value VARCHAR(100) NOT NULL,
    code_name VARCHAR(200) NOT NULL,
    code_english VARCHAR(200),
    description TEXT,
    sort_order INT NOT NULL DEFAULT 0,
    is_active VARCHAR(5) DEFAULT 'true',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (code_group_id, code_value)
);

CREATE INDEX IF NOT EXISTS idx_code_value_group ON catalog_code_value (code_group_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Domain (표준 도메인)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_domain (
    id SERIAL PRIMARY KEY,
    dictionary_id INT NOT NULL REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    domain_name VARCHAR(100) NOT NULL,
    domain_group VARCHAR(100),
    data_type VARCHAR(50) NOT NULL,
    data_length INT,
    data_precision INT,
    data_scale INT,
    description TEXT,
    code_group_id INT REFERENCES catalog_code_group(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (dictionary_id, domain_name)
);

CREATE INDEX IF NOT EXISTS idx_std_domain_dict ON catalog_standard_domain (dictionary_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Term (표준 용어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_term (
    id SERIAL PRIMARY KEY,
    dictionary_id INT NOT NULL REFERENCES catalog_standard_dictionary(id) ON DELETE CASCADE,
    term_name VARCHAR(200) NOT NULL,
    term_english VARCHAR(200) NOT NULL,
    term_abbr VARCHAR(100) NOT NULL,
    physical_name VARCHAR(100) NOT NULL,
    domain_id INT REFERENCES catalog_standard_domain(id) ON DELETE SET NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_by VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (dictionary_id, term_name)
);

CREATE INDEX IF NOT EXISTS idx_std_term_dict ON catalog_standard_term (dictionary_id);
CREATE INDEX IF NOT EXISTS idx_std_term_physical ON catalog_standard_term (physical_name);

-- ---------------------------------------------------------------------------
-- Data Standard - Term Words (용어 구성 단어)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_term_words (
    id SERIAL PRIMARY KEY,
    term_id INT NOT NULL REFERENCES catalog_standard_term(id) ON DELETE CASCADE,
    word_id INT NOT NULL REFERENCES catalog_standard_word(id) ON DELETE CASCADE,
    ordinal INT NOT NULL,
    UNIQUE (term_id, word_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_std_term_words_term ON catalog_standard_term_words (term_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Term-Column Mapping (표준 용어 ↔ 실제 컬럼 매핑)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_term_column_mapping (
    id SERIAL PRIMARY KEY,
    term_id INT NOT NULL REFERENCES catalog_standard_term(id) ON DELETE CASCADE,
    dataset_id INT NOT NULL REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    schema_id INT NOT NULL REFERENCES catalog_dataset_schemas(id) ON DELETE CASCADE,
    mapping_type VARCHAR(20) NOT NULL DEFAULT 'MATCHED',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (term_id, schema_id)
);

CREATE INDEX IF NOT EXISTS idx_term_col_mapping_term ON catalog_term_column_mapping (term_id);
CREATE INDEX IF NOT EXISTS idx_term_col_mapping_dataset ON catalog_term_column_mapping (dataset_id);

-- ---------------------------------------------------------------------------
-- Data Standard - Change Log (변경 이력)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_standard_change_log (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,
    entity_id INT NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(200),
    changed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_std_change_log_entity ON catalog_standard_change_log (entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- Dataset Embeddings (semantic search)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalog_dataset_embeddings (
    id SERIAL PRIMARY KEY,
    dataset_id INT NOT NULL UNIQUE REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    source_text TEXT NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    dimension INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dataset_embeddings_ivfflat
    ON catalog_dataset_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ---------------------------------------------------------------------------
-- Seed: Source Analysis Platforms (Java / Python)
-- ---------------------------------------------------------------------------

INSERT INTO catalog_platforms (name, logo_url, platform_id, type)
VALUES ('java', NULL, gen_random_uuid()::text, 'source_analysis')
ON CONFLICT (platform_id) DO NOTHING;

INSERT INTO catalog_platforms (name, logo_url, platform_id, type)
VALUES ('python', NULL, gen_random_uuid()::text, 'source_analysis')
ON CONFLICT (platform_id) DO NOTHING;
