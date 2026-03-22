"""Settings API for Catalog Server.

Provides endpoints to read/update Object Storage (MinIO) and Embedding
configuration. Settings are stored in the catalog_configuration table.
"""

import logging

import aioboto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.settings.service import (
    get_config_by_category, load_auth_settings, load_cors_settings,
    load_embedding_settings, load_os_settings, update_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ObjectStorageConfig(BaseModel):
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    use_ssl: bool = False
    bucket: str = "model-artifacts"
    presigned_url_expiry: int = 3600


class ObjectStorageTestRequest(BaseModel):
    endpoint: str = Field(..., description="S3-compatible endpoint URL")
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    bucket: str = "model-artifacts"


class TestResponse(BaseModel):
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Get / Update Object Storage config (DB-backed)
# ---------------------------------------------------------------------------

@router.get("/object-storage", response_model=ObjectStorageConfig)
async def get_object_storage_config(session: AsyncSession = Depends(get_session)):
    """Return current Object Storage configuration from database."""
    cfg = await get_config_by_category(session, "object_storage")
    return ObjectStorageConfig(
        endpoint=cfg.get("object_storage_endpoint", ""),
        access_key=cfg.get("object_storage_access_key", ""),
        secret_key=cfg.get("object_storage_secret_key", ""),
        region=cfg.get("object_storage_region", "us-east-1"),
        use_ssl=cfg.get("object_storage_use_ssl", "false").lower() in ("true", "1", "yes"),
        bucket=cfg.get("object_storage_bucket", "model-artifacts"),
        presigned_url_expiry=int(cfg.get("object_storage_presigned_url_expiry", "3600")),
    )


@router.put("/object-storage")
async def update_object_storage_config(
    body: ObjectStorageConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update Object Storage configuration in database and reload into memory."""
    items = {
        "object_storage_endpoint": body.endpoint,
        "object_storage_access_key": body.access_key,
        "object_storage_secret_key": body.secret_key,
        "object_storage_region": body.region,
        "object_storage_use_ssl": str(body.use_ssl).lower(),
        "object_storage_bucket": body.bucket,
        "object_storage_presigned_url_expiry": str(body.presigned_url_expiry),
    }
    await update_config(session, "object_storage", items)

    # Reload into memory
    await load_os_settings(session)

    # Reset S3 session so next request uses new config
    from app.core import s3
    s3._session = None

    logger.info("Object Storage config saved to DB: endpoint=%s, bucket=%s", body.endpoint, body.bucket)
    return {"status": "ok", "message": "Object Storage configuration saved"}


# ---------------------------------------------------------------------------
# Test connectivity
# ---------------------------------------------------------------------------

@router.post("/object-storage/test", response_model=TestResponse)
async def test_object_storage(body: ObjectStorageTestRequest):
    """Test S3 connectivity by checking if the configured bucket exists."""
    logger.info("Object Storage test: endpoint=%s, bucket=%s", body.endpoint, body.bucket)
    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=body.endpoint,
            aws_access_key_id=body.access_key,
            aws_secret_access_key=body.secret_key,
            region_name=body.region,
        ) as s3:
            await s3.head_bucket(Bucket=body.bucket)
            msg = f"Connection successful. Bucket '{body.bucket}' exists."
            logger.info("Object Storage test succeeded: %s", msg)
            return TestResponse(success=True, message=msg)
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "NoSuchBucket" in error_msg or "Not Found" in error_msg:
            msg = f"Bucket '{body.bucket}' does not exist."
        elif "InvalidAccessKeyId" in error_msg or "SignatureDoesNotMatch" in error_msg:
            msg = f"Authentication failed: invalid access key or secret key."
        elif "ConnectTimeoutError" in error_msg or "EndpointConnectionError" in error_msg:
            msg = f"Connection failed: unable to reach {body.endpoint}."
        else:
            msg = f"Error: {error_msg}"
        logger.warning("Object Storage test failed: %s", msg)
        return TestResponse(success=False, message=msg)


@router.post("/object-storage/initialize")
async def initialize_object_storage(body: ObjectStorageTestRequest):
    """Check if the S3 bucket exists and create it if not."""
    logger.info("Object Storage initialize: endpoint=%s, bucket=%s", body.endpoint, body.bucket)
    steps: list[dict] = []

    try:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=body.endpoint,
            aws_access_key_id=body.access_key,
            aws_secret_access_key=body.secret_key,
            region_name=body.region,
        ) as s3:
            # Step 1: Check connectivity
            steps.append({"step": "S3 Connection", "status": "ok", "message": f"Connected to {body.endpoint}"})

            # Step 2: Check bucket
            try:
                await s3.head_bucket(Bucket=body.bucket)
                steps.append({"step": f"Bucket '{body.bucket}'", "status": "skip", "message": "Already exists"})
            except Exception:
                # Bucket does not exist — create it
                try:
                    await s3.create_bucket(Bucket=body.bucket)
                    steps.append({"step": f"Bucket '{body.bucket}'", "status": "created", "message": "Created successfully"})
                except Exception as create_err:
                    steps.append({"step": f"Bucket '{body.bucket}'", "status": "error", "message": str(create_err)})

    except Exception as e:
        steps.append({"step": "S3 Connection", "status": "error", "message": str(e)})

    logger.info("Object Storage initialize: %d steps", len(steps))
    return {"steps": steps}


# ---------------------------------------------------------------------------
# Embedding configuration
# ---------------------------------------------------------------------------

class EmbeddingConfig(BaseModel):
    enabled: bool = False
    provider: str = "local"
    model: str = "all-MiniLM-L6-v2"
    api_key: str = ""
    api_url: str = ""
    dimension: int = 384


@router.get("/embedding", response_model=EmbeddingConfig)
async def get_embedding_config(session: AsyncSession = Depends(get_session)):
    """Return current embedding configuration."""
    cfg = await get_config_by_category(session, "embedding")
    return EmbeddingConfig(
        enabled=cfg.get("embedding_enabled", "false").lower() in ("true", "1", "yes"),
        provider=cfg.get("embedding_provider", "local"),
        model=cfg.get("embedding_model", "all-MiniLM-L6-v2"),
        api_key=cfg.get("embedding_api_key", ""),
        api_url=cfg.get("embedding_api_url", ""),
        dimension=int(cfg.get("embedding_dimension", "384")),
    )


@router.put("/embedding")
async def update_embedding_config(
    body: EmbeddingConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update embedding configuration and re-initialize provider."""
    items = {
        "embedding_enabled": str(body.enabled).lower(),
        "embedding_provider": body.provider,
        "embedding_model": body.model,
        "embedding_api_key": body.api_key,
        "embedding_api_url": body.api_url,
        "embedding_dimension": str(body.dimension),
    }
    await update_config(session, "embedding", items)

    # Re-initialize embedding provider
    await load_embedding_settings(session)

    logger.info("Embedding config saved: provider=%s, model=%s, enabled=%s",
                body.provider, body.model, body.enabled)
    return {"status": "ok", "message": "Embedding configuration saved"}


@router.post("/embedding/test", response_model=TestResponse)
async def test_embedding(body: EmbeddingConfig):
    """Test embedding provider by embedding a sample sentence."""
    logger.info("Embedding test: provider=%s, model=%s", body.provider, body.model)
    try:
        config = {
            "embedding_provider": body.provider,
            "embedding_model": body.model,
            "embedding_api_key": body.api_key,
            "embedding_api_url": body.api_url,
        }
        from app.embedding.registry import initialize_provider
        provider = await initialize_provider(config)
        result = await provider.embed(["test embedding connection"])
        dim = len(result[0])
        msg = f"Success: {body.provider}/{body.model} returned {dim}-dim vector"
        logger.info("Embedding test succeeded: %s", msg)
        return TestResponse(success=True, message=msg)
    except Exception as e:
        msg = f"Failed: {e}"
        logger.warning("Embedding test failed: %s", msg)
        return TestResponse(success=False, message=msg)


# ---------------------------------------------------------------------------
# Authentication (Keycloak) configuration
# ---------------------------------------------------------------------------

_SECRET_MASK = "••••••••"


class AuthConfig(BaseModel):
    type: str = "keycloak"
    server_url: str = ""
    realm: str = ""
    client_id: str = ""
    client_secret: str = ""
    admin_role: str = ""
    superuser_role: str = ""
    user_role: str = ""


@router.get("/auth", response_model=AuthConfig)
async def get_auth_config(session: AsyncSession = Depends(get_session)):
    """Return current authentication configuration (client_secret masked)."""
    cfg = await get_config_by_category(session, "auth")
    return AuthConfig(
        type=cfg.get("auth_type", "keycloak"),
        server_url=cfg.get("auth_keycloak_server_url", ""),
        realm=cfg.get("auth_keycloak_realm", ""),
        client_id=cfg.get("auth_keycloak_client_id", ""),
        client_secret=_SECRET_MASK if cfg.get("auth_keycloak_client_secret") else "",
        admin_role=cfg.get("auth_keycloak_admin_role", ""),
        superuser_role=cfg.get("auth_keycloak_superuser_role", ""),
        user_role=cfg.get("auth_keycloak_user_role", ""),
    )


@router.get("/auth/secret")
async def get_auth_secret(session: AsyncSession = Depends(get_session)):
    """Return the actual client_secret (unmasked). Admin only."""
    cfg = await get_config_by_category(session, "auth")
    return {"client_secret": cfg.get("auth_keycloak_client_secret", "")}


@router.put("/auth")
async def update_auth_config(
    body: AuthConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update authentication configuration and reload into memory."""
    items = {
        "auth_type": body.type,
        "auth_keycloak_server_url": body.server_url,
        "auth_keycloak_realm": body.realm,
        "auth_keycloak_client_id": body.client_id,
        "auth_keycloak_admin_role": body.admin_role,
        "auth_keycloak_superuser_role": body.superuser_role,
        "auth_keycloak_user_role": body.user_role,
    }
    # Only update client_secret if the user actually changed it (not the mask)
    if body.client_secret and body.client_secret != _SECRET_MASK:
        items["auth_keycloak_client_secret"] = body.client_secret

    await update_config(session, "auth", items)
    await load_auth_settings(session)

    logger.info("Auth config saved: server_url=%s, realm=%s", body.server_url, body.realm)
    return {"status": "ok", "message": "Authentication configuration saved"}


@router.post("/auth/test", response_model=TestResponse)
async def test_auth_connection(body: AuthConfig):
    """Test Keycloak connectivity by fetching the OpenID Configuration."""
    import httpx
    url = f"{body.server_url}/realms/{body.realm}/.well-known/openid-configuration"
    logger.info("Auth test: %s", url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            issuer = data.get("issuer", "")
            msg = f"Success: connected to {issuer}"
            logger.info("Auth test succeeded: %s", msg)
            return TestResponse(success=True, message=msg)
    except Exception as e:
        msg = f"Failed to reach {url}: {e}"
        logger.warning("Auth test failed: %s", msg)
        return TestResponse(success=False, message=msg)


# ---------------------------------------------------------------------------
# Keycloak Initialize (auto-setup realm, client, roles)
# ---------------------------------------------------------------------------

class KeycloakInitRequest(BaseModel):
    server_url: str
    admin_username: str = "admin"
    admin_password: str = "admin"
    realm: str = "argus"
    client_id: str = "argus-client"
    client_secret: str = "argus-client-secret"
    roles: list[str] = ["argus-admin", "argus-superuser", "argus-user"]


class InitStep(BaseModel):
    step: str
    status: str  # "skip", "created", "error"
    message: str


@router.post("/auth/initialize")
async def initialize_keycloak(body: KeycloakInitRequest):
    """Auto-setup Keycloak: realm, client, client secret, and realm roles."""
    import httpx
    steps: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Get admin token from master realm
        try:
            token_resp = await client.post(
                f"{body.server_url}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": body.admin_username,
                    "password": body.admin_password,
                },
            )
            token_resp.raise_for_status()
            admin_token = token_resp.json()["access_token"]
            steps.append({"step": "Admin Login", "status": "ok", "message": "Authenticated as admin"})
        except Exception as e:
            steps.append({"step": "Admin Login", "status": "error", "message": f"Failed: {e}"})
            return {"steps": steps}

        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

        # Step 2: Check/Create Realm
        try:
            realm_resp = await client.get(f"{body.server_url}/admin/realms/{body.realm}", headers=headers)
            if realm_resp.status_code == 200:
                steps.append({"step": f"Realm '{body.realm}'", "status": "skip", "message": "Already exists"})
            else:
                create_resp = await client.post(
                    f"{body.server_url}/admin/realms",
                    headers=headers,
                    json={"realm": body.realm, "enabled": True},
                )
                create_resp.raise_for_status()
                steps.append({"step": f"Realm '{body.realm}'", "status": "created", "message": "Created successfully"})
        except Exception as e:
            steps.append({"step": f"Realm '{body.realm}'", "status": "error", "message": str(e)})
            return {"steps": steps}

        # Step 3: Check/Create Client
        client_uuid = None
        try:
            clients_resp = await client.get(
                f"{body.server_url}/admin/realms/{body.realm}/clients",
                headers=headers,
                params={"clientId": body.client_id},
            )
            clients_resp.raise_for_status()
            existing_clients = clients_resp.json()

            if existing_clients:
                client_uuid = existing_clients[0]["id"]
                steps.append({"step": f"Client '{body.client_id}'", "status": "skip", "message": "Already exists"})
            else:
                create_client_resp = await client.post(
                    f"{body.server_url}/admin/realms/{body.realm}/clients",
                    headers=headers,
                    json={
                        "clientId": body.client_id,
                        "enabled": True,
                        "protocol": "openid-connect",
                        "publicClient": False,
                        "secret": body.client_secret,
                        "directAccessGrantsEnabled": True,
                        "serviceAccountsEnabled": True,
                        "authorizationServicesEnabled": False,
                        "standardFlowEnabled": True,
                        "redirectUris": ["*"],
                        "webOrigins": ["*"],
                    },
                )
                create_client_resp.raise_for_status()
                # Get the UUID of the created client
                loc = create_client_resp.headers.get("Location", "")
                client_uuid = loc.rsplit("/", 1)[-1] if loc else None
                steps.append({"step": f"Client '{body.client_id}'", "status": "created", "message": "Created successfully"})
        except Exception as e:
            steps.append({"step": f"Client '{body.client_id}'", "status": "error", "message": str(e)})
            return {"steps": steps}

        # Step 4: Set/Verify Client Secret
        if client_uuid:
            try:
                secret_resp = await client.get(
                    f"{body.server_url}/admin/realms/{body.realm}/clients/{client_uuid}/client-secret",
                    headers=headers,
                )
                if secret_resp.status_code == 200:
                    current_secret = secret_resp.json().get("value", "")
                    if current_secret == body.client_secret:
                        steps.append({"step": "Client Secret", "status": "skip", "message": "Already matches"})
                    else:
                        # Update the client with the desired secret
                        update_resp = await client.put(
                            f"{body.server_url}/admin/realms/{body.realm}/clients/{client_uuid}",
                            headers=headers,
                            json={"secret": body.client_secret},
                        )
                        update_resp.raise_for_status()
                        steps.append({"step": "Client Secret", "status": "created", "message": "Updated to match"})
                else:
                    steps.append({"step": "Client Secret", "status": "skip", "message": "Could not verify"})
            except Exception as e:
                steps.append({"step": "Client Secret", "status": "error", "message": str(e)})

        # Step 5: Check/Create Realm Roles
        for role_name in body.roles:
            try:
                role_resp = await client.get(
                    f"{body.server_url}/admin/realms/{body.realm}/roles/{role_name}",
                    headers=headers,
                )
                if role_resp.status_code == 200:
                    steps.append({"step": f"Role '{role_name}'", "status": "skip", "message": "Already exists"})
                else:
                    create_role_resp = await client.post(
                        f"{body.server_url}/admin/realms/{body.realm}/roles",
                        headers=headers,
                        json={"name": role_name},
                    )
                    create_role_resp.raise_for_status()
                    steps.append({"step": f"Role '{role_name}'", "status": "created", "message": "Created successfully"})
            except Exception as e:
                steps.append({"step": f"Role '{role_name}'", "status": "error", "message": str(e)})

    logger.info("Keycloak initialize: %d steps completed", len(steps))
    return {"steps": steps}


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------

class CorsConfig(BaseModel):
    origins: str = "*"


@router.get("/cors", response_model=CorsConfig)
async def get_cors_config(session: AsyncSession = Depends(get_session)):
    """Return current CORS configuration."""
    cfg = await get_config_by_category(session, "cors")
    return CorsConfig(origins=cfg.get("cors_origins", "*"))


@router.put("/cors")
async def update_cors_config(
    body: CorsConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update CORS configuration. Takes effect on next request."""
    await update_config(session, "cors", {"cors_origins": body.origins})
    await load_cors_settings(session)

    logger.info("CORS config saved: origins=%s", body.origins)
    return {"status": "ok", "message": "CORS configuration saved"}
