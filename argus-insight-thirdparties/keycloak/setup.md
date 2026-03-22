# Keycloak Setup

## Prerequisites

- Docker and Docker Compose installed
- Keycloak container running (`docker compose up -d`)
- `curl` and `python3` available

## Quick Start

```bash
cd keycloak

# 1. Start Keycloak
docker compose up -d

# 2. Wait for Keycloak to be ready (takes ~30 seconds)
until curl -sf http://localhost:8180/realms/master > /dev/null 2>&1; do
  echo "Waiting for Keycloak..."; sleep 5
done

# 3. Run setup script
./setup-realm.sh
```

## setup-realm.sh

Automates the initial Keycloak configuration:

| Step | Action |
|------|--------|
| 1 | Get master admin token |
| 2 | Create `argus` realm |
| 3 | Create `argus-client` client (confidential, secret: `argus-client-secret`) |
| 4 | Create realm roles: `argus-admin`, `argus-superuser`, `argus-user` |
| 5 | Set `argus-user` as default role for new users |
| 6 | Create `admin` user (password: `admin`, email: `admin@argus.local`) |
| 7 | Assign `argus-admin` role to `admin` user |

The script is idempotent — already existing items are skipped.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | `http://localhost:8180` | Keycloak server URL |
| `MASTER_USER` | `admin` | Master realm admin username |
| `MASTER_PASS` | `admin` | Master realm admin password |

### Examples

```bash
# Default (localhost:8180)
./setup-realm.sh

# Custom Keycloak URL
KEYCLOAK_URL=http://keycloak:8080 ./setup-realm.sh

# Custom master credentials
MASTER_USER=myadmin MASTER_PASS=mypass ./setup-realm.sh
```

## Docker Compose Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker logs -f argus-keycloak

# Restart
docker compose restart
```

## Access

| Service | URL |
|---------|-----|
| Admin Console | http://localhost:8180/admin (admin / admin) |
| Realm Settings | http://localhost:8180/admin/master/console/#/argus |
| OIDC Discovery | http://localhost:8180/realms/argus/.well-known/openid-configuration |
