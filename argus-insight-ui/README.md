# Argus Frontend


## Build & Run


### Install `pnpm`

Node 16 버전 이상인 경우 다음의 커맨드를 실행합니다.

```bash
corepack enable
```

### Install Package

```bash
pnpm install
```

### Run

```bash
pnpm run dev --host 10.0.1.50
```

## 프로젝트 구조

### 전체 구조

```
argus-frontend/
├── apps/
│   └── web/               # Next.js 16 메인 앱
├── packages/
│   ├── ui/                # 공유 UI 컴포넌트 라이브러리 (@workspace/ui)
│   ├── eslint-config/     # 공유 ESLint 설정
│   └── typescript-config/ # 공유 TypeScript 설정
├── turbo.json             # Turbo 빌드 오케스트레이션
├── pnpm-workspace.yaml    # pnpm 워크스페이스 설정
└── package.json           # 루트 패키지
```

### 기술 스택

| 항목 | 버전/도구 |
|------|-----------|
| 패키지 매니저 | pnpm 9.0.6 |
| 빌드 오케스트레이터 | Turbo 2.8.8 |
| 프레임워크 | Next.js 16.1.6 |
| 리액트 | React 19.2.4 |
| CSS | Tailwind CSS v4 |
| UI 라이브러리 | shadcn/ui + Radix UI |
| 타입 | TypeScript 5.9.3 |

### 패키지 간 의존 관계

```
web (Next.js App)
  └─ imports ──→ @workspace/ui (컴포넌트, cn 유틸, CSS)
  └─ uses ─────→ @workspace/eslint-config/next-js
  └─ uses ─────→ @workspace/typescript-config/nextjs

@workspace/ui
  └─ uses ─────→ @workspace/eslint-config/react-internal
  └─ uses ─────→ @workspace/typescript-config/react-library
```

### 주요 파일 위치

| 파일 | 경로 |
|------|------|
| 글로벌 CSS | `packages/ui/src/styles/globals.css` |
| cn() 유틸 | `packages/ui/src/lib/utils.ts` |
| UI 컴포넌트 | `packages/ui/src/components/` |
| 앱 페이지 | `apps/web/app/` |
| ThemeProvider | `apps/web/components/theme-provider.tsx` |

---

## Adding components

To add components to your app, run the following command at the root of your `web` app:

```bash
pnpm dlx shadcn@latest add button -c apps/web
```

This will place the ui components in the `packages/ui/src/components` directory.

## Using components

To use the components in your app, import them from the `ui` package.

```tsx
import { Button } from "@workspace/ui/components/button";
```
