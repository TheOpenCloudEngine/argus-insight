# Argus Catalog UI

DataHub 스타일의 **데이터 카탈로그 프론트엔드** 웹 애플리케이션입니다. argus-insight-ui의 shadcn-admin 템플릿을 기반으로 구성되었습니다.

## 기술 스택

| 항목 | 기술 |
|------|------|
| 프레임워크 | Next.js 16 (App Router, Turbopack) |
| UI 라이브러리 | React 19 |
| 언어 | TypeScript 5.9 |
| 스타일링 | Tailwind CSS v4 (OKLCH 색상 공간) |
| 컴포넌트 | shadcn/ui (Radix UI + CVA) |
| 폼 관리 | React Hook Form + Zod |
| 데이터 테이블 | TanStack React Table v8 |
| 아이콘 | lucide-react |
| 모노레포 | Turborepo + pnpm workspace |

## 라우트 구조

| 경로 | 설명 |
|------|------|
| `/dashboard` | 카탈로그 대시보드 (통계, 최근 데이터셋) |
| `/dashboard/datasets` | 데이터셋 목록 (검색, 필터, 페이지네이션) |
| `/dashboard/datasets/[id]` | 데이터셋 상세 (스키마, 태그, 소유자, 용어) |
| `/dashboard/platforms` | 플랫폼 관리 |
| `/dashboard/tags` | 태그 관리 |
| `/dashboard/glossary` | 비즈니스 용어집 관리 |

## 주요 명령어

```bash
cd argus-catalog-ui
pnpm install
pnpm dev       # 개발 서버 (Turbopack, port 3000)
pnpm build     # 프로덕션 빌드
pnpm lint      # ESLint
```

## 백엔드 연동

- API 프록시: `middleware.ts`에서 `/api/v1/*` 요청을 `API_BASE_URL`로 프록시
- 기본 백엔드: `http://localhost:4600` (argus-catalog-server)
