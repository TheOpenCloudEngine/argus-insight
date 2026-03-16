# Argus Insight

## 목표

확장가능한 Data + AI Platform으로서 데이터의 전 생명주기 동안 활용할 수 있는 소프트웨어 스택과 관리 방법을 제공하고, 이를 통해 데이터를 잘 활용하고 가치있게 만들 수 있는 플랫폼을 만든 것을 목표로 합니다.

## 제공하는 핵심 기능

* Data + AI Software Stack
* Kubernetes EcoSystem
* Data Catalog
* Data Science Workbench

## Architecture

### Overview

Argus Insight는 데이터의 전 생명주기를 관리하는 지능형 Data + AI Platform입니다.
Kubernetes 기반의 소프트웨어 스택 배포, 서버 리소스 모니터링, DNS 관리, 워크스페이스 협업 등을 통합 제공합니다.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Argus Insight UI (Next.js)                         │
│                                                                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Dashboard  │ │ Host Mgmt  │ │ App Deploy │ │  Workspace  │ │ Monitoring  │   │
│  │ (Charts)   │ │ (DNS)      │ │ (K8s)      │ │ (Collab)    │ │ (Grafana)   │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬──────┘ └──────┬──────┘   │
└────────┼───────────────┼──────────────┼───────────────┼───────────────┼─────────┘
         │               │              │               │               │
         ▼               ▼              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Argus Insight Server (FastAPI)                          │
│                                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Agent Mgmt   │ │ DNS Mgmt     │ │ Deploy Mgmt  │ │ Workspace & Auth     │    │
│  │ (Heartbeat)  │ │ (PowerDNS)   │ │ (K8s+Harbor) │ │ (User/Collaboration) │    │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────────────────────┘    │
└─────────┼────────────────┼────────────────┼─────────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────────────────────────────────────┐
│ Argus Insight  │ │   PowerDNS   │ │              Kubernetes Cluster              │
│ Agent          │ │              │ │                                              │
│ ┌────────────┐ │ │ FQDN 기반     │ │  ┌─────────────────────────────────────────┐ │
│ │ CPU/Memory │ │ │ 도메인 관리     │ │  │         Software Stack (Helm)           │ │
│ │ Disk/Net   │ │ │ 호스트 연동     │ │  │                                         │ │
│ │ OS Info    │ │ │              │ │  │  Data Ingestion    Data Processing      │ │
│ └────────────┘ │ └──────────────┘ │  │  ┌───────┐        ┌───────┐ ┌────────┐  │ │
│                │                  │  │  │ NiFi  │        │ Spark │ │Airflow │  │ │
│ Heartbeat ─────┤                  │  │  └───┬───┘        └───────┘ └────────┘  │ │
│ (60s interval) │                  │  │      │                                  │ │
└────────────────┘                  │  │  Messaging        Query Engine          │ │
                                    │  │  ┌───────┐        ┌───────┐ ┌─────────┐ │ │
                                    │  │  │ Kafka │        │ Trino │ │Starrocks│ │ │
┌──────────────────────────────┐    │  │  └───────┘        └───────┘ └─────────┘ │ │
│       Harbor Registry        │    │  │                                         │ │
│                              │    │  │  AI/ML             Development          │ │
│  ┌────────────┐ ┌──────────┐ │    │  │  ┌───────┐ ┌────┐ ┌──────┐ ┌─────────┐  │ │
│  │ Docker     │ │ Helm     │ │    │  │  │MLFlow │ │AI  │ │VS    │ │Jupyter  │  │ │
│  │ Images     │ │ Charts   │ │────│──│  │       │ │Agt │ │Code  │ │Notebook │  │ │
│  └────────────┘ └──────────┘ │    │  │  └───────┘ └────┘ └──────┘ └─────────┘  │ │
└──────────────────────────────┘    │  │  ┌───────┐                              │ │
                                    │  │  │KServe │  Model Serving               │ │
┌──────────────────────────────┐    │  │  └───────┘                              │ │
│       Monitoring Stack       │    │  │                                         │ │
│                              │    │  │  Catalog                                │ │
│  ┌────────────┐ ┌──────────┐ │    │  │  ┌──────────────┐                       │ │
│  │ Prometheus │→│ Grafana  │ │    │  │  │Unity Catalog │ Metadata 통합 관리      │ │
│  └────────────┘ └──────────┘ │    │  │  └──────────────┘                       │ │
└──────────────────────────────┘    │  │                                         │ │
                                    │  │  Object Storage                         │ │
                                    │  │  ┌───────┐ ┌───────┐                    │ │
                                    │  │  │ MinIO │ │ Ozone │  파일/데이터 저장      │ │
                                    │  │  └───────┘ └───────┘                    │ │
                                    │  └─────────────────────────────────────────┘ │
                                    └──────────────────────────────────────────────┘
```

### Core Components

#### Argus Insight UI

사용자 인터페이스를 제공하는 웹 애플리케이션으로, 아래 기능을 통합 관리합니다.

| 기능 | 설명 |
|------|------|
| Dashboard | Agent가 수집한 서버 리소스(CPU, Memory, Disk, Network)를 차트로 시각화 |
| Host Management | 호스트 등록/삭제, PowerDNS 연동을 통한 FQDN 도메인 관리 |
| App Deployment | Kubernetes 클러스터에 소프트웨어 스택 배포 및 관리 |
| Workspace | 사용자 로그인 후 워크스페이스 생성, 공동 작업자 초대 및 협업 |
| Image Management | Harbor와 연계한 Docker Image 및 Helm Chart 관리 |

#### Argus Insight Server

UI의 요청을 처리하고 Agent, PowerDNS, Kubernetes, Harbor 등 외부 시스템과 연동하는 중앙 서버입니다.

- Agent로부터 Heartbeat를 수신하여 서버 상태 관리
- PowerDNS API를 통해 FQDN 기반 도메인/호스트 CRUD 수행
- Harbor API를 통해 이미지 조회 및 Kubernetes 배포 연계
- 사용자 인증, 워크스페이스, 권한 관리

#### Argus Insight Agent

관리 대상 서버에 설치되어 리소스 정보를 수집하고 Server에 전송하는 에이전트입니다.

- 60초 간격 Heartbeat 송신 (CPU, Memory, Disk, Network, OS 정보)
- 원격 명령 실행, 패키지 관리, WebSocket 터미널 제공

### Infrastructure Services

#### PowerDNS — DNS Management

플랫폼의 모든 서버는 PowerDNS를 통해 FQDN 형식의 도메인을 관리합니다.
Argus Insight UI에서 호스트를 등록/삭제하면 Server가 PowerDNS와 연동하여 DNS 레코드를 자동 관리합니다.

#### Harbor — Image & Chart Registry

Docker Image와 Helm Chart를 중앙에서 관리합니다.
UI에서 이미지 관리 및 애플리케이션 배포를 요청하면 Server가 Harbor와 Kubernetes를 연계하여 작업을 수행합니다.

#### Prometheus + Grafana — Monitoring

Prometheus로 메트릭을 수집하고 Grafana 대시보드를 통해 인프라 및 애플리케이션 모니터링을 수행합니다.

### Kubernetes Software Stack

Kubernetes 클러스터에 배포 가능한 소프트웨어 스택은 다음과 같이 분류됩니다.

| Category | Components | Description |
|----------|------------|-------------|
| **Data Ingestion** | NiFi | Kafka, 외부 시스템에서 데이터를 수집하여 파이프라인 구성. MinIO/Ozone에 저장 |
| **Messaging** | Kafka | 실시간 데이터 스트리밍 및 이벤트 처리 |
| **Data Processing** | Spark, Airflow | 대규모 데이터 처리(Spark), 데이터 엔지니어링 워크플로우 자동화(Airflow) |
| **Query Engine** | Trino, StarRocks | 분산 SQL 쿼리 엔진. Unity Catalog를 통해 메타데이터 관리 |
| **Object Storage** | MinIO, Ozone | 사용자의 모든 파일 및 데이터를 저장하는 Object Storage |
| **Catalog** | Unity Catalog | 모델, 테이블, 데이터 파일 등의 메타데이터 통합 관리 |
| **AI/ML** | MLFlow, KServe, AI Agent | 모델 실험(MLFlow), 모델 서빙(KServe), AI Agent |
| **Development** | VS Code, Jupyter | 코드 작성(VS Code), 노트북 기반 연구(Jupyter) |

### User Workflow

```
사용자 로그인
    │
    ▼
Workspace 생성
    │
    ├──▶ 공동 작업자 초대 (협업, Fine-Tuning 등)
    │
    ├──▶ 애플리케이션 배포 (Kubernetes + Harbor)
    │     └── Kafka, Spark, Jupyter, VS Code, MLFlow ...
    │
    ├──▶ 데이터 파이프라인 구성
    │     └── NiFi → Kafka → Spark/Airflow → MinIO/Ozone
    │
    ├──▶ 데이터 분석 및 쿼리
    │     └── Trino / StarRocks (Unity Catalog 메타데이터 연동)
    │
    ├──▶ ML 실험 및 모델 서빙
    │     └── Jupyter/VS Code → MLFlow → KServe
    │
    └──▶ 서버 모니터링
          └── Dashboard (Agent 데이터) + Grafana (Prometheus)
```

## License

Apache License 2.0
