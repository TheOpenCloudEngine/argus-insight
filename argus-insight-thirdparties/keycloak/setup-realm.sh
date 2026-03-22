#!/bin/bash
#
# Keycloak Realm Setup Script
#
# Creates the 'argus' realm, 'argus-client' client, realm roles,
# and an admin user with argus-admin role.
#
# Prerequisites:
#   - Keycloak running at KEYCLOAK_URL (default: http://localhost:8180)
#   - Master realm admin credentials
#
# Usage:
#   ./setup-realm.sh
#   KEYCLOAK_URL=http://keycloak:8080 ./setup-realm.sh

set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
MASTER_USER="${MASTER_USER:-admin}"
MASTER_PASS="${MASTER_PASS:-admin}"

REALM="argus"
CLIENT_ID="argus-client"
CLIENT_SECRET="argus-client-secret"

echo "=== Keycloak Realm Setup ==="
echo "Keycloak URL: $KEYCLOAK_URL"
echo ""

# ---------------------------------------------------------------------------
# 1. Get master admin token
# ---------------------------------------------------------------------------
echo "[1/7] Getting admin token..."
TOKEN=$(curl -sf -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "username=$MASTER_USER&password=$MASTER_PASS&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  OK"

# ---------------------------------------------------------------------------
# 2. Create realm
# ---------------------------------------------------------------------------
echo "[2/7] Creating realm '$REALM'..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "realm": "'"$REALM"'",
    "enabled": true,
    "displayName": "Argus",
    "sslRequired": "none",
    "registrationAllowed": false,
    "loginWithEmailAllowed": true,
    "duplicateEmailsAllowed": false,
    "resetPasswordAllowed": true,
    "bruteForceProtected": true,
    "accessTokenLifespan": 3600,
    "ssoSessionIdleTimeout": 1800,
    "ssoSessionMaxLifespan": 36000
  }')
if [ "$HTTP" = "201" ]; then
  echo "  Created"
elif [ "$HTTP" = "409" ]; then
  echo "  Already exists (skipped)"
else
  echo "  Failed (HTTP $HTTP)"
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Create client
# ---------------------------------------------------------------------------
echo "[3/7] Creating client '$CLIENT_ID'..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "'"$CLIENT_ID"'",
    "name": "Argus Client",
    "enabled": true,
    "protocol": "openid-connect",
    "publicClient": false,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": true,
    "directAccessGrantsEnabled": true,
    "secret": "'"$CLIENT_SECRET"'",
    "redirectUris": ["http://localhost:3000/*", "http://localhost:4600/*"],
    "webOrigins": ["http://localhost:3000", "http://localhost:4600", "+"]
  }')
if [ "$HTTP" = "201" ]; then
  echo "  Created"
elif [ "$HTTP" = "409" ]; then
  echo "  Already exists (skipped)"
else
  echo "  Failed (HTTP $HTTP)"
  exit 1
fi

# ---------------------------------------------------------------------------
# 4. Create realm roles
# ---------------------------------------------------------------------------
echo "[4/7] Creating realm roles..."
for ROLE_NAME in argus-admin argus-superuser argus-user; do
  case $ROLE_NAME in
    argus-admin)     DESC="Argus Administrator" ;;
    argus-superuser) DESC="Argus Super User" ;;
    argus-user)      DESC="Argus User" ;;
  esac
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms/$REALM/roles" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"'"$ROLE_NAME"'","description":"'"$DESC"'"}')
  if [ "$HTTP" = "201" ]; then
    echo "  $ROLE_NAME - Created"
  elif [ "$HTTP" = "409" ]; then
    echo "  $ROLE_NAME - Already exists (skipped)"
  else
    echo "  $ROLE_NAME - Failed (HTTP $HTTP)"
  fi
done

# ---------------------------------------------------------------------------
# 5. Set argus-user as default role
# ---------------------------------------------------------------------------
echo "[5/7] Setting argus-user as default role..."
DEFAULT_ROLE_ID=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/roles/default-roles-$REALM" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")

ARGUS_USER_ROLE_ID=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/roles/argus-user" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

if [ -n "$DEFAULT_ROLE_ID" ]; then
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$KEYCLOAK_URL/admin/realms/$REALM/roles-by-id/$DEFAULT_ROLE_ID/composites" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '[{"id":"'"$ARGUS_USER_ROLE_ID"'","name":"argus-user"}]')
  if [ "$HTTP" = "204" ]; then
    echo "  OK"
  else
    echo "  Skipped (HTTP $HTTP, may already be set)"
  fi
else
  echo "  Skipped (default-roles-$REALM not found)"
fi

# ---------------------------------------------------------------------------
# 6. Create admin user
# ---------------------------------------------------------------------------
echo "[6/7] Creating admin user..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms/$REALM/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@argus.local",
    "firstName": "Admin",
    "lastName": "User",
    "enabled": true,
    "emailVerified": true,
    "credentials": [{"type": "password", "value": "admin", "temporary": false}]
  }')
if [ "$HTTP" = "201" ]; then
  echo "  Created"
elif [ "$HTTP" = "409" ]; then
  echo "  Already exists (skipped)"
else
  echo "  Failed (HTTP $HTTP)"
  exit 1
fi

# ---------------------------------------------------------------------------
# 7. Assign argus-admin role to admin user
# ---------------------------------------------------------------------------
echo "[7/7] Assigning argus-admin role to admin user..."
USER_ID=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/users?username=admin&exact=true" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

ADMIN_ROLE_ID=$(curl -sf "$KEYCLOAK_URL/admin/realms/$REALM/roles/argus-admin" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "$KEYCLOAK_URL/admin/realms/$REALM/users/$USER_ID/role-mappings/realm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"id":"'"$ADMIN_ROLE_ID"'","name":"argus-admin"}]')
if [ "$HTTP" = "204" ]; then
  echo "  OK"
else
  echo "  Skipped (HTTP $HTTP, may already be assigned)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Realm:    $REALM"
echo "  Client:   $CLIENT_ID (secret: $CLIENT_SECRET)"
echo "  Roles:    argus-admin, argus-superuser, argus-user"
echo "  Default:  argus-user"
echo "  User:     admin / admin (argus-admin)"
echo ""
echo "  Admin Console: $KEYCLOAK_URL/admin"
echo "  Token URL:     $KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token"
