# RAG UI

Argus RAG Server의 프론트엔드 웹 애플리케이션입니다. Collection 관리, 검색 테스트, 데이터 소스 관리, 설정 등을 제공합니다.

## 기술 스택

- Next.js 16, React 19, TypeScript 5.9
- Tailwind CSS v4
- Lucide React (아이콘)
- Sonner (토스트 알림)
- Recharts (차트)

## 주요 페이지

| 경로 | 기능 |
|------|------|
| /dashboard | 전체 통계 대시보드 (Collection 수, 문서 수, 임베딩 커버리지) |
| /dashboard/collections | Collection 목록, 생성, 삭제, 동기화 |
| /dashboard/collections/[id] | Collection 상세 — 문서, 소스, 작업 이력, 임베딩 관리 |
| /dashboard/search | 검색 Playground — 하이브리드 검색 테스트, 가중치 조절 |
| /dashboard/sources | 전체 데이터 소스 현황, 수동 동기화 트리거 |
| /dashboard/jobs | 작업 이력 (전체 Collection 통합) |
| /dashboard/settings | 임베딩 모델 설정, 청킹 전략 설정 |

## 프로젝트 구조

```
argus-rag-ui/
├── apps/web/
│   ├── app/
│   │   ├── layout.tsx              # 루트 레이아웃
│   │   ├── page.tsx                # → /dashboard 리다이렉트
│   │   └── dashboard/
│   │       ├── layout.tsx          # 사이드바 + 메인 영역
│   │       ├── page.tsx            # 대시보드
│   │       ├── collections/        # Collection 목록 + 상세
│   │       ├── search/             # 검색 Playground
│   │       ├── sources/            # 데이터 소스
│   │       ├── settings/           # 설정
│   │       └── jobs/               # 작업 이력
│   ├── lib/api.ts                  # API 클라이언트 (타입 포함)
│   ├── middleware.ts               # /api/v1/* → :4800 프록시
│   └── .env.development            # API_BASE_URL=http://localhost:4800
├── package.json
├── pnpm-workspace.yaml
└── turbo.json
```

## 주요 명령어

```bash
cd argus-rag-ui
pnpm install
pnpm dev       # 개발 서버 (Turbopack)
pnpm build     # 빌드
```

## API 프록시

Next.js middleware가 `/api/v1/*` 요청을 `API_BASE_URL`(기본 `http://localhost:4800`)로 프록시합니다.
