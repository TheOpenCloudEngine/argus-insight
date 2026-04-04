"""ML Studio service — training job management."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml_studio.models import ArgusMLJob, ArgusMLPipeline
from app.ml_studio.schemas import (
    PipelineResponse,
    TrainJobResponse,
    TrainRequest,
)

logger = logging.getLogger(__name__)


def _job_to_response(job: ArgusMLJob) -> TrainJobResponse:
    return TrainJobResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        name=job.name,
        source=job.source or "wizard",
        status=job.status,
        task_type=job.task_type,
        target_column=job.target_column,
        metric=job.metric,
        algorithm=job.algorithm,
        progress=job.progress,
        data_source=job.data_source or {},
        config=job.config,
        results=job.results,
        error_message=job.error_message,
        pipeline_id=job.pipeline_id,
        generated_code=job.generated_code,
        author_username=job.author_username,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


async def create_pipeline_job(
    session: AsyncSession,
    workspace_id: int,
    name: str,
    pipeline_id: int | None,
    generated_code: str,
    author_user_id: int,
    author_username: str | None,
) -> TrainJobResponse:
    """Create a Modeler pipeline execution job."""
    job = ArgusMLJob(
        workspace_id=workspace_id,
        name=name,
        source="modeler",
        status="pending",
        task_type="pipeline",
        target_column="",
        metric="",
        algorithm="",
        data_source={},
        config={},
        progress=0,
        pipeline_id=pipeline_id,
        generated_code=generated_code,
        author_user_id=author_user_id,
        author_username=author_username,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    logger.info("Pipeline job created: id=%d name=%s", job.id, job.name)
    return _job_to_response(job)


async def create_job(
    session: AsyncSession,
    req: TrainRequest,
    author_user_id: int,
    author_username: str | None,
) -> TrainJobResponse:
    """Create a new ML training job record."""
    # Auto-select metric based on task type
    metric = req.metric
    if metric == "auto":
        metric = {
            "classification": "f1",
            "regression": "rmse",
            "timeseries": "rmse",
        }.get(req.task_type.value, "f1")

    job = ArgusMLJob(
        workspace_id=req.workspace_id,
        name=req.name,
        status="pending",
        task_type=req.task_type.value,
        target_column=req.target_column,
        metric=metric,
        algorithm=req.algorithm.value,
        data_source=req.data_source,
        config={
            "feature_columns": req.feature_columns,
            "exclude_columns": req.exclude_columns,
            "time_limit_seconds": req.time_limit_seconds,
            "test_split": req.test_split,
        },
        progress=0,
        author_user_id=author_user_id,
        author_username=author_username,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    logger.info("ML job created: id=%d name=%s task=%s", job.id, job.name, job.task_type)
    return _job_to_response(job)


async def get_job(session: AsyncSession, job_id: int) -> TrainJobResponse | None:
    result = await session.execute(
        select(ArgusMLJob).where(ArgusMLJob.id == job_id)
    )
    job = result.scalars().first()
    return _job_to_response(job) if job else None


async def update_job_status(
    session: AsyncSession,
    job_id: int,
    status: str,
    progress: int = 0,
    results: dict | None = None,
    error_message: str | None = None,
) -> None:
    result = await session.execute(
        select(ArgusMLJob).where(ArgusMLJob.id == job_id)
    )
    job = result.scalars().first()
    if not job:
        return
    job.status = status
    job.progress = progress
    if results:
        job.results = results
    if error_message:
        job.error_message = error_message
    if status in ("completed", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def list_jobs(
    session: AsyncSession,
    workspace_id: int,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[TrainJobResponse], int]:
    """Returns (jobs, total_count)."""
    from sqlalchemy import func

    count_q = select(func.count(ArgusMLJob.id)).where(ArgusMLJob.workspace_id == workspace_id)
    total = (await session.execute(count_q)).scalar() or 0

    result = await session.execute(
        select(ArgusMLJob)
        .where(ArgusMLJob.workspace_id == workspace_id)
        .order_by(ArgusMLJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = [_job_to_response(j) for j in result.scalars().all()]
    return jobs, total


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

def _pipeline_to_response(p: ArgusMLPipeline) -> PipelineResponse:
    return PipelineResponse(
        id=p.id,
        workspace_id=p.workspace_id,
        name=p.name,
        description=p.description or "",
        pipeline_json=p.pipeline_json or {},
        author_username=p.author_username,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def save_pipeline(
    session: AsyncSession,
    workspace_id: int,
    name: str,
    description: str,
    pipeline_json: dict,
    author_user_id: int,
    author_username: str | None,
) -> PipelineResponse:
    p = ArgusMLPipeline(
        workspace_id=workspace_id,
        name=name,
        description=description,
        pipeline_json=pipeline_json,
        author_user_id=author_user_id,
        author_username=author_username,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    logger.info("Pipeline saved: id=%d name=%s", p.id, p.name)
    return _pipeline_to_response(p)


async def update_pipeline(
    session: AsyncSession,
    pipeline_id: int,
    name: str | None = None,
    description: str | None = None,
    pipeline_json: dict | None = None,
) -> PipelineResponse | None:
    result = await session.execute(
        select(ArgusMLPipeline).where(ArgusMLPipeline.id == pipeline_id)
    )
    p = result.scalars().first()
    if not p:
        return None
    if name is not None:
        p.name = name
    if description is not None:
        p.description = description
    if pipeline_json is not None:
        p.pipeline_json = pipeline_json
    await session.commit()
    await session.refresh(p)
    return _pipeline_to_response(p)


async def get_pipeline(session: AsyncSession, pipeline_id: int) -> PipelineResponse | None:
    result = await session.execute(
        select(ArgusMLPipeline).where(ArgusMLPipeline.id == pipeline_id)
    )
    p = result.scalars().first()
    return _pipeline_to_response(p) if p else None


async def list_pipelines(
    session: AsyncSession, workspace_id: int,
) -> tuple[list[PipelineResponse], int]:
    from sqlalchemy import func as sa_func

    total = (await session.execute(
        select(sa_func.count(ArgusMLPipeline.id)).where(ArgusMLPipeline.workspace_id == workspace_id)
    )).scalar() or 0

    result = await session.execute(
        select(ArgusMLPipeline)
        .where(ArgusMLPipeline.workspace_id == workspace_id)
        .order_by(ArgusMLPipeline.updated_at.desc())
    )
    items = [_pipeline_to_response(p) for p in result.scalars().all()]
    return items, total


async def delete_pipeline(session: AsyncSession, pipeline_id: int) -> bool:
    result = await session.execute(
        select(ArgusMLPipeline).where(ArgusMLPipeline.id == pipeline_id)
    )
    p = result.scalars().first()
    if not p:
        return False
    await session.delete(p)
    await session.commit()
    return True
