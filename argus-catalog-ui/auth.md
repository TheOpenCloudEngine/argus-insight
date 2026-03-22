# Argus Catalog SSO Authentication

## Overview

Argus Catalog uses **Keycloak** as the Identity Provider (IdP) for Single Sign-On (SSO) via the **OpenID Connect (OIDC)** protocol. The authentication flow involves three components:

1. **Keycloak Server** - Issues and manages JWT tokens
2. **argus-catalog-server (Backend)** - Verifies JWT tokens and protects API endpoints
3. **argus-catalog-ui (Frontend)** - Manages login UI, token storage, and authenticated API calls

## Architecture

```
┌─────────────────┐      OIDC/JWT       ┌─────────────────────┐
│   Keycloak       │◄───────────────────►│  argus-catalog-     │
│   (Port 8180)    │   Token issuance    │  server (Port 4600) │
│                  │   Token verification│                     │
└────────┬─────────┘                     └──────────┬──────────┘
         │                                          │
         │  PostgreSQL (keycloak DB)                 │ PostgreSQL (argus_catalog DB)
         │                                          │
         ▼                                          ▼
┌─────────────────┐                      ┌─────────────────────┐
│  PostgreSQL      │                     │  argus-catalog-ui   │
│  (Port 5432)     │                     │  (Port 3000)        │
└─────────────────┘                      └─────────────────────┘
```

## Keycloak Configuration

### Server

| Property          | Value                                  |
|-------------------|----------------------------------------|
| Image             | `quay.io/keycloak/keycloak:26.1`       |
| Container Name    | `argus-keycloak`                       |
| Host Port         | `8180` (mapped to container port 8080) |
| Admin Console     | `http://localhost:8180/admin`          |
| Admin Username    | `admin`                                |
| Admin Password    | `admin`                                |
| Database          | PostgreSQL (`keycloak` database)       |
| DB User           | `argus`                                |
| Startup Mode      | `start-dev` (development mode)         |

### Docker Compose

Location: `/root/projects/argus-insight/keycloak/docker-compose.yml`

```bash
# Start Keycloak
cd keycloak && docker compose up -d

# Stop Keycloak
cd keycloak && docker compose down

# View logs
docker logs -f argus-keycloak
```

### Realm: argus-catalog

| Property                | Value                             |
|-------------------------|-----------------------------------|
| Realm Name              | `argus-catalog`                   |
| SSL Required             | `none` (dev mode)                |
| Access Token Lifespan   | `3600` seconds (1 hour)           |
| SSO Session Idle Timeout| `1800` seconds (30 minutes)       |
| SSO Session Max Lifespan| `36000` seconds (10 hours)        |
| Brute Force Protection  | Enabled                           |

### Clients

#### argus-catalog-server (Backend - Confidential)

| Property                    | Value                               |
|-----------------------------|-------------------------------------|
| Client ID                   | `argus-catalog-server`              |
| Client Type                 | Confidential (non-public)           |
| Client Secret               | `argus-catalog-server-secret`       |
| Standard Flow Enabled       | `false`                             |
| Direct Access Grants        | `true`                              |
| Service Accounts Enabled    | `true`                              |

#### argus-catalog-ui (Frontend - Public)

| Property                    | Value                               |
|-----------------------------|-------------------------------------|
| Client ID                   | `argus-catalog-ui`                  |
| Client Type                 | Public                              |
| Standard Flow Enabled       | `true`                              |
| Redirect URIs               | `http://localhost:3000/*`, `http://localhost:4600/*` |
| Web Origins                 | `http://localhost:3000`, `http://localhost:4600`, `+` |

### Realm Roles

| Role Name       | Description                  |
|-----------------|------------------------------|
| `catalog-admin` | Argus Catalog Administrator  |
| `catalog-user`  | Argus Catalog User           |

### Test Users

| Username | Password | Email                        | Roles          |
|----------|----------|------------------------------|----------------|
| `admin`  | `admin`  | `admin@argus-catalog.local`  | `catalog-admin` |

## OIDC Endpoints

| Endpoint     | URL                                                                            |
|--------------|--------------------------------------------------------------------------------|
| Token        | `http://localhost:8180/realms/argus-catalog/protocol/openid-connect/token`      |
| Authorization| `http://localhost:8180/realms/argus-catalog/protocol/openid-connect/auth`       |
| UserInfo     | `http://localhost:8180/realms/argus-catalog/protocol/openid-connect/userinfo`   |
| JWKS         | `http://localhost:8180/realms/argus-catalog/protocol/openid-connect/certs`      |
| Logout       | `http://localhost:8180/realms/argus-catalog/protocol/openid-connect/logout`     |
| Well-Known   | `http://localhost:8180/realms/argus-catalog/.well-known/openid-configuration`   |

## Backend (argus-catalog-server) Integration

### Configuration

**config.yml** (`packaging/config/config.yml`):
```yaml
auth:
  type: keycloak
  keycloak:
    server_url: http://localhost:8180
    realm: argus-catalog
    client_id: argus-catalog-server
    client_secret: argus-catalog-server-secret
    admin_role: catalog-admin
    user_role: catalog-user
```

**config.properties** (`packaging/config/config.properties`):
```properties
auth.type=keycloak
auth.keycloak.server_url=http://localhost:8180
auth.keycloak.realm=argus-catalog
auth.keycloak.client_id=argus-catalog-server
auth.keycloak.client_secret=argus-catalog-server-secret
auth.keycloak.admin_role=catalog-admin
auth.keycloak.user_role=catalog-user
```

### Dependencies

```
python-jose[cryptography]>=3.4.0   # JWT token decoding and verification
cachetools>=5.3.0                   # TTL cache for JWKS keys
```

### Auth Module (`app/core/auth.py`)

Provides FastAPI dependency injection for route protection:

```python
from app.core.auth import CurrentUser, AdminUser, OptionalUser

# Require authenticated user
@router.get("/protected")
async def protected(user: CurrentUser):
    return {"username": user.username, "is_admin": user.is_admin}

# Require admin role
@router.delete("/admin-only/{id}")
async def admin_only(id: int, user: AdminUser):
    ...

# Optional authentication (user may or may not be logged in)
@router.get("/public")
async def public(user: OptionalUser):
    if user:
        return {"greeting": f"Hello {user.username}"}
    return {"greeting": "Hello guest"}
```

**TokenUser fields:**
- `sub` - Keycloak user UUID
- `username` - Preferred username
- `email` - Email address
- `first_name`, `last_name` - Full name
- `roles` - Client-level roles
- `realm_roles` - Realm-level roles (includes `catalog-admin`, `catalog-user`)
- `is_admin` - `True` if user has `catalog-admin` realm role

### Auth API Endpoints (`app/auth/router.py`)

| Method | Path                   | Description                              | Auth Required |
|--------|------------------------|------------------------------------------|---------------|
| POST   | `/api/v1/auth/login`   | Authenticate user, return JWT tokens     | No            |
| POST   | `/api/v1/auth/refresh` | Refresh access token                     | No            |
| GET    | `/api/v1/auth/me`      | Get current user info from token         | Yes           |
| POST   | `/api/v1/auth/logout`  | Invalidate refresh token in Keycloak     | No            |

### Files Added/Modified (Backend)

| File                                   | Change Type | Description                                 |
|----------------------------------------|-------------|---------------------------------------------|
| `app/core/auth.py`                     | **NEW**     | JWT verification, FastAPI auth dependencies  |
| `app/auth/__init__.py`                 | **NEW**     | Auth package init                            |
| `app/auth/router.py`                   | **NEW**     | Login/refresh/me/logout endpoints            |
| `app/core/config.py`                   | MODIFIED    | Added `auth_keycloak_*` settings             |
| `app/main.py`                          | MODIFIED    | Registered `auth_router`                     |
| `requirements.txt`                     | MODIFIED    | Added `python-jose`, `cachetools`            |
| `packaging/config/config.yml`          | MODIFIED    | Added `auth` section                         |
| `packaging/config/config.properties`   | MODIFIED    | Added `auth.*` properties                    |

## Frontend (argus-catalog-ui) Integration

### Authentication Flow

1. User visits `/` -> redirected to `/login` if not authenticated
2. User submits credentials -> `POST /api/v1/auth/login` -> Keycloak issues JWT tokens
3. Tokens stored in `sessionStorage` (key: `argus_tokens`)
4. All API calls use `authFetch()` which injects `Authorization: Bearer <token>` header
5. Token auto-refreshes 60 seconds before expiry via `/api/v1/auth/refresh`
6. On 401 response, user is redirected to `/login`
7. Logout invalidates refresh token in Keycloak and clears `sessionStorage`

### Auth Feature Module (`features/auth/`)

| File               | Description                                              |
|--------------------|----------------------------------------------------------|
| `api.ts`           | API client for `/api/v1/auth/*` endpoints                |
| `auth-context.tsx` | React context provider with login/logout/token refresh   |
| `auth-fetch.ts`    | `authFetch()` - drop-in `fetch` replacement with Bearer token |
| `auth-guard.tsx`   | Route guard that redirects unauthenticated users         |
| `index.ts`         | Barrel exports                                           |

### Components

| File                           | Description                                           |
|--------------------------------|-------------------------------------------------------|
| `components/auth-provider-wrapper.tsx` | Client-side wrapper for `AuthProvider`          |
| `components/auth-guard-wrapper.tsx`    | Client-side wrapper for `AuthGuard`             |
| `components/sidebar-user.tsx`          | Sidebar footer with user info and logout button |

### Pages

| Route       | File                    | Description                     |
|-------------|-------------------------|---------------------------------|
| `/login`    | `app/login/page.tsx`    | Login form (username/password)  |
| `/`         | `app/page.tsx`          | Redirects based on auth status  |

### Files Added/Modified (Frontend)

| File                                        | Change Type | Description                              |
|---------------------------------------------|-------------|------------------------------------------|
| `features/auth/api.ts`                      | **NEW**     | Auth API client                          |
| `features/auth/auth-context.tsx`            | **NEW**     | AuthProvider with token management       |
| `features/auth/auth-fetch.ts`              | **NEW**     | Authenticated fetch wrapper              |
| `features/auth/auth-guard.tsx`             | **NEW**     | Route guard component                    |
| `features/auth/index.ts`                   | **NEW**     | Barrel exports                           |
| `components/auth-provider-wrapper.tsx`      | **NEW**     | Client wrapper for AuthProvider          |
| `components/auth-guard-wrapper.tsx`         | **NEW**     | Client wrapper for AuthGuard             |
| `components/sidebar-user.tsx`              | **NEW**     | Sidebar user display + logout            |
| `app/login/page.tsx`                       | **NEW**     | Login page                               |
| `app/layout.tsx`                           | MODIFIED    | Wrapped with `AuthProviderWrapper`       |
| `app/page.tsx`                             | MODIFIED    | Auth-based redirect                      |
| `app/dashboard/layout.tsx`                 | MODIFIED    | Wrapped with `AuthGuardWrapper`          |
| `components/app-sidebar.tsx`               | MODIFIED    | Added `SidebarUser` in footer            |
| `features/datasets/api.ts`                | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/glossary/api.ts`                | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/tags/api.ts`                    | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/users/api.ts`                   | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/settings/api.ts`               | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/comments/api.ts`               | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/filesystem/api.ts`             | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/models/api.ts`                 | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/oci-hub/api.ts`                | MODIFIED    | `fetch` -> `authFetch`                   |
| `features/datasets/components/lineage-tab.tsx` | MODIFIED | `fetch` -> `authFetch`              |

## PostgreSQL Database

### Keycloak Database

| Property      | Value           |
|---------------|-----------------|
| Database Name | `keycloak`      |
| Owner         | `argus`         |
| Encoding      | `UTF-8`         |
| Tables        | 87 (auto-created by Keycloak on first boot) |

### pg_hba.conf

Docker network access was added to allow the Keycloak container to connect:
```
host    all    argus    172.16.0.0/12    md5
```

## Keycloak Admin API Examples

```bash
# Get admin token
TOKEN=$(curl -s -X POST "http://localhost:8180/realms/master/protocol/openid-connect/token" \
  -d "username=admin&password=admin&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List realm users
curl -s "http://localhost:8180/admin/realms/argus-catalog/users" \
  -H "Authorization: Bearer $TOKEN"

# Create a new user
curl -s -X POST "http://localhost:8180/admin/realms/argus-catalog/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "enabled": true,
    "credentials": [{"type": "password", "value": "password123", "temporary": false}]
  }'
```

## Testing Authentication

```bash
# Login via backend API
curl -s -X POST http://localhost:4600/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Get current user info
curl -s http://localhost:4600/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"

# Refresh token
curl -s -X POST http://localhost:4600/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```
