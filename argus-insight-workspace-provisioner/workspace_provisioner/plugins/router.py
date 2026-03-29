"""Plugin management API endpoints.

Provides REST endpoints for:
- Listing available plugins with metadata and version info.
- Retrieving plugin details and config schemas.
- Updating plugin order, enabled state, and version selection.
- Validating proposed plugin orders against dependency constraints.
- Rescanning plugin directories for new/removed plugins.
- Managing named deployment pipelines.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from workspace_provisioner.plugins.models import ArgusPluginConfig
from workspace_provisioner.plugins.registry import PluginRegistry
from workspace_provisioner.plugins.schemas import (
    PipelineCreateRequest,
    PipelineListResponse,
    PipelineResponse,
    PipelineUpdateRequest,
    PluginOrderItem,
    PluginOrderUpdateRequest,
    PluginOrderValidateRequest,
    PluginOrderValidateResponse,
    PluginRescanResponse,
    PluginResponse,
    PluginVersionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])


def _get_registry() -> PluginRegistry:
    return PluginRegistry.get_instance()


async def _build_plugin_response(
    registry: PluginRegistry,
    name: str,
    session: AsyncSession,
    include_config_schema: bool = False,
) -> PluginResponse:
    """Build a PluginResponse by merging registry metadata with DB config."""
    meta = registry.get(name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    # Load admin config from DB
    result = await session.execute(
        select(ArgusPluginConfig).where(ArgusPluginConfig.plugin_name == name)
    )
    db_config = result.scalars().first()

    versions = []
    for ver_key, ver_meta in meta.versions.items():
        schema = None
        if include_config_schema:
            schema = registry.get_config_schema(name, ver_key)
        versions.append(
            PluginVersionResponse(
                version=ver_meta.version,
                display_name=ver_meta.display_name,
                description=ver_meta.description,
                status=ver_meta.status,
                release_date=ver_meta.release_date,
                min_k8s_version=ver_meta.min_k8s_version,
                changelog=ver_meta.changelog,
                upgradeable_from=ver_meta.upgradeable_from,
                config_schema=schema,
            )
        )

    return PluginResponse(
        name=meta.name,
        display_name=meta.display_name,
        description=meta.description,
        icon=meta.icon,
        category=meta.category,
        depends_on=meta.depends_on,
        provides=meta.provides,
        requires=meta.requires,
        tags=meta.tags,
        source=meta.source,
        versions=versions,
        default_version=meta.default_version,
        enabled=db_config.enabled if db_config else None,
        display_order=db_config.display_order if db_config else None,
        selected_version=db_config.selected_version if db_config else None,
    )


@router.get("", response_model=list[PluginResponse])
async def list_plugins(session: AsyncSession = Depends(get_session)):
    """List all available plugins with metadata and admin configuration."""
    registry = _get_registry()
    plugins = registry.get_all()
    responses = []
    for meta in plugins:
        resp = await _build_plugin_response(registry, meta.name, session)
        responses.append(resp)

    # Sort by display_order (configured first), then by name
    responses.sort(key=lambda p: (p.display_order is None, p.display_order or 0, p.name))
    return responses


# ---------------------------------------------------------------------------
# Pipeline CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(session: AsyncSession = Depends(get_session)):
    """List all saved pipelines."""
    from workspace_provisioner.plugins.models import ArgusPipeline
    result = await session.execute(
        select(ArgusPipeline)
        .where(ArgusPipeline.deleted.is_(False))
        .order_by(ArgusPipeline.created_at.desc())
    )
    pipelines = result.scalars().all()

    items = []
    for p in pipelines:
        # Load plugin configs for this pipeline
        cfg_result = await session.execute(
            select(ArgusPluginConfig)
            .where(ArgusPluginConfig.pipeline_id == p.id)
            .order_by(ArgusPluginConfig.display_order)
        )
        configs = cfg_result.scalars().all()
        items.append(PipelineResponse(
            id=p.id, name=p.name, display_name=p.display_name,
            description=p.description, version=p.version or 1, created_by=p.created_by,
            plugins=[PluginOrderItem(
                plugin_name=c.plugin_name, enabled=c.enabled,
                display_order=c.display_order,
                selected_version=c.selected_version,
                default_config=c.default_config,
            ) for c in configs],
            created_at=p.created_at, updated_at=p.updated_at,
        ))
    return PipelineListResponse(items=items, total=len(items))


@router.post("/pipelines", response_model=PipelineResponse)
async def create_pipeline(req: PipelineCreateRequest, session: AsyncSession = Depends(get_session)):
    """Create a named pipeline with plugin configuration."""
    from workspace_provisioner.plugins.models import ArgusPipeline

    # Check uniqueness
    existing = await session.execute(
        select(ArgusPipeline).where(ArgusPipeline.name == req.name)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail=f"Pipeline '{req.name}' already exists")

    pipeline = ArgusPipeline(
        name=req.name, display_name=req.display_name,
        description=req.description,
        created_by=req.created_by,
    )
    session.add(pipeline)
    await session.commit()
    await session.refresh(pipeline)

    # Validate plugin order
    registry = _get_registry()
    enabled_ordered = [
        item.plugin_name for item in sorted(req.plugins, key=lambda x: x.display_order) if item.enabled
    ]
    versions = {item.plugin_name: item.selected_version for item in req.plugins if item.selected_version}
    violations = registry.validate_order(enabled_ordered, versions or None)
    if violations:
        await session.delete(pipeline)
        await session.commit()
        raise HTTPException(status_code=400, detail={"violations": violations})

    # Save plugin configs
    for item in req.plugins:
        config = ArgusPluginConfig(
            pipeline_id=pipeline.id, plugin_name=item.plugin_name,
            enabled=item.enabled, display_order=item.display_order,
            selected_version=item.selected_version, default_config=item.default_config,
        )
        session.add(config)
    await session.commit()

    logger.info("Pipeline created: %s (id=%d, %d plugins)", req.name, pipeline.id, len(req.plugins))

    return PipelineResponse(
        id=pipeline.id, name=pipeline.name, display_name=pipeline.display_name,
        description=pipeline.description, version=pipeline.version or 1, created_by=pipeline.created_by,
        plugins=[PluginOrderItem(
            plugin_name=p.plugin_name, enabled=p.enabled, display_order=p.display_order,
            selected_version=p.selected_version, default_config=p.default_config,
        ) for p in req.plugins],
        created_at=pipeline.created_at, updated_at=pipeline.updated_at,
    )


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """Get a pipeline by ID with its plugin configuration."""
    from workspace_provisioner.plugins.models import ArgusPipeline
    result = await session.execute(select(ArgusPipeline).where(ArgusPipeline.id == pipeline_id))
    pipeline = result.scalars().first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    cfg_result = await session.execute(
        select(ArgusPluginConfig).where(ArgusPluginConfig.pipeline_id == pipeline.id)
        .order_by(ArgusPluginConfig.display_order)
    )
    configs = cfg_result.scalars().all()
    return PipelineResponse(
        id=pipeline.id, name=pipeline.name, display_name=pipeline.display_name,
        description=pipeline.description, version=pipeline.version or 1, created_by=pipeline.created_by,
        plugins=[PluginOrderItem(
            plugin_name=c.plugin_name, enabled=c.enabled, display_order=c.display_order,
            selected_version=c.selected_version, default_config=c.default_config,
        ) for c in configs],
        created_at=pipeline.created_at, updated_at=pipeline.updated_at,
    )


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """Delete a pipeline and its plugin configurations."""
    from workspace_provisioner.plugins.models import ArgusPipeline
    result = await session.execute(select(ArgusPipeline).where(ArgusPipeline.id == pipeline_id))
    pipeline = result.scalars().first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Soft delete
    pipeline.deleted = True
    await session.commit()
    logger.info("Pipeline soft-deleted: %s (id=%d)", pipeline.name, pipeline.id)
    return {"status": "ok", "message": f"Pipeline '{pipeline.name}' deleted"}


@router.post("/pipelines/{pipeline_id}/clone", response_model=PipelineResponse)
async def clone_pipeline(pipeline_id: int, session: AsyncSession = Depends(get_session)):
    """Clone a pipeline with a new ID and name."""
    from workspace_provisioner.plugins.models import ArgusPipeline
    import secrets
    from datetime import datetime, timezone

    result = await session.execute(select(ArgusPipeline).where(ArgusPipeline.id == pipeline_id))
    source = result.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Generate new pipeline ID
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d-%H%M%S")
    hex_str = secrets.token_hex(2)
    new_name = f"pipeline-{date_str}-{hex_str}"

    clone = ArgusPipeline(
        name=new_name,
        display_name=f"Cloned {source.display_name}",
        description=source.description,
        created_by=source.created_by,
    )
    session.add(clone)
    await session.commit()
    await session.refresh(clone)

    # Clone plugin configs
    cfg_result = await session.execute(
        select(ArgusPluginConfig)
        .where(ArgusPluginConfig.pipeline_id == source.id)
        .order_by(ArgusPluginConfig.display_order)
    )
    configs = cfg_result.scalars().all()
    new_configs = []
    for c in configs:
        new_cfg = ArgusPluginConfig(
            pipeline_id=clone.id,
            plugin_name=c.plugin_name,
            enabled=c.enabled,
            display_order=c.display_order,
            selected_version=c.selected_version,
            default_config=c.default_config,
        )
        session.add(new_cfg)
        new_configs.append(new_cfg)
    await session.commit()

    logger.info("Pipeline cloned: %s -> %s (id=%d)", source.name, clone.name, clone.id)
    return PipelineResponse(
        id=clone.id, name=clone.name, display_name=clone.display_name,
        description=clone.description, version=clone.version or 1, created_by=clone.created_by,
        plugins=[PluginOrderItem(
            plugin_name=c.plugin_name, enabled=c.enabled,
            display_order=c.display_order,
            selected_version=c.selected_version,
            default_config=c.default_config,
        ) for c in new_configs],
        created_at=clone.created_at, updated_at=clone.updated_at,
    )


@router.put("/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    req: PipelineUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing pipeline's metadata and plugin configuration."""
    from workspace_provisioner.plugins.models import ArgusPipeline

    result = await session.execute(
        select(ArgusPipeline).where(ArgusPipeline.id == pipeline_id)
    )
    pipeline = result.scalars().first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Update metadata fields if provided
    if req.display_name is not None:
        pipeline.display_name = req.display_name
    if req.description is not None:
        pipeline.description = req.description

    # Increment version on every save
    pipeline.version = (pipeline.version or 0) + 1

    # Update plugins if provided
    if req.plugins is not None:
        registry = _get_registry()
        enabled_ordered = [
            item.plugin_name
            for item in sorted(req.plugins, key=lambda x: x.display_order)
            if item.enabled
        ]
        versions = {
            item.plugin_name: item.selected_version
            for item in req.plugins
            if item.selected_version
        }
        violations = registry.validate_order(enabled_ordered, versions or None)
        if violations:
            raise HTTPException(status_code=400, detail={"violations": violations})

        # Delete old plugin configs
        old_cfgs = await session.execute(
            select(ArgusPluginConfig).where(
                ArgusPluginConfig.pipeline_id == pipeline_id
            )
        )
        for c in old_cfgs.scalars().all():
            await session.delete(c)
        await session.flush()

        # Insert new plugin configs
        for item in req.plugins:
            config = ArgusPluginConfig(
                pipeline_id=pipeline.id,
                plugin_name=item.plugin_name,
                enabled=item.enabled,
                display_order=item.display_order,
                selected_version=item.selected_version,
                default_config=item.default_config,
            )
            session.add(config)

    await session.commit()
    await session.refresh(pipeline)

    # Load updated configs for response
    cfg_result = await session.execute(
        select(ArgusPluginConfig)
        .where(ArgusPluginConfig.pipeline_id == pipeline.id)
        .order_by(ArgusPluginConfig.display_order)
    )
    configs = cfg_result.scalars().all()

    logger.info("Pipeline updated: %s (id=%d)", pipeline.name, pipeline.id)
    return PipelineResponse(
        id=pipeline.id, name=pipeline.name, display_name=pipeline.display_name,
        description=pipeline.description, version=pipeline.version or 1,
        created_by=pipeline.created_by,
        plugins=[PluginOrderItem(
            plugin_name=c.plugin_name, enabled=c.enabled,
            display_order=c.display_order,
            selected_version=c.selected_version,
            default_config=c.default_config,
        ) for c in configs],
        created_at=pipeline.created_at, updated_at=pipeline.updated_at,
    )


# ---------------------------------------------------------------------------
# Plugin detail and management endpoints
# ---------------------------------------------------------------------------


@router.get("/{plugin_name}", response_model=PluginResponse)
async def get_plugin(
    plugin_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get plugin details including all version info and config schemas."""
    registry = _get_registry()
    return await _build_plugin_response(
        registry, plugin_name, session, include_config_schema=True
    )


@router.get("/{plugin_name}/versions/{version}/schema")
async def get_plugin_version_schema(plugin_name: str, version: str):
    """Get JSON Schema for a specific plugin version's configuration.

    Used by the UI to dynamically generate configuration forms.
    """
    registry = _get_registry()
    meta = registry.get(plugin_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    if version not in meta.versions:
        raise HTTPException(
            status_code=404,
            detail=f"Version '{version}' not found for plugin '{plugin_name}'",
        )

    schema = registry.get_config_schema(plugin_name, version)
    if schema is None:
        return {"message": "No configurable settings for this plugin version"}
    return schema


@router.put("/order")
async def update_plugin_order(
    req: PluginOrderUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update the global plugin order, enabled state, and version selection.

    Validates dependency constraints before saving. Returns 400 if the
    proposed order violates any dependency rules.
    """
    registry = _get_registry()

    # Validate all plugin names exist
    for item in req.plugins:
        if not registry.get(item.plugin_name):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown plugin: '{item.plugin_name}'",
            )

    # Validate order for enabled plugins
    enabled_ordered = [
        item.plugin_name for item in sorted(req.plugins, key=lambda x: x.display_order)
        if item.enabled
    ]
    versions = {
        item.plugin_name: item.selected_version
        for item in req.plugins
        if item.selected_version
    }

    violations = registry.validate_order(enabled_ordered, versions or None)
    if violations:
        raise HTTPException(status_code=400, detail={"violations": violations})

    # Upsert all plugin configs
    for item in req.plugins:
        result = await session.execute(
            select(ArgusPluginConfig).where(
                ArgusPluginConfig.plugin_name == item.plugin_name
            )
        )
        existing = result.scalars().first()

        if existing:
            existing.enabled = item.enabled
            existing.display_order = item.display_order
            existing.selected_version = item.selected_version
            existing.default_config = item.default_config
        else:
            config = ArgusPluginConfig(
                plugin_name=item.plugin_name,
                enabled=item.enabled,
                display_order=item.display_order,
                selected_version=item.selected_version,
                default_config=item.default_config,
            )
            session.add(config)

    await session.commit()
    logger.info("Plugin order updated: %s", [p.plugin_name for p in req.plugins])
    return {"status": "ok", "message": f"Updated {len(req.plugins)} plugin configs"}


@router.post("/validate-order", response_model=PluginOrderValidateResponse)
async def validate_plugin_order(req: PluginOrderValidateRequest):
    """Validate a proposed plugin order without saving (dry-run).

    Returns whether the order is valid, any violations, and a
    suggested order that respects dependency constraints.
    """
    registry = _get_registry()

    # Validate all names exist
    for name in req.plugin_names:
        if not registry.get(name):
            return PluginOrderValidateResponse(
                valid=False,
                violations=[f"Unknown plugin: '{name}'"],
                suggested_order=[],
            )

    violations = registry.validate_order(req.plugin_names, req.versions)

    suggested = []
    if violations:
        try:
            suggested = registry.resolve_order(req.plugin_names, req.versions)
        except ValueError:
            pass

    return PluginOrderValidateResponse(
        valid=len(violations) == 0,
        violations=violations,
        suggested_order=suggested,
    )


@router.post("/rescan", response_model=PluginRescanResponse)
async def rescan_plugins(session: AsyncSession = Depends(get_session)):
    """Rescan plugin directories for new or removed plugins.

    Discovers plugins from builtin and external directories, then
    synchronizes with the database (auto-registers new plugins,
    marks removed plugins as disabled).
    """
    registry = _get_registry()
    old_names = {m.name for m in registry.get_all()}

    registry.rescan()

    new_names = {m.name for m in registry.get_all()}
    added = new_names - old_names
    removed = old_names - new_names

    # Auto-register new plugins in DB with default order
    if added:
        max_order_result = await session.execute(
            select(ArgusPluginConfig.display_order)
            .order_by(ArgusPluginConfig.display_order.desc())
            .limit(1)
        )
        max_order = max_order_result.scalar() or 0

        for i, name in enumerate(sorted(added)):
            config = ArgusPluginConfig(
                plugin_name=name,
                enabled=True,
                display_order=max_order + i + 1,
            )
            session.add(config)
        await session.commit()

    # Disable removed plugins
    if removed:
        for name in removed:
            result = await session.execute(
                select(ArgusPluginConfig).where(ArgusPluginConfig.plugin_name == name)
            )
            config = result.scalars().first()
            if config:
                config.enabled = False
        await session.commit()

    logger.info(
        "Plugin rescan: total=%d, new=%s, removed=%s",
        len(new_names), sorted(added), sorted(removed),
    )
    return PluginRescanResponse(
        total_plugins=len(new_names),
        new_plugins=sorted(added),
        removed_plugins=sorted(removed),
    )
