# Argus Catalog Architecture

## System Architecture

```mermaid
graph TB
    subgraph UI["Argus Catalog UI (Next.js 16 / React 19)"]
        direction LR
        Dashboard[Dashboard]
        Datasets[Datasets<br/>Schema / Lineage / Terms]
        Models[Models<br/>MLflow / OCI Hub]
        Standards[Data Standards<br/>Dictionary / Word / Domain / Term]
        Glossary[Glossary<br/>Tree Classification]
        Alerts[Alerts<br/>Rules / Notifications]
        Platforms[Platforms]
        Search[Semantic Search]
        Settings[Settings / Users]
    end

    UI -->|REST API| Server

    subgraph Server["Argus Catalog Server (FastAPI / Python 3.11+)"]
        direction TB

        subgraph API["API Layer"]
            CatalogAPI["/api/v1/catalog<br/>Datasets, Platforms, Tags<br/>Glossary, Pipelines, Lineage"]
            ModelAPI["/api/v1/models<br/>MLflow Registry"]
            UCAPI["/api/2.1/unity-catalog<br/>UC OSS Compatible"]
            OCIAPI["/api/v1/oci-models<br/>OCI Model Hub"]
            StdAPI["/api/v1/standards<br/>Dictionary, Word, Domain<br/>Term, Code, Compliance"]
            AlertAPI["/api/v1/alerts<br/>Rules, Summary, Status"]
            SearchAPI["/api/v1/search<br/>Hybrid Search"]
            OtherAPI["/api/v1/comments<br/>/api/v1/filesystem<br/>/api/v1/auth, usermgr"]
        end

        subgraph SVC["Service Layer"]
            CatalogSvc["Catalog Service<br/>Dataset CRUD / Schema History<br/>Platform Sync / Lineage"]
            AlertSvc["Alert Service<br/>Rule Engine / Impact Analysis<br/>Notification Dispatch"]
            StdSvc["Standard Service<br/>Morpheme Analysis<br/>Auto-Mapping / Compliance"]
            ModelSvc["Model Service<br/>MLflow / UC Compat<br/>OCI Hub / Artifact Store"]
            EmbedSvc["Embedding Service<br/>OpenAI / Ollama<br/>Sentence-Transformers"]
        end

        subgraph ORM["Data Layer (SQLAlchemy 2.0 async)"]
            CatalogTbl["catalog_* (18 tables)<br/>datasets, platforms, schemas<br/>tags, owners, glossary"]
            LineageTbl["argus_* (12 tables)<br/>pipeline, lineage, column_mapping<br/>alert_rule, query_history"]
            StdTbl["catalog_standard_* (9 tables)<br/>dictionary, word, domain<br/>term, code_group, code_value"]
        end

        API --> SVC
        SVC --> ORM
    end

    subgraph Infra["Infrastructure"]
        PG[(PostgreSQL<br/>+ pgvector)]
        S3[(S3 / MinIO<br/>Model Artifacts)]
        KC[Keycloak<br/>OIDC Auth<br/>optional]
    end

    ORM --> PG
    ModelSvc --> S3
    Server -.->|optional| KC

    subgraph Extensions["Argus Catalog Extensions"]
        direction TB

        subgraph Sync["Metadata Sync Service"]
            MySQL[MySQL]
            PgSQL[PostgreSQL]
            Hive[Hive<br/>Thrift]
            Impala[Impala<br/>CM API]
            Trino[Trino]
            StarRocks[StarRocks]
            Others[Greenplum / Oracle<br/>MSSQL / Kudu]
        end

        subgraph Collectors["Query Event Collectors (Java)"]
            HiveHook[Hive Hook]
            ImpalaAgent[Impala Agent]
            TrinoListener[Trino Listener]
            SRAudit[StarRocks Audit]
        end

        subgraph Analyzers["Source Code Analyzers"]
            JavaAnalyzer[Java Analyzer<br/>JPA / MyBatis / JDBC]
            PyAnalyzer[Python Analyzer<br/>SQLAlchemy / Django]
            SQLGlot[SQLGlot Impala<br/>SQL Lineage Parser]
        end
    end

    Sync -->|metadata| Server
    Collectors -->|query history| Server
    Analyzers -->|table mappings| Server

    subgraph SDK["Argus Catalog SDK"]
        CLI["argus-model CLI<br/>list / pull / push<br/>import-hf / import-local"]
    end

    SDK -->|REST API| Server

    subgraph Sources["Enterprise Data Sources"]
        DB1[(MySQL)]
        DB2[(Oracle)]
        DB3[(PostgreSQL)]
        DB4[(Hive / Impala)]
        DB5[(Trino / StarRocks)]
    end

    Sources --> Sync
    Sources --> Collectors

    style UI fill:#e0f2fe,stroke:#0284c7
    style Server fill:#f0fdf4,stroke:#16a34a
    style Extensions fill:#fef3c7,stroke:#d97706
    style Infra fill:#f3e8ff,stroke:#9333ea
    style SDK fill:#fce7f3,stroke:#db2777
    style Sources fill:#f1f5f9,stroke:#64748b
```

## Data Flow

```mermaid
flowchart LR
    subgraph Sources["Data Sources"]
        S1[(MySQL)]
        S2[(Oracle)]
        S3[(Hive)]
        S4[(Impala)]
        S5[(Trino)]
    end

    subgraph Collect["Collection"]
        Sync[Metadata<br/>Sync]
        Hook[Query<br/>Hooks]
        Code[Source Code<br/>Analysis]
    end

    subgraph Catalog["Argus Catalog"]
        Meta[Metadata<br/>Store]
        Lineage[Lineage<br/>Tracking]
        Alert[Alert<br/>Engine]
        Std[Standard<br/>Management]
        Embed[Semantic<br/>Search]
        Model[Model<br/>Registry]
    end

    subgraph Output["Output"]
        WebUI[Web UI]
        Webhook[Slack / Teams<br/>Webhook]
        MLFW[MLflow<br/>Integration]
        CLITOOL[CLI / SDK]
    end

    Sources --> Sync --> Meta
    Sources --> Hook --> Lineage
    Code --> Meta

    Meta --> Lineage --> Alert --> Webhook
    Meta --> Std
    Meta --> Embed --> WebUI
    Model --> MLFW
    Model --> CLITOOL
    Meta --> WebUI

    style Sources fill:#f1f5f9,stroke:#64748b
    style Collect fill:#fef3c7,stroke:#d97706
    style Catalog fill:#f0fdf4,stroke:#16a34a
    style Output fill:#e0f2fe,stroke:#0284c7
```

## Cross-Platform Lineage

```mermaid
flowchart LR
    subgraph Source["Source Platform"]
        PG[(PostgreSQL<br/>employees)]
    end

    subgraph Pipeline["Data Pipeline"]
        ETL[ETL Job<br/>Parquet Export]
    end

    subgraph Target["Target Platform"]
        IMP[(Impala<br/>emp_fact)]
    end

    subgraph Catalog["Argus Catalog"]
        LIN[Lineage<br/>Tracking]
        COL[Column<br/>Mapping]
        RULE[Alert<br/>Rule]
    end

    PG -->|"emp_id (INT)"| ETL
    ETL -->|"employee_key (BIGINT)"| IMP

    PG -.->|schema sync| LIN
    IMP -.->|schema sync| LIN
    LIN --> COL
    COL -->|"emp_id → employee_key<br/>CAST INT→BIGINT"| COL

    PG -->|"schema change<br/>detected"| RULE
    RULE -->|"BREAKING alert<br/>salary column dropped"| Notify[Slack / Email<br/>Owner Notification]

    style Source fill:#e0f2fe,stroke:#0284c7
    style Pipeline fill:#fef3c7,stroke:#d97706
    style Target fill:#dbeafe,stroke:#3b82f6
    style Catalog fill:#f0fdf4,stroke:#16a34a
```

## Alert Rule Engine

```mermaid
flowchart TD
    Change[Schema Change<br/>Detected] --> Eval[Evaluate All<br/>Active Rules]

    Eval --> Scope{Scope<br/>Match?}

    Scope -->|DATASET| DS[Dataset ID<br/>matches?]
    Scope -->|TAG| TG[Dataset has<br/>this tag?]
    Scope -->|LINEAGE| LN[Dataset in this<br/>lineage?]
    Scope -->|PLATFORM| PF[Dataset on this<br/>platform?]
    Scope -->|ALL| AL[Always match]

    DS --> Trigger
    TG --> Trigger
    LN --> Trigger
    PF --> Trigger
    AL --> Trigger

    Trigger{Trigger<br/>Match?}

    Trigger -->|ANY| T1[All changes]
    Trigger -->|SCHEMA_CHANGE| T2[DROP/MODIFY<br/>filter]
    Trigger -->|COLUMN_WATCH| T3[Specific columns<br/>only]
    Trigger -->|MAPPING_BROKEN| T4[Mapped columns<br/>changed]

    T1 --> Severity
    T2 --> Severity
    T3 --> Severity
    T4 --> Severity

    Severity[Determine<br/>Severity]
    Severity -->|Column DROP| BRK[BREAKING]
    Severity -->|Type change| WRN[WARNING]
    Severity -->|Other| INF[INFO]

    BRK --> Create[Create Alert]
    WRN --> Create
    INF --> Create

    Create --> Notify[Dispatch<br/>Notifications]
    Notify --> APP[IN_APP<br/>Bell Badge]
    Notify --> WH[WEBHOOK<br/>Slack/Teams]
    Notify --> OWN[Dataset<br/>Owners]

    style Change fill:#fecaca,stroke:#dc2626
    style Create fill:#bbf7d0,stroke:#16a34a
    style BRK fill:#fecaca,stroke:#dc2626
    style WRN fill:#fef3c7,stroke:#d97706
    style INF fill:#e0f2fe,stroke:#0284c7
```

## Data Standard - Morpheme Analysis

```mermaid
flowchart LR
    Input["Input<br/>고객전화번호"] --> Analyze[Greedy Longest<br/>Match]

    subgraph Dict["Word Dictionary"]
        W1["고객<br/>CUST<br/>GENERAL"]
        W2["전화<br/>TEL<br/>GENERAL"]
        W3["번호<br/>NO<br/>SUFFIX"]
    end

    Dict --> Analyze

    Analyze --> Decompose["고객 + 전화 + 번호"]

    Decompose --> AutoGen[Auto Generate]

    AutoGen --> English["English:<br/>Customer Telephone Number"]
    AutoGen --> Abbr["Abbreviation:<br/>CUST_TEL_NO"]
    AutoGen --> Physical["Physical Name:<br/>cust_tel_no"]

    W3 -->|"SUFFIX → Domain"| Domain["Domain: 번호<br/>VARCHAR(20)"]

    Physical --> Mapping[Auto-Map<br/>to Dataset Columns]
    Domain --> Mapping

    Mapping --> Match["cust_tel_no = cust_tel_no<br/>✅ MATCHED"]
    Mapping --> Viol["phone_num ≠ cust_tel_no<br/>⚠️ VIOLATION"]
    Mapping --> Unmap["created_at<br/>⬜ UNMAPPED"]

    Match --> Rate["Compliance Rate<br/>78%"]
    Viol --> Rate
    Unmap --> Rate

    style Input fill:#e0f2fe,stroke:#0284c7
    style Dict fill:#fef3c7,stroke:#d97706
    style Domain fill:#f3e8ff,stroke:#9333ea
    style Rate fill:#f0fdf4,stroke:#16a34a
    style Match fill:#bbf7d0,stroke:#16a34a
    style Viol fill:#fecaca,stroke:#dc2626
```

## AI Journey - Enterprise Data to AI

```mermaid
flowchart TB
    subgraph DC["🗂 Data Catalog"]
        direction TB
        S1["1. 데이터 가시화"] --> S2["2. 데이터 이해"]
    end

    S2 --> S3["3. 데이터 연결"]

    subgraph BD["📊 Big Data"]
        direction TB
        S4["4. 데이터 통합"]
    end

    S3 --> S4
    S4 --> S5["5. 분석 고도화"]

    subgraph AI["🤖 AI"]
        direction TB
        S6["6. AI 모델 개발"] --> S7["7. AI 서빙/운영"]
    end

    S5 --> S6

    S3 -.- DC
    S3 -.- BD
    S5 -.- BD
    S5 -.- AI

    style DC fill:#e0f2fe,stroke:#0284c7
    style BD fill:#f3e8ff,stroke:#9333ea
    style AI fill:#fce7f3,stroke:#db2777

    style S1 fill:#fff,stroke:#0284c7
    style S2 fill:#fff,stroke:#3b82f6
    style S3 fill:#e8e0ff,stroke:#6366f1,stroke-width:3px
    style S4 fill:#fff,stroke:#7c3aed
    style S5 fill:#f5e0f0,stroke:#9333ea,stroke-width:3px
    style S6 fill:#fff,stroke:#c026d3
    style S7 fill:#fff,stroke:#db2777
```
