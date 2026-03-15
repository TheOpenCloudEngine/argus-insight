# Argus Insight UI

Argus Insight 플랫폼의 **프론트엔드 웹 애플리케이션**입니다. shadcn-admin을 기반으로 구성되었으며, Turborepo 모노레포 구조로 관리됩니다.

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
| 테마 | next-themes (light/dark/system) |
| 모노레포 | Turborepo + pnpm workspace |
| 린터/포맷터 | ESLint 9 + Prettier |
| Node.js | >= 20 |
| 패키지 매니저 | pnpm 9.x |

## 프로젝트 구조

```
argus-insight-ui/
├── package.json               # 루트 패키지 (워크스페이스 설정)
├── pnpm-workspace.yaml        # pnpm 워크스페이스 정의
├── turbo.json                 # Turborepo 태스크 설정
├── tsconfig.json              # 루트 TypeScript 설정
├── .eslintrc.js               # 루트 ESLint 설정
├── .prettierrc                # Prettier 설정
├── .npmrc                     # npm 레지스트리 설정
├── apps/
│   └── web/                   # Next.js 웹 애플리케이션
│       ├── app/               # App Router 페이지
│       ├── components/        # 공통 컴포넌트
│       ├── features/          # 기능별 모듈 (users, configuration)
│       ├── hooks/             # 커스텀 React 훅
│       ├── lib/               # 유틸리티, API 클라이언트
│       ├── types/             # TypeScript 타입 정의
│       └── data/              # 정적 데이터 (메뉴, 설정)
└── packages/
    ├── ui/                    # 공유 UI 컴포넌트 라이브러리
    │   ├── src/components/    # shadcn/ui 기반 컴포넌트 (~23개)
    │   ├── src/hooks/         # 공유 훅
    │   ├── src/lib/           # cn() 유틸리티
    │   └── src/styles/        # globals.css (Tailwind + 테마 변수)
    ├── eslint-config/         # 공유 ESLint 설정
    └── typescript-config/     # 공유 TypeScript 설정
```

## 라우트 구조 (App Router)

| 경로 | 페이지 | 설명 |
|------|--------|------|
| `/` | `app/page.tsx` | 대시보드로 리다이렉트 |
| `/dashboard` | `app/dashboard/page.tsx` | 대시보드 개요 (통계, 알림, 서버 상태) |
| `/dashboard/users` | `app/dashboard/users/page.tsx` | 사용자 관리 |
| `/dashboard/configuration` | `app/dashboard/configuration/page.tsx` | 서비스 설정 |

레이아웃:
- `app/layout.tsx` - 루트 레이아웃 (ThemeProvider)
- `app/dashboard/layout.tsx` - 대시보드 레이아웃 (사이드바 + 헤더)

## 주요 컴포넌트

### 공통 컴포넌트 (`apps/web/components/`)

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| AppSidebar | `app-sidebar.tsx` | 메인 네비게이션 사이드바 (async server component) |
| AppSidebarNav | `app-sidebar-nav.tsx` | 네비게이션 그룹 렌더링 (client) |
| AppSidebarUser | `app-sidebar-user.tsx` | 사용자 프로필 드롭다운 (client) |
| DashboardHeader | `dashboard-header.tsx` | 헤더 (검색, 알림, 테마 토글) |
| ThemeProvider | `theme-provider.tsx` | 테마 제공자 (D 키로 토글) |
| ConfirmDialog | `confirm-dialog.tsx` | 확인 다이얼로그 |

### Data Table (`apps/web/components/data-table/`)

재사용 가능한 데이터 테이블 컴포넌트 세트:
- `toolbar.tsx` - 검색, 필터, 뷰 옵션
- `pagination.tsx` - 페이지네이션 (페이지 번호 버튼)
- `column-header.tsx` - 정렬 가능한 컬럼 헤더
- `faceted-filter.tsx` - 다중 선택 필터
- `view-options.tsx` - 컬럼 표시/숨김
- `bulk-actions.tsx` - 선택된 행에 대한 일괄 작업 바

### 공유 UI 컴포넌트 (`packages/ui/src/components/`)

shadcn/ui 기반 컴포넌트 라이브러리 (~23개):
button, input, label, form, checkbox, radio-group, select, textarea, dialog, alert-dialog, card, badge, avatar, tooltip, popover, dropdown-menu, table, tabs, separator, skeleton, sheet, sidebar, command

## 기능 모듈 (Feature Modules)

### Users (`apps/web/features/users/`)

사용자 CRUD 관리 기능:

| 파일 | 설명 |
|------|------|
| `components/users-table.tsx` | TanStack Table 기반 사용자 목록 |
| `components/users-columns.tsx` | 컬럼 정의 (선택, 이름, 이메일, 상태, 역할, 액션) |
| `components/users-provider.tsx` | Context Provider (다이얼로그/필터 상태) |
| `components/users-primary-buttons.tsx` | 활성화/비활성화/추가 버튼 |
| `components/users-action-dialog.tsx` | 사용자 추가/수정 폼 (React Hook Form + Zod) |
| `components/users-delete-dialog.tsx` | 삭제 확인 다이얼로그 |
| `components/users-status-dialog.tsx` | 일괄 활성화/비활성화 |
| `data/schema.ts` | Zod 검증 스키마 |
| `data/users.ts` | 목업 사용자 데이터 (15명) |
| `data/data.ts` | 역할/상태 매핑 |

### Configuration (`apps/web/features/configuration/`)

서비스 설정 관리:
- `components/service-configuration.tsx` - 설정 폼 빌더
- `components/config-field.tsx` - 필드 타입별 렌더러 (checkbox, text, radio, textarea, key-value)

## 데이터 모델

### User

```typescript
{
  id: string
  firstName: string
  lastName: string
  username: string
  email: string
  phoneNumber: string
  status: "active" | "inactive"
  role: "admin" | "user"
  createdAt: Date
  updatedAt: Date
}
```

### Menu

```typescript
{
  groups: [{
    id: string
    label: string
    items: [{ id, title, url, icon }]
  }]
}
```

## 핵심 패턴

- **Context + Hooks**: 기능별 React Context (UsersProvider)로 상태 관리
- **Server Components**: AppSidebar 등 서버 컴포넌트로 데이터 fetch
- **폼 검증**: React Hook Form + Zod 스키마 기반 검증
- **데이터 테이블**: TanStack Table + 정렬/필터/페이지네이션/일괄작업
- **경로 별칭**: `@/` (앱 내부), `@workspace/ui/*` (공유 패키지)
- **테마**: next-themes + CSS 변수 (OKLCH), D 키 토글

## 주요 명령어

```bash
# 작업 디렉토리
cd argus-insight-ui

# 의존성 설치
pnpm install

# 개발 서버 실행 (Turbopack)
pnpm dev

# 프로덕션 빌드
pnpm build

# 린트 검사
pnpm lint

# 코드 포맷팅
pnpm format
```

## 설정 파일

### turbo.json

Turborepo 태스크 설정. `build`는 의존 패키지 빌드 후 실행, `dev`는 캐시 없이 persistent 모드.

### pnpm-workspace.yaml

`apps/*`와 `packages/*`를 워크스페이스로 관리.

### components.json (shadcn/ui)

shadcn/ui CLI 설정. `radix-vega` 스타일, RSC 활성화, `neutral` 기본 색상.

### .npmrc

npm 레지스트리를 내부 Nexus 서버(`http://10.0.1.50:8081/repository/npm-public/`)로 지정.

## 새 페이지 추가 방법

1. `apps/web/app/dashboard/{페이지명}/page.tsx` 생성
2. 필요 시 `apps/web/features/{기능명}/` 디렉토리에 컴포넌트, 스키마, 데이터 구성
3. `apps/web/data/menu.json`에 메뉴 항목 추가
4. `apps/web/lib/icon-map.ts`에 아이콘 매핑 추가 (새 아이콘 사용 시)

## 새 공유 컴포넌트 추가 방법

1. `packages/ui/src/components/{컴포넌트}.tsx` 생성
2. `packages/ui/package.json`의 exports에 경로 추가 (필요 시)
3. 앱에서 `import { Component } from "@workspace/ui/components/{컴포넌트}"` 사용

## 인증 (TODO)

- `apps/web/lib/session.ts`에 세션 관리 스텁 구현됨 (목업 데이터)
- 세션 쿠키: `argus_session`
- 실제 인증 연동은 TODO 상태
