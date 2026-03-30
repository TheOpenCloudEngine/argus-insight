"""Infrastructure configuration API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.settings import service
from app.settings.schemas import (
    CheckPathRequest,
    CheckPathResponse,
    DockerRegistryTestRequest,
    DockerRegistryTestResponse,
    InfraConfigResponse,
    ObjectStorageInitRequest,
    ObjectStorageInitResponse,
    ObjectStorageTestRequest,
    ObjectStorageTestResponse,
    PrometheusTestRequest,
    PrometheusTestResponse,
    UnityCatalogInitRequest,
    UnityCatalogInitResponse,
    UnityCatalogTestRequest,
    UnityCatalogTestResponse,
    UpdateInfraCategoryRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/configuration", response_model=InfraConfigResponse)
async def get_configuration(
    session: AsyncSession = Depends(get_session),
) -> InfraConfigResponse:
    """Fetch the full infrastructure configuration."""
    return await service.get_infra_config(session)


@router.put("/configuration/category", status_code=204)
async def update_category(
    body: UpdateInfraCategoryRequest,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Update settings within a single infrastructure category."""
    try:
        await service.update_infra_category(session, body.category, body.items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # If argus category contains prometheus keys, push config to all REGISTERED agents
    if body.category == "argus" and service._PROMETHEUS_KEYS & body.items.keys():
        changed_keys = service._PROMETHEUS_KEYS & body.items.keys()
        logger.info(
            "Prometheus config updated via UI, pushing to agents: %s",
            {k: body.items[k] for k in changed_keys},
        )
        # Fetch the full argus config to send complete prometheus values
        argus_config = await service.get_infra_category_items(session, "argus")
        argus_config.update(body.items)
        await service.push_prometheus_config_to_agents(session, argus_config)


@router.post("/object-storage/test", response_model=ObjectStorageTestResponse)
async def test_object_storage(body: ObjectStorageTestRequest) -> ObjectStorageTestResponse:
    """Test Object Storage connectivity by listing buckets."""
    result = await service.test_object_storage(
        body.endpoint, body.access_key, body.secret_key, body.region,
    )
    return ObjectStorageTestResponse(**result)


@router.post("/object-storage/initialize", response_model=ObjectStorageInitResponse)
async def initialize_object_storage(body: ObjectStorageInitRequest) -> ObjectStorageInitResponse:
    """Initialize Object Storage by ensuring the 'global' bucket exists."""
    result = await service.initialize_object_storage(
        body.endpoint, body.access_key, body.secret_key, body.region,
    )
    return ObjectStorageInitResponse(**result)


@router.post("/prometheus/test", response_model=PrometheusTestResponse)
async def test_prometheus(body: PrometheusTestRequest) -> PrometheusTestResponse:
    """Test connectivity to Prometheus Push Gateway."""
    result = await service.test_prometheus(body.host, body.port)
    return PrometheusTestResponse(**result)


@router.post("/docker-registry/test", response_model=DockerRegistryTestResponse)
async def test_docker_registry(body: DockerRegistryTestRequest) -> DockerRegistryTestResponse:
    """Test connectivity to a Docker Registry."""
    result = await service.test_docker_registry(body.url, body.username, body.password)
    return DockerRegistryTestResponse(**result)


@router.post("/unity-catalog/test", response_model=UnityCatalogTestResponse)
async def test_unity_catalog(body: UnityCatalogTestRequest) -> UnityCatalogTestResponse:
    """Test connectivity to a Unity Catalog server."""
    result = await service.test_unity_catalog(body.url, body.access_token)
    return UnityCatalogTestResponse(**result)


@router.post("/unity-catalog/initialize", response_model=UnityCatalogInitResponse)
async def initialize_unity_catalog(body: UnityCatalogInitRequest) -> UnityCatalogInitResponse:
    """Initialize Unity Catalog with 'global' metastore and 'default' catalog."""
    result = await service.initialize_unity_catalog(body.url, body.access_token)
    return UnityCatalogInitResponse(**result)


@router.post("/check-path", response_model=CheckPathResponse)
async def check_path(body: CheckPathRequest) -> CheckPathResponse:
    """Check if a file path exists on the server."""
    exists = Path(body.path).is_file()
    return CheckPathResponse(path=body.path, exists=exists)


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


class TestResponse(BaseModel):
    success: bool
    message: str


@router.get("/auth", response_model=AuthConfig)
async def get_auth_config(session: AsyncSession = Depends(get_session)):
    """Return current authentication configuration (client_secret masked)."""
    cfg = await service.get_config_by_category(session, "auth")
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
    """Return the actual client_secret (unmasked)."""
    cfg = await service.get_config_by_category(session, "auth")
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
    if body.client_secret and body.client_secret != _SECRET_MASK:
        items["auth_keycloak_client_secret"] = body.client_secret

    await service.update_infra_category(session, "auth", items)
    await service.load_auth_settings(session)

    logger.info("Auth config saved: type=%s, server_url=%s, realm=%s", body.type, body.server_url, body.realm)
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
    status: str
    message: str


@router.post("/auth/initialize")
async def initialize_keycloak(body: KeycloakInitRequest):
    """Auto-setup Keycloak: realm, client, client secret, and realm roles."""
    import httpx
    steps: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Get admin token
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
# GitLab Settings
# ---------------------------------------------------------------------------

_GITLAB_TOKEN_MASK = "••••••••"


class GitlabConfig(BaseModel):
    url: str = ""
    username: str = "root"
    password: str = ""
    token: str = ""
    group_path: str = "workspaces"
    default_branch: str = "main"
    project_visibility: str = "internal"


class GitlabTestRequest(BaseModel):
    url: str
    token: str


class TestResponse(BaseModel):
    success: bool
    message: str


@router.get("/gitlab")
async def get_gitlab_config(session: AsyncSession = Depends(get_session)):
    """Get GitLab configuration (token masked)."""
    cfg = await service.get_config_by_category(session, "gitlab")
    token = cfg.get("gitlab_token", "")
    password = cfg.get("gitlab_password", "")
    return GitlabConfig(
        url=cfg.get("gitlab_url", ""),
        username=cfg.get("gitlab_username", "root"),
        password=_GITLAB_TOKEN_MASK if password else "",
        token=_GITLAB_TOKEN_MASK if token else "",
        group_path=cfg.get("gitlab_group_path", "workspaces"),
        default_branch=cfg.get("gitlab_default_branch", "main"),
        project_visibility=cfg.get("gitlab_project_visibility", "internal"),
    )


@router.get("/gitlab/token")
async def get_gitlab_token(session: AsyncSession = Depends(get_session)):
    """Get the real GitLab token (for reveal toggle)."""
    cfg = await service.get_config_by_category(session, "gitlab")
    return {"token": cfg.get("gitlab_token", "")}


@router.get("/gitlab/password")
async def get_gitlab_password(session: AsyncSession = Depends(get_session)):
    """Get the real GitLab password (for reveal toggle)."""
    cfg = await service.get_config_by_category(session, "gitlab")
    return {"password": cfg.get("gitlab_password", "")}


@router.put("/gitlab")
async def update_gitlab_config(
    body: GitlabConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update GitLab configuration and reinitialize the client."""
    items = {
        "gitlab_url": body.url,
        "gitlab_username": body.username,
        "gitlab_group_path": body.group_path,
        "gitlab_default_branch": body.default_branch,
        "gitlab_project_visibility": body.project_visibility,
    }
    if body.token and body.token != _GITLAB_TOKEN_MASK:
        items["gitlab_token"] = body.token
    if body.password and body.password != _GITLAB_TOKEN_MASK:
        items["gitlab_password"] = body.password

    await service.update_infra_category(session, "gitlab", items)
    await service.load_gitlab_settings(session)

    logger.info("GitLab config saved: url=%s", body.url)
    return {"status": "ok", "message": "GitLab configuration saved"}


@router.post("/gitlab/test")
async def test_gitlab_connection(
    body: GitlabTestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Test GitLab connection by authenticating and fetching version."""
    import gitlab as gitlab_lib

    url = body.url.strip()
    token = body.token.strip()

    # Resolve masked token
    if token == _GITLAB_TOKEN_MASK:
        cfg = await service.get_config_by_category(session, "gitlab")
        token = cfg.get("gitlab_token", "")

    if not url or not token:
        return TestResponse(success=False, message="URL and token are required")

    try:
        gl = gitlab_lib.Gitlab(url=url, private_token=token)
        gl.auth()
        version = gl.version()
        user = gl.user.username if gl.user else "unknown"
        return TestResponse(
            success=True,
            message=f"GitLab connection successful ({version[0]}, user: {user})",
        )
    except Exception as e:
        return TestResponse(success=False, message=f"Connection failed: {e}")


# ---------------------------------------------------------------------------
# Kubernetes Settings
# ---------------------------------------------------------------------------

class K8sConfig(BaseModel):
    kubeconfig_path: str = "/etc/rancher/k3s/k3s.yaml"
    namespace_prefix: str = "argus-ws-"
    context: str = ""


@router.get("/k8s")
async def get_k8s_config(session: AsyncSession = Depends(get_session)):
    """Get Kubernetes configuration."""
    cfg = await service.get_config_by_category(session, "k8s")
    return K8sConfig(
        kubeconfig_path=cfg.get("k8s_kubeconfig_path", "/etc/rancher/k3s/k3s.yaml"),
        namespace_prefix=cfg.get("k8s_namespace_prefix", "argus-ws-"),
        context=cfg.get("k8s_context", ""),
    )


@router.put("/k8s")
async def update_k8s_config(
    body: K8sConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update Kubernetes configuration."""
    items = {
        "k8s_kubeconfig_path": body.kubeconfig_path,
        "k8s_namespace_prefix": body.namespace_prefix,
        "k8s_context": body.context,
    }
    await service.update_infra_category(session, "k8s", items)
    logger.info("K8s config saved: kubeconfig=%s, prefix=%s", body.kubeconfig_path, body.namespace_prefix)
    return {"status": "ok", "message": "Kubernetes configuration saved"}


# ---------------------------------------------------------------------------
# Deploy Mapping (Service → Pipeline)
# ---------------------------------------------------------------------------

DEPLOY_MAPPING_SERVICES = [
    {"service_key": "mlflow", "service_label": "MLflow", "icon": "mlflow", "default_constraint": "per_workspace"},
    {"service_key": "vscode", "service_label": "VS Code Server", "icon": "code", "default_constraint": "per_user"},
    {"service_key": "airflow", "service_label": "Airflow", "icon": "airflow", "default_constraint": "per_workspace"},
    {"service_key": "jupyter", "service_label": "Jupyter Lab", "icon": "jupyter", "default_constraint": "per_user"},
    {"service_key": "kserve", "service_label": "KServe", "icon": "kserve", "default_constraint": "per_workspace"},
    {"service_key": "neo4j", "service_label": "Neo4j", "icon": "neo4j", "default_constraint": "per_workspace"},
    {"service_key": "milvus", "service_label": "Milvus", "icon": "milvus", "default_constraint": "per_workspace"},
    {"service_key": "mindsdb", "service_label": "MindsDB", "icon": "brain", "default_constraint": "per_workspace"},
]

CONSTRAINT_LABELS = {
    "per_workspace": "One per workspace",
    "per_user": "One per user",
}


class DeployMappingItem(BaseModel):
    pipeline_id: int | None = None
    constraint: str | None = None  # "per_workspace" or "per_user"


@router.get("/deploy-mapping")
async def get_deploy_mapping(session: AsyncSession = Depends(get_session)):
    """Get all service-to-pipeline deploy mappings."""
    cfg = await service.get_config_by_category(session, "deploy_mapping")

    # Also fetch pipeline names for display
    pipeline_names: dict[int, str] = {}
    try:
        from sqlalchemy import select
        from workspace_provisioner.plugins.models import ArgusPipeline
        result = await session.execute(
            select(ArgusPipeline.id, ArgusPipeline.display_name).where(
                ArgusPipeline.deleted.is_(False),
            )
        )
        for row in result:
            pipeline_names[row.id] = row.display_name
    except Exception:
        pass

    mappings = []
    for svc in DEPLOY_MAPPING_SERVICES:
        key = f"service_{svc['service_key']}"
        raw_id = cfg.get(key, "")
        pipeline_id = int(raw_id) if raw_id else None
        constraint = cfg.get(f"constraint_{svc['service_key']}", "") or svc["default_constraint"]
        mappings.append({
            "service_key": svc["service_key"],
            "service_label": svc["service_label"],
            "icon": svc["icon"],
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline_names.get(pipeline_id) if pipeline_id else None,
            "constraint": constraint,
            "constraint_label": CONSTRAINT_LABELS.get(constraint, constraint),
        })

    return {"mappings": mappings}


@router.put("/deploy-mapping/{service_key}")
async def update_deploy_mapping(
    service_key: str,
    body: DeployMappingItem,
    session: AsyncSession = Depends(get_session),
):
    """Set or clear the pipeline mapping for a service."""
    valid_keys = {s["service_key"] for s in DEPLOY_MAPPING_SERVICES}
    if service_key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Unknown service key: {service_key}")

    items: dict[str, str] = {}
    items[f"service_{service_key}"] = str(body.pipeline_id) if body.pipeline_id is not None else ""
    if body.constraint:
        items[f"constraint_{service_key}"] = body.constraint
    await service.update_infra_category(session, "deploy_mapping", items)
    logger.info(
        "Deploy mapping updated: %s → pipeline_id=%s, constraint=%s",
        service_key, body.pipeline_id, body.constraint,
    )
    return {"status": "ok", "service_key": service_key, "pipeline_id": body.pipeline_id, "constraint": body.constraint}


@router.get("/k8s/namespace/{namespace}")
async def check_k8s_namespace(
    namespace: str,
    session: AsyncSession = Depends(get_session),
):
    """Check if a Kubernetes namespace exists."""
    import asyncio

    cfg = await service.get_config_by_category(session, "k8s")
    kubeconfig = cfg.get("k8s_kubeconfig_path", "/etc/rancher/k3s/k3s.yaml")
    context = cfg.get("k8s_context", "")

    cmd = ["kubectl", "get", "namespace", namespace, "--no-headers"]
    if kubeconfig:
        cmd.extend(["--kubeconfig", kubeconfig])
    if context:
        cmd.extend(["--context", context])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        exists = proc.returncode == 0
        return {"exists": exists, "namespace": namespace}
    except Exception as e:
        logger.warning("K8s namespace check failed: %s", e)
        return {"exists": False, "namespace": namespace, "error": str(e)}
