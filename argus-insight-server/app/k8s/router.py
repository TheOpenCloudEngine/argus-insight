"""Kubernetes dashboard API endpoints."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.k8s import service
from app.k8s.client import K8sClient
from app.k8s.schemas import (
    ClusterOverview,
    K8sResource,
    K8sResourceList,
    NamespaceOverview,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/k8s", tags=["kubernetes"])


# ── Cluster Info & Overview ────────────────────────────────────────


@router.get("/overview", response_model=ClusterOverview)
async def cluster_overview(session: AsyncSession = Depends(get_session)):
    """Get cluster-wide overview with resource counts and recent events."""
    try:
        return await service.get_cluster_overview(session)
    except Exception as e:
        logger.error("Failed to get cluster overview: %s", e)
        raise HTTPException(status_code=502, detail=f"Kubernetes API error: {e}") from e


@router.get("/overview/{namespace}", response_model=NamespaceOverview)
async def namespace_overview(
    namespace: str,
    session: AsyncSession = Depends(get_session),
):
    """Get overview data for a specific namespace."""
    try:
        return await service.get_namespace_overview(session, namespace)
    except Exception as e:
        logger.error("Failed to get namespace overview: %s", e)
        raise HTTPException(status_code=502, detail=f"Kubernetes API error: {e}") from e


@router.get("/resources")
async def supported_resources():
    """List all supported Kubernetes resource types."""
    return service.get_supported_resources()


# ── Namespaces (convenience) ──────────────────────────────────────


@router.get("/namespaces")
async def list_namespaces(session: AsyncSession = Depends(get_session)):
    """List all namespaces."""
    try:
        data = await service.list_resources(session, "namespaces")
        names = [
            (item.get("metadata") or {}).get("name", "")
            for item in data.items
        ]
        return {"namespaces": sorted(names)}
    except Exception as e:
        logger.error("Failed to list namespaces: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


# ── Generic Namespaced Resource CRUD ──────────────────────────────


@router.get("/{namespace}/{resource}", response_model=K8sResourceList)
async def list_namespaced_resources(
    namespace: str,
    resource: str,
    label_selector: str = Query("", alias="labelSelector"),
    field_selector: str = Query("", alias="fieldSelector"),
    limit: int | None = Query(None),
    continue_token: str = Query("", alias="continue"),
    session: AsyncSession = Depends(get_session),
):
    """List namespaced resources (pods, deployments, services, etc.)."""
    try:
        ns = None if namespace == "_all" else namespace
        return await service.list_resources(
            session, resource,
            namespace=ns,
            label_selector=label_selector,
            field_selector=field_selector,
            limit=limit,
            continue_token=continue_token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to list %s in %s: %s", resource, namespace, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/{namespace}/{resource}/{name}", response_model=K8sResource)
async def get_namespaced_resource(
    namespace: str,
    resource: str,
    name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single namespaced resource by name."""
    try:
        ns = None if namespace == "_cluster" else namespace
        return await service.get_resource(session, resource, name, namespace=ns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        if "404" in str(e) or "NotFound" in str(e):
            raise HTTPException(status_code=404, detail=f"{resource}/{name} not found") from e
        logger.error("Failed to get %s/%s in %s: %s", resource, name, namespace, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{namespace}/{resource}")
async def create_namespaced_resource(
    namespace: str,
    resource: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Create a namespaced resource."""
    try:
        ns = None if namespace == "_cluster" else namespace
        return await service.create_resource(session, resource, body, namespace=ns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to create %s in %s: %s", resource, namespace, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.put("/{namespace}/{resource}/{name}")
async def update_namespaced_resource(
    namespace: str,
    resource: str,
    name: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Update (replace) a namespaced resource."""
    try:
        ns = None if namespace == "_cluster" else namespace
        return await service.update_resource(session, resource, name, body, namespace=ns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to update %s/%s in %s: %s", resource, name, namespace, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.delete("/{namespace}/{resource}/{name}")
async def delete_namespaced_resource(
    namespace: str,
    resource: str,
    name: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a namespaced resource."""
    try:
        ns = None if namespace == "_cluster" else namespace
        return await service.delete_resource(session, resource, name, namespace=ns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Failed to delete %s/%s in %s: %s", resource, name, namespace, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


# ── Scale ─────────────────────────────────────────────────────────


class ScaleRequest(BaseModel):
    replicas: int


@router.post("/{namespace}/{resource}/{name}/scale")
async def scale_namespaced_resource(
    namespace: str,
    resource: str,
    name: str,
    body: ScaleRequest,
    session: AsyncSession = Depends(get_session),
):
    """Scale a deployment or statefulset."""
    if resource not in ("deployments", "statefulsets"):
        raise HTTPException(status_code=400, detail="Only deployments and statefulsets can be scaled")
    try:
        return await service.scale_resource(
            session, resource, name, namespace, body.replicas,
        )
    except Exception as e:
        logger.error("Failed to scale %s/%s: %s", resource, name, e)
        raise HTTPException(status_code=502, detail=str(e)) from e


# ── Watch (SSE) ───────────────────────────────────────────────────


@router.get("/{namespace}/{resource}/watch")
async def watch_namespaced_resources(
    request: Request,
    namespace: str,
    resource: str,
    label_selector: str = Query("", alias="labelSelector"),
    resource_version: str = Query("", alias="resourceVersion"),
    session: AsyncSession = Depends(get_session),
):
    """Watch resource changes via Server-Sent Events (SSE)."""
    from app.k8s.service import _make_client

    k8s = await _make_client(session)
    ns = None if namespace == "_all" else namespace

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in k8s.watch_resources(
                resource,
                namespace=ns,
                resource_version=resource_version,
                label_selector=label_selector,
                timeout_seconds=300,
            ):
                if await request.is_disconnected():
                    break
                data = json.dumps(event, default=str)
                yield f"event: {event['type']}\ndata: {data}\n\n"
        except Exception as e:
            logger.warning("Watch stream error for %s/%s: %s", namespace, resource, e)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await k8s.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Pod Logs (SSE) ────────────────────────────────────────────────


@router.get("/{namespace}/pods/{name}/logs")
async def get_pod_logs(
    request: Request,
    namespace: str,
    name: str,
    container: str | None = Query(None),
    follow: bool = Query(False),
    tail_lines: int = Query(100, alias="tailLines"),
    since_seconds: int | None = Query(None, alias="sinceSeconds"),
    timestamps: bool = Query(True),
    session: AsyncSession = Depends(get_session),
):
    """Get pod logs. If follow=true, streams via SSE."""
    from app.k8s.service import _make_client

    k8s = await _make_client(session)

    if follow:
        async def log_stream() -> AsyncIterator[str]:
            try:
                async for line in k8s.get_pod_logs(
                    name, namespace,
                    container=container,
                    follow=True,
                    tail_lines=tail_lines,
                    since_seconds=since_seconds,
                    timestamps=timestamps,
                ):
                    if await request.is_disconnected():
                        break
                    yield f"data: {json.dumps({'line': line})}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            finally:
                await k8s.close()

        return StreamingResponse(
            log_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            lines: list[str] = []
            async for line in k8s.get_pod_logs(
                name, namespace,
                container=container,
                follow=False,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
                timestamps=timestamps,
            ):
                lines.append(line)
            return {"logs": lines}
        except Exception as e:
            logger.error("Failed to get logs for %s/%s: %s", namespace, name, e)
            raise HTTPException(status_code=502, detail=str(e)) from e
        finally:
            await k8s.close()
